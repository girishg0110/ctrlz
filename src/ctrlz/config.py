"""Project config: what production is, how to run it, what must not break.

A project is described by a ctrlz.toml (see examples/acme-store/ctrlz.toml). Relative
paths in it resolve against the file's own folder.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "examples" / "acme-store" / "ctrlz.toml"


@dataclass
class Persona:
    name: str
    label: str
    style: str
    script: list[str] = field(default_factory=list)  # fixed commands for CTRLZ_AGENT=scripted
    scripted: bool = False  # always replay `script` (a deliberate chaos agent to prove the checks work)


@dataclass
class Check:
    name: str
    command: str
    compare: str = "exit"  # exit | equal | no_decrease | no_increase | faster
    factor: float = 1.0  # for "faster": baseline / value must be >= factor
    headline: bool = False  # show this check's metric on tree nodes


@dataclass
class Config:
    path: Path
    name: str
    description: str
    source_dir: Path | None
    git_url: str | None
    git_branch: str | None
    setup: str
    start: str
    port: int
    health: str
    diff_ignore: list[str]
    task: str
    max_turns: int
    personas: list[Persona]
    checks_dir: Path | None
    checks: list[Check]

    @property
    def headline(self) -> Check | None:
        return next((c for c in self.checks if c.headline), None)


def load(path: str | os.PathLike | None = None) -> Config:
    path = Path(path or os.environ.get("CTRLZ_CONFIG") or DEFAULT_CONFIG).resolve()
    raw = tomllib.loads(path.read_text())
    base = path.parent
    src, app, agents = raw.get("source", {}), raw["app"], raw.get("agents", {})
    rel = lambda p: (base / p).resolve() if p else None
    personas = [Persona(**p) for p in agents.get("persona", [])]
    if not personas:
        raise ValueError(f"{path}: define at least one [[agents.persona]]")
    checks = [Check(**c) for c in raw.get("check", [])]
    if not checks:
        raise ValueError(f"{path}: define at least one [[check]]")
    for c in checks:
        if c.compare not in ("exit", "equal", "no_decrease", "no_increase", "faster"):
            raise ValueError(f"check '{c.name}': unknown compare '{c.compare}'")
    if not (src.get("dir") or src.get("git")):
        raise ValueError(f"{path}: [source] needs dir or git")
    return Config(
        path=path,
        name=raw.get("name", base.name),
        description=app.get("description", "").strip(),
        source_dir=rel(src.get("dir")),
        git_url=src.get("git"),
        git_branch=src.get("branch"),
        setup=app.get("setup", ""),
        start=app["start"],
        port=int(app.get("port", 8000)),
        health=app.get("health", "/"),
        diff_ignore=list(raw.get("diff", {}).get("ignore", [])),
        task=agents.get("task", ""),
        max_turns=int(os.environ.get("CTRLZ_MAX_TURNS", agents.get("max_turns", 10))),
        personas=personas,
        checks_dir=rel(raw.get("checks_dir")),
        checks=checks,
    )
