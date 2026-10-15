"""Verify the built wheel ships the frontend assets and the nested manifest.

Usage: python scripts/verify_wheel.py [path-to-wheel]
If no path is given, the newest dist/*.whl is used.
Exits non-zero with a clear message on any missing piece.
"""

import re
import sys
import zipfile
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parent.parent

DISTRIBUTION = "streamlit-listview"
MANIFEST = "streamlit_listview/pyproject.toml"
# The component entry __init__.py registers ("streamlit_listview.listview"),
# and the directory the wheel ships its bundle in.
COMPONENT_NAME = "listview"
ASSET_DIR = "frontend/build"


def _newest_wheel() -> Path:
    # Newest by modification time, not lexical order: lexically "0.10.0" sorts
    # before "0.9.0", which would pick the wrong (older) wheel when more than
    # one version sits in dist/.
    wheels = sorted(
        (ROOT / "dist").glob("streamlit_listview-*.whl"),
        key=lambda p: p.stat().st_mtime,
    )
    if not wheels:
        sys.exit("FAIL: no dist/streamlit_listview-*.whl found — run `uv build` first.")
    return wheels[-1]


# A table header (`[name]` or `[[name]]`) and a `version` key, each on a line
# of its own and with an optional trailing comment.
_TABLE_HEADER = re.compile(r"\s*(\[\[?)\s*([^\[\]]*?)\s*\]\]?\s*(?:#.*)?")
_VERSION_KEY = re.compile(r"""\s*version\s*=\s*(?:"([^"]+)"|'([^']+)')\s*(?:#.*)?""")


def project_version(pyproject_text: str) -> str:
    """The `version` key of a pyproject.toml's [project] table.

    THE parser for that field: scripts/push_gate.py, tests/test_packaging.py
    and tests/test_readme.py call this helper instead of keeping their own
    regexes, because three copies of this parse had drifted apart. It reads
    lines, not TOML: the push gate runs on the standard library of Python
    3.10, which has no TOML parser. The subset it reads is a `[project]`
    header and a `version = "..."` (or `'...'`) line below it, each on a line
    of its own; a key of any other table, a subtable included, never counts.
    tests/test_packaging.py checks that both shipped pyprojects stay inside
    the subset. Raises ValueError when the table has no such line or more
    than one, so each caller can fail its own way.
    """
    versions: list[str] = []
    in_project = False
    for line in pyproject_text.splitlines():
        header = _TABLE_HEADER.fullmatch(line)
        if header:
            in_project = header.group(1) == "[" and header.group(2) == "project"
            continue
        key = _VERSION_KEY.fullmatch(line) if in_project else None
        if key:
            versions.append(key.group(1) if key.group(1) is not None else key.group(2))
    if not versions:
        raise ValueError("no [project].version field")
    if len(versions) > 1:
        raise ValueError("more than one [project].version field")
    return versions[0]


def _parse_toml(text: str) -> dict[str, Any]:
    """Parse `text` as Streamlit does: with `tomllib`, or `toml` on Python 3.10.

    Streamlit reads the shipped manifest when the server starts
    (components/v2/manifest_scanner.py). Streamlit 1.66 and later parse it with
    `tomllib` and need Python 3.11, which brought it; earlier releases parse it
    with `toml`, their own dependency, and only they install on Python 3.10.
    On Python 3.11 and later with Streamlit 1.65 or earlier, the two parsers
    differ; CI installs the newest Streamlit, which parses as this does.
    scripts/push_gate.py imports this module on the standard library alone, so
    both imports wait for the call. Both parsers raise a ValueError for a
    document they cannot parse.
    """
    # ty checks one Python version, CI's 3.12 ([tool.ty.environment] in
    # pyproject.toml). It reports an import the environment lacks even inside
    # a `try`, but not in a branch that version never runs.
    if sys.version_info >= (3, 11):
        import tomllib

        return tomllib.loads(text)
    import toml

    return cast(dict[str, Any], toml.loads(text))


def _table(data: Any, *keys: str) -> dict[str, Any]:
    """The table under `keys`, or an empty one where the path is not a table."""
    for key in keys:
        data = data.get(key) if isinstance(data, dict) else None
    return data if isinstance(data, dict) else {}


def manifest_problems(text: str, version: str) -> list[str]:
    """What keeps Streamlit from using this component manifest; empty if nothing.

    Streamlit takes the manifest only when `[project].name` names the
    distribution after PEP 503 normalization, and it finds the bundle through
    the component's `asset_dir`. A manifest that fails to parse or to match
    leaves the component without its bundle. The version must equal the
    release's, as tests/test_packaging.py requires of the source copy.
    """
    try:
        data = _parse_toml(text)
    except ValueError as error:
        return [f"{MANIFEST} is not valid TOML ({error})"]
    problems: list[str] = []
    project = _table(data, "project")
    name = str(project.get("name", ""))
    # PEP 503 normalization, as packaging.utils.canonicalize_name does it; the
    # push gate runs this module without `packaging`.
    if re.sub(r"[-_.]+", "-", name).lower() != DISTRIBUTION:
        problems.append(
            f"[project].name {name!r} is not the distribution {DISTRIBUTION!r}"
        )
    if project.get("version") != version:
        problems.append(
            f"[project].version {project.get('version')!r} is not {version!r}"
        )
    # Streamlit reads only the list's dict entries and treats anything else
    # as no component at all.
    components = _table(data, "tool", "streamlit", "component").get("components")
    entries = components if isinstance(components, list) else []
    if not any(
        isinstance(entry, dict)
        and entry.get("name") == COMPONENT_NAME
        and entry.get("asset_dir") == ASSET_DIR
        for entry in entries
    ):
        problems.append(
            "no [[tool.streamlit.component.components]] entry with "
            f"name {COMPONENT_NAME!r} and asset_dir {ASSET_DIR!r}"
        )
    return problems


def _expected_version() -> str:
    """Read [project].version from the root pyproject.toml (single source)."""
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    try:
        return project_version(text)
    except ValueError as error:
        sys.exit(f"FAIL: could not read [project].version from pyproject.toml: {error}")


def _check_package_files(wheel: Path, names: list[str]) -> None:
    """Exit unless the wheel's package files outside the bundle are the
    source tree's: nothing more, and no module or type marker less.

    The source tree is the list, so a new module needs no entry here.
    """
    # setuptools ships whatever its staging directory build/lib holds, so a
    # module deleted from the source can ship from an earlier build's copy.
    # _build_backend deletes that copy and stops when it cannot; this check
    # catches a wheel built some other way.
    absent = sorted(
        n
        for n in names
        if n.startswith("streamlit_listview/")
        and not n.startswith("streamlit_listview/frontend/build/")
        and not n.endswith("/")
        and not (ROOT / n).is_file()
    )
    if absent:
        sys.exit(
            f"FAIL: wheel {wheel.name} ships files absent from the source tree: "
            f"{', '.join(absent)}"
        )
    print("  ok: every package file outside frontend/build/ exists in the source")

    # The reverse: the file names alone would pass a wheel that lacks a
    # module or the type marker.
    package = ROOT / "streamlit_listview"
    required = sorted(
        f"streamlit_listview/{path.name}"
        for path in [*package.glob("*.py"), package / "py.typed"]
    )
    lacking = [name for name in required if name not in names]
    if lacking:
        sys.exit(
            f"FAIL: wheel {wheel.name} lacks files of the source tree: "
            f"{', '.join(lacking)}"
        )
    print("  ok: every module of the package and py.typed ship")


def main() -> None:
    wheel = Path(sys.argv[1]) if len(sys.argv) > 1 else _newest_wheel()
    with zipfile.ZipFile(wheel) as zf:
        names = zf.namelist()
        manifest = zf.read(MANIFEST).decode("utf-8") if MANIFEST in names else None

    def has(pred, desc):
        if not any(pred(n) for n in names):
            sys.exit(f"FAIL: wheel {wheel.name} is missing {desc}")
        print(f"  ok: {desc}")

    def has_exactly_one(pred, desc):
        """Assert the wheel carries *one* match — the registration contract.

        `st.components.v2.component(js="index-*.js", css="index-*.css")` resolves
        those globs against `asset_dir`, and Streamlit's resolver
        (`component_path_utils`) raises `StreamlitComponentRegistryError` for both
        zero matches ("No files found matching pattern") and more than one
        ("Exactly one file must match the pattern"). A plain "at least one" check
        would pass a wheel that cannot register, so assert the real invariant and
        say which way it broke.
        """
        matches = sorted(n for n in names if pred(n))
        if len(matches) != 1:
            found = ", ".join(matches) if matches else "none"
            sys.exit(
                f"FAIL: wheel {wheel.name} must ship exactly one {desc}, "
                f"found {len(matches)} ({found})"
            )
        print(f"  ok: exactly one {desc}")

    print(f"Inspecting {wheel.name} ({len(names)} entries)")
    has_exactly_one(
        lambda n: (
            n.startswith("streamlit_listview/frontend/build/")
            and n.endswith(".js")
            and "/index-" in n
        ),
        "built index-*.js",
    )
    has_exactly_one(
        lambda n: (
            n.startswith("streamlit_listview/frontend/build/")
            and n.endswith(".css")
            and "/index-" in n
        ),
        "built index-*.css",
    )

    # The bundle carries the code of the frontend's npm packages, and their
    # licenses require their notices in every copy: Vite writes them into
    # THIRD_PARTY_LICENSES.md next to the bundle.
    has(
        lambda n: n == "streamlit_listview/frontend/build/THIRD_PARTY_LICENSES.md",
        "the third-party license file frontend/build/THIRD_PARTY_LICENSES.md",
    )

    # The package-data glob is frontend/build/**/* — the wheel packages
    # EVERYTHING under build/, so a file slipped in beside the bundle between
    # compile and `uv build` would ship (and be attested) silently. The
    # single-chunk build emits exactly one index-*.js plus one index-*.css and
    # the license file, all directly under build/; with the checks above this
    # pins the wheel's build/ contents to exactly that set.
    bundle_entry = re.compile(
        r"^streamlit_listview/frontend/build/"
        r"(?:index-[^/]+\.(?:js|css)|THIRD_PARTY_LICENSES\.md)$"
    )
    unexpected = sorted(
        n
        for n in names
        if n.startswith("streamlit_listview/frontend/build/")
        and not bundle_entry.match(n)
    )
    if unexpected:
        sys.exit(
            f"FAIL: wheel {wheel.name} ships unexpected files under "
            f"frontend/build/: {', '.join(unexpected)}"
        )
    print("  ok: frontend/build/ carries nothing beside the bundle and its licenses")

    has(lambda n: n == MANIFEST, "the nested component manifest")
    expected = _expected_version()
    problems = manifest_problems(cast(str, manifest), expected)
    if problems:
        sys.exit(f"FAIL: wheel {wheel.name}: {'; '.join(problems)}")
    print("  ok: the manifest names the distribution, the component and its bundle")

    # PEP 639: license-files = ["LICENSE", "NOTICE"] must land in dist-info/licenses/
    # so every distributed artifact carries the license text and the third-party
    # attributions for the ported Streamlit/react-feather code.
    has(
        lambda n: n.endswith(".dist-info/licenses/LICENSE"),
        "dist-info/licenses/LICENSE",
    )
    has(lambda n: n.endswith(".dist-info/licenses/NOTICE"), "dist-info/licenses/NOTICE")

    # The in-tree build backend ships in the sdist (so sdist->wheel builds) but
    # must never leak into the installed wheel.
    if any(Path(n).name == "_build_backend.py" for n in names):
        sys.exit(f"FAIL: wheel {wheel.name} must not ship _build_backend.py")
    print("  ok: build backend excluded from the wheel")

    _check_package_files(wheel, names)

    # version sanity: the wheel filename carries the version declared in
    # pyproject.toml (precise prefix match so e.g. 11.0.0 can't satisfy 1.0.0).
    if not wheel.name.startswith(f"streamlit_listview-{expected}-"):
        sys.exit(f"FAIL: wheel {wheel.name} is not version {expected}")
    print(f"  ok: wheel filename is {expected}")
    print("PASS: wheel contents verified")


if __name__ == "__main__":
    main()
