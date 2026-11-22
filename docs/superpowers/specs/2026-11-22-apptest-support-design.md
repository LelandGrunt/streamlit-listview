# AppTest support: design

The listview becomes testable with `AppTest`, Streamlit's headless test framework (`streamlit.testing.v1`). Two changes do it. `import streamlit_listview` works in any Python process. A new module, `streamlit_listview.testing`, lets a test read and set the selection of a keyed listview.

## Why

The Lightweight MDM app picks a table in its Table Editor through a listview. It runs Streamlit 1.67 and `streamlit-listview` 1.1.0 from PyPI. Its tests cannot exercise that path through `AppTest`, for two reasons.

**The import fails outside a Streamlit runtime.** `streamlit_listview/__init__.py` declares the component at import time. The declaration resolves the globs `index-*.js` and `index-*.css` through the component manifests. Only a running server or an `AppTest` run has read those manifests. Anywhere else the import raises:

```text
StreamlitAPIException: Component 'streamlit_listview.listview' must be declared in pyproject.toml with asset_dir to use file-backed css.
```

pytest imports MDM's `pages/widgets/widgets_connection.py` directly for its unit tests, and that module imports the listview. MDM therefore puts a stub module into `sys.modules` (`stub_components_without_runtime` in its `scripts/package_set_check.py`). The stub stays for the whole pytest process. Every later `AppTest` run that renders the listview then fails on the stub's `RuntimeError`. MDM's performance harness picks the treeview for this reason. This repository meets the same failure in `scripts/smoke_wheel.py`, which locates the package without importing it.

**A test cannot select an entry.** `AppTest` models a Components V2 element as an `UnknownElement`, which has no `set_value()`. For a keyed element, Streamlit documents one way out: assign its state through `at.session_state[key]`. For the listview that state has the internal shape `{"selection": [...]}`, which no test author can guess.

The work succeeds when MDM drops its stub, renders the Table Editor with the listview through `AppTest`, and selects a table through `streamlit_listview.testing`.

## Goals

- `import streamlit_listview` succeeds in any Python process that has Streamlit installed, with or without a runtime. An `AppTest` run later in the same process renders the real listview.
- `streamlit_listview.testing` finds a keyed listview in an `AppTest`, reads its options and its selection, and sets the selection. It uses public Streamlit API only.
- The helper refuses the selections a browser user cannot make, so a test cannot pass on an impossible state. One gap remains, and *Set* below names it.
- The README shows how to test an app that uses the listview, and names what the helper leaves out.

## Non-goals

- Firing `on_change` from a test. A selection written to `at.session_state` fires no callback. Approach A would fire it, at the cost of private `AppTest` API. A later change can add it when a test needs a callback.
- Listviews without a `key`. `at.session_state` reaches keyed widgets only.
- Behavior that lives in the frontend alone: search, collapsing groups, scrolling, and the keyboard.
- Adding an entry through the add field. Before it adds an entry, the add field trims the text and looks for a matching row by label and by folded id. Mirroring that in Python would add a sixth rule that both languages keep. `set_selection` therefore refuses an unknown id, even under `accept_new_options`.
- Changes to Streamlit itself (approach C).
- The changes in the MDM repository, and the release of the listview. Both follow this work.

## Anti-goals

The work fails, even if its tests pass, when:

- a browser sees any change: in the element, the payload, the number of reruns, or when `on_change` fires;
- a test passes on a selection no browser user can make: a disabled row the user cannot pick, a disabled listview, an unknown id, or more ids than the mode allows;
- an app that only renders a listview loads `streamlit.testing`.

## Constraints

- The package keeps `streamlit >= 1.51` and `requires-python >= 3.10`.
- The helper needs Streamlit 1.66 or later. Before 1.59, `AppTest` cannot load a Components V2 element at all. From 1.59 to 1.65, a selection written to `at.session_state` lasts one run, and the next run restores `default`. Streamlit 1.66 needs Python 3.11, so the helper does not serve Python 3.10. The import fix serves every supported version.
- Row identity goes through `_id_key`. The helper ships each known id in the option's own spelling, as `_resolve_default_ids` does. Root `CLAUDE.md`, *Invariants that span both languages*, gives the reason.
- Python coverage stays at 100 %, the new module included.
- GitHub `main` carries released library code only. The work ships with the next release. It adds a public module, so that release is a minor version.

## Approaches

### The import

| Approach | Trade-off |
|---|---|
| **Declare the component on the first call of `listview()`** (chosen) | One code path. Streamlit asks that a component be declared once, and it still is. |
| Declare at import, and on failure declare on the first call | Keeps today's path for a server, but leaves two paths to test and to keep in step. |
| Change nothing here; each app imports the listview inside a function | No change in this package, but every app that tests with `AppTest` must learn the trap. |

### The selection

| Approach | Trade-off |
|---|---|
| A. Send the component's widget state as the browser does | Fires `on_change` and reaches unkeyed listviews. Needs private `AppTest` API (`at._tree`, `at._run`), which any Streamlit release can break. |
| **B. Write the selection to `at.session_state[key]`** (chosen) | Public API, documented by Streamlit. Reaches keyed listviews only, fires no `on_change`, and needs Streamlit 1.66. |
| C. Ask Streamlit to support Components V2 in `AppTest` | Right for every component in the long run. Streamlit decides on its form and its date. |

The user chose the first-call declaration with B. MDM keys every listview. Its listview's `on_change` only sets `table_editor_connection_changed`, which no code reads: item 9.4 of MDM's `openspec/changes/archive/2026-09-28-migrate-to-streamlit-listview/tasks.md` records it as dead.

## Design

### Declare the component on the first call

- `__init__.py` keeps the component callable in a module global that starts as `None`. A function, `_get_component()`, declares the component on its first call, with the arguments of today's declaration. Later calls return the cached callable.
- A `threading.Lock` guards the declaration. Two sessions can render their first listview at the same moment, each in its own script thread, and must not register the name twice.
- `listview()` calls `_get_component()` after every parameter check, right before it mounts the component.
- A missing bundle now fails at the first `listview()` call instead of at the import.
- One process can run several `AppTest` instances in a row, each with a registry of its own. Streamlit registers a declared callable again on each new runtime (`_ensure_component_on_active_runtime` in `streamlit.components.v2`), so the cached callable serves them all. A test proves it.

### Read and set the selection: `streamlit_listview.testing`

A test uses the module like this:

```python
from streamlit.testing.v1 import AppTest
from streamlit_listview.testing import get_listview

at = AppTest.from_file("app.py").run()
tables = get_listview(at, "tables")
assert [option.id for option in tables.options] == ["dbo.Customers", "dbo.Orders"]
tables.set_selection("dbo.Orders").run()
assert at.markdown[0].value == "Selected: Orders"
```

**Find.** `get_listview(at, key)` returns a `ListviewElement`. It filters `at.get("bidi_component")` by the component name `streamlit_listview.listview` and by `key`. Without a match it raises `KeyError`, as `at.get_by_key()` does. The message names the keys that exist, and the exception of the last run when it raised. It needs a finished run, because no element exists before the first `at.run()`.

**Read.** Each attribute comes from the element's payload, `json.loads(element.proto.json)`, except `selection`.

| Attribute | Value |
|---|---|
| `key` | the key the test passed |
| `label` | the label as Markdown source |
| `disabled` | `True` when the whole listview is disabled |
| `selection_mode` | `"single"` or `"multi"` |
| `max_selections` | an `int`, or `None` |
| `accept_new_options` | `True` when the user may add entries |
| `options` | a list of `Option(id, label, group, disabled)`, in the payload's order |
| `selection` | the ids stored in `at.session_state[key]["selection"]` |

The payload holds the options as `sort` ordered them. The frontend then draws each group as a block, so the screen can show another order. `Option.group` is `None` for an option without a group. `Option.disabled` is `False` when the payload row omits the key. `selection` holds the ids as stored. The value `listview()` returns can differ, because `map_selection` corrects the stored ids against the current options. A test therefore asserts on what the app does with the returned value.

**Set.** `set_selection(ids)` takes what `default` takes: one id, a list of ids, or `None` to clear. It writes `{"selection": [...]}` to `at.session_state[key]` and returns the element, so `.run()` can follow. `run()` calls `at.run()` and returns the `AppTest`. Every attribute reads the latest run, so `set_selection` checks against the parameters the app rendered last, and a reused element stays current. When the latest run rendered no listview with the key, an attribute raises the `KeyError` of `get_listview`.

Before it writes, `set_selection` raises `AppTestError`, as `AppTest` does for a disabled widget, when:

- the listview is disabled;
- an id names a disabled option that the stored selection does not hold;
- an id names no option, whether or not `accept_new_options` is on;
- two ids name the same row;
- `selection_mode="single"` gets more than one id;
- `selection_mode="multi"` gets more ids than `max_selections`.

Each id ships in the option's own spelling: `set_selection("1")` against the int option `1` writes `1`.

A disabled option that the stored selection holds, for example from `default`, may stay. The browser locks such a row: in multi mode the user cannot deselect it, and in single mode the user can replace it but not clear it. The helper does not check that a locked row stays. A test can therefore drop it, which no user can. The README names this gap.

**Version.** Under Streamlit before 1.66, importing `streamlit_listview.testing` raises `ImportError`. The message names the installed version and the minimum.

**Isolation.** `streamlit_listview/__init__.py` does not import `testing`.

### Docs

- `README.md` gains a section *Testing with AppTest* under *API*, after *Keying*. It shows the example above, lists the refusals, and names the limits: keyed listviews only; no `on_change`, unlike `set_value()` on Streamlit's own widgets; no new entries; a locked disabled row that a test can drop; Streamlit 1.66 and Python 3.11; frontend behavior belongs in a browser test.
- `CHANGELOG.md` gains `## [Unreleased]` with *Added* for the helper and *Fixed* for the import, and the `[Unreleased]` compare link that the release skill expects.
- Root `CLAUDE.md` (*Architecture*) and `streamlit_listview/CLAUDE.md` (*Files*) say that the component is declared on the first call. They add the rule never to declare it at import time, with its reason, and list `testing.py`.
- `HARNESS.md` describes the new steps of the wheel smoke test.

### Tests

- **Import.** A test runs a new Python process with the real component factory and no runtime. The process imports `streamlit_listview`, then renders a listview through `AppTest`: MDM's order. A unit test checks that two calls declare the component once.
- **Unit-suite setup.** The import-time patch of `st.components.v2.component` in `tests/conftest.py` goes away. The `listview_mod` fixture records the declaration at the first call instead of at the import.
- **Helper.** `AppTest` tests cover each attribute, each refusal, the spelling of ids, an unknown id under `accept_new_options`, a selected disabled row that stays, `None`, and the version guard.
- **Bundle.** Today `tests/test_demo_app.py` renders a mock listview, because of the global patch in `tests/conftest.py`. Once the patch goes, every test that renders through `AppTest` needs the built bundle. Without it these tests fail with a message that names `npm run build`.
- **Wheel.** `scripts/smoke_wheel.py` imports the package before `AppTest` runs, and sets a selection through the helper. The installed wheel then proves both changes.
- **Versions.** `uv.lock` pins Streamlit 1.66 for Python 3.11 and later, the helper's minimum. CI installs the newest Streamlit. Together they test both ends.

## Decisions

The user decided:

- the scope: a test both renders the listview and sets its selection;
- the approaches: declaration on the first call, and the selection through `at.session_state` (B);
- what follows from B: keyed listviews only, and no `on_change`;
- the rule for disabled rows: a selected disabled row may stay, a new one is refused, and the helper does not enforce the lock.

The designer decided, and the user can overrule:

- the names `get_listview`, `ListviewElement`, `Option`, `selection` and `set_selection`, which take ids rather than the values `listview()` returns;
- `AppTestError` for a refused selection and `KeyError` for a missing key, following `AppTest`;
- no new entries through the helper, which keeps the add field's matching rules out of Python;
- `options` in the payload's order, not in the order of the blocks on screen;
- an `ImportError` below Streamlit 1.66, which leaves Python 3.10 without the helper;
- the lock around the declaration;
- a failing test, not a skipped one, without a built bundle;
- the README section's place, and the extended wheel smoke test.

## Left to the builder

- The names of private functions and the layout of the tests.
- Whether `Option` is a dataclass or a named tuple.
- The wording of the README section and of the error messages.
