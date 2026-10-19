#!/usr/bin/env python3
"""Turn a generated dataset into SQL you can paste into a Postgres SQL editor (for example Neon).

  python scripts/export_postgres_sql.py --dataset data/generated/default

Writes two files next to the data:
  postgres_load.sql      creates the 4 tables and inserts every row  (run this in Postgres)
  zetaris_register.sql   the Zetaris statements that register that Postgres as a source (run in the Zetaris SQL Editor,
                         ONE statement at a time; creating a datasource needs administrator rights on Zetaris)
No passwords are written. Fill the placeholders by hand.
"""
import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.store import SCHEMAS  # noqa: E402

PG_TYPES = {"TEXT": "TEXT", "INTEGER": "INTEGER", "REAL": "DOUBLE PRECISION"}
DATE_COLS = {"cutoff_date", "order_date"}


def lit(v, typ, col):
    if v == "":
        return "NULL"
    return v if typ in ("INTEGER", "REAL") else "'" + v.replace("'", "''") + "'"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="data/generated/default")
    ap.add_argument("--chunk", type=int, default=400)
    ap.add_argument("--schema", default="public")
    a = ap.parse_args()
    d = Path(a.dataset)
    out = ["-- StockWhy synthetic data. All values are SYNTHETIC.", "BEGIN;"]
    for table, cols in SCHEMAS.items():
        defs = [c.strip().split() for c in cols.split(",")]
        ddl = ", ".join(f"{n} {'DATE' if n in DATE_COLS else PG_TYPES[t]}" for n, t in defs)
        out += [f"DROP TABLE IF EXISTS {a.schema}.{table};", f"CREATE TABLE {a.schema}.{table} ({ddl});"]
        with open(d / f"{table}.csv", newline="") as fh:
            rd = csv.reader(fh)
            next(rd)
            rows = list(rd)
        for i in range(0, len(rows), a.chunk):
            vals = ",\n".join("(" + ", ".join(lit(v, defs[j][1], defs[j][0]) for j, v in enumerate(r)) + ")"
                              for r in rows[i:i + a.chunk])
            out.append(f"INSERT INTO {a.schema}.{table} VALUES\n{vals};")
        print(f"{table}: {len(rows)} rows")
    out.append("COMMIT;")
    (d / "postgres_load.sql").write_text("\n".join(out) + "\n")
    reg = """-- Run these in the Zetaris SQL Editor, ONE statement at a time. Creating a datasource needs administrator rights.
-- Replace the placeholders. Do not commit this file with a real password.

CREATE DATASOURCE stockwhy_pg DESCRIBE BY "StockWhy synthetic data" OPTIONS (
  jdbcdriver "org.postgresql.Driver",
  jdbcurl "jdbc:postgresql://YOUR_HOST:5432/YOUR_DATABASE?sslmode=require",
  username "YOUR_USER",
  password "YOUR_PASSWORD",
  fetchsize "1000"
);

REGISTER DATASOURCE TABLES FROM stockwhy_pg;

-- Check it worked:
SHOW DATASOURCE TABLES stockwhy_pg;
SELECT * FROM stockwhy_pg.stock LIMIT 5;

-- Then set ZETARIS_SCHEMA=stockwhy_pg in .env
"""
    (d / "zetaris_register.sql").write_text(reg)
    print("Wrote", d / "postgres_load.sql", "and", d / "zetaris_register.sql")


if __name__ == "__main__":
    main()
