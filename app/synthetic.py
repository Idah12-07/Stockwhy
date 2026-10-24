"""Seeded synthetic data generator for the stock-out investigator.

Everything written here is SYNTHETIC. It mimics the *structure* of facility
commodity reports, orders, supplier fill and county payments. It never writes
the planted cause into the dataset folder: the cause is only returned to the
caller (scripts use it for back-testing; the agent code never sees it).
"""
import csv
import json
import math
import random
from datetime import date, timedelta
from pathlib import Path

from .months import MONTHS, N_MONTHS, idx, label, shift

CAUSES = [
    "late_order", "supplier_underfill", "payment_arrears", "demand_surge",
    "record_error", "expiry", "national_disruption", "multi",
]
COMMODITIES = [
    "oxytocin 10IU inj", "amoxicillin dispersible tab", "ORS sachet",
    "zinc 20mg tab", "magnesium sulphate inj", "iron-folate tab",
]


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def generate(out_dir, seed=7, n_facilities=30, plant_cause=None, target_month="2026-03", noise=1.0, history=False, events=None, fill_mean=0.92):
    """Write CSV/JSON files into out_dir. Returns (question, truth).

    question: dict(facility_id, commodity, month) or None if nothing planted.
    truth: dict(primary, contributing) or None. Keep it out of the agent's reach.
    """
    """noise: 1.0 is the default level; 2.0 and 3.0 make demand and supplier fill much messier.
    fill_mean: typical share of an order the supplier delivers (0.92 by default; real county studies report about 0.5-0.6).
    history: also plant the same simple cause at the same facility six months earlier (to demo case memory).
    events: optional list of (facility_id, commodity, month_index, cause) to plant MANY labelled stock-outs in one county."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    fscale = fill_mean / 0.92
    facilities = [f"FAC-{i:03d}" for i in range(1, n_facilities + 1)]
    coords = {f: (-1.29 + rng.uniform(-0.45, 0.45), 36.82 + rng.uniform(-0.45, 0.45)) for f in facilities}
    base = {(f, c): rng.uniform(80, 400) for f in facilities for c in COMMODITIES}

    target = None
    if plant_cause:
        assert plant_cause in CAUSES, plant_cause
        target = (rng.choice(facilities), rng.choice(COMMODITIES))
    tM = idx(target_month)

    late = set()            # (f, c, order_t)
    fill_over = {}          # (f, c, order_t) -> fill rate
    demand_mult = {}        # (f, c, t) -> multiplier
    waste_start = {}        # (f, c, t) -> fraction of base removed at start of month
    reported_over = {}      # (f, c, t) -> reported stockout days
    arrears_months = set()
    notes = [
        {"month": "2025-06", "commodity": "ORS sachet", "source": "KEMSA notice (synthetic)",
         "title": "Routine delivery schedule update", "url": "https://example.org/synthetic/1", "synthetic": True},
        {"month": "2025-11", "commodity": "zinc 20mg tab", "source": "Tender notice (synthetic)",
         "title": "Framework tender opened", "url": "https://example.org/synthetic/2", "synthetic": True},
    ]
    truth = None
    SIMPLE = ("late_order", "supplier_underfill", "demand_surge", "record_error", "expiry", "multi")
    if target:
        pf, pc = target
        plant_months = [tM]
        if history and plant_cause in SIMPLE:
            plant_months.append(tM - 6)  # the same problem happened here half a year earlier
        for tt in plant_months:
            if plant_cause == "late_order":
                late.add((pf, pc, tt - 1)); truth = ("late_order", [])
            elif plant_cause == "supplier_underfill":
                fill_over[(pf, pc, tt - 1)] = 0.15; truth = ("supplier_underfill", [])
            elif plant_cause == "payment_arrears":
                arrears_months = {tM - 3, tM - 2, tM - 1, tM}
                for f in facilities:
                    for t in (tM - 2, tM - 1):
                        fill_over[(f, pc, t)] = rng.uniform(0.3, 0.5)
                truth = ("payment_arrears", [])
            elif plant_cause == "demand_surge":
                demand_mult[(pf, pc, tt)] = 2.2; truth = ("demand_surge", [])
            elif plant_cause == "record_error":
                reported_over[(pf, pc, tt)] = 18; truth = ("record_error", [])
            elif plant_cause == "expiry":
                waste_start[(pf, pc, tt)] = 0.55; fill_over[(pf, pc, tt - 1)] = 0.7
                truth = ("expiry", ["supplier_underfill"])
            elif plant_cause == "national_disruption":
                for f in facilities:
                    fill_over[(f, pc, tM - 1)] = rng.uniform(0.03, 0.15)
                notes.append({"month": shift(target_month, -1), "commodity": pc,
                              "source": "KEMSA notice (synthetic)",
                              "title": f"Supply interruption affecting {pc}",
                              "url": "https://example.org/synthetic/national", "synthetic": True})
                truth = ("national_disruption", [])
            elif plant_cause == "multi":
                late.add((pf, pc, tt - 1)); demand_mult[(pf, pc, tt)] = 1.5
                truth = ("late_order", ["demand_surge"])

    thin_pairs = set()
    if target and plant_cause not in (None, "record_error"):
        thin_pairs.add(target)
    for (ef, ec, et, ecause) in (events or []):
        if ecause == "late_order":
            late.add((ef, ec, et - 1))
        elif ecause == "supplier_underfill":
            fill_over[(ef, ec, et - 1)] = 0.15
        elif ecause == "demand_surge":
            demand_mult[(ef, ec, et)] = 2.2
        elif ecause == "record_error":
            reported_over[(ef, ec, et)] = 18
        elif ecause == "expiry":
            waste_start[(ef, ec, et)] = 0.55; fill_over[(ef, ec, et - 1)] = 0.7
        elif ecause == "multi":
            late.add((ef, ec, et - 1)); demand_mult[(ef, ec, et)] = 1.5
        else:
            raise ValueError("events support only the facility-level causes, got " + str(ecause))
        if ecause != "record_error":
            thin_pairs.add((ef, ec))

    stock_rows, order_rows = [], []
    sid = oid = 0
    for f in facilities:
        for c in COMMODITIES:
            b = base[(f, c)]
            thin = (f, c) in thin_pairs
            cover = 1.6 if thin else 2.5
            opening = cover * b
            received = [0.0] * (N_MONTHS + 3)
            for t in range(N_MONTHS):
                m = MONTHS[t]
                w = min(opening, waste_start.get((f, c, t), 0.0) * b)
                rec = received[t]
                # ordering (cycle cut-off is the 10th; delivery next month)
                y, mo = int(m[:4]), int(m[5:7])
                cutoff = date(y, mo, 10)
                is_late = (f, c, t) in late
                order_date = cutoff + timedelta(days=rng.randint(9, 12)) if is_late else cutoff - timedelta(days=rng.randint(0, 6))
                proj_closing = opening - w + rec - b
                qty_req = max(0, round((cover * b - proj_closing) / fill_mean))
                gfill = _clamp(rng.gauss(fill_mean, 0.05 * noise), 0.6 * fscale, 1.0)
                fill = fill_over[(f, c, t)] * fscale if (f, c, t) in fill_over else gfill
                qty_del = round(qty_req * fill)
                d_idx = t + (2 if is_late else 1)
                received[d_idx] += qty_del
                oid += 1
                order_rows.append([oid, f, c, m, cutoff.isoformat(), order_date.isoformat(), qty_req, qty_del, label(d_idx)])
                # month consumption
                available = opening - w + rec
                demand = b * rng.uniform(1 - 0.1 * noise, 1 + 0.1 * noise) * demand_mult.get((f, c, t), 1.0)
                consumed = min(demand, available)
                short = demand - consumed
                so_days = round(30 * short / demand) if short > 0.02 * demand else 0
                closing = available - consumed
                reported = reported_over.get((f, c, t), so_days)
                sid += 1
                stock_rows.append([sid, f, c, m, round(opening), round(rec), round(w), round(consumed), round(closing), reported])
                opening = closing

    def write(name, header, rows):
        with open(out / name, "w", newline="") as fh:
            wr = csv.writer(fh)
            wr.writerow(header)
            wr.writerows(rows)

    write("facilities.csv", ["facility_id", "lat", "lon"], [[f, round(coords[f][0], 4), round(coords[f][1], 4)] for f in facilities])
    write("stock.csv", ["id", "facility_id", "commodity", "month", "opening", "received", "wastage", "consumed", "closing", "reported_stockout_days"], stock_rows)
    write("orders.csv", ["id", "facility_id", "commodity", "month", "cutoff_date", "order_date", "qty_requested", "qty_delivered", "delivery_month"], order_rows)
    pay_rows = []
    for t, m in enumerate(MONTHS):
        if t in arrears_months:
            pay_rows.append([t + 1, m, 1, rng.randint(40, 120) * 1_000_000])
        elif rng.random() < 0.1:
            pay_rows.append([t + 1, m, 1, rng.randint(2, 8) * 1_000_000])
        else:
            pay_rows.append([t + 1, m, 0, 0])
    write("payments.csv", ["id", "month", "county_arrears_flag", "amount_owed_kes"], pay_rows)
    (out / "web_notes.json").write_text(json.dumps(notes, indent=1))
    (out / "manifest.json").write_text(json.dumps({"synthetic": True, "seed": seed, "n_facilities": n_facilities}, indent=1))

    question = {"facility_id": target[0], "commodity": target[1], "month": target_month} if target else None
    truth_d = {"primary": truth[0], "contributing": truth[1]} if truth else None
    return question, truth_d


EVENT_CAUSES = ["late_order", "supplier_underfill", "demand_surge", "record_error", "expiry", "multi"]


def generate_many(out_dir, seed=7, n_facilities=150, share=0.3, noise=1.0, fill_mean=0.92):
    """A realistic county: about `share` of facility-medicine pairs have one stock-out with a known cause.

    Real studies find roughly 20-50% of facilities report a stock-out of a tracer medicine over six months
    (ThinkWell 2024), so a county with one stock-out is far too clean. Returns a list of labelled events.
    Only facility-level causes are planted (county-wide causes such as arrears are one-per-county).
    """
    rng = random.Random(seed * 7919 + 1)
    pairs = [(f"FAC-{i:03d}", c) for i in range(1, n_facilities + 1) for c in COMMODITIES]
    chosen = rng.sample(pairs, int(len(pairs) * share))
    ev = [(f, c, rng.randrange(8, N_MONTHS - 1), rng.choice(EVENT_CAUSES)) for f, c in chosen]
    generate(out_dir, seed=seed, n_facilities=n_facilities, noise=noise, events=ev, fill_mean=fill_mean)
    # keep only events that really produced a reported stock-out
    rows = {}
    with open(Path(out_dir) / "stock.csv", newline="") as fh:
        for r in csv.DictReader(fh):
            rows[(r["facility_id"], r["commodity"], r["month"])] = int(r["reported_stockout_days"])
    labelled = []
    for f, c, t, cause in ev:
        if rows.get((f, c, label(t)), 0) > 0:
            primary, contrib = ("late_order", ["demand_surge"]) if cause == "multi" else (cause, ["supplier_underfill"] if cause == "expiry" else [])
            labelled.append({"facility_id": f, "commodity": c, "month": label(t), "primary": primary, "contributing": contrib})
    return labelled
