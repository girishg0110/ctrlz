"""Seeds shop.db with a realistic-looking store: customers, orders and order items.

order_items.order_id is deliberately left unindexed, which is what makes the
dashboard slow. Uses only the standard library so it runs in a bare sandbox.
"""

import os
import random
import sqlite3
import sys
from datetime import datetime, timedelta

N_CUSTOMERS = 5_000
N_ORDERS = int(os.environ.get("SEED_ORDERS", 200_000))
ITEMS_PER_ORDER = (1, 11)

FIRST = ["Ava", "Liam", "Mia", "Noah", "Zoe", "Ethan", "Iris", "Omar", "Lena", "Kai", "Rosa", "Theo"]
LAST = ["Chen", "Patel", "Garcia", "Kim", "Nguyen", "Smith", "Okafor", "Rossi", "Haddad", "Silva"]
SKUS = [f"SKU-{i:04d}" for i in range(1, 801)]
STATUSES = ["delivered"] * 8 + ["shipped", "processing", "refunded"]


def main(path: str) -> None:
    if os.path.exists(path):
        os.remove(path)
    rng = random.Random(42)
    db = sqlite3.connect(path)
    db.executescript(
        """
        CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT, email TEXT);
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY, customer_id INTEGER, created_at TEXT,
            status TEXT, total REAL
        );
        CREATE TABLE order_items (
            id INTEGER PRIMARY KEY, order_id INTEGER, sku TEXT, qty INTEGER, price REAL
        );
        """
    )
    db.executemany(
        "INSERT INTO customers VALUES (?, ?, ?)",
        (
            (i, f"{rng.choice(FIRST)} {rng.choice(LAST)}", f"user{i}@example.com")
            for i in range(1, N_CUSTOMERS + 1)
        ),
    )

    start = datetime(2019, 1, 1)
    span = (datetime(2026, 10, 15) - start).total_seconds()
    orders, items = [], []
    item_id = 1
    for oid in range(1, N_ORDERS + 1):
        created = start + timedelta(seconds=span * (oid / N_ORDERS) + rng.uniform(-3600, 3600))
        total = 0.0
        for _ in range(rng.randrange(*ITEMS_PER_ORDER)):
            qty, price = rng.randint(1, 4), round(rng.uniform(3, 180), 2)
            total += qty * price
            items.append((item_id, oid, rng.choice(SKUS), qty, price))
            item_id += 1
        orders.append(
            (oid, rng.randint(1, N_CUSTOMERS), created.isoformat(timespec="seconds"),
             rng.choice(STATUSES), round(total, 2))
        )
    # Insert in shuffled order so rowid order != created_at order, like a real table.
    rng.shuffle(items)
    db.executemany("INSERT INTO orders VALUES (?, ?, ?, ?, ?)", orders)
    db.executemany("INSERT INTO order_items VALUES (?, ?, ?, ?, ?)", items)
    db.commit()
    n_items = db.execute("SELECT COUNT(*) FROM order_items").fetchone()[0]
    print(f"seeded {N_ORDERS} orders, {n_items} items into {path}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "shop.db")
