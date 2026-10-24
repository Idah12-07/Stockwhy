#!/usr/bin/env python3
"""Score the agent on a county with MANY labelled stock-outs.

  python scripts/generate_data.py --many 0.3 --facilities 100 --seed 5
  python scripts/score_events.py --dataset data/generated/many_s5_f100 --key scripts/_truth/many_s5_f100.json

The answer key is read only here, never by the agent.
"""
import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.pipeline import run_investigation  # noqa: E402
from app.store import LocalStore  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--dataset", required=True)
ap.add_argument("--key", required=True, help="JSON list of labelled events (from generate_data.py --many)")
a = ap.parse_args()

events = json.loads(Path(a.key).read_text())
store = LocalStore(a.dataset)
conf = Counter()
abstain = 0
for e in events:
    res = run_investigation(store, {k: e[k] for k in ("facility_id", "commodity", "month")})
    if res["status"] != "ok":
        pred = "abstain"
        abstain += 1
    else:
        pred = res["verdict"]["ranked"][0]["hypothesis"]
    conf[(e["primary"], pred)] += 1

classes = sorted({t for t, _ in conf})
n = len(events)
right = sum(v for (t, p), v in conf.items() if t == p)
print(f"{n} labelled stock-outs, top-1 accuracy {right / n:.0%}, abstained on {abstain}\n")
print(f"{'cause':22} {'precision':>9} {'recall':>7} {'cases':>6}")
for c in classes:
    tp = conf[(c, c)]
    fp = sum(v for (t, p), v in conf.items() if p == c and t != c)
    fn = sum(v for (t, p), v in conf.items() if t == c and p != c)
    print(f"{c:22} {tp / (tp + fp) if tp + fp else 0:>9.0%} {tp / (tp + fn) if tp + fn else 0:>7.0%} {tp + fn:>6}")
wrong = [(k, v) for k, v in conf.items() if k[0] != k[1]]
if wrong:
    print("\nMistakes (true -> predicted):", ", ".join(f"{t}->{p}: {v}" for (t, p), v in sorted(wrong, key=lambda x: -x[1])[:6]))
