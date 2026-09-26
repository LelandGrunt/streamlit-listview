"""Verify the built wheel ships the frontend assets and the nested manifest.

Usage: python scripts/verify_wheel.py [path-to-wheel]
If no path is given, the newest dist/*.whl is used.
Exits non-zero with a clear message on any missing piece.
"""
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


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


def project_version(pyproject_text: str) -> str:
    """The `version = "..."` field in a pyproject.toml's text.

    THE parser for that field: tests/test_packaging.py and tests/test_readme.py
    import this helper instead of keeping their own regexes — three copies of
    this parse had already drifted apart in how they anchored. Anchored at
    column 0 (the strictest of the drifted variants) on purpose: both
    pyprojects write the [project] table's keys unindented, and a looser
    ``^\\s*`` could silently match an indented `version` key belonging to some
    other table. Raises ValueError when the field is missing so each caller
    can fail its own way (sys.exit here, assert in the tests).
    """
    match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', pyproject_text)
    if not match:
        raise ValueError("no [project].version field found")
    return match.group(1)


def _expected_version() -> str:
    """Read [project].version from the root pyproject.toml (single source)."""
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    try:
        return project_version(text)
    except ValueError:
        sys.exit("FAIL: could not read [project].version from pyproject.toml")


def main() -> None:
    wheel = Path(sys.argv[1]) if len(sys.argv) > 1 else _newest_wheel()
    with zipfile.ZipFile(wheel) as zf:
        names = zf.namelist()

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
    has_exactly_one(lambda n: n.startswith("streamlit_listview/frontend/build/")
                    and n.endswith(".js") and "/index-" in n, "built index-*.js")
    has_exactly_one(lambda n: n.startswith("streamlit_listview/frontend/build/")
                    and n.endswith(".css") and "/index-" in n, "built index-*.css")

    # The package-data glob is frontend/build/**/* — the wheel packages
    # EVERYTHING under build/, so a file slipped in beside the bundle between
    # compile and `uv build` would ship (and be attested) silently. The
    # single-chunk build emits exactly one index-*.js plus one index-*.css,
    # both directly under build/; with the exactly-one checks above this pins
    # the wheel's build/ contents to exactly that set.
    bundle_entry = re.compile(r"^streamlit_listview/frontend/build/index-[^/]+\.(?:js|css)$")
    unexpected = sorted(
        n for n in names
        if n.startswith("streamlit_listview/frontend/build/") and not bundle_entry.match(n)
    )
    if unexpected:
        sys.exit(
            f"FAIL: wheel {wheel.name} ships unexpected files under "
            f"frontend/build/: {', '.join(unexpected)}"
        )
    print("  ok: frontend/build/ carries nothing beside the two bundle files")

    has(lambda n: n == "streamlit_listview/pyproject.toml", "the nested component manifest")

    # PEP 639: license-files = ["LICENSE", "NOTICE"] must land in dist-info/licenses/
    # so every distributed artifact carries the license text and the third-party
    # attributions for the ported Streamlit/react-feather code.
    has(lambda n: n.endswith(".dist-info/licenses/LICENSE"), "dist-info/licenses/LICENSE")
    has(lambda n: n.endswith(".dist-info/licenses/NOTICE"), "dist-info/licenses/NOTICE")

    # The in-tree build backend ships in the sdist (so sdist->wheel builds) but
    # must never leak into the installed wheel.
    if any(Path(n).name == "_build_backend.py" for n in names):
        sys.exit(f"FAIL: wheel {wheel.name} must not ship _build_backend.py")
    print("  ok: build backend excluded from the wheel")

    # version sanity: the wheel filename carries the version declared in
    # pyproject.toml (precise prefix match so e.g. 11.0.0 can't satisfy 1.0.0).
    expected = _expected_version()
    if not wheel.name.startswith(f"streamlit_listview-{expected}-"):
        sys.exit(f"FAIL: wheel {wheel.name} is not version {expected}")
    print(f"  ok: wheel filename is {expected}")
    print("PASS: wheel contents verified")


if __name__ == "__main__":
    main()
