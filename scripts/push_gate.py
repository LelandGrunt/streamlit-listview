"""Gate every push to GitHub on a released, consistent and working state.

GitHub `main` shows released code only: Streamlit Community Cloud runs the
hosted demo from it and installs the version that `demo/requirements.txt` pins
from PyPI. GitHub therefore takes only `main` and `v*` tags, and a push there
passes four stages. Each stage reports all of its findings at once, and a stage
runs only when every earlier stage passed:

1. refs: only main and new v* tags, nothing deleted, no force push;
2. local state: a command-line confirmation that names the version, HEAD of a
   clean tree, consistent version information and a released changelog;
3. remote state: the release order (the tag, then the PyPI release, then
   main), and main carrying the library code of that release;
4. the CI suite on the pushed commit, once per commit.

Usage:
    python scripts/push_gate.py install                  # once per clone
    python scripts/push_gate.py hook <remote> <url>      # git; refs on stdin
    python scripts/push_gate.py check tag <tag>          # release.yml
    python scripts/push_gate.py check main [--remote R]  # ci.yml

Standard library only, Python 3.10 or later: CI runs it with the runner's
python3, without an install.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import cast

import verify_wheel

CONFIRM_KEY = "listview.pushGithub"
MAIN_REF = "refs/heads/main"
TAG_REF_PREFIX = "refs/tags/v"
PYPI_URL = "https://pypi.org/pypi/streamlit-listview/{version}/json"
PYPI_TIMEOUT_S = 10
FRONTEND = "streamlit_listview/frontend"

# The Python version of CI: every job in .github/workflows/ci.yml sets up uv with
# this python-version, which setup-uv exports to the job as UV_PYTHON. ty checks
# against the version UV_PYTHON names, else against python-version under
# [tool.ty.environment] in pyproject.toml. The suite runs with it too, so it
# reads the packages that uv.lock pins for CI's Python. tests/test_push_gate.py
# pins it to the workflows and to that setting.
CI_PYTHON = "3.12"

# X.Y.Z, or X.Y.Z with a pre-release suffix: the spellings the release skill
# allows, without leading zeros. The wheel filename normalizes "1.0.0-rc.1" to
# "1.0.0rc1" and "1.0.02" to "1.0.2", while the release checks compare the raw
# string, so such a release would fail. [0-9], not \d: \d matches every
# Unicode decimal digit, and PEP 440 admits only ASCII ones.
_NUMBER = r"(?:0|[1-9][0-9]*)"
CANONICAL_VERSION = re.compile(
    rf"{_NUMBER}\.{_NUMBER}\.{_NUMBER}(?:(?:a|b|rc){_NUMBER})?"
)
DEMO_PIN = re.compile(r"(?mi)^\s*streamlit[-_.]listview\s*==\s*([^\s;#]+)")
EXPECTED_VERSION = re.compile(r'(?m)^EXPECTED_VERSION\s*=\s*"([^"]+)"')
LOCK_ENTRY = re.compile(
    r'(?m)^name\s*=\s*"streamlit-listview"\s*\n\s*version\s*=\s*"([^"]+)"'
)
UNRELEASED = re.compile(r"(?i)\bunreleased\b")

# The shipped package without its documentation, tests and test configuration.
# A difference here between the release tag and main means that main carries
# library code PyPI does not ship.
LIBRARY_PATHSPEC = (
    "streamlit_listview",
    ":(exclude,glob)**/CLAUDE.md",
    ":(exclude,glob)**/*.test.ts",
    ":(exclude,glob)**/*.test.tsx",
    ":(exclude)streamlit_listview/frontend/src/__tests__",
    ":(exclude)streamlit_listview/frontend/src/test",
    ":(exclude)streamlit_listview/frontend/src/bench",
    ":(exclude)streamlit_listview/frontend/.oxlintrc.json",
    ":(exclude)streamlit_listview/frontend/tsconfig.test.json",
    ":(exclude)streamlit_listview/frontend/vitest.config.ts",
)

SHIM_MARKER = "# streamlit-listview push gate"
SHIM = f"""#!/bin/sh
{SHIM_MARKER}. Written by `scripts/push_gate.py install`;
# the rules live in scripts/push_gate.py of the checkout that pushes. A push to
# another host passes before uv starts, so a client without uv on PATH works.
case "$(printf '%s' "$2" | tr '[:upper:]' '[:lower:]')" in
    *github.com*) ;;
    *) exit 0 ;;
esac
if [ -f scripts/push_gate.py ]; then
    exec uv run --no-project python scripts/push_gate.py hook "$@"
fi
echo "push gate: this checkout has no scripts/push_gate.py." >&2
echo "push gate: push to GitHub from a checkout of main." >&2
exit 1
"""

# The files that carry the version, in the order version_findings checks them.
VERSION_FILES = (
    "pyproject.toml",
    "streamlit_listview/pyproject.toml",
    "tests/test_packaging.py",
    "README.md",
    "demo/requirements.txt",
    "uv.lock",
    "CHANGELOG.md",
)

# Reads one file of a commit: its text, or None when the commit lacks it. Raises
# UnicodeDecodeError when the file is not UTF-8.
Read = Callable[[str], str | None]


def demo_pins(requirements: str) -> list[str]:
    """Every `streamlit-listview==<version>` pin in a requirements file.

    THE parse for the demo pin: tests/test_packaging.py calls it too, so the
    gate and the test agree on what counts as a pin.
    """
    return cast(list[str], DEMO_PIN.findall(requirements))


def dist_names(version: str) -> tuple[str, str]:
    """The wheel and sdist filenames that README.md shows for a version.

    tests/test_readme.py checks the README against the same two names.
    """
    return (
        f"streamlit_listview-{version}-py3-none-any.whl",
        f"streamlit_listview-{version}.tar.gz",
    )


def expected_version(test_packaging: str) -> str | None:
    """`EXPECTED_VERSION` in tests/test_packaging.py, or None."""
    match = EXPECTED_VERSION.search(test_packaging)
    return cast(str, match.group(1)) if match else None


def lock_version(lock: str) -> str | None:
    """The version that uv.lock records for this project, or None."""
    match = LOCK_ENTRY.search(lock)
    return cast(str, match.group(1)) if match else None


def _project_version(pyproject: str | None) -> tuple[str | None, str]:
    """The [project].version of a pyproject.toml, or None and the reason."""
    try:
        return verify_wheel.project_version(pyproject or ""), ""
    except ValueError as error:
        return None, str(error)


def _found(value: str | None) -> str:
    return "none" if value is None else value


def version_findings(read: Read, today: date) -> tuple[str | None, list[str]]:
    """The version of a commit and every flaw in its version information.

    The root pyproject.toml is the source of truth. Without its version the
    other places have nothing to agree with, so the check stops there. A file
    that is not UTF-8 stops it too: its contents cannot be compared.
    """
    texts: dict[str, str] = {}
    undecodable: list[str] = []
    for path in VERSION_FILES:
        try:
            texts[path] = read(path) or ""
        except UnicodeDecodeError:
            undecodable.append(f"{path}: not valid UTF-8. Save it as UTF-8.")
    version, problem = _project_version(texts.get("pyproject.toml"))
    if undecodable:
        return version, undecodable
    if version is None:
        return None, [f"pyproject.toml: {problem}."]
    findings: list[str] = []
    if not CANONICAL_VERSION.fullmatch(version):
        findings.append(
            f'pyproject.toml: "{version}" is no canonical PEP 440 version. Write '
            "X.Y.Z, or X.Y.Z followed by a, b or rc and a number."
        )
    findings.extend(_agreement_findings(texts, version))
    findings.extend(changelog_findings(texts["CHANGELOG.md"], version, today))
    return version, findings


def _agreement_findings(texts: dict[str, str], version: str) -> list[str]:
    """The places other than the changelog that do not name `version`."""
    findings: list[str] = []
    nested, problem = _project_version(texts["streamlit_listview/pyproject.toml"])
    if nested != version:
        found = problem if nested is None else f"version {nested}"
        findings.append(
            f"streamlit_listview/pyproject.toml: {found}, expected {version}."
        )
    expected = expected_version(texts["tests/test_packaging.py"])
    if expected != version:
        findings.append(
            f"tests/test_packaging.py: EXPECTED_VERSION {_found(expected)}, "
            f"expected {version}."
        )
    for name in dist_names(version):
        if name not in texts["README.md"]:
            findings.append(f"README.md: no {name}. Update the dist filename examples.")
    pins = demo_pins(texts["demo/requirements.txt"])
    if pins != [version]:
        findings.append(
            f"demo/requirements.txt: pins {pins}, expected exactly one "
            f"streamlit-listview=={version}."
        )
    locked = lock_version(texts["uv.lock"])
    if locked != version:
        findings.append(
            f"uv.lock: records {_found(locked)}, expected {version}. Run `uv lock`."
        )
    return findings


def changelog_findings(changelog: str, version: str, today: date) -> list[str]:
    """What keeps CHANGELOG.md from describing `version` as released.

    `today` is the current UTC date. A release date up to one day later
    passes, so the date of every time zone does.
    """
    lines = changelog.splitlines()
    findings: list[str] = []
    unreleased = [
        str(number)
        for number, line in enumerate(lines, start=1)
        if UNRELEASED.search(line)
    ]
    if unreleased:
        findings.append(
            f'CHANGELOG.md:{",".join(unreleased)}: "Unreleased" remains. Turn the '
            f'section into "## [{version}] - YYYY-MM-DD" and its link into '
            f'"[{version}]: ...".'
        )
    heading = next(
        (
            (number, line.rstrip())
            for number, line in enumerate(lines, start=1)
            if line.startswith("## [")
        ),
        None,
    )
    if heading is None:
        findings.append(
            f'CHANGELOG.md: no version heading. Add "## [{version}] - YYYY-MM-DD".'
        )
    else:
        number, text = heading
        findings.extend(_heading_findings(number, text, version, today))
    # [ \t], not \s: an empty link must not borrow the URL of the next line.
    if not re.search(rf"(?m)^\[{re.escape(version)}\]:[ \t]*\S", changelog):
        findings.append(
            f'CHANGELOG.md: no link line "[{version}]: <url>". Add one below the '
            "others."
        )
    return findings


def _heading_findings(
    number: int, heading: str, version: str, today: date
) -> list[str]:
    pattern = rf"## \[{re.escape(version)}\] - (\d{{4}}-\d{{2}}-\d{{2}})"
    match = re.fullmatch(pattern, heading)
    if match is None:
        message = (
            f'CHANGELOG.md:{number}: the newest heading reads "{heading}", '
            f'expected "## [{version}] - YYYY-MM-DD".'
        )
        return [message]
    released = match.group(1)
    try:
        day = date.fromisoformat(released)
    except ValueError:
        return [f"CHANGELOG.md:{number}: {released} is not a valid date."]
    if day > today + timedelta(days=1):
        return [
            f"CHANGELOG.md:{number}: the release date {released} lies in the future."
        ]
    return []


class GitError(Exception):
    """A git command failed; the message carries the command and its stderr."""


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def git(repo: Path, *args: str) -> str:
    """Run git in `repo` and return its output without the final newline."""
    result = _git(repo, *args)
    if result.returncode != 0:
        raise GitError(f"git {' '.join(args)}: {result.stderr.strip()}")
    return result.stdout.rstrip("\n")


def commit_reader(repo: Path, commit: str) -> Read:
    """A reader for the files of one commit.

    It decodes UTF-8 itself, so a file in another encoding raises
    UnicodeDecodeError here, where version_findings can name the file.
    """

    def read(path: str) -> str | None:
        result = subprocess.run(
            ["git", "show", f"{commit}:{path}"],
            cwd=repo,
            capture_output=True,
            check=False,
        )
        return result.stdout.decode("utf-8") if result.returncode == 0 else None

    return read


def working_tree_status(repo: Path) -> str:
    """`git status --porcelain`, untracked files included whatever the config."""
    return git(repo, "status", "--porcelain", "--untracked-files=normal")


def short(sha: str) -> str:
    return sha[:12]


def is_zero(sha: str) -> bool:
    """Whether a pre-push sha marks a ref that does not exist: all zeros."""
    return set(sha) == {"0"}


def has_commit(repo: Path, sha: str) -> bool:
    return _git(repo, "cat-file", "-e", f"{sha}^{{commit}}").returncode == 0


def is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool:
    result = _git(repo, "merge-base", "--is-ancestor", ancestor, descendant)
    return result.returncode == 0


def peel(repo: Path, sha: str) -> str:
    """The commit that a ref names, through an annotated tag."""
    return git(repo, "rev-parse", f"{sha}^{{commit}}")


def _indent(text: str) -> str:
    return "\n".join(f"      {line}" for line in text.splitlines())


@dataclass(frozen=True)
class RefUpdate:
    """One line of git's pre-push input."""

    local_ref: str
    local_sha: str
    remote_ref: str
    remote_sha: str

    @property
    def is_main(self) -> bool:
        return self.remote_ref == MAIN_REF

    @property
    def is_tag(self) -> bool:
        return self.remote_ref.startswith(TAG_REF_PREFIX)


def parse_updates(text: str) -> list[RefUpdate]:
    """The ref updates that git passes to a pre-push hook on stdin."""
    updates: list[RefUpdate] = []
    for line in text.splitlines():
        if line.strip():
            local_ref, local_sha, remote_ref, remote_sha = line.rsplit(maxsplit=3)
            updates.append(RefUpdate(local_ref, local_sha, remote_ref, remote_sha))
    return updates


def _ref_finding(repo: Path, update: RefUpdate) -> str | None:
    ref = update.remote_ref
    if not (update.is_main or update.is_tag):
        return (
            f"{ref}: GitHub takes only main and v* tags. Push other branches to "
            "Azure DevOps."
        )
    if is_zero(update.local_sha):
        return f"{ref}: the push deletes it. GitHub keeps main and every release tag."
    if is_zero(update.remote_sha):
        return None
    if update.is_tag:
        return (
            f"{ref}: the tag exists on GitHub, and a release tag never moves. "
            "Release a new version instead."
        )
    if not has_commit(repo, update.remote_sha):
        return (
            f"{ref}: GitHub's main is at {short(update.remote_sha)}, which this "
            "clone lacks. Run `git fetch` and push again."
        )
    if not is_ancestor(repo, update.remote_sha, update.local_sha):
        return (
            f"{ref}: the push rewrites GitHub's main: {short(update.remote_sha)} "
            f"is no ancestor of {short(update.local_sha)}. Force pushes are "
            "refused."
        )
    return None


def ref_findings(repo: Path, updates: list[RefUpdate]) -> list[str]:
    """Stage 1: GitHub takes main and new v* tags, and nothing is rewritten."""
    return [finding for update in updates if (finding := _ref_finding(repo, update))]


def confirmation_finding(repo: Path, version: str) -> str | None:
    """Stage 2: whether the push carries `-c listview.pushGithub=<version>`."""
    usage = f"Push with `git -c {CONFIRM_KEY}={version} push ...`."
    result = _git(repo, "config", "--show-scope", "--get", CONFIRM_KEY)
    if result.returncode != 0:
        return f"No confirmation. {usage}"
    scope, _, value = result.stdout.strip().partition("\t")
    if scope != "command":
        return (
            f"The confirmation comes from the {scope} git config, and only the "
            f"command line counts. Run `git config --{scope} --unset "
            f"{CONFIRM_KEY}`. {usage}"
        )
    if value != version:
        return (
            f"The confirmation names {value}, but the pushed commit is "
            f"{version}. {usage}"
        )
    return None


def checkout_findings(repo: Path, updates: list[RefUpdate], head: str) -> list[str]:
    """Stage 2: the push sends HEAD of a clean tree, so the suite tests it."""
    findings: list[str] = []
    for update in updates:
        commit = peel(repo, update.local_sha)
        if commit != head:
            findings.append(
                f"{update.remote_ref}: the push sends {short(commit)}, but HEAD "
                f"is {short(head)}. Check out the commit you push."
            )
    status = working_tree_status(repo)
    if status:
        findings.append(
            "The working tree has changes. Commit or remove them, so the suite "
            f"tests exactly the pushed commit:\n{_indent(status)}"
        )
    return findings


def tag_name_findings(updates: list[RefUpdate], version: str) -> list[str]:
    """Stage 2: a pushed tag names the version of its commit."""
    expected = f"{TAG_REF_PREFIX}{version}"
    return [
        f"{update.remote_ref}: the tag of version {version} is v{version}."
        for update in updates
        if update.is_tag and update.remote_ref != expected
    ]


class PyPIError(Exception):
    """PyPI gave no clear answer; the gate then refuses the push."""


# Answers whether PyPI serves a version; raises PyPIError when it cannot tell.
PyPI = Callable[[str], bool]


def pypi_knows(version: str) -> bool:
    """Whether PyPI serves streamlit-listview at `version`."""
    url = PYPI_URL.format(version=version)
    try:
        with urllib.request.urlopen(url, timeout=PYPI_TIMEOUT_S) as response:
            status = response.status
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return False
        raise PyPIError(f"PyPI answered {error.code} for {url}.") from error
    except OSError as error:
        raise PyPIError(
            f"PyPI is unreachable ({error}). The gate needs it to check the "
            "release order."
        ) from error
    if status != 200:
        raise PyPIError(f"PyPI answered {status} for {url}.")
    return True


def remote_refs(repo: Path, remote: str, *refs: str) -> dict[str, str]:
    """The sha that a remote lists for each of `refs`, by full ref name.

    GitError when the remote cannot be read.
    """
    shas: dict[str, str] = {}
    for line in git(repo, "ls-remote", remote, *refs).splitlines():
        sha, _, name = line.partition("\t")
        shas[name] = sha
    return shas


def remote_tag_commit(repo: Path, remote: str, tag: str) -> str | None:
    """The commit that a tag names on a remote, through an annotated tag.

    None when the remote lacks the tag; GitError when it cannot be read.
    """
    ref = f"refs/tags/{tag}"
    peeled = f"{ref}^{{}}"
    shas = remote_refs(repo, remote, ref, peeled)
    return shas.get(peeled) or shas.get(ref)


def tag_base_findings(repo: Path, remote: str, head: str) -> list[str]:
    """Stage 3 for a tag: GitHub's main can fast-forward to the tagged commit.

    A PyPI release cannot be undone, so the gate refuses a release that main
    could not follow before the release starts.
    """
    try:
        main = remote_refs(repo, remote, MAIN_REF).get(MAIN_REF)
    except GitError as error:
        return [f"Cannot read the refs on {remote}: {error}"]
    if main is None:
        return []
    if not has_commit(repo, main):
        message = (
            f"GitHub's main is at {short(main)}, which this clone lacks. Run "
            "`git fetch` and push again."
        )
        return [message]
    if not is_ancestor(repo, main, head):
        message = (
            f"GitHub's main is at {short(main)}, which is no ancestor of the "
            f"tagged commit {short(head)}. After the release, main could not "
            "follow without a force push. Tag a commit that builds on GitHub's "
            "main."
        )
        return [message]
    return []


def library_changes(repo: Path, released: str, head: str) -> list[str]:
    """The library files that differ between a release commit and `head`."""
    names = git(repo, "diff", "--name-only", released, head, "--", *LIBRARY_PATHSPEC)
    return names.splitlines()


def main_tag_findings(repo: Path, remote: str, head: str, version: str) -> list[str]:
    """Stage 3 for main: its release tag is on GitHub, and main ships its library."""
    tag = f"v{version}"
    try:
        released = remote_tag_commit(repo, remote, tag)
    except GitError as error:
        return [f"Cannot read the refs on {remote}: {error}"]
    if released is None:
        message = (
            f"Tag {tag} is not on GitHub. Push it first: "
            f"`git -c {CONFIRM_KEY}={version} push <remote> {tag}`."
        )
        return [message]
    if not has_commit(repo, released):
        message = (
            f"Tag {tag} on GitHub names {short(released)}, which this clone "
            "lacks. Run `git fetch --tags`."
        )
        return [message]
    if not is_ancestor(repo, released, head):
        message = (
            f"Tag {tag} on GitHub names {short(released)}, which is no ancestor "
            f"of the pushed commit {short(head)}."
        )
        return [message]
    changed = library_changes(repo, released, head)
    if changed:
        listing = _indent("\n".join(changed))
        message = (
            f"The library changed since {tag}. Release a new version before "
            f"pushing main:\n{listing}"
        )
        return [message]
    return []


def release_findings(
    repo: Path,
    remote: str,
    head: str,
    version: str,
    targets: set[str],
    pypi: PyPI,
) -> list[str]:
    """Stage 3: the release order on PyPI and GitHub, and main's library code.

    `targets` names what the push sends: "tag", "main" or both.
    """
    findings: list[str] = []
    known: bool | None = None
    try:
        known = pypi(version)
    except PyPIError as error:
        findings.append(str(error))
    if "tag" in targets:
        if known:
            findings.append(
                f"PyPI already serves {version}, and PyPI never takes a version "
                "twice. Release a new version."
            )
        findings.extend(tag_base_findings(repo, remote, head))
    if "main" in targets:
        if known is False:
            findings.append(
                f"PyPI does not serve {version} yet. Push main once the release "
                f"workflow has published it: the hosted demo installs {version} "
                "from PyPI."
            )
        findings.extend(main_tag_findings(repo, remote, head, version))
    return findings


@dataclass(frozen=True)
class Step:
    """One command of the suite, run from `cwd` below the repository root."""

    name: str
    args: tuple[str, ...]
    cwd: str = "."
    env: tuple[tuple[str, str], ...] = ()


# Runs one suite step in the repository with the given environment and returns
# its exit code.
Runner = Callable[[Step, Path, dict[str, str]], int]


def suite_steps(version: str, wheel_dir: Path) -> list[Step]:
    """What CI runs: ci.yml's lint job, its test-build-verify job, and its e2e
    job's browser suite in Chromium. run_suite runs them on CI's Python.

    `npm ci` comes first: the pre-commit hooks for the frontend need
    node_modules, as in CI's lint job. `playwright install chromium` does
    nothing when the browser is present.
    """
    wheel = wheel_dir / f"streamlit_listview-{version}-py3-none-any.whl"
    devel = ("uv", "run", "--locked", "--extra", "devel")
    skip_npm = (("LISTVIEW_SKIP_NPM_BUILD", "1"),)
    return [
        Step("npm ci", ("npm", "ci"), cwd=FRONTEND),
        Step(
            "pre-commit",
            ("uvx", "pre-commit", "run", "--all-files", "--show-diff-on-failure"),
        ),
        Step("npm run build", ("npm", "run", "build"), cwd=FRONTEND),
        Step("npm test", ("npm", "test"), cwd=FRONTEND),
        Step(
            "pytest",
            (*devel, "pytest", "tests/", "--cov", "--cov-report=term-missing"),
            env=skip_npm,
        ),
        Step(
            "playwright install",
            (*devel, "playwright", "install", "chromium"),
            env=skip_npm,
        ),
        Step("e2e", (*devel, "pytest", "e2e/"), env=skip_npm),
        Step("wheel build", ("uv", "build", "--wheel", "--out-dir", str(wheel_dir))),
        Step(
            "verify_wheel.py",
            (*devel, "python", "scripts/verify_wheel.py", str(wheel)),
            env=skip_npm,
        ),
        Step(
            "smoke_wheel.py",
            (*devel, "python", "scripts/smoke_wheel.py", str(wheel)),
            env=skip_npm,
        ),
    ]


def run_step(step: Step, repo: Path, env: dict[str, str]) -> int:
    """Run one suite step with its output on the console; return its exit code."""
    print(f"push gate: {step.name}: {' '.join(step.args)}", flush=True)
    # shutil.which also finds npm.cmd on Windows, which subprocess alone misses.
    executable = shutil.which(step.args[0])
    if executable is None:
        print(f"push gate: {step.args[0]} is not on PATH.", file=sys.stderr)
        return 127
    result = subprocess.run(
        [executable, *step.args[1:]],
        cwd=repo / step.cwd,
        env=env,
        stdin=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode


def suite_cache(repo: Path) -> Path:
    """The file that lists every commit whose suite run passed."""
    common = git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")
    return Path(common) / "push-gate" / "passed"


def run_suite(
    repo: Path, version: str, head: str, runner: Runner = run_step
) -> list[str]:
    """Stage 4: the CI suite on the pushed commit, once per commit."""
    cache = suite_cache(repo)
    if cache.is_file() and head in cache.read_text(encoding="utf-8").split():
        print(
            f"push gate: the suite passed for {short(head)} before; it does not "
            "run again.",
            flush=True,
        )
        return []
    # git exports GIT_DIR to the hooks of a linked worktree. Inherited, it would
    # turn a test's temporary repository into this one, and GIT_CONFIG_PARAMETERS
    # would carry the confirmation into the tests.
    env = {
        name: value
        for name, value in os.environ.items()
        if not name.upper().startswith("GIT_")
    }
    # CI's Python, in a project environment of the suite's own. uv replaces a
    # project environment of another Python version, and on Windows that fails
    # halfway through the checkout's .venv when the hook runs from it.
    env["UV_PYTHON"] = CI_PYTHON
    env["UV_PROJECT_ENVIRONMENT"] = str(cache.parent / "venv")
    with tempfile.TemporaryDirectory(
        prefix="push-gate-", ignore_cleanup_errors=True
    ) as wheel_dir:
        for step in suite_steps(version, Path(wheel_dir)):
            code = runner(step, repo, {**env, **dict(step.env)})
            if code != 0:
                message = (
                    f"The suite failed at {step.name} (exit code {code}). Fix it, "
                    "commit, and push again."
                )
                return [message]
    status = working_tree_status(repo)
    if status:
        message = (
            "The suite changed the working tree. Review the changes, commit "
            f"them, and push again:\n{_indent(status)}"
        )
        return [message]
    cache.parent.mkdir(parents=True, exist_ok=True)
    with cache.open("a", encoding="utf-8") as passed:
        passed.write(f"{head}\n")
    return []


def refuse(headline: str, findings: list[str]) -> int:
    """Print the findings under a headline; return the refusing exit code."""
    print(f"push gate: {headline}", file=sys.stderr)
    for finding in findings:
        print(f"  - {finding}", file=sys.stderr)
    return 1


def is_github(url: str) -> bool:
    return "github.com" in url.lower()


def utc_today() -> date:
    return datetime.now(timezone.utc).date()


def hook(
    repo: Path,
    url: str,
    refs: str,
    *,
    pypi: PyPI = pypi_knows,
    runner: Runner = run_step,
    today: date | None = None,
) -> int:
    """git's pre-push hook: the four stages for a push to GitHub.

    Returns 0 to let the push go ahead. A push to any other host passes
    unchecked.
    """
    if not is_github(url):
        return 0
    updates = parse_updates(refs)
    if not updates:
        return 0
    headline = f"refused the push to {url}"
    findings = ref_findings(repo, updates)
    if findings:
        return refuse(headline, findings)
    head = git(repo, "rev-parse", "HEAD")
    version, version_problems = version_findings(
        commit_reader(repo, head), today or utc_today()
    )
    checkout = checkout_findings(repo, updates, head)
    if version is None:
        # Without a version, the confirmation and the tag name have nothing to
        # match; the version finding says what to fix first.
        return refuse(headline, [*checkout, *version_problems])
    confirmation = confirmation_finding(repo, version)
    findings = [
        *([confirmation] if confirmation else []),
        *checkout,
        *tag_name_findings(updates, version),
        *version_problems,
    ]
    if findings:
        return refuse(headline, findings)
    targets = {"main" if update.is_main else "tag" for update in updates}
    findings = release_findings(repo, url, head, version, targets, pypi)
    if findings:
        return refuse(headline, findings)
    findings = run_suite(repo, version, head, runner)
    if findings:
        return refuse(headline, findings)
    print("push gate: passed.", flush=True)
    return 0


def check(
    repo: Path,
    target: str,
    *,
    tag: str | None = None,
    remote: str = "origin",
    pypi: PyPI = pypi_knows,
    today: date | None = None,
) -> int:
    """CI's checks of HEAD: the version information and the remote state.

    `target` is "tag" (release.yml, with the pushed `tag`) or "main" (ci.yml).
    """
    subject = tag or target
    headline = f"{subject} fails the release checks"
    head = git(repo, "rev-parse", "HEAD")
    version, findings = version_findings(
        commit_reader(repo, head), today or utc_today()
    )
    if version is not None and tag is not None:
        pushed = RefUpdate("HEAD", head, f"refs/tags/{tag}", "0" * 40)
        findings.extend(tag_name_findings([pushed], version))
    if findings or version is None:
        return refuse(headline, findings)
    findings = release_findings(repo, remote, head, version, {target}, pypi)
    if findings:
        return refuse(headline, findings)
    print(f"push gate: {subject} passes the release checks.", flush=True)
    return 0


def install(repo: Path) -> int:
    """Write the pre-push shim into the hooks directory all worktrees share."""
    scope, _, hooks_path = (
        _git(repo, "config", "--show-scope", "--get", "core.hooksPath")
        .stdout.strip()
        .partition("\t")
    )
    if scope and scope not in ("local", "worktree"):
        print(
            f"push gate: core.hooksPath comes from the {scope} git config "
            f"({hooks_path}). A hook there would gate every repository that "
            "uses it. Unset it, or set core.hooksPath in this repository.",
            file=sys.stderr,
        )
        return 1
    hooks = Path(
        git(repo, "rev-parse", "--path-format=absolute", "--git-path", "hooks")
    )
    shim = hooks / "pre-push"
    current = (
        shim.read_text(encoding="utf-8", errors="replace") if shim.exists() else ""
    )
    if current and SHIM_MARKER not in current:
        print(
            f"push gate: {shim} holds another pre-push hook. Merge the two by "
            "hand, or move it away and install again.",
            file=sys.stderr,
        )
        return 1
    hooks.mkdir(parents=True, exist_ok=True)
    shim.write_text(SHIM, encoding="utf-8", newline="\n")
    shim.chmod(0o755)
    print(f"push gate: installed {shim}")
    return 0


def _use_utf8() -> None:
    """Read the refs and write the findings as UTF-8, as git does.

    On Windows, Python reads and writes a pipe in the ANSI code page, which
    mangles every non-ASCII character of a ref name or a finding.
    """
    streams = (
        (sys.stdin, "replace"),
        (sys.stdout, "backslashreplace"),
        (sys.stderr, "backslashreplace"),
    )
    for stream, errors in streams:
        # Duck-typed, as in e2e/perf/report.py: a wrapped stream may proxy
        # reconfigure without being a TextIOWrapper.
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors=errors)


def main(argv: list[str] | None = None) -> int:
    _use_utf8()
    parser = argparse.ArgumentParser(
        prog="push_gate.py", description="Gate every push to GitHub."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("install", help="write the pre-push hook")
    hook_parser = commands.add_parser("hook", help="git's pre-push hook")
    hook_parser.add_argument("remote")
    hook_parser.add_argument("url")
    check_parser = commands.add_parser("check", help="CI's release checks of HEAD")
    targets = check_parser.add_subparsers(dest="target", required=True)
    targets.add_parser("tag").add_argument("name")
    targets.add_parser("main").add_argument("--remote", default="origin")
    args = parser.parse_args(argv)
    repo = Path.cwd()
    try:
        if args.command == "install":
            return install(repo)
        if args.command == "hook":
            return hook(repo, args.url, sys.stdin.read())
        if args.target == "tag":
            return check(repo, "tag", tag=args.name)
        return check(repo, "main", remote=args.remote)
    except GitError as error:
        # Refuse with the command and its message rather than a traceback.
        return refuse("a git command failed", [str(error)])


if __name__ == "__main__":
    sys.exit(main())
