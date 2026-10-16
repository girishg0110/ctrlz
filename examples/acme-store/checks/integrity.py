"""Prints row counts and revenue. Ctrl+Z requires them to equal production's (compare = "equal")."""
import json
import sqlite3

db = sqlite3.connect("shop.db")
orders, revenue = db.execute("SELECT COUNT(*), COALESCE(SUM(total), 0) FROM orders").fetchone()
items = db.execute("SELECT COUNT(*) FROM order_items").fetchone()[0]
print(json.dumps({"orders": orders, "items": items, "revenue": round(revenue, 2)}))
