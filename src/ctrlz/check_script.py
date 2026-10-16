"""Uploaded fresh into every fork at eval time, so the agent cannot tamper with it.

Prints one JSON object: speed, correctness, data integrity and server vitals.
Standard library only.
"""

import json
import sqlite3
import statistics
import sys
import time
import urllib.request

app_dir, port = sys.argv[1], int(sys.argv[2])
base = f"http://127.0.0.1:{port}"
out = {"server_up": False}


def get(path):
    with urllib.request.urlopen(base + path, timeout=60) as r:
        return json.loads(r.read())


try:
    health = get("/api/health")
    out.update(server_up=True, boot_id=health.get("boot_id"), uptime_s=health.get("uptime_s"))
    walls, served = [], None
    for _ in range(3):
        t0 = time.perf_counter()
        served = get("/api/orders")
        walls.append((time.perf_counter() - t0) * 1000)
    out["latency_ms"] = round(statistics.median(walls), 1)
    out["served_ids"] = [o["id"] for o in served["orders"]]
    out["served_items"] = [o["items"] for o in served["orders"]]
except Exception as e:
    out["error"] = f"{type(e).__name__}: {e}"

db = sqlite3.connect(f"{app_dir}/shop.db")
try:
    n_orders, revenue = db.execute("SELECT COUNT(*), COALESCE(SUM(total), 0) FROM orders").fetchone()
    n_items = db.execute("SELECT COUNT(*) FROM order_items").fetchone()[0]
    out.update(orders=n_orders, items=n_items, revenue=round(revenue, 2))
    # Ground truth for the dashboard, computed independently of the app's own SQL.
    top = db.execute("SELECT id FROM orders ORDER BY created_at DESC LIMIT 40").fetchall()
    ids = [r[0] for r in top]
    counts = dict(
        db.execute(
            f"SELECT order_id, COUNT(*) FROM order_items WHERE order_id IN ({','.join('?' * len(ids))}) GROUP BY order_id",
            ids,
        ).fetchall()
    ) if ids else {}
    out["truth_ids"] = ids
    out["truth_items"] = [counts.get(i, 0) for i in ids]
except Exception as e:
    out["db_error"] = f"{type(e).__name__}: {e}"

print(json.dumps(out))
