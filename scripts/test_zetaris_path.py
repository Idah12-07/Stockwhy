#!/usr/bin/env python3
"""Check that the Zetaris code path gives the SAME answers as the local path.

Uses the fake server (not real Zetaris), so it proves our client logic: SQL inlining, column naming,
type conversion and portable SQL. Run:  python scripts/test_zetaris_path.py
"""
import os
import sys
import tempfile
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from app.pipeline import run_investigation  # noqa: E402
from app.store import LocalStore  # noqa: E402
from app.synthetic import CAUSES, generate  # noqa: E402
from app.tools.zetaris_client import ZetarisStore  # noqa: E402
from fake_zetaris_server import KEY, ORG, make_server  # noqa: E402


def sig(res):
    if res["status"] == "nothing_to_investigate":
        return ("none",)
    return tuple((r["hypothesis"], round(r["score"], 3)) for r in res["verdict"]["ranked"]) + (
        (res["action"] or {}).get("transfer") and res["action"]["transfer"]["from"],)


bad = 0
for i, cause in enumerate(CAUSES):
    with tempfile.TemporaryDirectory() as d:
        q, _ = generate(d, seed=300 + i, plant_cause=cause)
        srv = make_server(d, port=8900 + i, schema="TEAM1")
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        os.environ.update(ZETARIS_REST_URL=f"http://127.0.0.1:{8900 + i}/api/v1.0", ZETARIS_ORG_ID=ORG,
                          ZETARIS_API_KEY=KEY, ZETARIS_SCHEMA="TEAM1")
        a = run_investigation(LocalStore(d), q)
        b = run_investigation(ZetarisStore(d), q)
        srv.shutdown()
    same = sig(a) == sig(b)
    bad += not same
    print(f"{cause:22} {'same answer through Zetaris path' if same else 'DIFFERENT'}")
print("ALL SAME" if not bad else f"{bad} DIFFERENT")
sys.exit(1 if bad else 0)
