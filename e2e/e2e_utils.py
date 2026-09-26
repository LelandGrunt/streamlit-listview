# e2e/e2e_utils.py
import contextlib
import logging
import os
import socket
import subprocess
import sys
import time
import typing
from contextlib import closing
from tempfile import TemporaryFile

import requests

LOGGER = logging.getLogger(__file__)


def _find_free_port() -> int:
    """Find and return a free TCP port on localhost."""
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        # SO_REUSEADDR must be set BEFORE bind() to take effect; setting it after
        # bind was a no-op. It lets the discovered port be re-bound promptly
        # (avoiding a TIME_WAIT race) when Streamlit binds it right after this
        # probe socket closes.
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("", 0))
        return int(s.getsockname()[1])


class StreamlitRunner:
    """Context manager that runs a Streamlit script in a subprocess for e2e tests."""

    def __init__(
        self,
        script_path: os.PathLike,
        server_port: typing.Optional[int] = None,
        extra_args: typing.Optional[typing.List[str]] = None,
        startup_timeout: int = 60,
    ):
        self._proc = None
        self._stdout_file = None
        self.server_port = server_port
        self.script_path = script_path
        self.extra_args = list(extra_args or [])
        # How long start() waits for /_stcore/health. Overridable because the GIF
        # generator (scripts/gif/generate.py) shares this launcher but may be the
        # first run after a fresh install, when Streamlit still has to serve a
        # cold component bundle.
        self.startup_timeout = startup_timeout

    def __enter__(self) -> "StreamlitRunner":
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def start(self) -> None:
        self.server_port = self.server_port or _find_free_port()
        self._stdout_file = TemporaryFile("w+")
        args = [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(self.script_path),
            f"--server.port={self.server_port}",
            "--server.headless=true",
            "--browser.gatherUsageStats=false",
            "--global.developmentMode=false",
            *self.extra_args,
        ]
        LOGGER.info("Running: %s", " ".join(args))
        self._proc = subprocess.Popen(
            args,
            stdout=self._stdout_file,
            stderr=subprocess.STDOUT,
            text=True,
            env={**os.environ.copy()},
        )
        if not self._wait_until_running():
            output = self._read_output()
            self.stop()
            raise RuntimeError(
                f"Streamlit app failed to start.\n--- server output ---\n{output}"
            )

    def stop(self) -> None:
        """Stop the server and its whole process tree, then close the log file.

        Idempotent: safe to call twice, or when the process already exited (both
        ``__exit__`` and the failure path in ``start`` call it).

        ``streamlit run`` spawns a multi-process tree on Windows; terminating
        only the launcher orphans the rest, which keeps holding the port for the
        rest of the session and makes a later module's ``_find_free_port()``
        collide with a still-bound port. So on Windows we kill the tree with
        ``taskkill /T``, and on every platform a ``wait()`` timeout escalates to
        ``kill()`` instead of being swallowed with the handle dropped.
        """
        if self._proc is not None:
            if self._proc.poll() is None:
                try:
                    if os.name == "nt":
                        subprocess.run(
                            ["taskkill", "/F", "/T", "/PID", str(self._proc.pid)],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                    else:
                        self._proc.terminate()
                except OSError:
                    # e.g. taskkill missing from PATH — degrade to a direct kill
                    # rather than propagating out of a teardown path.
                    self._proc.kill()
                try:
                    self._proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self._proc.kill()
                    with contextlib.suppress(subprocess.TimeoutExpired):
                        self._proc.wait(timeout=5)
            else:
                self._proc.wait()  # reap the already-exited child
            self._proc = None
        if self._stdout_file is not None:
            self._stdout_file.close()
            self._stdout_file = None

    def _read_output(self) -> str:
        if self._stdout_file is None:
            return ""
        self._stdout_file.seek(0)
        return self._stdout_file.read()

    def _wait_until_running(self) -> bool:
        start = time.time()
        with requests.Session() as session:
            while time.time() - start < self.startup_timeout:
                if self._proc is not None and self._proc.poll() is not None:
                    return False  # process already exited
                with contextlib.suppress(requests.RequestException):
                    resp = session.get(self.server_url + "/_stcore/health", timeout=2)
                    if resp.text == "ok":
                        return True
                # 0.2s, not 1s: a coarse poll overshot readiness by ~0.5s per
                # boot on average; the wait is bounded by startup_timeout and
                # the per-request timeout above, not by this granularity.
                time.sleep(0.2)
        return False

    @property
    def server_url(self) -> str:
        if not self.server_port:
            raise RuntimeError("Unknown server port")
        return f"http://localhost:{self.server_port}"
