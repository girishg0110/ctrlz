"""Records a real Ctrl+Z run in the dashboard (running on localhost:7861, production already set up).

Drives the browser through the demo and writes:
  video/raw/run.webm         the screen recording
  video/src/markers.json     seconds-into-recording for each beat, used to cut scenes

Usage: uv run python video/tools/record.py
"""

import json
import shutil
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "video" / "raw"
URL = "http://localhost:7861"
TASK = "The orders page is slow. Fix it."


def state() -> dict:
    with urllib.request.urlopen(f"{URL}/api/state", timeout=10) as r:
        return json.loads(r.read())


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    s0 = state()
    assert s0["main"] and not s0["busy"], "set up production in the dashboard first"
    markers: dict[str, float] = {}

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(
            viewport={"width": 1440, "height": 810}, device_scale_factor=2,
            record_video_dir=str(RAW / "tmp"), record_video_size={"width": 1920, "height": 1080},
        )
        page = ctx.new_page()
        t0 = time.time()
        mark = lambda k: markers.__setitem__(k, round(time.time() - t0, 2)) or print(f"{markers[k]:7.2f}  {k}", flush=True)

        page.goto(URL)
        page.wait_for_selector("#frame", state="visible")
        mark("dashboard")
        time.sleep(9)  # the slow store renders and refreshes once

        box = page.locator("#task")
        box.fill("")
        mark("typing")
        box.type(TASK, delay=55)
        time.sleep(0.8)
        mark("fork_click")
        page.click("#runBtn")

        seen, careful_selected = set(), False
        while True:
            s = state()
            nodes = {n["id"]: n for n in s["nodes"].values() if n.get("run_id")}
            for nid, n in nodes.items():
                key = f"{n['persona']}_{n['status']}"
                if key not in seen:
                    seen.add(key)
                    mark(key)
            if not careful_selected and any(n["status"] == "running" for n in nodes.values()):
                careful = next(n for n in nodes.values() if n["persona"] == "careful")
                page.click(f'g.node[data-id="{careful["id"]}"]')
                careful_selected = True
                mark("careful_selected")
            agg = next((n for n in nodes.values() if n["persona"] == "aggressive"), None)
            if agg and agg["status"] == "fail" and "aggressive_clicked" not in markers:
                time.sleep(1.5)
                page.click(f'g.node[data-id="{agg["id"]}"]')
                mark("aggressive_clicked")
                time.sleep(9)  # the broken store loads in the left panel
                page.click("#backBtn")
                mark("back_to_production")
                time.sleep(7)
                page.click(f'g.node[data-id="{careful["id"]}"]')
                mark("careful_reselected")
            if s["status"] == "review" and not s["busy"]:
                mark("review")
                break
            time.sleep(0.5)

        time.sleep(3)
        winner = s["runs"][-1]["winner"]
        page.click(f'g.node[data-id="{winner}"]')
        mark("winner_selected")
        time.sleep(4)
        page.get_by_text("Promote to production").click()
        mark("promote_click")
        while state()["main"] != winner or state()["busy"]:
            time.sleep(0.5)
        mark("promoted")
        time.sleep(10)  # the fast store renders in the left panel
        mark("end")
        video = page.video.path()
        ctx.close()
        browser.close()

    shutil.move(video, RAW / "run.webm")
    shutil.rmtree(RAW / "tmp", ignore_errors=True)
    final = state()
    (ROOT / "video" / "src" / "markers.json").write_text(json.dumps({
        "markers": markers,
        "baseline_before": s0["baseline"],
        "baseline_after": final["baseline"],
        "verdicts": {n["persona"]: {"status": n["status"], "gates": (n.get("verdict") or {}).get("gates"),
                                    "judge": (n.get("verdict") or {}).get("judge")}
                     for n in final["nodes"].values() if n.get("persona") and n.get("run_id") == s["runs"][-1]["id"]},
    }, indent=1))
    print("saved", RAW / "run.webm")


if __name__ == "__main__":
    main()
