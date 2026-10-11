"""The push gate in scripts/push_gate.py, which guards every push to GitHub.

The rule tests call the gate's functions in process. Tests that need git run it
in repositories under tmp_path, where a bare repository below a "github.com"
directory stands in for GitHub, so `git ls-remote` needs no network. Fakes
replace PyPI and the suite runner. The integration tests at the end push
through the installed hook with real git.
"""

import io
import os
import runpy
import shutil
import subprocess
import sys
import urllib.error
from collections.abc import Callable
from datetime import date
from email.message import Message
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"

sys.path.insert(0, str(SCRIPTS))

import push_gate

VERSION = "1.2.3"
TODAY = date(2026, 10, 8)
ZERO = "0" * 40
SHA_A = "a" * 40
SHA_B = "b" * 40
MAIN = "refs/heads/main"
TAG = f"refs/tags/v{VERSION}"


def release_files(version: str = VERSION) -> dict[str, str]:
    """Every file that carries the version: consistent and released."""
    return {
        ".gitignore": "__pycache__/\n",
        "pyproject.toml": (
            f'[project]\nname = "streamlit-listview"\nversion = "{version}"\n'
        ),
        "streamlit_listview/pyproject.toml": (
            f'[project]\nname = "streamlit_listview"\nversion = "{version}"\n'
        ),
        "streamlit_listview/__init__.py": "VALUE = 1\n",
        "tests/test_packaging.py": f'EXPECTED_VERSION = "{version}"\n',
        "README.md": (
            f"- `dist/streamlit_listview-{version}-py3-none-any.whl`\n"
            f"- `dist/streamlit_listview-{version}.tar.gz` (sdist)\n"
        ),
        "demo/requirements.txt": f"streamlit>=1.51\nstreamlit-listview=={version}\n",
        "uv.lock": (
            'version = 1\n\n[[package]]\nname = "streamlit-listview"\n'
            f'version = "{version}"\nsource = {{ editable = "." }}\n'
        ),
        # Non-ASCII on purpose: the real changelog carries dashes and
        # ellipses, which the gate must read as UTF-8 on Windows too.
        "CHANGELOG.md": (
            f"# Changelog\n\n## [{version}] - 2026-10-01\n\n"
            "- Search 100,000 options \u2014 in a second\u2026\n\n"
            f"[{version}]: https://example.com/compare/v1.2.2...v{version}\n"
        ),
    }


def reader_of(files: dict[str, str]) -> push_gate.Read:
    """A commit reader over files in memory."""
    return lambda path: files.get(path)


def changelog(heading: str, body: str = "- A change.", link: str | None = None) -> str:
    """A changelog whose newest heading, `heading`, sits on line 3."""
    if link is None:
        link = f"[{VERSION}]: https://example.com/v{VERSION}"
    return f"# Changelog\n\n{heading}\n\n{body}\n\n{link}\n"


@pytest.fixture(autouse=True)
def isolated_git(tmp_path, monkeypatch):
    """Run git without the caller's GIT_* variables, global or system config."""
    for name in list(os.environ):
        if name.upper().startswith("GIT_"):
            monkeypatch.delenv(name)
    config = tmp_path / "gitconfig"
    config.write_text(
        "[core]\n\tlongpaths = true\n[init]\n\tdefaultBranch = main\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for role in ("AUTHOR", "COMMITTER"):
        monkeypatch.setenv(f"GIT_{role}_NAME", "Push Gate")
        monkeypatch.setenv(f"GIT_{role}_EMAIL", "push-gate@example.com")


class Repo:
    """A git work tree whose remote `origin` is the bare repository at `url`."""

    def __init__(self, path: Path, url: str) -> None:
        self.path = path
        self.url = url

    def git(self, *args: str) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=self.path,
            capture_output=True,
            encoding="utf-8",
            check=False,
        )
        assert result.returncode == 0, result.stderr
        return result.stdout.strip()

    def write(self, files: dict[str, str]) -> None:
        for name, text in files.items():
            path = self.path / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="\n")

    def commit(
        self, files: dict[str, str] | None = None, message: str = "change"
    ) -> str:
        self.write(files or {})
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", message)
        return self.head

    @property
    def head(self) -> str:
        return self.git("rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path) -> Repo:
    """A work tree on main with one released commit, and an empty GitHub."""
    remote = tmp_path / "github.com" / "remote.git"
    subprocess.run(
        ["git", "init", "-q", "--bare", str(remote)], check=True, capture_output=True
    )
    repo = Repo(tmp_path / "work", str(remote))
    repo.path.mkdir()
    repo.git("init", "-q", "-b", "main")
    repo.git("remote", "add", "origin", repo.url)
    repo.commit(release_files(), "release")
    return repo


def update(
    remote_ref: str, local_sha: str, remote_sha: str = ZERO
) -> push_gate.RefUpdate:
    """A pre-push line that sends `local_sha` to `remote_ref`."""
    return push_gate.RefUpdate("HEAD", local_sha, remote_ref, remote_sha)


def confirm(monkeypatch, version: str = VERSION) -> None:
    """Make git see `-c listview.pushGithub=<version>`, as `git -c ... push` does."""
    monkeypatch.setenv("GIT_CONFIG_PARAMETERS", f"'listview.pushGithub'='{version}'")


class FakeResponse:
    """What urlopen returns: a context manager with a status."""

    def __init__(self, status: int) -> None:
        self.status = status

    def __enter__(self):  # unannotated: typing.Self needs Python 3.11
        return self

    def __exit__(self, *exc_info: object) -> None:
        pass


def fake_urlopen(monkeypatch, answer: int | BaseException) -> list[tuple[str, float]]:
    """Replace urlopen: `answer` is a status code or an exception to raise."""
    calls: list[tuple[str, float]] = []

    def urlopen(url: str, timeout: float) -> FakeResponse:
        calls.append((url, timeout))
        if isinstance(answer, BaseException):
            raise answer
        return FakeResponse(answer)

    monkeypatch.setattr(push_gate.urllib.request, "urlopen", urlopen)
    return calls


def http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(push_gate.PYPI_URL, code, "status", Message(), None)


def pypi_says(known: bool) -> push_gate.PyPI:
    return lambda version: known


def pypi_down(version: str) -> bool:
    raise push_gate.PyPIError("PyPI is unreachable (test).")


def publish(repo: Repo, *, annotated: bool = True) -> str:
    """Tag HEAD as the release and push main and the tag; return HEAD."""
    if annotated:
        repo.git("tag", "-a", f"v{VERSION}", "-m", "release")
    else:
        repo.git("tag", f"v{VERSION}")
    repo.git("push", "-q", "origin", "main", f"v{VERSION}")
    return repo.head


STEPS = [
    "npm ci",
    "pre-commit",
    "npm run build",
    "npm test",
    "pytest",
    "playwright install",
    "e2e",
    "wheel build",
    "verify_wheel.py",
]


class Recorder:
    """A suite runner that records the steps and answers with exit codes."""

    def __init__(
        self,
        codes: dict[str, int] | None = None,
        effects: dict[str, Callable[[], object]] | None = None,
    ) -> None:
        self.names: list[str] = []
        self.envs: dict[str, dict[str, str]] = {}
        self.codes = codes or {}
        self.effects = effects or {}

    def __call__(self, step: push_gate.Step, repo: Path, env: dict[str, str]) -> int:
        self.names.append(step.name)
        self.envs[step.name] = env
        if step.name in self.effects:
            self.effects[step.name]()
        return self.codes.get(step.name, 0)


def no_pypi(version: str) -> bool:
    pytest.fail("the gate asked PyPI before the local checks passed")


def no_suite(step: push_gate.Step, repo: Path, env: dict[str, str]) -> int:
    pytest.fail("the gate ran the suite before the remote checks passed")


def tag_push(repo: Repo) -> str:
    """Tag HEAD as the release; return the pre-push line that sends the tag."""
    repo.git("tag", "-a", f"v{VERSION}", "-m", "release")
    sha = repo.git("rev-parse", TAG)
    return f"{TAG} {sha} {TAG} {ZERO}\n"


UV = shutil.which("uv")
needs_uv = pytest.mark.skipif(UV is None, reason="the hook runs the gate through uv")


@pytest.fixture
def gated(repo: Repo) -> Repo:
    """The fixture repository with the gate committed and its hook installed."""
    repo.commit(
        {
            "scripts/push_gate.py": (SCRIPTS / "push_gate.py").read_text(
                encoding="utf-8"
            ),
            "scripts/verify_wheel.py": (SCRIPTS / "verify_wheel.py").read_text(
                encoding="utf-8"
            ),
        },
        "add the push gate",
    )
    assert push_gate.install(repo.path) == 0
    return repo


def run_git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run git in `cwd` and return the result, a failure included."""
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, encoding="utf-8", check=False
    )


def test_demo_pins_reads_every_pin():
    text = (
        "streamlit>=1.51\n"
        "streamlit-listview==1.2.3\n"
        "Streamlit_Listview == 1.2.4 ; python_version > '3'\n"
    )
    assert push_gate.demo_pins(text) == ["1.2.3", "1.2.4"]


def test_dist_names_name_the_wheel_and_the_sdist():
    assert push_gate.dist_names(VERSION) == (
        "streamlit_listview-1.2.3-py3-none-any.whl",
        "streamlit_listview-1.2.3.tar.gz",
    )


def test_expected_version_reads_the_constant():
    text = 'X = 1\nEXPECTED_VERSION = "1.2.3"\n'
    assert push_gate.expected_version(text) == "1.2.3"
    assert push_gate.expected_version("X = 1\n") is None


def test_lock_version_reads_this_projects_entry():
    lock = (
        '[[package]]\nname = "streamlit"\nversion = "1.51.0"\n\n'
        '[[package]]\nname = "streamlit-listview"\nversion = "1.2.3"\n'
    )
    assert push_gate.lock_version(lock) == "1.2.3"
    assert push_gate.lock_version('[[package]]\nname = "streamlit"\n') is None


def test_consistent_release_files_pass():
    read = reader_of(release_files())
    assert push_gate.version_findings(read, TODAY) == (VERSION, [])


def test_crlf_line_endings_pass():
    files = {name: text.replace("\n", "\r\n") for name, text in release_files().items()}
    assert push_gate.version_findings(reader_of(files), TODAY) == (VERSION, [])


def test_a_missing_root_version_stops_the_check():
    files = {**release_files(), "pyproject.toml": '[project]\nname = "x"\n'}
    assert push_gate.version_findings(reader_of(files), TODAY) == (
        None,
        ["pyproject.toml: no [project].version field."],
    )


@pytest.mark.parametrize(
    "version", ["1.2.3", "1.0.0", "10.20.30", "1.2.3a1", "1.2.3b2", "1.2.3rc10"]
)
def test_canonical_versions_pass(version):
    read = reader_of(release_files(version))
    assert push_gate.version_findings(read, TODAY) == (version, [])


@pytest.mark.parametrize(
    "version",
    [
        "1.2.3-rc.1",
        "1.2",
        "v1.2.3",
        "1.2.3.post1",
        "1.2.3rc",
        # Leading zeros: the wheel filename normalizes them away.
        "1.0.02",
        "01.0.0",
        "1.2.3rc01",
    ],
)
def test_a_non_canonical_version_is_refused(version):
    found, findings = push_gate.version_findings(
        reader_of(release_files(version)), TODAY
    )
    expected = (
        f'pyproject.toml: "{version}" is no canonical PEP 440 version. Write '
        "X.Y.Z, or X.Y.Z followed by a, b or rc and a number."
    )
    assert found == version
    assert findings == [expected]


@pytest.mark.parametrize(
    ("path", "text", "expected"),
    [
        (
            "streamlit_listview/pyproject.toml",
            'version = "9.9.9"\n',
            "streamlit_listview/pyproject.toml: version 9.9.9, expected 1.2.3.",
        ),
        (
            "tests/test_packaging.py",
            'EXPECTED_VERSION = "9.9.9"\n',
            "tests/test_packaging.py: EXPECTED_VERSION 9.9.9, expected 1.2.3.",
        ),
        (
            "demo/requirements.txt",
            "streamlit-listview==9.9.9\n",
            "demo/requirements.txt: pins ['9.9.9'], expected exactly one streamlit-listview==1.2.3.",
        ),
        (
            "demo/requirements.txt",
            "streamlit-listview==1.2.3\nstreamlit_listview==1.2.3\n",
            "demo/requirements.txt: pins ['1.2.3', '1.2.3'], expected exactly one streamlit-listview==1.2.3.",
        ),
        (
            "uv.lock",
            '[[package]]\nname = "streamlit-listview"\nversion = "9.9.9"\n',
            "uv.lock: records 9.9.9, expected 1.2.3. Run `uv lock`.",
        ),
    ],
)
def test_a_place_that_disagrees_is_named(path, text, expected):
    files = {**release_files(), path: text}
    assert push_gate.version_findings(reader_of(files), TODAY) == (
        VERSION,
        [expected],
    )


def test_a_missing_file_disagrees():
    files = release_files()
    del files["uv.lock"]
    assert push_gate.version_findings(reader_of(files), TODAY) == (
        VERSION,
        ["uv.lock: records none, expected 1.2.3. Run `uv lock`."],
    )


def test_readme_without_the_dist_filenames_is_named():
    files = {**release_files(), "README.md": "- `streamlit_listview-1.2.2.tar.gz`\n"}
    _, findings = push_gate.version_findings(reader_of(files), TODAY)
    assert findings == [
        "README.md: no streamlit_listview-1.2.3-py3-none-any.whl. Update the dist filename examples.",
        "README.md: no streamlit_listview-1.2.3.tar.gz. Update the dist filename examples.",
    ]


def test_a_released_changelog_passes():
    text = changelog(f"## [{VERSION}] - 2026-10-01")
    assert push_gate.changelog_findings(text, VERSION, TODAY) == []


def test_unreleased_is_refused_with_its_lines():
    text = changelog(
        "## [Unreleased]",
        link="[Unreleased]: https://example.com/compare/v1.2.2...HEAD",
    )
    assert push_gate.changelog_findings(text, VERSION, TODAY) == [
        'CHANGELOG.md:3,7: "Unreleased" remains. Turn the section into "## [1.2.3] - YYYY-MM-DD" and its link into "[1.2.3]: ...".',
        'CHANGELOG.md:3: the newest heading reads "## [Unreleased]", expected "## [1.2.3] - YYYY-MM-DD".',
        'CHANGELOG.md: no link line "[1.2.3]: <url>". Add one below the others.',
    ]


def test_unreleased_in_prose_is_refused_too():
    text = changelog(
        f"## [{VERSION}] - 2026-10-01", body="- Drops an unreleased draft."
    )
    assert push_gate.changelog_findings(text, VERSION, TODAY) == [
        'CHANGELOG.md:5: "Unreleased" remains. Turn the section into "## [1.2.3] - YYYY-MM-DD" and its link into "[1.2.3]: ...".'
    ]


@pytest.mark.parametrize(
    "heading",
    [
        "## [1.2.2] - 2026-09-01",
        "## [1.2.3] \u2013 2026-10-01",
        "## [1.2.3]",
        "## [1.2.3] - 1 Oct 2026",
    ],
)
def test_a_malformed_newest_heading_is_quoted(heading):
    findings = push_gate.changelog_findings(changelog(heading), VERSION, TODAY)
    assert findings == [
        f'CHANGELOG.md:3: the newest heading reads "{heading}", expected "## [1.2.3] - YYYY-MM-DD".'
    ]


def test_an_invalid_date_is_refused():
    text = changelog("## [1.2.3] - 2026-02-30")
    assert push_gate.changelog_findings(text, VERSION, TODAY) == [
        "CHANGELOG.md:3: 2026-02-30 is not a valid date."
    ]


def test_tomorrow_passes_but_the_day_after_is_refused():
    tomorrow = changelog("## [1.2.3] - 2026-10-09")
    later = changelog("## [1.2.3] - 2026-10-10")
    assert push_gate.changelog_findings(tomorrow, VERSION, TODAY) == []
    assert push_gate.changelog_findings(later, VERSION, TODAY) == [
        "CHANGELOG.md:3: the release date 2026-10-10 lies in the future."
    ]


def test_a_changelog_without_versions_is_refused():
    text = "# Changelog\n\nNothing yet.\n"
    assert push_gate.changelog_findings(text, VERSION, TODAY) == [
        'CHANGELOG.md: no version heading. Add "## [1.2.3] - YYYY-MM-DD".',
        'CHANGELOG.md: no link line "[1.2.3]: <url>". Add one below the others.',
    ]


def test_a_missing_link_line_is_refused():
    text = changelog("## [1.2.3] - 2026-10-01", link="[1.2.2]: https://example.com")
    assert push_gate.changelog_findings(text, VERSION, TODAY) == [
        'CHANGELOG.md: no link line "[1.2.3]: <url>". Add one below the others.'
    ]


def test_git_raises_with_the_command_and_its_error(repo):
    with pytest.raises(push_gate.GitError, match="git rev-parse no-such-ref"):
        push_gate.git(repo.path, "rev-parse", "no-such-ref")


def test_commit_reader_decodes_utf8_and_misses_absent_files(repo):
    read = push_gate.commit_reader(repo.path, repo.head)
    assert "\u2014" in (read("CHANGELOG.md") or "")
    assert read("no/such/file") is None
    assert push_gate.version_findings(read, TODAY) == (VERSION, [])


def test_parse_updates_reads_every_line():
    text = f"HEAD {SHA_A} {MAIN} {ZERO}\n\n(delete) {ZERO} refs/tags/v1.2.2 {SHA_B}\n"
    assert push_gate.parse_updates(text) == [
        push_gate.RefUpdate("HEAD", SHA_A, MAIN, ZERO),
        push_gate.RefUpdate("(delete)", ZERO, "refs/tags/v1.2.2", SHA_B),
    ]


def test_new_refs_and_a_fast_forward_pass(repo):
    base = repo.head
    head = repo.commit(message="next")
    updates = [update(MAIN, head, base), update(TAG, head)]
    assert push_gate.ref_findings(repo.path, updates) == []


def test_a_branch_other_than_main_is_refused(repo):
    updates = [update("refs/heads/feature", repo.head)]
    assert push_gate.ref_findings(repo.path, updates) == [
        "refs/heads/feature: GitHub takes only main and v* tags. Push other branches to Azure DevOps."
    ]


@pytest.mark.parametrize("ref", [MAIN, TAG])
def test_a_deletion_is_refused(repo, ref):
    findings = push_gate.ref_findings(repo.path, [update(ref, ZERO, repo.head)])
    assert findings == [
        f"{ref}: the push deletes it. GitHub keeps main and every release tag."
    ]


def test_moving_a_tag_is_refused(repo):
    findings = push_gate.ref_findings(repo.path, [update(TAG, repo.head, repo.head)])
    assert findings == [
        f"{TAG}: the tag exists on GitHub, and a release tag never moves. Release a new version instead."
    ]


def test_a_force_push_of_main_is_refused(repo):
    base = repo.head
    published = repo.commit(message="published")
    repo.git("reset", "-q", "--hard", base)
    rewritten = repo.commit(message="rewritten")
    findings = push_gate.ref_findings(repo.path, [update(MAIN, rewritten, published)])
    assert findings == [
        f"{MAIN}: the push rewrites GitHub's main: {published[:12]} is no ancestor of {rewritten[:12]}. Force pushes are refused."
    ]


def test_an_unknown_github_main_asks_for_a_fetch(repo):
    findings = push_gate.ref_findings(repo.path, [update(MAIN, repo.head, "1" * 40)])
    assert findings == [
        f"{MAIN}: GitHub's main is at 111111111111, which this clone lacks. Run `git fetch` and push again."
    ]


def test_a_command_line_confirmation_passes(repo, monkeypatch):
    confirm(monkeypatch)
    assert push_gate.confirmation_finding(repo.path, VERSION) is None


def test_a_missing_confirmation_is_refused(repo):
    assert push_gate.confirmation_finding(repo.path, VERSION) == (
        "No confirmation. Push with `git -c listview.pushGithub=1.2.3 push ...`."
    )


def test_a_confirmation_of_another_version_is_refused(repo, monkeypatch):
    confirm(monkeypatch, "1.2.2")
    assert push_gate.confirmation_finding(repo.path, VERSION) == (
        "The confirmation names 1.2.2, but the pushed commit is 1.2.3. Push with `git -c listview.pushGithub=1.2.3 push ...`."
    )


def test_a_stored_confirmation_does_not_count(repo):
    repo.git("config", "listview.pushGithub", VERSION)
    assert push_gate.confirmation_finding(repo.path, VERSION) == (
        "The confirmation comes from the local git config, and only the command line counts. Run `git config --local --unset listview.pushGithub`. Push with `git -c listview.pushGithub=1.2.3 push ...`."
    )


def test_head_of_a_clean_tree_passes_with_either_kind_of_tag(repo):
    repo.git("tag", "light")
    repo.git("tag", "-a", "annotated", "-m", "release")
    updates = [
        update(MAIN, repo.head),
        update(TAG, repo.git("rev-parse", "light")),
        update(TAG, repo.git("rev-parse", "annotated")),
    ]
    assert push_gate.checkout_findings(repo.path, updates, repo.head) == []


def test_a_commit_other_than_head_is_refused(repo):
    old = repo.head
    head = repo.commit(message="next")
    findings = push_gate.checkout_findings(repo.path, [update(MAIN, old)], head)
    assert findings == [
        f"{MAIN}: the push sends {old[:12]}, but HEAD is {head[:12]}. Check out the commit you push."
    ]


def test_an_untracked_file_is_refused(repo):
    (repo.path / "notes.txt").write_text("draft\n", encoding="utf-8")
    updates = [update(MAIN, repo.head)]
    assert push_gate.checkout_findings(repo.path, updates, repo.head) == [
        "The working tree has changes. Commit or remove them, so the suite tests exactly the pushed commit:\n      ?? notes.txt"
    ]


def test_a_tag_must_name_the_version():
    updates = [
        update(TAG, SHA_A),
        update("refs/tags/v9.9.9", SHA_A),
        update(MAIN, SHA_A),
    ]
    assert push_gate.tag_name_findings(updates, VERSION) == [
        "refs/tags/v9.9.9: the tag of version 1.2.3 is v1.2.3."
    ]


def test_pypi_knows_a_published_version(monkeypatch):
    calls = fake_urlopen(monkeypatch, 200)
    assert push_gate.pypi_knows(VERSION) is True
    assert calls == [("https://pypi.org/pypi/streamlit-listview/1.2.3/json", 10)]


def test_pypi_does_not_know_a_404(monkeypatch):
    fake_urlopen(monkeypatch, http_error(404))
    assert push_gate.pypi_knows(VERSION) is False


@pytest.mark.parametrize(
    ("answer", "message"),
    [
        (http_error(503), "PyPI answered 503"),
        (urllib.error.URLError("no route"), "PyPI is unreachable"),
        (TimeoutError("timed out"), "PyPI is unreachable"),
        (204, "PyPI answered 204"),
    ],
)
def test_an_unclear_pypi_answer_raises(monkeypatch, answer, message):
    fake_urlopen(monkeypatch, answer)
    with pytest.raises(push_gate.PyPIError, match=message):
        push_gate.pypi_knows(VERSION)


@pytest.mark.parametrize("annotated", [True, False])
def test_remote_tag_commit_peels_the_tag(repo, annotated):
    head = publish(repo, annotated=annotated)
    assert push_gate.remote_tag_commit(repo.path, repo.url, f"v{VERSION}") == head


def test_remote_tag_commit_misses_an_absent_tag(repo):
    assert push_gate.remote_tag_commit(repo.path, repo.url, "v9.9.9") is None


def test_remote_tag_commit_raises_for_an_unreadable_remote(repo, tmp_path):
    missing = str(tmp_path / "github.com" / "none.git")
    with pytest.raises(push_gate.GitError):
        push_gate.remote_tag_commit(repo.path, missing, "v1")


def test_library_changes_skip_docs_tests_and_test_configuration(repo):
    released = publish(repo)
    frontend = "streamlit_listview/frontend"
    head = repo.commit(
        {
            "streamlit_listview/__init__.py": "VALUE = 2\n",
            "streamlit_listview/CLAUDE.md": "# Notes\n",
            f"{frontend}/CLAUDE.md": "# Notes\n",
            f"{frontend}/package.json": "{}\n",
            f"{frontend}/src/Listview.tsx": "export {};\n",
            f"{frontend}/src/Listview.test.tsx": "export {};\n",
            f"{frontend}/src/hooks/useFilter.test.ts": "export {};\n",
            f"{frontend}/src/__tests__/types.test.ts": "export {};\n",
            f"{frontend}/src/test/makeData.ts": "export {};\n",
            f"{frontend}/src/bench/fixtures.ts": "export {};\n",
            f"{frontend}/.oxlintrc.json": "{}\n",
            f"{frontend}/tsconfig.test.json": "{}\n",
            f"{frontend}/vitest.config.ts": "export {};\n",
            "demo/app.py": "VALUE = 1\n",
        }
    )
    assert push_gate.library_changes(repo.path, released, head) == [
        "streamlit_listview/__init__.py",
        f"{frontend}/package.json",
        f"{frontend}/src/Listview.tsx",
    ]


def test_a_new_tag_passes_while_pypi_lacks_the_version(repo):
    findings = push_gate.release_findings(
        repo.path, repo.url, repo.head, VERSION, {"tag"}, pypi_says(False)
    )
    assert findings == []


def test_a_tag_that_pypi_already_serves_is_refused(repo):
    findings = push_gate.release_findings(
        repo.path, repo.url, repo.head, VERSION, {"tag"}, pypi_says(True)
    )
    assert findings == [
        "PyPI already serves 1.2.3, and PyPI never takes a version twice. Release a new version."
    ]


def test_an_unclear_pypi_answer_is_a_finding(repo):
    findings = push_gate.release_findings(
        repo.path, repo.url, repo.head, VERSION, {"tag"}, pypi_down
    )
    assert findings == ["PyPI is unreachable (test)."]


def test_main_passes_after_the_release(repo):
    head = publish(repo)
    findings = push_gate.release_findings(
        repo.path, repo.url, head, VERSION, {"main"}, pypi_says(True)
    )
    assert findings == []


def test_main_waits_for_pypi(repo):
    head = publish(repo)
    findings = push_gate.release_findings(
        repo.path, repo.url, head, VERSION, {"main"}, pypi_says(False)
    )
    assert findings == [
        "PyPI does not serve 1.2.3 yet. Push main once the release workflow has published it: the hosted demo installs 1.2.3 from PyPI."
    ]


def test_main_with_pypi_down_still_checks_the_tag(repo):
    findings = push_gate.release_findings(
        repo.path, repo.url, repo.head, VERSION, {"main"}, pypi_down
    )
    assert findings == [
        "PyPI is unreachable (test).",
        "Tag v1.2.3 is not on GitHub. Push it first: `git -c listview.pushGithub=1.2.3 push <remote> v1.2.3`.",
    ]


def test_main_after_a_docs_change_passes(repo):
    publish(repo)
    head = repo.commit({"streamlit_listview/CLAUDE.md": "# Notes\n", "docs.md": "x\n"})
    assert push_gate.main_tag_findings(repo.path, repo.url, head, VERSION) == []


def test_main_with_a_library_change_is_refused(repo):
    publish(repo)
    head = repo.commit({"streamlit_listview/__init__.py": "VALUE = 2\n"})
    assert push_gate.main_tag_findings(repo.path, repo.url, head, VERSION) == [
        "The library changed since v1.2.3. Release a new version before pushing main:\n      streamlit_listview/__init__.py"
    ]


def test_main_needs_the_tag_among_its_ancestors(repo):
    head = repo.head
    repo.git("checkout", "-q", "-b", "side")
    side = repo.commit(message="side")
    repo.git("tag", "-a", f"v{VERSION}", "-m", "release")
    repo.git("push", "-q", "origin", f"v{VERSION}")
    assert push_gate.main_tag_findings(repo.path, repo.url, head, VERSION) == [
        f"Tag v1.2.3 on GitHub names {side[:12]}, which is no ancestor of the pushed commit {head[:12]}."
    ]


def test_main_needs_the_tag_commit_in_this_clone(repo, tmp_path):
    repo.git("push", "-q", "origin", "main")
    other = Repo(tmp_path / "other", repo.url)
    subprocess.run(
        ["git", "clone", "-q", repo.url, str(other.path)],
        check=True,
        capture_output=True,
    )
    elsewhere = other.commit(message="elsewhere")
    other.git("tag", "-a", f"v{VERSION}", "-m", "release")
    other.git("push", "-q", "origin", f"v{VERSION}")
    assert push_gate.main_tag_findings(repo.path, repo.url, repo.head, VERSION) == [
        f"Tag v1.2.3 on GitHub names {elsewhere[:12]}, which this clone lacks. Run `git fetch --tags`."
    ]


def test_an_unreadable_github_is_a_finding(repo, tmp_path):
    missing = str(tmp_path / "github.com" / "none.git")
    findings = push_gate.main_tag_findings(repo.path, missing, repo.head, VERSION)
    assert len(findings) == 1
    assert findings[0].startswith(f"Cannot read the refs on {missing}: git ls-remote")


def test_suite_steps_run_cis_commands_and_verify_the_versions_wheel(tmp_path):
    steps = push_gate.suite_steps(VERSION, tmp_path)
    assert [step.name for step in steps] == STEPS
    frontend = [steps[0].cwd, steps[2].cwd, steps[3].cwd]
    assert frontend == ["streamlit_listview/frontend"] * 3
    devel = ("uv", "run", "--locked", "--extra", "devel")
    assert steps[5].args == (*devel, "playwright", "install", "chromium")
    assert steps[6].args == (*devel, "pytest", "e2e/")
    skip_npm = {"LISTVIEW_SKIP_NPM_BUILD": "1"}
    assert [dict(step.env) for step in steps[4:7]] == [skip_npm] * 3
    assert steps[-1].args == (
        sys.executable,
        "scripts/verify_wheel.py",
        str(tmp_path / "streamlit_listview-1.2.3-py3-none-any.whl"),
    )


def test_the_suite_runs_in_order_and_remembers_the_pass(repo):
    runner = Recorder()
    assert push_gate.run_suite(repo.path, VERSION, repo.head, runner) == []
    assert runner.names == STEPS
    cache = push_gate.suite_cache(repo.path)
    assert cache.read_text(encoding="utf-8").split() == [repo.head]


def test_the_suite_stops_at_the_first_failure(repo):
    runner = Recorder(codes={"npm test": 1})
    assert push_gate.run_suite(repo.path, VERSION, repo.head, runner) == [
        "The suite failed at npm test (exit code 1). Fix it, commit, and push again."
    ]
    assert runner.names == STEPS[:4]
    assert not push_gate.suite_cache(repo.path).exists()


def test_the_suite_runs_without_git_variables(repo, monkeypatch):
    monkeypatch.setenv("GIT_PUSH_GATE_PROBE", "1")
    monkeypatch.delenv("LISTVIEW_SKIP_NPM_BUILD", raising=False)
    runner = Recorder()
    push_gate.run_suite(repo.path, VERSION, repo.head, runner)
    for name, env in runner.envs.items():
        assert not [key for key in env if key.upper().startswith("GIT_")], name
        skips_npm = name in {"pytest", "playwright install", "e2e"}
        assert ("LISTVIEW_SKIP_NPM_BUILD" in env) == skips_npm, name


def test_a_passed_commit_skips_the_suite(repo, capsys):
    cache = push_gate.suite_cache(repo.path)
    cache.parent.mkdir(parents=True)
    cache.write_text(f"{repo.head}\n", encoding="utf-8")
    runner = Recorder()
    assert push_gate.run_suite(repo.path, VERSION, repo.head, runner) == []
    assert runner.names == []
    assert "passed for" in capsys.readouterr().out


def test_a_cache_of_other_commits_runs_the_suite(repo):
    cache = push_gate.suite_cache(repo.path)
    cache.parent.mkdir(parents=True)
    cache.write_text(f"{SHA_A}\n", encoding="utf-8")
    runner = Recorder()
    assert push_gate.run_suite(repo.path, VERSION, repo.head, runner) == []
    assert runner.names == STEPS
    assert cache.read_text(encoding="utf-8").split() == [SHA_A, repo.head]


def test_the_suite_may_not_change_the_tree(repo):
    def stray() -> None:
        (repo.path / "stray.txt").write_text("x\n", encoding="utf-8")

    runner = Recorder(effects={"npm ci": stray})
    assert push_gate.run_suite(repo.path, VERSION, repo.head, runner) == [
        "The suite changed the working tree. Review the changes, commit them, and push again:\n      ?? stray.txt"
    ]
    assert not push_gate.suite_cache(repo.path).exists()


def test_run_step_returns_the_exit_code(repo, capsys):
    step = push_gate.Step("exit", (sys.executable, "-c", "raise SystemExit(3)"))
    assert push_gate.run_step(step, repo.path, dict(os.environ)) == 3
    assert "push gate: exit:" in capsys.readouterr().out


def test_run_step_reports_a_missing_tool(repo, capsys):
    step = push_gate.Step("missing", ("no-such-tool-for-the-push-gate",))
    assert push_gate.run_step(step, repo.path, dict(os.environ)) == 127
    assert "no-such-tool-for-the-push-gate is not on PATH" in capsys.readouterr().err


def test_hook_lets_any_other_host_pass(repo):
    assert push_gate.hook(repo.path, "https://dev.azure.com/x/_git/y", "junk") == 0


def test_hook_with_nothing_to_push_passes(repo):
    assert push_gate.hook(repo.path, repo.url, "\n") == 0


def test_hook_stops_after_the_ref_stage(repo, capsys):
    refs = f"HEAD {repo.head} refs/heads/feature {ZERO}\n"
    code = push_gate.hook(
        repo.path, repo.url, refs, pypi=no_pypi, runner=no_suite, today=TODAY
    )
    err = capsys.readouterr().err
    assert code == 1
    assert f"push gate: refused the push to {repo.url}" in err
    assert "GitHub takes only main" in err
    assert "No confirmation" not in err


def test_hook_reports_every_local_finding_at_once(repo, capsys):
    (repo.path / "notes.txt").write_text("draft\n", encoding="utf-8")
    refs = f"HEAD {repo.head} {MAIN} {ZERO}\n"
    code = push_gate.hook(
        repo.path, repo.url, refs, pypi=no_pypi, runner=no_suite, today=TODAY
    )
    err = capsys.readouterr().err
    assert code == 1
    assert "No confirmation" in err
    assert "The working tree has changes" in err


def test_hook_refuses_a_commit_without_a_version(repo, monkeypatch, capsys):
    confirm(monkeypatch)
    head = repo.commit({"pyproject.toml": '[project]\nname = "x"\n'})
    refs = f"HEAD {head} {MAIN} {ZERO}\n"
    code = push_gate.hook(
        repo.path, repo.url, refs, pypi=no_pypi, runner=no_suite, today=TODAY
    )
    err = capsys.readouterr().err
    assert code == 1
    assert "no [project].version field" in err
    assert "<version>" not in err


def test_hook_stops_before_the_suite_when_pypi_has_the_tag(repo, monkeypatch, capsys):
    confirm(monkeypatch)
    refs = tag_push(repo)
    code = push_gate.hook(
        repo.path, repo.url, refs, pypi=pypi_says(True), runner=no_suite, today=TODAY
    )
    assert code == 1
    assert "PyPI already serves 1.2.3" in capsys.readouterr().err


def test_hook_passes_a_release_tag_after_the_suite(repo, monkeypatch, capsys):
    confirm(monkeypatch)
    refs = tag_push(repo)
    runner = Recorder()
    code = push_gate.hook(
        repo.path, repo.url, refs, pypi=pypi_says(False), runner=runner, today=TODAY
    )
    assert code == 0
    assert runner.names == STEPS
    assert "push gate: passed." in capsys.readouterr().out


def test_hook_passes_main_after_the_release(repo, monkeypatch):
    released = publish(repo)
    head = repo.commit({"docs.md": "x\n"})
    confirm(monkeypatch)
    refs = f"HEAD {head} {MAIN} {released}\n"
    code = push_gate.hook(
        repo.path, repo.url, refs, pypi=pypi_says(True), runner=Recorder(), today=TODAY
    )
    assert code == 0


def test_hook_refuses_when_the_suite_fails(repo, monkeypatch, capsys):
    confirm(monkeypatch)
    refs = tag_push(repo)
    runner = Recorder(codes={"pytest": 1})
    code = push_gate.hook(
        repo.path, repo.url, refs, pypi=pypi_says(False), runner=runner, today=TODAY
    )
    assert code == 1
    assert "The suite failed at pytest" in capsys.readouterr().err


def test_check_tag_passes_a_release(repo, capsys):
    code = push_gate.check(
        repo.path, "tag", tag=f"v{VERSION}", pypi=pypi_says(False), today=TODAY
    )
    assert code == 0
    assert "push gate: v1.2.3 passes the release checks." in capsys.readouterr().out


def test_check_tag_refuses_a_tag_of_another_version(repo, capsys):
    code = push_gate.check(repo.path, "tag", tag="v9.9.9", pypi=no_pypi, today=TODAY)
    err = capsys.readouterr().err
    assert code == 1
    assert "push gate: v9.9.9 fails the release checks" in err
    assert "refs/tags/v9.9.9: the tag of version 1.2.3 is v1.2.3." in err


def test_check_main_passes_after_the_release(repo):
    publish(repo)
    code = push_gate.check(repo.path, "main", pypi=pypi_says(True), today=TODAY)
    assert code == 0


def test_check_main_refuses_an_unreleased_changelog(repo, capsys):
    publish(repo)
    repo.commit({"CHANGELOG.md": changelog("## [Unreleased]")})
    assert push_gate.check(repo.path, "main", pypi=no_pypi, today=TODAY) == 1
    assert '"Unreleased" remains' in capsys.readouterr().err


def test_check_main_refuses_before_pypi_has_the_release(repo, capsys):
    publish(repo)
    assert push_gate.check(repo.path, "main", pypi=pypi_says(False), today=TODAY) == 1
    assert "PyPI does not serve 1.2.3 yet" in capsys.readouterr().err


def test_install_writes_the_shim_with_lf_endings(repo, capsys):
    assert push_gate.install(repo.path) == 0
    content = (repo.path / ".git" / "hooks" / "pre-push").read_bytes()
    assert content.startswith(b"#!/bin/sh\n")
    assert b"\r\n" not in content
    assert push_gate.SHIM_MARKER.encode() in content
    assert push_gate.install(repo.path) == 0
    assert "installed" in capsys.readouterr().out


def test_install_keeps_a_foreign_hook(repo, capsys):
    shim = repo.path / ".git" / "hooks" / "pre-push"
    shim.parent.mkdir(parents=True, exist_ok=True)
    shim.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    assert push_gate.install(repo.path) == 1
    assert shim.read_text(encoding="utf-8") == "#!/bin/sh\nexit 0\n"
    assert "holds another pre-push hook" in capsys.readouterr().err


def test_main_installs_the_shim(repo, monkeypatch):
    monkeypatch.chdir(repo.path)
    assert push_gate.main(["install"]) == 0
    assert (repo.path / ".git" / "hooks" / "pre-push").is_file()


def test_main_runs_the_hook_on_stdin(repo, monkeypatch):
    monkeypatch.chdir(repo.path)
    refs = f"HEAD {repo.head} refs/heads/feature {ZERO}\n"
    monkeypatch.setattr(sys, "stdin", io.StringIO(refs))
    assert push_gate.main(["hook", "origin", repo.url]) == 1


def test_main_checks_a_tag(repo, monkeypatch):
    monkeypatch.chdir(repo.path)
    fake_urlopen(monkeypatch, http_error(404))
    assert push_gate.main(["check", "tag", f"v{VERSION}"]) == 0


def test_main_checks_main(repo, monkeypatch):
    publish(repo)
    monkeypatch.chdir(repo.path)
    fake_urlopen(monkeypatch, 200)
    assert push_gate.main(["check", "main"]) == 0


def test_the_script_runs_main(monkeypatch):
    argv = ["push_gate.py", "hook", "azure", "https://dev.azure.com/x"]
    monkeypatch.setattr(sys, "argv", argv)
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    with pytest.raises(SystemExit) as exit_info:
        runpy.run_path(str(SCRIPTS / "push_gate.py"), run_name="__main__")
    assert exit_info.value.code == 0


@needs_uv
def test_the_hook_lets_another_host_pass(gated, tmp_path):
    azure = tmp_path / "azure" / "remote.git"
    subprocess.run(
        ["git", "init", "-q", "--bare", str(azure)], check=True, capture_output=True
    )
    result = run_git(gated.path, "push", str(azure), "main")
    assert result.returncode == 0, result.stderr


@needs_uv
def test_the_hook_refuses_github_without_confirmation(gated):
    result = run_git(gated.path, "push", "origin", "main")
    assert result.returncode != 0
    assert "No confirmation" in result.stderr


@needs_uv
def test_the_hook_refuses_a_feature_branch(gated):
    gated.git("branch", "feature")
    result = run_git(gated.path, "push", "origin", "feature")
    assert result.returncode != 0
    assert "GitHub takes only main and v* tags" in result.stderr


@needs_uv
def test_the_hook_runs_in_a_linked_worktree(gated, tmp_path):
    worktree = Repo(tmp_path / "wt", gated.url)
    gated.git("worktree", "add", "-q", str(worktree.path), "-b", "side")
    worktree.commit({"notes.md": "x\n"})
    result = run_git(worktree.path, "push", "origin", "HEAD:main")
    assert result.returncode != 0
    assert "No confirmation" in result.stderr
    assert "but HEAD is" not in result.stderr


@needs_uv
def test_a_checkout_without_the_gate_cannot_push_to_github(gated, tmp_path):
    gated.git("checkout", "-q", "-b", "old", "HEAD~1")
    result = run_git(
        gated.path, "-c", "listview.pushGithub=1.2.3", "push", "origin", "old:main"
    )
    assert result.returncode != 0
    assert "has no scripts/push_gate.py" in result.stderr
    azure = tmp_path / "azure" / "remote.git"
    subprocess.run(
        ["git", "init", "-q", "--bare", str(azure)], check=True, capture_output=True
    )
    assert run_git(gated.path, "push", str(azure), "old").returncode == 0


def test_ci_and_the_release_workflow_run_the_gate():
    """Drift guard: GitHub repeats the gate's checks, so a push that skipped
    the hook with --no-verify still fails where everyone sees it."""
    workflows = ROOT / ".github" / "workflows"
    ci = (workflows / "ci.yml").read_text(encoding="utf-8")
    release = (workflows / "release.yml").read_text(encoding="utf-8")
    assert "python3 scripts/push_gate.py check main" in ci
    assert "fetch-depth: 0" in ci
    assert 'python3 scripts/push_gate.py check tag "$GITHUB_REF_NAME"' in release
    # check tag compares the tag with GitHub's main, which a shallow clone lacks.
    assert "fetch-depth: 0" in release


def test_ci_runs_the_browser_suite_that_the_gate_runs():
    """Drift guard: the gate's e2e step and CI's e2e job run the same suite."""
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "playwright install --with-deps chromium" in ci
    assert "-m pytest e2e/" in ci


def test_findings_reach_a_pipe_as_utf8(repo):
    # git shows the hook's output as UTF-8; Python on Windows writes a pipe in
    # the ANSI code page unless told otherwise, which mangles the en dash.
    repo.commit({"CHANGELOG.md": changelog("## [1.2.3] \u2013 2026-10-01")})
    result = run_script(repo, "check", "tag", f"v{VERSION}")
    assert result.returncode == 1
    assert "\u2013" in result.stderr.decode("utf-8", errors="replace")


def run_script(
    repo: Repo, *args: str, refs: str = ""
) -> subprocess.CompletedProcess[bytes]:
    """Run push_gate.py as git runs it: stdio on pipes, no UTF-8 override."""
    env = {
        name: value
        for name, value in os.environ.items()
        if name not in ("PYTHONIOENCODING", "PYTHONUTF8")
    }
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "push_gate.py"), *args],
        cwd=repo.path,
        input=refs.encode("utf-8"),
        capture_output=True,
        env=env,
        check=False,
    )


def test_main_tolerates_streams_without_reconfigure(monkeypatch):
    monkeypatch.setattr(sys, "stdout", io.StringIO())
    monkeypatch.setattr(sys, "stderr", io.StringIO())
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    assert push_gate.main(["hook", "azure", "https://dev.azure.com/x"]) == 0


@needs_uv
def test_the_hook_lets_another_host_pass_without_uv(gated, tmp_path, monkeypatch):
    # A GUI git client may run with a PATH that lacks uv; a push to another
    # host must still pass, because only a GitHub push needs the gate.
    path = os.pathsep.join(
        entry
        for entry in os.environ["PATH"].split(os.pathsep)
        if shutil.which("uv", path=entry) is None
    )
    if shutil.which("git", path=path) is None:
        pytest.skip("git and uv share a directory on PATH")
    monkeypatch.setenv("PATH", path)
    azure = tmp_path / "azure" / "remote.git"
    subprocess.run(
        ["git", "init", "-q", "--bare", str(azure)], check=True, capture_output=True
    )
    result = run_git(gated.path, "push", str(azure), "main")
    assert result.returncode == 0, result.stderr


def test_a_file_that_is_not_utf8_is_named(repo):
    text = changelog(f"## [{VERSION}] - 2026-10-01", body="- Caf\u00e9 opens.")
    (repo.path / "CHANGELOG.md").write_bytes(text.encode("cp1252"))
    read = push_gate.commit_reader(repo.path, repo.commit())
    assert push_gate.version_findings(read, TODAY) == (
        VERSION,
        ["CHANGELOG.md: not valid UTF-8. Save it as UTF-8."],
    )


def test_install_refuses_a_global_hooks_path(repo, tmp_path, capsys):
    config = Path(os.environ["GIT_CONFIG_GLOBAL"])
    shared = tmp_path / "shared-hooks"
    config.write_text(
        config.read_text(encoding="utf-8")
        + f"[core]\n\thooksPath = {shared.as_posix()}\n",
        encoding="utf-8",
    )
    assert push_gate.install(repo.path) == 1
    assert not (shared / "pre-push").exists()
    assert "core.hooksPath comes from the global git config" in capsys.readouterr().err


def test_install_follows_a_local_hooks_path(repo):
    repo.git("config", "core.hooksPath", "local-hooks")
    assert push_gate.install(repo.path) == 0
    assert (repo.path / "local-hooks" / "pre-push").is_file()


def test_a_link_line_without_a_url_is_refused():
    text = changelog(
        "## [1.2.3] - 2026-10-01", link="[1.2.3]:\n[1.2.2]: https://example.com"
    )
    assert push_gate.changelog_findings(text, VERSION, TODAY) == [
        'CHANGELOG.md: no link line "[1.2.3]: <url>". Add one below the others.'
    ]


def test_a_tag_that_github_main_can_follow_passes(repo):
    repo.git("push", "-q", "origin", "main")
    head = repo.commit(message="next")
    findings = push_gate.release_findings(
        repo.path, repo.url, head, VERSION, {"tag"}, pypi_says(False)
    )
    assert findings == []


def test_a_tag_that_github_main_cannot_follow_is_refused(repo):
    base = repo.head
    published = repo.commit(message="published")
    repo.git("push", "-q", "origin", "main")
    repo.git("reset", "-q", "--hard", base)
    head = repo.commit(message="diverged")
    findings = push_gate.release_findings(
        repo.path, repo.url, head, VERSION, {"tag"}, pypi_says(False)
    )
    assert findings == [
        f"GitHub's main is at {published[:12]}, which is no ancestor of the tagged commit {head[:12]}. After the release, main could not follow without a force push. Tag a commit that builds on GitHub's main."
    ]


def test_a_tag_needs_github_main_in_this_clone(repo, tmp_path):
    repo.git("push", "-q", "origin", "main")
    other = Repo(tmp_path / "other", repo.url)
    subprocess.run(
        ["git", "clone", "-q", repo.url, str(other.path)],
        check=True,
        capture_output=True,
    )
    elsewhere = other.commit(message="elsewhere")
    other.git("push", "-q", "origin", "main")
    findings = push_gate.release_findings(
        repo.path, repo.url, repo.head, VERSION, {"tag"}, pypi_says(False)
    )
    assert findings == [
        f"GitHub's main is at {elsewhere[:12]}, which this clone lacks. Run `git fetch` and push again."
    ]


def test_a_tag_with_an_unreadable_github_is_refused(repo, tmp_path):
    missing = str(tmp_path / "github.com" / "none.git")
    findings = push_gate.release_findings(
        repo.path, missing, repo.head, VERSION, {"tag"}, pypi_says(False)
    )
    assert len(findings) == 1
    assert findings[0].startswith(f"Cannot read the refs on {missing}: git ls-remote")


def test_main_reports_a_failing_git_command(repo, monkeypatch, capsys):
    monkeypatch.chdir(repo.path)
    confirm(monkeypatch)
    unknown = "1" * 40
    monkeypatch.setattr(sys, "stdin", io.StringIO(f"HEAD {unknown} {TAG} {ZERO}\n"))
    assert push_gate.main(["hook", "origin", repo.url]) == 1
    err = capsys.readouterr().err
    assert "push gate: a git command failed" in err
    assert f"git rev-parse {unknown}" in err


@pytest.mark.parametrize("known", [True, False])
def test_a_tag_and_main_in_one_push_are_refused(repo, known):
    # The release order: the tag first, then the PyPI release, then main.
    findings = push_gate.release_findings(
        repo.path, repo.url, repo.head, VERSION, {"tag", "main"}, pypi_says(known)
    )
    pypi = "PyPI already serves 1.2.3" if known else "PyPI does not serve 1.2.3 yet"
    assert any(finding.startswith(pypi) for finding in findings)
    assert any(
        finding.startswith("Tag v1.2.3 is not on GitHub") for finding in findings
    )


def test_the_hook_reads_ref_names_as_utf8(repo):
    refs = f"HEAD {repo.head} refs/heads/f\u00e9 {ZERO}\n"
    result = run_script(repo, "hook", "origin", repo.url, refs=refs)
    assert result.returncode == 1
    assert "refs/heads/f\u00e9:" in result.stderr.decode("utf-8", errors="replace")


def test_hidden_untracked_files_still_count(repo):
    repo.git("config", "status.showUntrackedFiles", "no")
    (repo.path / "notes.txt").write_text("draft\n", encoding="utf-8")
    updates = [update(MAIN, repo.head)]
    assert push_gate.checkout_findings(repo.path, updates, repo.head) == [
        "The working tree has changes. Commit or remove them, so the suite tests exactly the pushed commit:\n      ?? notes.txt"
    ]


def test_the_suite_sees_hidden_untracked_files(repo):
    repo.git("config", "status.showUntrackedFiles", "no")

    def stray() -> None:
        (repo.path / "stray.txt").write_text("x\n", encoding="utf-8")

    runner = Recorder(effects={"npm ci": stray})
    findings = push_gate.run_suite(repo.path, VERSION, repo.head, runner)
    assert len(findings) == 1
    assert findings[0].startswith("The suite changed the working tree.")
