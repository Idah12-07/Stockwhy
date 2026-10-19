#!/usr/bin/env python3
"""A stand-in for Zetaris REST so you can test our client without a Zetaris instance.

It mimics what the public Zetaris docs describe: POST <base>/sql-editor/sqls/run with a bearer key,
X-Org-ID and X-Request-ID headers, answering {"data": [[...string values...]]} with no column names.
It answers by running the SQL on the local CSV data. It is NOT Zetaris; it only tests our plumbing.

  python scripts/fake_zetaris_server.py --dataset data/generated/default --port 8899
"""
import argparse
import json
import re
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.store import LocalStore  # noqa: E402

KEY, ORG = "fake-key", "1"


def make_server(data_dir, port=8899, schema="TEAM1"):
    store = LocalStore(data_dir)
    prefix = re.compile(rf"\b{re.escape(schema)}\.", re.I) if schema else None

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_POST(self):
            ok = (self.headers.get("Authorization") == f"Bearer {KEY}" and self.headers.get("X-Org-ID") == ORG
                  and self.headers.get("X-Request-ID"))
            if not ok:
                self.send_response(401); self.end_headers(); return
            if not self.path.endswith("/sql-editor/sqls/run"):
                self.send_response(404); self.end_headers(); return
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            sql = body["sql"]
            sql = prefix.sub("", sql) if prefix else sql
            if sql.strip().upper().startswith("SELECT 1"):
                rows = [["1"]]
            else:
                rows = [[("" if v is None else str(v)) for v in r.values()] for r in store.query(sql)]
            out = json.dumps({"data": rows[: body.get("limit", 100)]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(out)

    return ThreadingHTTPServer(("127.0.0.1", port), H)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="data/generated/default")
    ap.add_argument("--port", type=int, default=8899)
    ap.add_argument("--schema", default="TEAM1")
    a = ap.parse_args()
    srv = make_server(a.dataset, a.port, a.schema)
    print(f"Fake Zetaris on http://127.0.0.1:{a.port}/api/v1.0  key={KEY} org={ORG} schema={a.schema}")
    srv.serve_forever()
