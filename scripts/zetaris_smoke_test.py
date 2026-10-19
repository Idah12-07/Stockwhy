#!/usr/bin/env python3
"""Step-by-step Zetaris connection check. Run it, read each line, and paste the output to your team.

  python scripts/zetaris_smoke_test.py

It only READS. It never creates or changes anything on the Zetaris instance.
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import load_env  # noqa: E402

load_env()
from app.tools.zetaris_client import ZetarisError, ZetarisStore  # noqa: E402


def step(n, text):
    print(f"\n[{n}] {text}")


def show(raw):
    print("    raw response:", json.dumps(raw)[:400])


need = ["ZETARIS_REST_URL", "ZETARIS_ORG_ID", "ZETARIS_API_KEY"]
step(1, "Settings in .env")
missing = [v for v in need if not os.environ.get(v)]
if os.environ.get("ZETARIS_ROUTE") == "proxy":
    missing = [v for v in ["ZETARIS_BASE_URL", "ZETARIS_ORG_ID", "ZETARIS_API_KEY"] if not os.environ.get(v)]
if missing:
    print("    FAIL: missing", ", ".join(missing), "(copy .env.example to .env and fill them in)")
    sys.exit(1)
print("    OK: all required settings are present (values are not printed)")

try:
    z = ZetarisStore()
    step(2, "Can we reach Zetaris and run SELECT 1?")
    show(z.raw("SELECT 1 AS one"))
    print("    OK" if z.last_raw else "    FAIL")

    step(3, "Which databases can we see? (SHOW LIGHTNING DATABASES)")
    show(z.raw("SHOW LIGHTNING DATABASES"))

    schema = os.environ.get("ZETARIS_SCHEMA", "").strip()
    step(4, f"Are our StockWhy tables there? (looking in '{schema or '(no ZETARIS_SCHEMA set)'}')")
    if not schema:
        print("    SKIPPED: set ZETARIS_SCHEMA in .env once your tables are registered")
        sys.exit(0)
    for table in ("facilities", "stock", "orders", "payments"):
        try:
            show(z.raw(f"SELECT * FROM {schema}.{table} LIMIT 2"))
            print(f"    OK: {schema}.{table} answered")
        except ZetarisError as e:
            print(f"    FAIL: {schema}.{table}: {e}")

    step(5, "Run one real StockWhy investigation through Zetaris")
    rows = z.query(f"SELECT facility_id, commodity, month, reported_stockout_days FROM {z.t('stock')} "
                   "WHERE reported_stockout_days > 5 LIMIT 1")
    if not rows:
        print("    No stock-out rows found; check that stock was loaded.")
        sys.exit(1)
    r = rows[0]
    from app.pipeline import run_investigation
    from app.report import render
    res = run_investigation(z, {"facility_id": r["facility_id"], "commodity": r["commodity"], "month": r["month"]})
    print(render(res)[:900])
    print("\n    DONE: Zetaris is wired in. Note the run time above; it was", res.get("seconds"), "s")
except ZetarisError as e:
    print("    FAIL:", e)
    sys.exit(1)
