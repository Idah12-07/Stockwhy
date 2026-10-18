#!/usr/bin/env python3
"""Back-test: plant each cause under many seeds, run the agent, compare with the planted truth.

The truth comes straight from the generator return value; the agent only sees the data folder.
"""
import argparse
import json
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.pipeline import run_investigation  # noqa: E402
from app.store import LocalStore  # noqa: E402
from app.synthetic import CAUSES, generate  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--per-cause", type=int, default=10)
ap.add_argument("--seed0", type=int, default=1000)
a = ap.parse_args()

stats = defaultdict(lambda: {"n": 0, "top1": 0, "top2": 0, "escalated": 0, "wrong": []})
for ci, cause in enumerate(CAUSES):
    for k in range(a.per_cause):
        seed = a.seed0 + ci * 100 + k
        with tempfile.TemporaryDirectory() as d:
            q, truth = generate(d, seed=seed, plant_cause=cause)
            res = run_investigation(LocalStore(d), q)
        s = stats[cause]
        s["n"] += 1
        if res["status"] != "ok":
            s["escalated"] += 1
            s["wrong"].append(seed)
            continue
        ranked = [r["hypothesis"] for r in res["verdict"]["ranked"]]
        s["top1"] += ranked[0] == truth["primary"]
        hit2 = truth["primary"] in ranked[:2]
        s["top2"] += hit2
        if not hit2:
            s["wrong"].append(seed)

print(f"{'planted cause':22} {'n':>3} {'top-1':>6} {'top-2':>6} {'escal.':>7}")
tot = {"n": 0, "top1": 0, "top2": 0}
for cause in CAUSES:
    s = stats[cause]
    print(f"{cause:22} {s['n']:>3} {s['top1']:>6} {s['top2']:>6} {s['escalated']:>7}   misses: {s['wrong'][:5]}")
    for key in tot:
        tot[key] += s[key]
print(f"{'ALL':22} {tot['n']:>3} {tot['top1']:>6} {tot['top2']:>6}   top-1 {tot['top1']/tot['n']:.0%}, top-2 {tot['top2']/tot['n']:.0%}")
Path("logs").mkdir(exist_ok=True)
Path("logs/backtest.json").write_text(json.dumps({k: {x: y for x, y in v.items()} for k, v in stats.items()}, indent=1))
