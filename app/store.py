"""Data access. The agents only call Store.query(); swap the backend, not the agents.

LocalStore  : loads the generated CSVs into an in-memory SQLite database (offline mode).
ZetarisStore: TODO - same interface, queries go through Zetaris via MCP.
"""
import csv
import json
import sqlite3
import threading
from pathlib import Path

SCHEMAS = {
    "facilities": "facility_id TEXT, lat REAL, lon REAL",
    "stock": "id INTEGER, facility_id TEXT, commodity TEXT, month TEXT, opening REAL, received REAL, wastage REAL, consumed REAL, closing REAL, reported_stockout_days INTEGER",
    "orders": "id INTEGER, facility_id TEXT, commodity TEXT, month TEXT, cutoff_date TEXT, order_date TEXT, qty_requested REAL, qty_delivered REAL, delivery_month TEXT",
    "payments": "id INTEGER, month TEXT, county_arrears_flag INTEGER, amount_owed_kes REAL",
}


class LocalStore:
    name = "local-sqlite (offline adapter)"

    def __init__(self, data_dir):
        self.dir = Path(data_dir)
        self.db = sqlite3.connect(":memory:", check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        for table, cols in SCHEMAS.items():
            self.db.execute(f"CREATE TABLE {table} ({cols})")
            with open(self.dir / f"{table}.csv", newline="") as fh:
                reader = csv.reader(fh)
                next(reader)
                rows = list(reader)
            marks = ",".join("?" * len(rows[0]))
            self.db.executemany(f"INSERT INTO {table} VALUES ({marks})", rows)
        self.db.commit()
        self._lock = threading.Lock()  # branches run in parallel; one query at a time on the shared connection

    def query(self, sql, params=()):
        with self._lock:
            return [dict(r) for r in self.db.execute(sql, params).fetchall()]

    def web_notes(self):
        return json.loads((self.dir / "web_notes.json").read_text())


def get_store(data_dir, mode="offline"):
    if mode == "live":
        from .tools.zetaris_client import ZetarisStore
        return ZetarisStore()
    return LocalStore(data_dir)
