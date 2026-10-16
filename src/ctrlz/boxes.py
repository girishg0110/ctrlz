"""Sandbox backends. A Box is somewhere an agent can run shell commands, that can be forked.

DaytonaBox  - a Daytona Linux VM sandbox. fork() copies disk *and* memory, so
              running processes (the store's web server) carry on in the child.
LocalBox    - a temp directory plus a local server process, for offline UI work.
              fork() copies files only and boots a fresh server.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import urllib.request
import uuid
from dataclasses import dataclass, field
from pathlib import Path

DEMO_APP = Path(__file__).resolve().parents[2] / "demo_app"
APP_PORT = 8000
SHARE_PORT = 8001
SHARE_DIR = "/tmp/ctrlz-share"

_WARM: dict[str, list] = {}
_WARM_LOCK = threading.Lock()


def _take_warm(snapshot: str):
    with _WARM_LOCK:
        pool = _WARM.get(snapshot) or []
        return pool.pop() if pool else None


@dataclass
class ExecResult:
    exit_code: int
    output: str


class Box:
    name: str
    app_dir: str
    port: int = APP_PORT

    native_fork: bool = False

    def exec(self, command: str, timeout: int = 120) -> ExecResult: ...
    def fork(self, name: str) -> "Box": ...

    def fork_many(self, names: list[str]) -> list["Box"]:
        return [self.fork(n) for n in names]
    def upload(self, content: bytes, remote_path: str) -> None: ...
    def preview(self) -> tuple[str, dict[str, str]]:
        """Base URL for the store app, plus headers needed to reach it."""
        ...
    def delete(self) -> None: ...

    @property
    def sandbox_id(self) -> str:
        return self.name

    def boot_app(self) -> None:
        """Seed the database and start the store server in the background."""
        r = self.exec("python3 seed.py shop.db", timeout=600)
        if r.exit_code != 0:
            raise RuntimeError(f"seed failed: {r.output}")
        self.exec(f"APP_PORT={self.port} nohup python3 server.py > server.log 2>&1 &")
        self.wait_healthy()

    def wait_healthy(self, timeout: float = 60) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            r = self.exec(
                f"python3 -c \"import urllib.request;print(urllib.request.urlopen('http://127.0.0.1:{self.port}/api/health',timeout=5).read().decode())\"",
                timeout=30,
            )
            if r.exit_code == 0 and "boot_id" in r.output:
                return
            time.sleep(1)
        raise RuntimeError("store server did not become healthy")


# --------------------------------------------------------------------------- Daytona


@dataclass
class DaytonaBox(Box):
    sandbox: object = None
    name: str = ""
    app_dir: str = ""
    port: int = APP_PORT
    snapshot: str = ""
    _preview: tuple[str, dict[str, str]] | None = field(default=None, repr=False)

    @classmethod
    def create(cls, snapshot: str, name: str, upload_app: bool = True) -> "DaytonaBox":
        from daytona import CreateSandboxFromSnapshotParams, Daytona

        daytona = Daytona()
        sb = daytona.create(
            CreateSandboxFromSnapshotParams(
                snapshot=snapshot,
                name=name,
                labels={"app": "ctrlz"},
                auto_stop_interval=120,
            ),
            timeout=300,
        )
        home = sb.process.exec("echo $HOME").result.strip() or "/root"
        box = cls(sandbox=sb, name=name, app_dir=f"{home}/app", snapshot=snapshot)
        sb.process.exec(f"mkdir -p {box.app_dir}")
        if upload_app:
            for f in ("server.py", "seed.py"):
                box.upload((DEMO_APP / f).read_bytes(), f"{box.app_dir}/{f}")
        return box

    @property
    def sandbox_id(self) -> str:
        return self.sandbox.id

    def exec(self, command: str, timeout: int = 120) -> ExecResult:
        try:
            r = self.sandbox.process.exec(command, cwd=self.app_dir, timeout=timeout)
            return ExecResult(int(r.exit_code or 0), r.result or "")
        except Exception as e:  # timeouts and transport errors become tool errors
            return ExecResult(124, f"[ctrlz] command failed: {e}")

    @property
    def native_fork(self) -> bool:
        return str(getattr(self.sandbox, "sandbox_class", "") or "").lower().replace("_", "-").endswith("linux-vm")

    def fork(self, name: str) -> "DaytonaBox":
        return self.fork_many([name])[0]

    def fork_many(self, names: list[str]) -> list["DaytonaBox"]:
        if self.native_fork:
            # A parent serves one fork at a time, so native forks go sequentially (~1s each).
            return [
                DaytonaBox(sandbox=self.sandbox.fork(name=n, timeout=120), name=n,
                           app_dir=self.app_dir, port=self.port, snapshot=self.snapshot)
                for n in names
            ]
        return self._copy_fork_many(names)

    def _copy_fork_many(self, names: list[str]) -> list["DaytonaBox"]:
        """Fallback for container sandboxes, which cannot fork: copy the app's files
        into fresh sandboxes and restart the server there. No memory is carried over."""
        from concurrent.futures import ThreadPoolExecutor

        archive = "/tmp/ctrlz-state.tgz"
        # The parent serves its state archive on SHARE_PORT so children can pull it over
        # Daytona's network instead of round-tripping through this machine.
        r = self.exec(
            f"mkdir -p {SHARE_DIR} && tar czf {SHARE_DIR}/state.tgz -C {self.app_dir} --exclude=server.log . && "
            f"(pgrep -f 'http.server {SHARE_PORT}' >/dev/null || "
            f"(cd {SHARE_DIR} && nohup python3 -m http.server {SHARE_PORT} > /tmp/ctrlz-share.log 2>&1 &))",
            timeout=300,
        )
        if r.exit_code != 0:
            raise RuntimeError(f"state archive failed: {r.output}")
        share = self.sandbox.get_preview_link(SHARE_PORT)
        fetch = (
            "python3 -c \"import urllib.request as u; "
            f"r=u.Request('{share.url.rstrip('/')}/state.tgz', headers={{'X-Daytona-Preview-Token': '{share.token or ''}', "
            "'X-Daytona-Skip-Preview-Warning': 'true'}); "
            f"open('{archive}','wb').write(u.urlopen(r, timeout=120).read())\""
        )
        local_copy: list[bytes] = []
        lock = threading.Lock()

        def make(name: str) -> "DaytonaBox":
            child = _take_warm(self.snapshot) or DaytonaBox.create(self.snapshot, name, upload_app=False)
            child.name = name
            if child.exec(fetch, timeout=180).exit_code != 0:
                with lock:  # sandbox network is restricted: fall back to relaying through here
                    if not local_copy:
                        local_copy.append(self.sandbox.fs.download_file(f"{SHARE_DIR}/state.tgz"))
                child.upload(local_copy[0], archive)
            child.exec(f"mkdir -p {child.app_dir} && tar xzf {archive} -C {child.app_dir}", timeout=300)
            child.exec(f"APP_PORT={child.port} nohup python3 server.py > server.log 2>&1 &")
            child.wait_healthy()
            return child

        with ThreadPoolExecutor(len(names)) as pool:
            return list(pool.map(make, names))

    @staticmethod
    def prewarm(snapshot: str, n: int) -> None:
        """Create empty sandboxes ahead of time so a copy-fork skips provisioning."""
        def one(_):
            try:
                box = DaytonaBox.create(snapshot, f"ctrlz-warm-{uuid.uuid4().hex[:6]}", upload_app=False)
                with _WARM_LOCK:
                    _WARM.setdefault(snapshot, []).append(box)
            except Exception as e:
                print(f"[ctrlz] prewarm failed: {e}")

        missing = n - len(_WARM.get(snapshot, []))
        for i in range(max(0, missing)):
            threading.Thread(target=one, args=(i,), daemon=True).start()

    @staticmethod
    def drain_warm() -> None:
        with _WARM_LOCK:
            boxes = [b for bs in _WARM.values() for b in bs]
            _WARM.clear()
        for b in boxes:
            try:
                b.delete()
            except Exception:
                pass

    def upload(self, content: bytes, remote_path: str) -> None:
        self.sandbox.fs.upload_file(content, remote_path)

    def preview(self) -> tuple[str, dict[str, str]]:
        if self._preview is None:
            link = self.sandbox.get_preview_link(self.port)
            self._preview = (
                link.url.rstrip("/"),
                {"X-Daytona-Preview-Token": link.token or "", "X-Daytona-Skip-Preview-Warning": "true"},
            )
        return self._preview

    def delete(self) -> None:
        self.sandbox.delete()


# --------------------------------------------------------------------------- Local


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@dataclass
class LocalBox(Box):
    name: str = ""
    app_dir: str = ""
    port: int = 0
    proc: subprocess.Popen | None = field(default=None, repr=False)

    @classmethod
    def create(cls, name: str) -> "LocalBox":
        root = Path(tempfile.mkdtemp(prefix=f"ctrlz-{name}-"))
        shutil.copytree(DEMO_APP, root / "app")
        return cls(name=name, app_dir=str(root / "app"), port=_free_port())

    def boot_app(self) -> None:
        r = self.exec("python3 seed.py shop.db", timeout=600)
        if r.exit_code != 0:
            raise RuntimeError(f"seed failed: {r.output}")
        self._start_server()

    def _start_server(self) -> None:
        log = open(Path(self.app_dir) / "server.log", "w")
        self.proc = subprocess.Popen(
            ["python3", "server.py"], cwd=self.app_dir, stdout=log, stderr=log,
            env={**os.environ, "APP_PORT": str(self.port)},
        )
        self.wait_healthy()

    def exec(self, command: str, timeout: int = 120) -> ExecResult:
        try:
            p = subprocess.run(
                ["bash", "-c", command], cwd=self.app_dir, capture_output=True, text=True,
                timeout=timeout, env={**os.environ, "APP_PORT": str(self.port)},
            )
            return ExecResult(p.returncode, p.stdout + p.stderr)
        except subprocess.TimeoutExpired:
            return ExecResult(124, f"[ctrlz] command timed out after {timeout}s")

    def fork(self, name: str) -> "LocalBox":
        root = Path(tempfile.mkdtemp(prefix=f"ctrlz-{name}-"))
        shutil.copytree(self.app_dir, root / "app", ignore=shutil.ignore_patterns("server.log"))
        child = LocalBox(name=name, app_dir=str(root / "app"), port=_free_port())
        child._start_server()
        return child

    def upload(self, content: bytes, remote_path: str) -> None:
        Path(remote_path).parent.mkdir(parents=True, exist_ok=True)
        Path(remote_path).write_bytes(content)

    def preview(self) -> tuple[str, dict[str, str]]:
        return f"http://127.0.0.1:{self.port}", {}

    def delete(self) -> None:
        if self.proc:
            self.proc.terminate()
        shutil.rmtree(Path(self.app_dir).parent, ignore_errors=True)


def http_get(url: str, headers: dict[str, str], timeout: float = 30) -> tuple[int, bytes, str]:
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(), r.headers.get("Content-Type", "text/html")
    except urllib.error.HTTPError as e:
        return e.code, e.read(), e.headers.get("Content-Type", "text/plain")
