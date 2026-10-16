"""Exit 0 if the dashboard API shows the right 40 orders with the right item counts."""
import json
import os
import sqlite3
import sys
import urllib.request

port = os.environ.get("APP_PORT", "8000")
try:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/orders", timeout=60) as r:
        served = json.loads(r.read())["orders"]
except Exception as e:
    print(json.dumps({"detail": f"server not answering: {type(e).__name__}: {e}"}))
    sys.exit(1)

# Ground truth, computed independently of the app's own SQL.
db = sqlite3.connect("shop.db")
ids = [r[0] for r in db.execute("SELECT id FROM orders ORDER BY created_at DESC LIMIT 40")]
marks = ",".join("?" * len(ids))
counts = dict(db.execute(f"SELECT order_id, COUNT(*) FROM order_items WHERE order_id IN ({marks}) GROUP BY order_id", ids))
ok = [o["id"] for o in served] == ids and [o["items"] for o in served] == [counts.get(i, 0) for i in ids]
print(json.dumps({"detail": "dashboard matches ground truth" if ok else "dashboard rows differ from ground truth"}))
sys.exit(0 if ok else 1)
