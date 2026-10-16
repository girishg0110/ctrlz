"""Sandbox backends. A Box is somewhere an agent can run shell commands, that can be forked.

DaytonaBox  - a Daytona sandbox. On Linux VM sandboxes fork() copies disk *and* memory,
              so running processes carry on in the child. Container sandboxes fall back
              to copying the app folder into fresh sandboxes and restarting the app.
LocalBox    - a temp directory plus a local process group, for offline work.

What runs inside a box (source, setup, start command, port, health check) comes from
the project config (see config.py).
"""

from __future__ import annotations

import io
import os
import shutil
import signal
import socket
import subprocess
import tarfile
import tempfile
import threading
import time
import urllib.request
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from .config import Config

SHARE_PORT = 8001
SHARE_DIR = "/tmp/ctrlz-share"
GIT = "git -c user.email=ctrlz@localhost -c user.name=ctrlz"

_WARM: dict[str, list] = {}
_WARM_PENDING: dict[str, int] = {}
_WARM_LOCK = threading.Lock()


def _take_warm(snapshot: str, wait: float = 90):
    """A pre-created sandbox, waiting for one still being created rather than making a
    new one (which could exceed the org's CPU quota)."""
    deadline = time.time() + wait
    while True:
        with _WARM_LOCK:
            pool = _WARM.get(snapshot) or []
            if pool:
                return pool.pop()
            if not _WARM_PENDING.get(snapshot) or time.time() > deadline:
                return None
        time.sleep(0.5)


def _tar_dir(path: Path) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for p in sorted(path.rglob("*")):
            rel = p.relative_to(path)
            if any(part in ("__pycache__", ".venv", "node_modules") for part in rel.parts):
                continue
            tar.add(p, arcname=str(rel), recursive=False)
    return buf.getvalue()


@dataclass
class ExecResult:
    exit_code: int
    output: str


class Box:
    cfg: Config
    name: str
    app_dir: str
    port: int

    native_fork: bool = False

    def exec(self, command: str, timeout: int = 120) -> ExecResult: ...
    def fork(self, name: str) -> "Box": ...
    def upload(self, content: bytes, remote_path: str) -> None: ...
    def preview(self) -> tuple[str, dict[str, str]]:
        """Base URL for the app, plus headers needed to reach it."""
        ...
    def delete(self) -> None: ...

    def fork_many(self, names: list[str]) -> list["Box"]:
        return [self.fork(n) for n in names]

    @property
    def sandbox_id(self) -> str:
        return self.name

    def start_app(self) -> None:
        self.exec(self.cfg.start, timeout=60)
        self.wait_healthy()

    def boot_app(self) -> None:
        """Run setup, start the app, and commit a git baseline so forks can be diffed."""
        if self.cfg.setup:
            r = self.exec(self.cfg.setup, timeout=900)
            if r.exit_code != 0:
                raise RuntimeError(f"setup failed: {r.output[-2000:]}")
        self.start_app()
        ignore = "\n".join(self.cfg.diff_ignore + ["*.log"])
        self.exec(
            f"(test -d .git || git init -q) && mkdir -p .git/info && printf '%s\\n' '{ignore}' >> .git/info/exclude "
            f"&& {GIT} add -A && {GIT} commit -qm 'ctrlz baseline' --allow-empty",
            timeout=300,
        )

    def diff(self) -> str:
        """Code changes since production's baseline (data files excluded via diff.ignore)."""
        r = self.exec(f"{GIT} add -A >/dev/null 2>&1; git diff --cached --stat; echo; git diff --cached", timeout=120)
        return r.output.strip() + "\n" if r.exit_code == 0 and r.output.strip() else ""

    def wait_healthy(self, timeout: float = 90) -> None:
        url = f"http://127.0.0.1:{self.port}{self.cfg.health}"
        deadline = time.time() + timeout
        while time.time() < deadline:
            r = self.exec(f"python3 -c \"import urllib.request;urllib.request.urlopen('{url}',timeout=5)\"", timeout=30)
            if r.exit_code == 0:
                return
            time.sleep(1)
        raise RuntimeError(f"app did not answer on {self.cfg.health} within {timeout:.0f}s")


# --------------------------------------------------------------------------- Daytona


@dataclass
class DaytonaBox(Box):
    cfg: Config = None
    sandbox: object = None
    name: str = ""
    app_dir: str = ""
    port: int = 8000
    snapshot: str = ""
    _preview: tuple[str, dict[str, str]] | None = field(default=None, repr=False)

    @classmethod
    def create(cls, cfg: Config, snapshot: str, name: str, with_source: bool = True) -> "DaytonaBox":
        from daytona import CreateSandboxFromSnapshotParams, Daytona

        sb = Daytona().create(
            CreateSandboxFromSnapshotParams(snapshot=snapshot, name=name, labels={"app": "ctrlz"}, auto_stop_interval=120),
            timeout=300,
        )
        home = sb.process.exec("echo $HOME").result.strip() or "/root"
        box = cls(cfg=cfg, sandbox=sb, name=name, app_dir=f"{home}/app", port=cfg.port, snapshot=snapshot)
        if with_source:
            box._fetch_source()
        else:
            sb.process.exec(f"mkdir -p {box.app_dir}")
        return box

    def _fetch_source(self) -> None:
        if self.cfg.git_url:
            self.sandbox.git.clone(self.cfg.git_url, self.app_dir, branch=self.cfg.git_branch)
            return
        self.sandbox.process.exec(f"mkdir -p {self.app_dir}")
        self.upload(_tar_dir(self.cfg.source_dir), "/tmp/ctrlz-src.tgz")
        self.exec(f"tar xzf /tmp/ctrlz-src.tgz -C {self.app_dir}", timeout=300)

    @property
    def sandbox_id(self) -> str:
        return self.sandbox.id

    def exec(self, command: str, timeout: int = 120) -> ExecResult:
        try:
            r = self.sandbox.process.exec(command, cwd=self.app_dir, env={"APP_PORT": str(self.port)}, timeout=timeout)
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
                DaytonaBox(cfg=self.cfg, sandbox=self.sandbox.fork(name=n, timeout=120), name=n,
                           app_dir=self.app_dir, port=self.port, snapshot=self.snapshot)
                for n in names
            ]
        return self._copy_fork_many(names)

    def _copy_fork_many(self, names: list[str]) -> list["DaytonaBox"]:
        """Fallback for container sandboxes, which cannot fork: copy the app folder
        into fresh sandboxes and restart the app there. No memory is carried over."""
        from concurrent.futures import ThreadPoolExecutor

        archive = "/tmp/ctrlz-state.tgz"
        # The parent serves its state archive on SHARE_PORT so children can pull it over
        # Daytona's network instead of round-tripping through this machine.
        r = self.exec(
            f"mkdir -p {SHARE_DIR} && tar czf {SHARE_DIR}/state.tgz -C {self.app_dir} --exclude='*.log' . && "
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
            child = _take_warm(self.snapshot) or DaytonaBox.create(self.cfg, self.snapshot, name, with_source=False)
            child.name, child.cfg, child.port = name, self.cfg, self.port
            if child.exec(fetch, timeout=180).exit_code != 0:
                with lock:  # sandbox network is restricted: fall back to relaying through here
                    if not local_copy:
                        local_copy.append(self.sandbox.fs.download_file(f"{SHARE_DIR}/state.tgz"))
                child.upload(local_copy[0], archive)
            child.exec(f"mkdir -p {child.app_dir} && tar xzf {archive} -C {child.app_dir}", timeout=300)
            child.start_app()
            return child

        with ThreadPoolExecutor(len(names)) as pool:
            return list(pool.map(make, names))

    @staticmethod
    def prewarm(cfg: Config, snapshot: str, n: int) -> None:
        """Create empty sandboxes ahead of time so a copy-fork skips provisioning."""
        def one(_):
            try:
                box = DaytonaBox.create(cfg, snapshot, f"ctrlz-warm-{uuid.uuid4().hex[:6]}", with_source=False)
                with _WARM_LOCK:
                    _WARM.setdefault(snapshot, []).append(box)
            except Exception as e:
                print(f"[ctrlz] prewarm failed: {e}")
            finally:
                with _WARM_LOCK:
                    _WARM_PENDING[snapshot] -= 1

        with _WARM_LOCK:
            missing = n - len(_WARM.get(snapshot, [])) - _WARM_PENDING.get(snapshot, 0)
            _WARM_PENDING[snapshot] = _WARM_PENDING.get(snapshot, 0) + max(0, missing)
        for i in range(max(0, missing)):
            threading.Thread(target=one, args=(i,), daemon=True).start()

    @staticmethod
    def drain_warm() -> None:
        deadline = time.time() + 60  # let in-flight creations land so they get deleted too
        while any(_WARM_PENDING.values()) and time.time() < deadline:
            time.sleep(0.5)
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
    cfg: Config = None
    name: str = ""
    app_dir: str = ""
    port: int = 0
    pgids: list[int] = field(default_factory=list, repr=False)

    @classmethod
    def create(cls, cfg: Config, name: str) -> "LocalBox":
        root = Path(tempfile.mkdtemp(prefix=f"ctrlz-{name}-"))
        if cfg.git_url:
            subprocess.run(["git", "clone", "-q", *(["-b", cfg.git_branch] if cfg.git_branch else []), cfg.git_url, str(root / "app")], check=True)
        else:
            shutil.copytree(cfg.source_dir, root / "app", ignore=shutil.ignore_patterns("__pycache__", ".venv", "node_modules"))
        return cls(cfg=cfg, name=name, app_dir=str(root / "app"), port=_free_port())

    def _env(self) -> dict[str, str]:
        return {**os.environ, "APP_PORT": str(self.port)}

    def start_app(self) -> None:
        # Own process group, so delete() stops whatever the start command spawned.
        p = subprocess.Popen(["bash", "-c", self.cfg.start], cwd=self.app_dir, env=self._env(),
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        self.pgids.append(p.pid)
        self.wait_healthy()

    def exec(self, command: str, timeout: int = 120) -> ExecResult:
        try:
            p = subprocess.run(["bash", "-c", command], cwd=self.app_dir, capture_output=True, text=True,
                               timeout=timeout, env=self._env())
            return ExecResult(p.returncode, p.stdout + p.stderr)
        except subprocess.TimeoutExpired:
            return ExecResult(124, f"[ctrlz] command timed out after {timeout}s")

    def fork(self, name: str) -> "LocalBox":
        root = Path(tempfile.mkdtemp(prefix=f"ctrlz-{name}-"))
        shutil.copytree(self.app_dir, root / "app", ignore=shutil.ignore_patterns("*.log"))
        child = LocalBox(cfg=self.cfg, name=name, app_dir=str(root / "app"), port=_free_port())
        child.start_app()
        return child

    def upload(self, content: bytes, remote_path: str) -> None:
        Path(remote_path).parent.mkdir(parents=True, exist_ok=True)
        Path(remote_path).write_bytes(content)

    def preview(self) -> tuple[str, dict[str, str]]:
        return f"http://127.0.0.1:{self.port}", {}

    def delete(self) -> None:
        for pgid in self.pgids:
            try:
                os.killpg(pgid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                pass
        shutil.rmtree(Path(self.app_dir).parent, ignore_errors=True)


def http_get(url: str, headers: dict[str, str], timeout: float = 30) -> tuple[int, bytes, str]:
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(), r.headers.get("Content-Type", "text/html")
    except urllib.error.HTTPError as e:
        return e.code, e.read(), e.headers.get("Content-Type", "text/plain")
