#!/usr/bin/env python3
"""Build a dataset. Example: python scripts/generate_data.py --seed 42 --plant-cause late_order"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.synthetic import CAUSES, generate, generate_many  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--seed", type=int, default=7)
ap.add_argument("--plant-cause", choices=CAUSES)
ap.add_argument("--facilities", type=int, default=30)
ap.add_argument("--out", default=None)
ap.add_argument("--many", type=float, default=None, metavar="SHARE",
                help="plant MANY labelled stock-outs: SHARE of facility-medicine pairs (for example 0.3); writes an answer key to scripts/_truth/")
ap.add_argument("--noise", type=float, default=1.0)
ap.add_argument("--fill", type=float, default=0.92, help="typical supplier fill rate; real county studies report 0.5-0.6")
a = ap.parse_args()
out = a.out or f"data/generated/s{a.seed}_{a.plant_cause or 'none'}"
if a.many:
    out = a.out or f"data/generated/many_s{a.seed}_f{a.facilities}"
    events = generate_many(out, seed=a.seed, n_facilities=a.facilities, share=a.many, noise=a.noise, fill_mean=a.fill)
    Path("scripts/_truth").mkdir(parents=True, exist_ok=True)
    key = Path(f"scripts/_truth/{Path(out).name}.json")
    key.write_text(json.dumps(events, indent=1))
    print(f"Wrote {out} with {len(events)} labelled stock-outs. Answer key: {key} (the agent never reads it)")
    raise SystemExit(0)
q, truth = generate(out, seed=a.seed, plant_cause=a.plant_cause, n_facilities=a.facilities, noise=a.noise, fill_mean=a.fill)
print(f"Wrote {out}")
if q:
    print("Question:", json.dumps(q))
    # The planted cause is kept OUT of the dataset folder on purpose.
    Path("scripts/_truth").mkdir(parents=True, exist_ok=True)
    Path(f"scripts/_truth/s{a.seed}_{a.plant_cause}.json").write_text(json.dumps({"question": q, **truth}, indent=1))
    print("Ground truth saved to scripts/_truth/ (the agent never reads this folder).")
