"""Headless end-to-end run: production sandbox -> fork x3 -> agents -> evals. Prints progress."""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from ctrlz import web  # noqa: E402  (loads .env.local and sets up Arize)

orc = web.orc
seen = 0


def wait(*done):
    global seen
    while True:
        s = orc.snapshot()
        for e in s["events"][seen:]:
            print(time.strftime("%H:%M:%S"), e["msg"], flush=True)
        seen = len(s["events"])
        for n in s["nodes"].values():
            for l in n["log"][n.get("_seen", 0):]:
                pass
        if not orc.busy and s["status"] in done + ("error",):
            return s
        time.sleep(1)


orc.setup()
wait("ready")
time.sleep(20)  # in the real demo setup happens well before; let the warm pool fill
t_run = time.time()
orc.run(sys.argv[1] if len(sys.argv) > 1 else "The orders page is slow. Fix it.")
s = wait("review")
print(f"run took {time.time() - t_run:.0f}s")
for n in s["nodes"].values():
    if n.get("persona"):
        v = n.get("verdict") or {}
        print(f"\n== {n['label']}: {n['status']}  ({len(n['log'])} log lines)")
        for l in n["log"]:
            if l["kind"] in ("cmd", "text"):
                print(f"  [{l['kind']}] {l['text'][:220]}")
        for k, g in (v.get("gates") or {}).items():
            if isinstance(g, dict):
                print(f"  {k}: {g['pass']} - {g['detail']}")
        if v.get("judge"):
            print(f"  judge: {v['judge']['verdict']} - {v['judge']['risk']}")
if "--keep" not in sys.argv:
    orc.teardown()
    print("sandboxes deleted")
