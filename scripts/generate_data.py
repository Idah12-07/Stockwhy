#!/usr/bin/env python3
"""Build a dataset. Example: python scripts/generate_data.py --seed 42 --plant-cause late_order"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.synthetic import CAUSES, generate  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--seed", type=int, default=7)
ap.add_argument("--plant-cause", choices=CAUSES)
ap.add_argument("--facilities", type=int, default=30)
ap.add_argument("--out", default=None)
a = ap.parse_args()
out = a.out or f"data/generated/s{a.seed}_{a.plant_cause or 'none'}"
q, truth = generate(out, seed=a.seed, plant_cause=a.plant_cause, n_facilities=a.facilities)
print(f"Wrote {out}")
if q:
    print("Question:", json.dumps(q))
    # The planted cause is kept OUT of the dataset folder on purpose.
    Path("scripts/_truth").mkdir(parents=True, exist_ok=True)
    Path(f"scripts/_truth/s{a.seed}_{a.plant_cause}.json").write_text(json.dumps({"question": q, **truth}, indent=1))
    print("Ground truth saved to scripts/_truth/ (the agent never reads this folder).")
