"""Smoke test: can this Daytona account create a Linux VM sandbox and fork it with memory?"""

import os
import sys
import time

from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
load_dotenv(".env.local")
load_dotenv(".env")

from ctrlz.boxes import DaytonaBox  # noqa: E402
from ctrlz.config import load  # noqa: E402

cfg = load(sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else None)

snapshot = os.environ.get("CTRLZ_SNAPSHOT", "daytona-small")
t = time.time()
parent = DaytonaBox.create(cfg, snapshot, f"ctrlz-smoke-{int(t)}")
print(f"created {parent.sandbox_id} in {time.time() - t:.1f}s, app_dir={parent.app_dir}")
print(parent.exec("python3 --version; uname -a; nproc; free -m | head -2").output)

t = time.time()
parent.boot_app()
print(f"seeded + booted in {time.time() - t:.1f}s")
print("parent healthy on", cfg.health)

t = time.time()
child = parent.fork(f"ctrlz-smoke-fork-{int(t)}")
print(f"forked {child.sandbox_id} in {time.time() - t:.2f}s")
child.wait_healthy()
print("child healthy; native fork (disk + memory):", parent.native_fork)

url, headers = child.preview()
from ctrlz.boxes import http_get  # noqa: E402

code, body, ctype = http_get(url + cfg.health, headers)
print("preview via proxy headers:", code, body[:200])

if "--keep" not in sys.argv:
    child.delete()
    time.sleep(3)
    parent.delete()
    print("cleaned up")
