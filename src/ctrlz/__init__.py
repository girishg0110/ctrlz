"""Ctrl+Z command line.

  ctrlz init                     write a starter ctrlz.toml in the current folder
  ctrlz serve [ctrlz.toml]       dashboard at http://localhost:7860
  ctrlz run "task" [ctrlz.toml]  headless: fork, run agents, check, write patches, print a report
  ctrlz clean                    delete every Daytona sandbox Ctrl+Z created (label app=ctrlz)

Without a config path, ./ctrlz.toml is used if present, else the Acme Store example.
"""

import argparse
import os
import sys
from pathlib import Path

STARTER = """\
# Ctrl+Z project config. Docs: https://github.com/girishg0110/ctrlz
name = "My service"
checks_dir = "ctrlz-checks"     # scripts your [[check]] commands use

[source]
dir = "."                       # this folder is uploaded into the production sandbox
# git = "https://github.com/you/your-app"

[app]
setup = "pip install -r requirements.txt"
start = "nohup python3 app.py > app.log 2>&1 &"   # must listen on $APP_PORT
port = 8000
health = "/"
description = \"\"\"What the service is and how it is laid out, for the agents.\"\"\"

[diff]
ignore = ["*.log", "*.db"]

[agents]
task = "Describe the change you want."
max_turns = 10

[[agents.persona]]
name = "careful"
label = "Careful"
style = "Measure first, make the smallest change that works, then verify."

[[agents.persona]]
name = "bold"
label = "Bold"
style = "Prefer a thorough rewrite if it makes the code clearly better."

# Each check runs in production (baseline) and in every fork, from the app folder.
# Exit code 0 = pass. With `compare`, the JSON object printed on the last line is
# compared with production's: equal | no_decrease | no_increase | faster (factor = x).
[[check]]
name = "Tests"
command = "python3 -m pytest -q"

[[check]]
name = "Health"
command = "python3 -c \\"import os,urllib.request;urllib.request.urlopen('http://127.0.0.1:'+os.environ['APP_PORT']+'/')\\""
"""


def _resolve(path: str | None) -> str | None:
    if path:
        return str(Path(path).resolve())
    if Path("ctrlz.toml").exists():
        return str(Path("ctrlz.toml").resolve())
    return None


def _run(args) -> int:
    from . import web  # loads env, tracing and the config

    orc = web.orc
    try:
        orc.setup()
        s = orc.wait()
        if s["status"] == "error":
            print(s["events"][-1]["msg"])
            return 1
        orc.run(args.task or "")
        s = orc.wait()
        print()
        for n in s["nodes"].values():
            if not n.get("persona"):
                continue
            v = n.get("verdict") or {}
            mark = "KEEP   " if v.get("keep") else "DISCARD"
            print(f"{mark} {n['label']}{'  <- recommended' if n.get('recommended') else ''}")
            for g in v.get("gates", []):
                print(f"   {'pass' if g['pass'] else 'FAIL'}  {g['name']}: {g['detail']}")
            if v.get("judge"):
                print(f"   judge {v['judge']['verdict']} ({v['judge']['score']}): {v['judge']['explanation']}")
            if v.get("error"):
                print(f"   error: {v['error']}")
        run_id = s["runs"][-1]["id"]
        print(f"\npatches, commands and verdicts: {Path(os.environ.get('CTRLZ_OUT', '.ctrlz/runs')) / run_id}/")
        return 0 if s["runs"][-1]["winner"] else 2
    finally:
        if not args.keep:
            orc.teardown()


def main() -> None:
    ap = argparse.ArgumentParser(prog="ctrlz", description="Agents work on forks; production moves only to a fork that passes.")
    sub = ap.add_subparsers(dest="cmd")
    p_serve = sub.add_parser("serve", help="start the dashboard")
    p_serve.add_argument("config", nargs="?")
    p_run = sub.add_parser("run", help="one headless run")
    p_run.add_argument("task", nargs="?", help="defaults to agents.task in the config")
    p_run.add_argument("config", nargs="?")
    p_run.add_argument("--keep", action="store_true", help="keep the sandboxes afterwards")
    sub.add_parser("init", help="write a starter ctrlz.toml here")
    sub.add_parser("clean", help="delete every Daytona sandbox Ctrl+Z created")
    args = ap.parse_args()

    if args.cmd == "clean":
        from dotenv import load_dotenv
        from daytona import Daytona

        for f in (".env.local", ".env", Path(__file__).resolve().parents[2] / ".env.local"):
            load_dotenv(f)
        for sb in Daytona().list():
            if (sb.labels or {}).get("app") == "ctrlz":
                sb.delete()
                print("deleted", sb.name)
        return

    if args.cmd == "init":
        if Path("ctrlz.toml").exists():
            sys.exit("ctrlz.toml already exists")
        Path("ctrlz.toml").write_text(STARTER)
        Path("ctrlz-checks").mkdir(exist_ok=True)
        print("wrote ctrlz.toml; edit it, then: ctrlz run")
        return

    cfg = _resolve(getattr(args, "config", None))
    if cfg:
        os.environ["CTRLZ_CONFIG"] = cfg
    if args.cmd == "run":
        sys.exit(_run(args))

    from .web import main as serve

    serve()
