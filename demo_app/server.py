"""Acme Store admin dashboard. Standard library only.

GET /            HTML dashboard (latest orders + server vitals)
GET /api/orders  latest orders with item counts, as JSON
GET /api/health  process vitals: boot id, pid, uptime, requests served

The boot id and request counter live in process memory. If they survive a
Daytona fork, the fork copied a *running* server, not just its files.
"""

import html
import json
import os
import sqlite3
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shop.db")
PORT = int(os.environ.get("APP_PORT", 8000))
BOOT_ID = uuid.uuid4().hex[:8]
STARTED = time.time()
REQUESTS = 0
LATEST_N = 40

LATEST_ORDERS_SQL = """
SELECT o.id, c.name, o.created_at, o.status, o.total,
       (SELECT COUNT(*) FROM order_items i WHERE i.order_id = o.id) AS items
FROM (SELECT * FROM orders ORDER BY created_at DESC LIMIT ?) o
JOIN customers c ON c.id = o.customer_id
ORDER BY o.created_at DESC
"""


def latest_orders():
    db = sqlite3.connect(DB_PATH)
    t0 = time.perf_counter()
    rows = db.execute(LATEST_ORDERS_SQL, (LATEST_N,)).fetchall()
    ms = (time.perf_counter() - t0) * 1000
    db.close()
    keys = ["id", "customer", "created_at", "status", "total", "items"]
    return [dict(zip(keys, r)) for r in rows], ms


def store_stats():
    db = sqlite3.connect(DB_PATH)
    n, revenue, oldest = db.execute(
        "SELECT COUNT(*), COALESCE(SUM(total), 0), MIN(created_at) FROM orders"
    ).fetchone()
    db.close()
    return {"orders": n, "revenue": round(revenue, 2), "oldest": oldest}


def vitals():
    return {
        "boot_id": BOOT_ID,
        "pid": os.getpid(),
        "uptime_s": round(time.time() - STARTED, 1),
        "requests": REQUESTS,
    }


def fmt_uptime(s):
    s = int(s)
    return f"{s // 3600}h {s % 3600 // 60}m {s % 60}s"


def render_dashboard():
    orders, ms = latest_orders()
    stats, v = store_stats(), vitals()
    speed = "fast" if ms < 100 else "slow" if ms > 400 else "ok"
    rows = "".join(
        f"<tr><td>#{o['id']}</td><td>{html.escape(o['customer'])}</td>"
        f"<td>{o['created_at'].replace('T', ' ')}</td><td><span class='st {o['status']}'>{o['status']}</span></td>"
        f"<td class='num'>{o['items']}</td><td class='num'>${o['total']:,.2f}</td></tr>"
        for o in orders
    )
    return f"""<!doctype html><html><head><meta charset="utf-8">
<meta http-equiv="refresh" content="4"><title>Acme Store</title>
<style>
:root {{ color-scheme: light; }}
body {{ font: 14px/1.4 -apple-system, system-ui, sans-serif; margin: 0; background: #f6f7f9; color: #1d2330; }}
header {{ background: #1d2330; color: #fff; padding: 14px 20px; display: flex; justify-content: space-between; align-items: center; }}
header b {{ font-size: 16px; }}
.vitals {{ font: 12px ui-monospace, monospace; opacity: .85; }}
.cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; padding: 16px 20px 0; }}
.card {{ background: #fff; border-radius: 10px; padding: 12px 14px; box-shadow: 0 1px 2px #0001; }}
.card small {{ color: #6b7280; display: block; }} .card div {{ font-size: 20px; font-weight: 600; }}
.fast {{ color: #15803d; }} .ok {{ color: #b45309; }} .slow {{ color: #b91c1c; }}
table {{ width: calc(100% - 40px); margin: 16px 20px; border-collapse: collapse; background: #fff; border-radius: 10px; overflow: hidden; box-shadow: 0 1px 2px #0001; }}
th, td {{ padding: 7px 12px; border-bottom: 1px solid #eef0f3; text-align: left; }}
th {{ background: #fafbfc; color: #6b7280; font-weight: 500; font-size: 12px; text-transform: uppercase; }}
.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
.st {{ font-size: 12px; padding: 2px 8px; border-radius: 99px; background: #eef0f3; }}
.st.delivered {{ background: #dcfce7; }} .st.refunded {{ background: #fee2e2; }} .st.shipped {{ background: #dbeafe; }}
</style></head><body>
<header><b>Acme Store &middot; Orders</b>
<span class="vitals">server {v['boot_id']} &middot; pid {v['pid']} &middot; up {fmt_uptime(v['uptime_s'])} &middot; {v['requests']} requests</span></header>
<div class="cards">
<div class="card"><small>Orders page query</small><div class="{speed}">{ms:,.0f} ms</div></div>
<div class="card"><small>Total orders</small><div>{stats['orders']:,}</div></div>
<div class="card"><small>Lifetime revenue</small><div>${stats['revenue']:,.0f}</div></div>
<div class="card"><small>Order history since</small><div>{(stats['oldest'] or '-')[:10]}</div></div>
</div>
<table><tr><th>Order</th><th>Customer</th><th>Placed</th><th>Status</th><th class="num">Items</th><th class="num">Total</th></tr>{rows}</table>
</body></html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        global REQUESTS
        REQUESTS += 1
        path = self.path.split("?")[0]
        try:
            if path == "/":
                self._send(200, render_dashboard(), "text/html; charset=utf-8")
            elif path == "/api/orders":
                orders, ms = latest_orders()
                self._send(200, json.dumps({"orders": orders, "query_ms": round(ms, 1)}))
            elif path == "/api/health":
                self._send(200, json.dumps({**vitals(), **store_stats()}))
            else:
                self._send(404, json.dumps({"error": "not found"}))
        except Exception as e:  # keep serving even if the DB is mid-migration
            self._send(500, json.dumps({"error": str(e)}))

    def _send(self, code, body, ctype="application/json"):
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    print(f"Acme Store listening on :{PORT} (boot {BOOT_ID})", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
