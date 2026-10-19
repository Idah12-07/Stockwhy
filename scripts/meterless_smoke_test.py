#!/usr/bin/env python3
"""Step-by-step Meterless H-MEM check.  Run:  python scripts/meterless_smoke_test.py
Needs Node.js 18+ and one-time:  cd meterless && npm install
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.memory import case_text  # noqa: E402
from app.pipeline import run_investigation  # noqa: E402
from app.report import render  # noqa: E402
from app.store import LocalStore  # noqa: E402
from app.synthetic import generate  # noqa: E402
from app.tools.meterless_memory import MemoryUnavailable, MeterlessMemory  # noqa: E402

print("[1] Start the Meterless H-MEM engine")
try:
    mem = MeterlessMemory(state_dir=tempfile.mkdtemp())
except MemoryUnavailable as e:
    print("    FAIL:", e)
    sys.exit(1)
print("    OK:", mem.info["engine"])

print("[2] Remember a case, then recall it")
mid = mem.remember(case_text({"facility_id": "FAC-999", "commodity": "ORS sachet", "month": "2026-01"}, "late_order", "high"))
got = mem.recall_cases("FAC-999", "ORS sachet")
print("    OK" if got and got[0]["memory_id"] == mid else "    FAIL", got)

print("[3] Audit trail (the engine's append-only ledger)")
print("   ", mem.audit(mid))

print("[4] Investigate the same facility twice and watch memory change the answer")
with tempfile.TemporaryDirectory() as d:
    q, _ = generate(d, seed=11, plant_cause="late_order", history=True)
    store = LocalStore(d)
    for month in ("2025-09", q["month"]):
        res = run_investigation(store, {**q, "month": month}, memory=mem)
        m = res["memory"]
        print(f"    {month}: top cause {res['verdict']['ranked'][0]['hypothesis']}, earlier cases {len(m['prior_cases'])}, repeat issue: {m['repeat_issue']}")
    print()
    print(render(res)[-700:])
mem.feedback(mid, "helpful")
print("[5] Feedback recorded:", mem.audit(mid)[-1])
mem.close()
