#!/usr/bin/env python3
"""Evaluate the agent: accuracy, per-cause precision/recall/F1, confusion matrix, confidence
calibration, abstention, citation validity and speed, at several noise levels.

Ground truth comes straight from the generator's return value. The agent only sees the data.
Run:  python scripts/evaluate.py            (about a minute)
      python scripts/evaluate.py --per-cause 10 --noise 1 2
"""
import argparse
import json
import re
import sys
import tempfile
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.hypotheses import HYPOTHESES  # noqa: E402
from app.pipeline import run_investigation  # noqa: E402
from app.store import LocalStore  # noqa: E402
from app.synthetic import CAUSES, generate  # noqa: E402

CLASSES = list(HYPOTHESES) + ["abstain"]


def citation_ok(store, cite):
    m = re.fullmatch(r"(stock|orders|payments)#(\d+)", cite)
    if m:
        return bool(store.query(f"SELECT 1 FROM {m.group(1)} WHERE id=?", (int(m.group(2)),)))
    return any(n["url"] == cite for n in store.web_notes())


def evaluate(noise, per_cause, seed0):
    rows, invalid, cites_total, cites_ok, secs = [], 0, 0, 0, []
    for ci, cause in enumerate(CAUSES):
        for k in range(per_cause):
            with tempfile.TemporaryDirectory() as d:
                q, truth = generate(d, seed=seed0 + ci * 1000 + k, plant_cause=cause, noise=noise)
                store = LocalStore(d)
                res = run_investigation(store, q)
                if res["status"] == "nothing_to_investigate":
                    invalid += 1  # the generator did not produce a stock-out; not the agent's fault
                    continue
                secs.append(res["seconds"])
                v = res["verdict"]
                ranked = [r["hypothesis"] for r in v["ranked"]]
                pred = "abstain" if v["escalate"] else ranked[0]
                rows.append({"cause": cause, "true": truth["primary"], "pred": pred, "top2": ranked[:2],
                             "contrib": truth["contributing"], "conf": v["confidence"]})
                for r in v["ranked"][:3]:
                    for c in r["citations"]:
                        cites_total += 1
                        cites_ok += citation_ok(store, c)
    n = len(rows)
    answered = [r for r in rows if r["pred"] != "abstain"]
    top1 = sum(r["pred"] == r["true"] for r in rows)
    top2 = sum(r["true"] in r["top2"] for r in rows)
    conf = Counter((r["true"], r["pred"]) for r in rows)
    per_class = {}
    for c in HYPOTHESES:
        tp = conf[(c, c)]
        fp = sum(conf[(t, c)] for t in HYPOTHESES if t != c)
        fn = sum(conf[(c, p)] for p in CLASSES if p != c)
        prec = tp / (tp + fp) if tp + fp else None
        rec = tp / (tp + fn) if tp + fn else None
        f1 = 2 * prec * rec / (prec + rec) if prec and rec else (0.0 if prec is not None and rec is not None else None)
        per_class[c] = {"precision": prec, "recall": rec, "f1": f1, "support": tp + fn}
    calib = {}
    for lvl in ("high", "medium", "low"):
        sub = [r for r in rows if r["conf"] == lvl]
        calib[lvl] = {"n": len(sub), "top1_accuracy": (sum(r["pred"] == r["true"] for r in sub) / len(sub)) if sub else None}
    with_contrib = [r for r in rows if r["contrib"]]
    return {
        "noise": noise, "scored": n, "invalid_scenarios": invalid,
        "top1_accuracy": top1 / n if n else None, "top2_accuracy": top2 / n if n else None,
        "accuracy_when_answering": (sum(r["pred"] == r["true"] for r in answered) / len(answered)) if answered else None,
        "abstain_rate": (n - len(answered)) / n if n else None,
        "secondary_cause_in_top2": (sum(any(c in r["top2"] for c in r["contrib"]) for r in with_contrib) / len(with_contrib)) if with_contrib else None,
        "citation_validity": cites_ok / cites_total if cites_total else None,
        "avg_seconds": sum(secs) / len(secs) if secs else None, "max_seconds": max(secs) if secs else None,
        "per_class": per_class, "calibration": calib,
        "confusion": {f"{t}->{p}": c for (t, p), c in sorted(conf.items())},
    }


def pct(x):
    return "n/a" if x is None else f"{x:.0%}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-cause", type=int, default=15)
    ap.add_argument("--noise", type=float, nargs="+", default=[1.0, 2.0, 3.0])
    ap.add_argument("--seed0", type=int, default=5000)
    a = ap.parse_args()
    out, lines = [], []
    for noise in a.noise:
        t0 = time.time()
        r = evaluate(noise, a.per_cause, a.seed0)
        out.append(r)
        lines += [f"## Noise level {noise}", "",
                  f"Scenarios scored: {r['scored']} (skipped {r['invalid_scenarios']} where no stock-out was produced). Random guess would be about 14%.", "",
                  f"- Top-1 accuracy: **{pct(r['top1_accuracy'])}**   Top-2 accuracy: **{pct(r['top2_accuracy'])}**",
                  f"- Accuracy when the agent answers (does not abstain): {pct(r['accuracy_when_answering'])}   Abstain rate: {pct(r['abstain_rate'])}",
                  f"- Secondary cause found in top 2 (multi-cause cases): {pct(r['secondary_cause_in_top2'])}",
                  f"- Citation validity (cited rows or URLs exist): {pct(r['citation_validity'])}",
                  f"- Speed: average {r['avg_seconds']:.2f}s, slowest {r['max_seconds']:.2f}s (offline mode)", "",
                  "| Cause | Precision | Recall | F1 | Cases |", "|---|---|---|---|---|"]
        for c, m in r["per_class"].items():
            lines.append(f"| {c} | {pct(m['precision'])} | {pct(m['recall'])} | {pct(m['f1'])} | {m['support']} |")
        lines += ["", "| Confidence label | Cases | Top-1 accuracy |", "|---|---|---|"]
        for lvl, m in r["calibration"].items():
            lines.append(f"| {lvl} | {m['n']} | {pct(m['top1_accuracy'])} |")
        lines += ["", "Most common mistakes (true -> predicted):"]
        wrong = sorted(((k, v) for k, v in r["confusion"].items() if k.split("->")[0] != k.split("->")[1]), key=lambda kv: -kv[1])[:5]
        lines += [f"- {k}: {v}" for k, v in wrong] or ["- none"]
        lines.append("")
        print(f"noise {noise}: top-1 {pct(r['top1_accuracy'])}, top-2 {pct(r['top2_accuracy'])}, abstain {pct(r['abstain_rate'])} ({time.time() - t0:.0f}s)", file=sys.stderr)
    Path("logs").mkdir(exist_ok=True)
    Path("logs/evaluation.json").write_text(json.dumps(out, indent=1))
    Path("logs/evaluation.md").write_text("# StockWhy evaluation (synthetic data)\n\n" + "\n".join(lines))
    print("\n".join(lines))
    print("Saved logs/evaluation.md and logs/evaluation.json", file=sys.stderr)


if __name__ == "__main__":
    main()
