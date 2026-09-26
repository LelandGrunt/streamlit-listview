"""In-tree PEP 517 build backend for streamlit-listview.

Thin wrapper around setuptools' build backend that compiles the frontend bundle
(``streamlit_listview/frontend/build``) with ``npm run build`` before a wheel or
sdist is produced. The bundle is gitignored, so this keeps it fresh and present
in every distribution without committing generated output to git.

Wired up in ``pyproject.toml``::

    [build-system]
    build-backend = "_build_backend"
    backend-path = ["."]

setuptools is imported lazily inside each hook, so this module also imports
cleanly where setuptools isn't installed (e.g. the test venv). That lets the
Python control flow be unit-tested without a build toolchain; at real build
time the PEP 517 frontend's isolated environment provides setuptools.

Set ``LISTVIEW_SKIP_NPM_BUILD=1`` to skip the npm step — useful when the bundle
was already built in a previous step (e.g. CI builds it once for the test run,
then installs the package editable).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

_FRONTEND = Path(__file__).resolve().parent / "streamlit_listview" / "frontend"


def _backend():
    """Return setuptools' build backend (imported lazily; present at build time)."""
    from setuptools import build_meta

    return build_meta


def _npm(*args: str) -> None:
    """Run an npm subcommand in the frontend directory.

    npm is resolved to an absolute path via ``shutil.which`` (which honors
    ``PATHEXT``, so it finds ``npm.cmd`` on Windows) and invoked as an argument
    *vector* with ``shell=False``. Passing a list rather than a shell string
    means no argument is ever parsed by a shell, so the call cannot become a
    command-injection sink even if a future edit lets a variable flow into
    ``args``.
    """
    npm = shutil.which("npm") or ("npm.cmd" if os.name == "nt" else "npm")
    argv = [npm, *args]
    print(f"[listview build] running `{' '.join(argv)}` in {_FRONTEND}", file=sys.stderr)
    # A non-zero exit (e.g. a typecheck or vite error) raises CalledProcessError,
    # which propagates so the real build failure is surfaced. npm's presence is
    # checked up front in _run_npm_build.
    subprocess.run(argv, cwd=str(_FRONTEND), check=True)


def _verify_bundle_present(reason: str) -> None:
    """Ensure ``frontend/build`` ships exactly one JS + one CSS bundle file.

    Guards the two skip paths (``LISTVIEW_SKIP_NPM_BUILD`` and a missing
    ``frontend/src``): skipping the build is only safe when ``build/`` already
    contains the bundle. ``build/`` is gitignored, so a fresh clone or a
    misconfigured CI step that skips the build before it ran would otherwise
    package a wheel with no ``index-*.js`` / ``index-*.css`` — and the component
    would fail to register at runtime (``st.components.v2.component``'s globs
    match nothing). Fail loudly here instead.

    "Exactly one" rather than "at least one" because that is the registration
    contract: Streamlit's glob resolver raises
    ``StreamlitComponentRegistryError`` for zero matches *and* for several
    ("Exactly one file must match the pattern"). A stale extra ``index-*.js``
    left next to a fresh one is just as unloadable as none at all.
    """
    build = _FRONTEND / "build"
    for pattern in ("index-*.js", "index-*.css"):
        matches = sorted(p.name for p in build.glob(pattern))
        if len(matches) != 1:
            raise RuntimeError(
                f"[listview build] {reason}, but {build} does not contain exactly "
                f"one {pattern} — found {len(matches)} "
                f"({', '.join(matches) if matches else 'none'}). The wheel would "
                "ship a bundle the component cannot register. Build the frontend "
                "(`npm run build` in streamlit_listview/frontend) before "
                "packaging, or unset LISTVIEW_SKIP_NPM_BUILD."
            )


def _run_npm_build() -> None:
    """Compile the frontend bundle, unless explicitly skipped."""
    if os.environ.get("LISTVIEW_SKIP_NPM_BUILD") == "1":
        print(
            "[listview build] LISTVIEW_SKIP_NPM_BUILD=1 — skipping npm build.",
            file=sys.stderr,
        )
        _verify_bundle_present("LISTVIEW_SKIP_NPM_BUILD=1 skipped the npm build")
        return
    if not (_FRONTEND / "src").exists():
        # No frontend source present — e.g. building a wheel from an sdist that
        # already ships the prebuilt bundle. Use the existing build/ as-is.
        print(
            "[listview build] no frontend/src — using the prebuilt bundle as-is.",
            file=sys.stderr,
        )
        _verify_bundle_present("no frontend/src to build from")
        return
    if shutil.which("npm") is None:
        raise RuntimeError(
            "Could not find npm on PATH. Node.js/npm is required to build the "
            "frontend bundle. Install Node.js, or set LISTVIEW_SKIP_NPM_BUILD=1 "
            "if streamlit_listview/frontend/build is already up to date."
        )
    # A clean clone has no node_modules; install deps once before building.
    if not (_FRONTEND / "node_modules").exists():
        _npm("ci")
    _npm("run", "build")


# ── PEP 517 hooks ────────────────────────────────────────────────────────────
# Pass-through hooks delegate straight to setuptools. The three build_* hooks
# compile the frontend bundle first.

def get_requires_for_build_wheel(config_settings=None):
    return _backend().get_requires_for_build_wheel(config_settings)


def get_requires_for_build_sdist(config_settings=None):
    return _backend().get_requires_for_build_sdist(config_settings)


def get_requires_for_build_editable(config_settings=None):
    return _backend().get_requires_for_build_editable(config_settings)


def prepare_metadata_for_build_wheel(metadata_directory, config_settings=None):
    return _backend().prepare_metadata_for_build_wheel(metadata_directory, config_settings)


def prepare_metadata_for_build_editable(metadata_directory, config_settings=None):
    return _backend().prepare_metadata_for_build_editable(metadata_directory, config_settings)


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    _run_npm_build()
    return _backend().build_wheel(wheel_directory, config_settings, metadata_directory)


def build_sdist(sdist_directory, config_settings=None):
    _run_npm_build()
    return _backend().build_sdist(sdist_directory, config_settings)


def build_editable(wheel_directory, config_settings=None, metadata_directory=None):
    _run_npm_build()
    return _backend().build_editable(wheel_directory, config_settings, metadata_directory)
