"""Prints the median time to load /api/orders. Ctrl+Z requires it to be `factor` times faster."""
import json
import os
import statistics
import sys
import time
import urllib.request

port = os.environ.get("APP_PORT", "8000")
walls = []
try:
    for _ in range(3):
        t0 = time.perf_counter()
        urllib.request.urlopen(f"http://127.0.0.1:{port}/api/orders", timeout=60).read()
        walls.append((time.perf_counter() - t0) * 1000)
except Exception as e:
    print(json.dumps({"detail": f"server not answering: {e}"}))
    sys.exit(1)
print(json.dumps({"latency_ms": round(statistics.median(walls), 1)}))
