# AppTest support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `import streamlit_listview` work outside a Streamlit runtime, and ship `streamlit_listview.testing`, which reads and sets the selection of a keyed listview in an `AppTest`.

**Architecture:** `__init__.py` declares the component on the first call of `listview()`, behind a lock, instead of at import. A new public module, `streamlit_listview/testing.py`, finds the listview's `bidi_component` element in an `AppTest`, reads its JSON payload, and writes `{"selection": [...]}` to `at.session_state[key]`. Only public Streamlit API is used.

**Tech Stack:** Python 3.10+, Streamlit ≥ 1.51 (helper: ≥ 1.66), `streamlit.testing.v1.AppTest`, pytest, uv.

**Spec:** `docs/superpowers/specs/2026-11-22-apptest-support-design.md`

## Global Constraints

- `pyproject.toml` keeps `streamlit >= 1.51` and `requires-python >= 3.10`.
- `streamlit_listview.testing` needs Streamlit 1.66. Below it, importing the module raises `ImportError("streamlit_listview.testing needs Streamlit 1.66 or later; found <version>.")`.
- Row identity goes through `_options._id_key`. The helper writes each id in the option's own spelling, the `id` the payload carries.
- Exceptions: a non-`str`/`int` id raises `ValueError` from `_options._validate_id(..., kind="selected")`; a refused selection raises `streamlit.testing.v1.AppTestError`; a missing key raises `KeyError`.
- A browser sees no change: same element, same payload, same reruns, same `on_change`.
- `streamlit_listview/__init__.py` never imports `testing`.
- Python coverage stays at 100 %: `uv run --extra devel pytest tests/ --cov --cov-report=term-missing`. Every function stays at a cyclomatic complexity of 10 or below.
- Tests that render through `AppTest` need the built bundle: `npm run build` in `streamlit_listview/frontend/` before pytest.
- Documents follow the repository's Strunk & White rule (root `CLAUDE.md`, *Docs*). Commits use the repository's conventional subjects, pass every pre-commit hook (never `--no-verify`), and end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

- **`get_listview` before `at.run()`.** `at.get()` then returns `[]`. A person expects an error that says to run the app first. Test in Task 2.
- **An id in another spelling.** `"7"` against the int option `7`, or a `class Color(str, Enum)` member. A person expects the option's own id in the state. Tests in Task 3.
- **A tuple of ids.** A person passes `("a", "b")` and expects two ids, not one invalid id. Test in Task 3.
- **A key that changed between runs.** MDM counts its key up on a remount. A person expects the `KeyError` to name the keys that do exist. Test in Task 2.
- **`selection` after `set_selection(...).run()`.** A person reads the same element again and expects the new ids. Test in Task 3.

---

### Task 1: Declare the component on the first call

**Files:**

- Modify: `streamlit_listview/__init__.py:20-25` (the declaration) and `:588-593` (the mount call)
- Modify: `tests/conftest.py` (the import-time patch, `FakeComponent`, `listview_mod`, a new `built_bundle` fixture)
- Modify: `tests/test_listview.py:28-33`
- Create: `tests/test_import.py`
- Modify: `tests/test_demo_app.py` (use `built_bundle`)
- Modify: `scripts/smoke_wheel.py` (`CHECK`, `problems`) and `tests/test_smoke_wheel.py`
- Modify: `CLAUDE.md:139`, `streamlit_listview/CLAUDE.md:7`, `HARNESS.md:183`, `CHANGELOG.md`

**Interfaces:**

- Produces: `streamlit_listview._COMPONENT_NAME = "streamlit_listview.listview"`; `streamlit_listview._get_component() -> Callable[..., Any]`; the module globals `_component: Callable[..., Any] | None` and `_component_lock: threading.Lock`; `FakeComponent.declarations: int`; the fixture `built_bundle` in `tests/conftest.py`.

- [ ] **Step 1: Write the failing unit tests in `tests/test_listview.py`**

Replace `test_component_declared_with_globs_and_root_html` with:

```python
def test_import_declares_nothing(listview_mod):
    _mod, fake = listview_mod
    assert fake.declarations == 0


def test_first_call_declares_with_globs_and_root_html(listview_mod):
    mod, fake = listview_mod
    call(mod)
    assert fake.declared == {
        "name": "streamlit_listview.listview",
        "js": "index-*.js",
        "css": "index-*.css",
        "html": '<div class="listview-root"></div>',
        "isolate_styles": True,
    }


def test_later_calls_reuse_the_declaration(listview_mod):
    mod, fake = listview_mod
    call(mod)
    call(mod)
    assert fake.declarations == 1
    assert len(fake.calls) == 2


def test_concurrent_first_calls_declare_once(listview_mod, monkeypatch):
    mod, fake = listview_mod
    entered, release = threading.Event(), threading.Event()
    factory = st.components.v2.component  # the fixture's fake factory

    def slow_factory(*args, **kwargs):
        entered.set()
        release.wait(5)
        return factory(*args, **kwargs)

    monkeypatch.setattr(st.components.v2, "component", slow_factory)
    results = []
    first = threading.Thread(target=lambda: results.append(mod._get_component()))
    first.start()
    assert entered.wait(5)
    second = threading.Thread(target=lambda: results.append(mod._get_component()))
    second.start()
    time.sleep(0.1)  # let the second thread reach the lock
    release.set()
    first.join(5)
    second.join(5)
    assert fake.declarations == 1
    assert results == [fake, fake]
```

`_get_component()` must look up `st.components.v2.component` at call time, so the monkeypatch reaches it.

- [ ] **Step 2: Write the failing process test in `tests/test_import.py`**

```python
SCRIPT = """
import json
import streamlit_listview  # a plain import, outside any runtime
from streamlit.testing.v1 import AppTest

def render():
    at = AppTest.from_string(
        "import streamlit as st\\n"
        "from streamlit_listview import listview\\n"
        "st.write(repr(listview('Pick', ['a', 'b'], key='pick', default='b')))\\n"
    ).run(timeout=60)
    return {
        "exceptions": [str(e.value) for e in at.exception],
        "markdown": [m.value for m in at.markdown],
    }

print(json.dumps([render(), render()]))
"""


def test_a_plain_import_then_two_apptests_render_the_real_listview(
    built_bundle, tmp_path
):
    result = subprocess.run(
        [sys.executable, "-I", "-c", SCRIPT],
        cwd=tmp_path,
        capture_output=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 0, result.stderr
    runs = json.loads(result.stdout.splitlines()[-1])
    assert runs == [{"exceptions": [], "markdown": ["'b'"]}] * 2
```

- [ ] **Step 3: Run the tests and see them fail**

Run: `uv run --extra devel pytest tests/test_listview.py -k "declare or concurrent" tests/test_import.py -v`
Expected: FAIL. `FakeComponent` has no `declarations`, `_get_component` does not exist, and the process test fails with `StreamlitAPIException: Component 'streamlit_listview.listview' must be declared in pyproject.toml with asset_dir to use file-backed css.`

- [ ] **Step 4: Implement `_get_component() -> Callable[..., Any]` in `streamlit_listview/__init__.py`**

Replace the module-level `_component = st.components.v2.component(...)` with `_COMPONENT_NAME`, `_component = None` and `_component_lock = threading.Lock()`. `_get_component()` takes the lock on every call, declares once with today's arguments (`_COMPONENT_NAME`, `js="index-*.js"`, `css="index-*.css"`, `html='<div class="listview-root"></div>'`), and returns the cached callable. Its docstring gives the reason: outside a Streamlit runtime the declaration raises `StreamlitAPIException`, and an app's tests import the package without one. `listview()` calls `_get_component()(data=..., default=..., on_selection_change=..., key=...)` where it calls `_component(...)` today.

- [ ] **Step 5: Update `tests/conftest.py`**

- Delete the import-time patch: `_import_time_fake`, `_import_time_patcher`, its `atexit` registration, the comment block above them, and imports that become unused.
- `FakeComponent` gains `self.declarations = 0`. The fixture's `fake_factory` counts each call in it. Comments say "recorded at the first call", not "at import".
- Add the fixture `built_bundle`. When `streamlit_listview/frontend/build/` holds no `index-*.js`, it calls `pytest.fail("This test renders the listview through AppTest and needs the built bundle: run npm run build in streamlit_listview/frontend.")`.
- `tests/test_demo_app.py` gains `pytestmark = pytest.mark.usefixtures("built_bundle")`. Without the global patch it renders the real listview.

- [ ] **Step 6: Import first in the wheel smoke test**

In `scripts/smoke_wheel.py`, `CHECK` replaces the `importlib.util.find_spec` lookup with `import streamlit_listview` before `AppTest` runs, and reports `streamlit_listview.__file__` as `"module"`. A missing package now fails the check process, and `_run` reports it as `SmokeError`. `problems()` drops its `module is None` branch, and `test_a_problem_is_named` drops that case. Update the comment above `CHECK`. Add to `tests/test_smoke_wheel.py`:

```python
def test_the_check_imports_the_package_before_apptest_runs():
    """An app's test suite imports the package outside a runtime first."""
    check = smoke_wheel.CHECK
    assert check.index("import streamlit_listview") < check.index("AppTest.from_string")
```

`test_the_check_reports_what_streamlit_resolved` runs `CHECK` against the editable install, so it now proves the fix too.

- [ ] **Step 7: Run the unit suite with the coverage gate**

Run: `uv run --extra devel pytest tests/ --cov --cov-report=term-missing`
Expected: every test passes; coverage 100 %.

- [ ] **Step 8: Run the browser suite**

The server now declares the component during a script run, not at import.
Run: `uv run --extra devel pytest e2e/`
Expected: every test passes.

- [ ] **Step 9: Update the docs**

- `CLAUDE.md:139` and `streamlit_listview/CLAUDE.md:7`: the wrapper declares the component on the first call of `listview()` (`_get_component`), not at import.
- `streamlit_listview/CLAUDE.md`, *Files*: add the rule never to declare the component at import time, with its reason in one sentence.
- `HARNESS.md:183`: the smoke test imports the package before `AppTest` runs, as an app's test suite does.
- `CHANGELOG.md`: add `## [Unreleased]` above `## [1.1.0]` with a `### Fixed` entry. It says that `import streamlit_listview` works outside a running app, in pytest, a type checker or a script; quotes the old `StreamlitAPIException`; and says the component is declared on the first call of `listview()`. Add `[Unreleased]: https://github.com/LelandGrunt/streamlit-listview/compare/v1.1.0...HEAD` above the `[1.1.0]` link.

- [ ] **Step 10: Commit**

```bash
git add streamlit_listview/__init__.py tests/ scripts/smoke_wheel.py CLAUDE.md streamlit_listview/CLAUDE.md HARNESS.md CHANGELOG.md
git commit -m "fix: declare the component on the first call of listview()"
```

---

### Task 2: Find and read a listview in an AppTest

**Files:**

- Create: `streamlit_listview/testing.py`
- Create: `tests/test_apptest_helper.py`

**Interfaces:**

- Consumes: `streamlit_listview._COMPONENT_NAME`; the fixture `built_bundle` (Task 1).
- Produces, in `streamlit_listview.testing`:
  - `@dataclass(frozen=True) class Option` with fields `id: str | int`, `label: str`, `group: str | None`, `disabled: bool`.
  - `class ListviewElement` with attributes `key: str`, `label: str`, `disabled: bool`, `selection_mode: Literal["single", "multi"]`, `max_selections: int | None`, `accept_new_options: bool`, `options: list[Option]`, and the property `selection -> list[str | int]`. Its constructor is `ListviewElement(at: AppTest, element: UnknownElement)`; tests use `get_listview`.
  - `def get_listview(at: AppTest, key: str) -> ListviewElement`.

- [ ] **Step 1: Write the failing tests in `tests/test_apptest_helper.py`**

The module starts with `pytestmark = pytest.mark.usefixtures("built_bundle")` and `testing = pytest.importorskip("streamlit_listview.testing", exc_type=ImportError)`, so a Python 3.10 environment with Streamlit 1.65 skips it.

```python
OPTIONS = [
    {"id": "dbo.Orders", "label": "Orders", "group": "dbo"},
    {"id": "dbo.Customers", "label": "Customers", "group": "dbo"},
    {"id": 7, "label": "Seven"},
    {"id": "old", "label": "Old", "disabled": True},
]
BASE = {
    "label": "**Tables**",
    "options": OPTIONS,
    "key": "tables",
    "selection_mode": "multi",
    "max_selections": 2,
    "default": ["dbo.Orders"],
}


def _app(params):
    import streamlit as st
    from streamlit_listview import listview

    st.write(f"picked={listview(**params)!r}")


def _run(**params):
    return AppTest.from_function(_app, args=(params,), default_timeout=60).run()


def test_get_listview_reads_the_payload():
    lv = testing.get_listview(_run(**BASE), "tables")
    assert (lv.key, lv.label, lv.disabled, lv.selection_mode) == (
        "tables",
        "**Tables**",
        False,
        "multi",
    )
    assert (lv.max_selections, lv.accept_new_options) == (2, False)


def test_options_follow_the_payload_order():
    assert testing.get_listview(_run(**BASE), "tables").options == [
        testing.Option("dbo.Orders", "Orders", "dbo", False),
        testing.Option("dbo.Customers", "Customers", "dbo", False),
        testing.Option(7, "Seven", None, False),
        testing.Option("old", "Old", None, True),
    ]


def test_selection_reads_the_stored_ids():
    assert testing.get_listview(_run(**BASE), "tables").selection == ["dbo.Orders"]


def test_a_listview_in_the_sidebar_is_found():
    # A second app function that renders listview("Side", ["a"], key="side")
    # inside `with st.sidebar:`.
    ...
    assert testing.get_listview(at, "side").label == "Side"


def test_a_missing_key_names_the_keys_that_exist():
    with pytest.raises(KeyError, match=r"'tables-1'.*'tables'"):
        testing.get_listview(_run(**BASE), "tables-1")


def test_get_listview_before_a_run_says_to_run_first():
    at = AppTest.from_function(_app, args=(BASE,), default_timeout=60)
    with pytest.raises(KeyError, match=r"at\.run\(\)"):
        testing.get_listview(at, "tables")


def test_another_component_with_the_key_is_no_listview():
    # A second app function that declares an inline V2 component,
    # st.components.v2.component("other_component", html="<div></div>"),
    # and renders it with key="other".
    ...
    with pytest.raises(KeyError, match="'other'"):
        testing.get_listview(at, "other")


def test_the_package_does_not_load_the_helper(tmp_path):
    script = "import sys, streamlit_listview; print('streamlit_listview.testing' in sys.modules)"
    result = subprocess.run(
        [sys.executable, "-I", "-c", script],
        cwd=tmp_path,
        capture_output=True,
        encoding="utf-8",
        check=True,
    )
    assert result.stdout.strip() == "False"


def test_import_refuses_streamlit_before_1_66(monkeypatch):
    monkeypatch.setattr(streamlit, "__version__", "1.65.0")
    monkeypatch.delitem(sys.modules, "streamlit_listview.testing")
    with pytest.raises(
        ImportError, match=r"needs Streamlit 1\.66 or later; found 1\.65\.0"
    ):
        importlib.import_module("streamlit_listview.testing")
```

- [ ] **Step 2: Run the tests and see them fail**

Run: `uv run --extra devel pytest tests/test_apptest_helper.py -v`
Expected: the module is skipped or errors, because `streamlit_listview.testing` does not exist.

- [ ] **Step 3: Implement `streamlit_listview/testing.py`**

- At import, parse `streamlit.__version__` with a regular expression for major and minor (a dev suffix such as `1.66.0.dev20261101` passes). Below `(1, 66)`, raise the `ImportError` from *Global Constraints*.
- `get_listview` filters `at.get("bidi_component")` by `element.proto.component_name == _COMPONENT_NAME` and `element.key == key`. Without a match, it raises `KeyError` with a message that names `key` and the sorted keys of the listviews found. When it finds no listview at all, the message adds "Call at.run() before get_listview()."
- `ListviewElement.__init__` parses `json.loads(element.proto.json)` once. `options` come from the payload's `items`: `group` is `None` without the key, `disabled` is `False` without it.
- `selection` returns a copy of `at.session_state[self.key]["selection"]` on each read.
- The module docstring says what the helper does and what it leaves out (keyed listviews only, no `on_change`, no new entries).

- [ ] **Step 4: Run the tests and see them pass**

Run: `uv run --extra devel pytest tests/test_apptest_helper.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add streamlit_listview/testing.py tests/test_apptest_helper.py
git commit -m "feat: find and read a listview in an AppTest"
```

---

### Task 3: Set the selection

**Files:**

- Modify: `streamlit_listview/testing.py`
- Modify: `tests/test_apptest_helper.py`

**Interfaces:**

- Consumes: `ListviewElement`, `get_listview`, `Option` (Task 2); `_options._id_key`, `_options._validate_id`.
- Produces: `ListviewElement.set_selection(self, ids: str | int | list[str | int] | tuple[str | int, ...] | None) -> ListviewElement`; `ListviewElement.run(self, *, timeout: float | None = None) -> AppTest`.

- [ ] **Step 1: Write the failing tests**

```python
SINGLE = {
    **BASE,
    "selection_mode": "single",
    "max_selections": None,
    "default": "dbo.Orders",
}


def test_set_selection_then_run_returns_the_options():
    at = _run(**BASE)
    testing.get_listview(at, "tables").set_selection(["dbo.Customers", 7]).run()
    assert at.markdown[0].value == (
        "picked=[{'id': 'dbo.Customers', 'label': 'Customers', 'group': 'dbo'}, "
        "{'id': 7, 'label': 'Seven'}]"
    )


def test_selection_shows_the_write_after_a_run():
    at = _run(**BASE)
    lv = testing.get_listview(at, "tables")
    lv.set_selection(["dbo.Customers"]).run()
    assert lv.selection == ["dbo.Customers"]
    assert testing.get_listview(at, "tables").selection == ["dbo.Customers"]


def test_the_selection_lasts_over_later_runs():
    at = _run(**BASE)
    testing.get_listview(at, "tables").set_selection(["dbo.Customers"]).run()
    at.run()
    assert at.markdown[0].value.startswith("picked=[{'id': 'dbo.Customers'")


def test_none_clears_the_selection():
    at = _run(**BASE)
    testing.get_listview(at, "tables").set_selection(None).run()
    assert at.markdown[0].value == "picked=[]"


def test_single_mode_takes_one_id():
    at = _run(**SINGLE)
    testing.get_listview(at, "tables").set_selection(7).run()
    assert at.markdown[0].value == "picked={'id': 7, 'label': 'Seven'}"


def test_an_id_is_written_in_the_options_spelling():
    lv = testing.get_listview(_run(**BASE), "tables")
    lv.set_selection(["7"])
    assert lv.selection == [7]


def test_an_enum_member_is_written_as_its_value():
    class Color(str, enum.Enum):
        RED = "red"

    lv = testing.get_listview(
        _run(
            label="Colors",
            options=["red", "blue"],
            key="tables",
            selection_mode="multi",
        ),
        "tables",
    )
    lv.set_selection([Color.RED])
    assert lv.selection == ["red"]
    assert type(lv.selection[0]) is str


def test_a_tuple_counts_as_a_list_of_ids():
    lv = testing.get_listview(_run(**BASE), "tables")
    lv.set_selection(("dbo.Customers", 7))
    assert lv.selection == ["dbo.Customers", 7]


def test_a_selected_disabled_option_may_stay():
    at = _run(**{**BASE, "default": ["old"]})
    lv = testing.get_listview(at, "tables")
    lv.set_selection(["old", "dbo.Orders"]).run()
    assert lv.selection == ["old", "dbo.Orders"]


@pytest.mark.parametrize(
    ("params", "ids", "message"),
    [
        ({**BASE, "disabled": True}, ["dbo.Customers"], "disabled listview"),
        (BASE, ["old"], "disabled option 'old'"),
        (BASE, ["nope"], "no option 'nope'"),
        ({**BASE, "accept_new_options": True}, ["nope"], "no new entries"),
        (BASE, ["dbo.Orders", "dbo.Orders"], "twice"),
        (BASE, [7, "7"], "twice"),
        (SINGLE, ["dbo.Orders", 7], "takes one id"),
        (BASE, ["dbo.Orders", "dbo.Customers", 7], "max_selections=2"),
    ],
)
def test_a_selection_no_user_can_make_is_refused(params, ids, message):
    at = _run(**params)
    lv = testing.get_listview(at, "tables")
    before = lv.selection
    with pytest.raises(AppTestError, match=message):
        lv.set_selection(ids)
    assert testing.get_listview(at, "tables").selection == before


def test_an_id_of_another_type_raises_valueerror():
    lv = testing.get_listview(_run(**BASE), "tables")
    with pytest.raises(ValueError, match="selected id must be a str or int"):
        lv.set_selection([1.5])
```

- [ ] **Step 2: Run the tests and see them fail**

Run: `uv run --extra devel pytest tests/test_apptest_helper.py -v`
Expected: FAIL with `AttributeError: 'ListviewElement' object has no attribute 'set_selection'`.

- [ ] **Step 3: Implement `set_selection` and `run`**

`set_selection` turns `None` into `[]`, a list or a tuple into a list, and any other value into a one-element list. It passes each id through `_validate_id(item_id, kind="selected")`, looks each up among `options` by `_id_key`, and checks in this order. The messages carry the fragments the tests match:

1. The listview is disabled: `Cannot change the disabled listview {key!r}: a browser user cannot interact with it.`
2. An id names no option: `Listview {key!r} has no option {id!r}.` With `accept_new_options`, add: `set_selection adds no new entries, even with accept_new_options.`
3. Two ids name one row: `Listview {key!r} got the option {id!r} twice.`
4. An id names a disabled option that the stored selection does not hold, compared by `_id_key`: `Cannot select the disabled option {id!r} in listview {key!r}: a browser user cannot pick it.`
5. Single mode gets more than one id: `Listview {key!r} has selection_mode='single' and takes one id, got {n}.`
6. Multi mode gets more ids than `max_selections`: `Listview {key!r} allows max_selections={max} ids, got {n}.`

Only then does it write `{"selection": [option.id, ...]}` to `at.session_state[self.key]` and return `self`. Split the checks into helpers so each function stays at complexity 10 or below. `run` returns `self._at.run(timeout=timeout)`.

- [ ] **Step 4: Run the tests and the coverage gate**

Run: `uv run --extra devel pytest tests/ --cov --cov-report=term-missing`
Expected: every test passes; coverage 100 %, `streamlit_listview/testing.py` included.

- [ ] **Step 5: Commit**

```bash
git add streamlit_listview/testing.py tests/test_apptest_helper.py
git commit -m "feat: set a listview's selection in an AppTest"
```

---

### Task 4: Document the helper and prove it from the wheel

**Files:**

- Modify: `README.md` (new section after *Keying*, before *Large lists*)
- Modify: `CHANGELOG.md`, `streamlit_listview/CLAUDE.md`, `HARNESS.md`
- Modify: `scripts/smoke_wheel.py` (`CHECK`, `problems`) and `tests/test_smoke_wheel.py`

**Interfaces:**

- Consumes: `get_listview`, `ListviewElement.set_selection`, `ListviewElement.run` (Tasks 2 and 3).
- Produces: the report key `"selected"` in the JSON line that `CHECK` prints.

- [ ] **Step 1: Write the failing smoke tests**

In `tests/test_smoke_wheel.py`, `_report()` gains `"selected": ["'b'"]`. `test_a_problem_is_named` gains the case `({"selected": ["None"]}, "the helper selected 'b', but the app returned ['None']")`. `test_the_check_reports_what_streamlit_resolved` asserts `report["selected"] == ["'b'"]`.

- [ ] **Step 2: Run the smoke tests and see them fail**

Run: `uv run --extra devel pytest tests/test_smoke_wheel.py -v`
Expected: FAIL; `problems()` ignores `"selected"`, and `CHECK` reports no such key.

- [ ] **Step 3: Extend `CHECK` and `problems()`**

The smoke app writes `repr(listview('Smoke test', ['a', 'b'], key='smoke'))` with `st.write`. After the first run, `CHECK` calls `get_listview(app, "smoke").set_selection("b").run(timeout=60)` and reports the markdown values as `"selected"`. `problems()` adds `the helper selected 'b', but the app returned {selected}` when `report["selected"] != ["'b'"]`. Update the module docstring.

- [ ] **Step 4: Run the smoke tests and see them pass**

Run: `uv run --extra devel pytest tests/test_smoke_wheel.py -v`
Expected: PASS.

- [ ] **Step 5: Write the docs**

- `README.md`, new section *Testing with AppTest* after *Keying*: the example from the spec's *Design*; the attributes of `ListviewElement`; the refusals; and the limits: keyed listviews only; `on_change` does not fire, unlike `set_value()` on Streamlit's own widgets, so test a callback in a browser; no new entries; a test can drop a locked disabled row that no user can drop; `selection` holds the stored ids, while the app sees what `listview()` returns; Streamlit 1.66 and Python 3.11.
- `CHANGELOG.md`, under `## [Unreleased]`: an `### Added` entry for `streamlit_listview.testing`, with its minimum version and the `on_change` limit.
- `streamlit_listview/CLAUDE.md`, *Files*: `testing.py` and its rules in two sentences: it uses public `AppTest` API only, and it mirrors only the refusals the spec lists.
- `HARNESS.md`: the smoke test sets a selection through the helper; the pytest paragraph names `tests/test_import.py` and `tests/test_apptest_helper.py`.

- [ ] **Step 6: Run every check**

Run: `uv run --extra devel pytest tests/ --cov --cov-report=term-missing`, then `pre-commit run --all-files`.
Expected: every test passes, coverage 100 %, every hook passes.

- [ ] **Step 7: Build the wheel and smoke-test it**

Run: `uv build`, then `uv run --extra devel python scripts/verify_wheel.py`, then `uv run --extra devel python scripts/smoke_wheel.py`.
Expected: `verify_wheel.py` passes with `testing.py` in the wheel; `smoke_wheel.py` prints `PASS: the listview renders from …`.

- [ ] **Step 8: Commit**

```bash
git add README.md CHANGELOG.md streamlit_listview/CLAUDE.md HARNESS.md scripts/smoke_wheel.py tests/test_smoke_wheel.py
git commit -m "docs: document testing with AppTest"
```
