#!/usr/bin/env python3
"""Entry point.

  python run.py --input input_examples/case1.json
  python run.py --scenario-seed 42 --plant-cause late_order
  python run.py --dataset data/generated/default --facility FAC-017 --commodity "oxytocin 10IU inj" --month 2026-03
"""
import argparse
import json
import sys
import time
from pathlib import Path

from app.pipeline import run_investigation
from app.report import render
from app.store import get_store
from app.synthetic import CAUSES, generate
from app.trace import Trace

DEFAULT_DIR = Path("data/generated/default")


def resolve(args):
    spec = {}
    if args.input:
        spec = json.loads(Path(args.input).read_text())
    scen = spec.get("scenario") or ({"seed": args.scenario_seed, "plant_cause": args.plant_cause} if args.scenario_seed is not None else None)
    question = spec.get("question") or ({"facility_id": args.facility, "commodity": args.commodity, "month": args.month} if args.facility else None)
    if scen:
        name = f"s{scen['seed']}_{scen.get('plant_cause') or 'none'}"
        data_dir = Path("data/generated") / name
        planted_q, _truth = generate(data_dir, seed=scen["seed"], plant_cause=scen.get("plant_cause"),
                                     n_facilities=scen.get("n_facilities", 30), noise=scen.get("noise", 1.0))  # truth is discarded here on purpose
        question = question or planted_q
    else:
        data_dir = Path(spec.get("dataset") or args.dataset or DEFAULT_DIR)
        if not (data_dir / "stock.csv").exists():
            generate(data_dir, seed=7)  # seeded, deterministic, no manual step
    if not question:
        sys.exit("Give a question: --input FILE, or --facility/--commodity/--month, or a planted scenario.")
    return data_dir, question


def main():
    ap = argparse.ArgumentParser(description="StockWhy: explain why a facility ran out of a medicine.")
    ap.add_argument("--input")
    ap.add_argument("--dataset")
    ap.add_argument("--facility")
    ap.add_argument("--commodity")
    ap.add_argument("--month")
    ap.add_argument("--scenario-seed", type=int)
    ap.add_argument("--plant-cause", choices=CAUSES)
    ap.add_argument("--mode", choices=["offline", "live"], default="offline",
                    help="offline: local data adapter; live: sponsor integrations (Zetaris, Meterless, NVIDIA, Bright Data)")
    ap.add_argument("--json", action="store_true", help="print JSON instead of the readable report")
    args = ap.parse_args()

    data_dir, question = resolve(args)
    store = get_store(data_dir, args.mode)
    trace = Trace("logs", "run")
    result = run_investigation(store, question, trace)
    md = render(result)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    Path("logs").mkdir(exist_ok=True)
    Path(f"logs/{stamp}_report.md").write_text(md)
    Path(f"logs/{stamp}_result.json").write_text(json.dumps(result, indent=1, default=str))
    print(json.dumps(result, indent=1, default=str) if args.json else md)
    print(f"\n[trace: {trace.path}]", file=sys.stderr)


if __name__ == "__main__":
    main()
