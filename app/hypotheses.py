"""The seven hypothesis tests. Each one COMPUTES evidence from the data.

Every function returns: {hypothesis, score (0..1), findings [str], citations [str]}.
Nothing here reads the planted cause; it only reads the tables.
"""
from statistics import mean, median

from .months import shift

HYPOTHESES = {
    "late_order": "Late or missed ordering",
    "supplier_underfill": "Supplier under-fill (facility-specific)",
    "payment_arrears": "Payment arrears (county-wide supply squeeze)",
    "demand_surge": "Demand surge",
    "record_error": "Stock-record error",
    "expiry": "Expiry or wastage",
    "national_disruption": "National supply disruption",
}


def _cap(x):
    return max(0.0, min(1.0, x))


def _baseline(store, ctx, window):
    months = [shift(ctx["month"], -k) for k in range(1, window + 1)]
    marks = ",".join("?" * len(months))
    rows = store.query(
        f"SELECT consumed FROM stock WHERE facility_id=? AND commodity=? AND month IN ({marks})",
        (ctx["facility_id"], ctx["commodity"], *months))
    return mean(r["consumed"] for r in rows) if rows else 0.0


def _row(store, ctx, month):
    r = store.query("SELECT * FROM stock WHERE facility_id=? AND commodity=? AND month=?",
                    (ctx["facility_id"], ctx["commodity"], month))
    return r[0] if r else None


def _order(store, ctx):
    r = store.query("SELECT * FROM orders WHERE facility_id=? AND commodity=? AND month=?",
                    (ctx["facility_id"], ctx["commodity"], shift(ctx["month"], -1)))
    return r[0] if r else None


def _fills(store, ctx, month, exclude_target=True):
    sql = "SELECT qty_delivered*1.0/qty_requested AS f FROM orders WHERE commodity=? AND month=? AND qty_requested>0"
    params = [ctx["commodity"], month]
    if exclude_target:
        sql += " AND facility_id<>?"
        params.append(ctx["facility_id"])
    return [r["f"] for r in store.query(sql, params)]


def _peer_drop(store, ctx):
    cur = _fills(store, ctx, shift(ctx["month"], -1))
    hist = []
    for k in range(3, 10):
        hist += _fills(store, ctx, shift(ctx["month"], -k))
    if not cur or not hist:
        return 0.0, 0.0, 0.0
    c, h = median(cur), median(hist)
    return _cap((h - c) / (0.5 * h)), c, h


def late_order(store, ctx, window):
    o = _order(store, ctx)
    if not o:
        return {"hypothesis": "late_order", "score": 0.6,
                "findings": ["No order record found for the cycle before the stock-out."], "citations": []}
    late = store.query("SELECT CAST(julianday(?) - julianday(?) AS INTEGER) AS d", (o["order_date"], o["cutoff_date"]))[0]["d"]
    slipped = o["delivery_month"] > shift(o["month"], 1)
    score = _cap(late / 10)
    f = [f"Order for {o['month']} was placed {late} day(s) {'after' if late > 0 else 'before'} the cycle cut-off ({o['cutoff_date']})."]
    if slipped:
        f.append(f"Delivery slipped to {o['delivery_month']} instead of {shift(o['month'], 1)}.")
    return {"hypothesis": "late_order", "score": score, "findings": f, "citations": [f"orders#{o['id']}"]}


def supplier_underfill(store, ctx, window):
    o = _order(store, ctx)
    _, cur_peer, _ = _peer_drop(store, ctx)
    if not o or o["qty_requested"] <= 0 or not cur_peer:
        return {"hypothesis": "supplier_underfill", "score": 0.0, "findings": ["No comparable order data."], "citations": []}
    own = o["qty_delivered"] / o["qty_requested"]
    score = _cap(max(0.0, cur_peer - own) / (0.5 * cur_peer))
    return {"hypothesis": "supplier_underfill", "score": score,
            "findings": [f"This facility received {own:.0%} of its order; other facilities received a median {cur_peer:.0%} for the same commodity and cycle."],
            "citations": [f"orders#{o['id']}"]}


def payment_arrears(store, ctx, window):
    drop, cur, hist = _peer_drop(store, ctx)
    months = [shift(ctx["month"], -k) for k in range(0, 4)]
    marks = ",".join("?" * len(months))
    pays = store.query(f"SELECT * FROM payments WHERE month IN ({marks}) AND county_arrears_flag=1", months)
    major = [p for p in pays if p["amount_owed_kes"] >= 30_000_000]
    factor = 1.0 if major else 0.2
    f = [f"County-wide median fill for this commodity fell to {cur:.0%} from a typical {hist:.0%}."]
    if major:
        f.append(f"County arrears of about KES {max(p['amount_owed_kes'] for p in major) / 1e6:.0f}M recorded in the same period.")
    else:
        f.append("No major county arrears recorded in the same period.")
    return {"hypothesis": "payment_arrears", "score": _cap(drop * factor), "findings": f,
            "citations": [f"payments#{p['id']}" for p in major]}


def demand_surge(store, ctx, window):
    r = _row(store, ctx, ctx["month"])
    base = _baseline(store, ctx, window)
    if not r or base <= 0:
        return {"hypothesis": "demand_surge", "score": 0.0, "findings": ["No baseline available."], "citations": []}
    ratio = r["consumed"] / base
    return {"hypothesis": "demand_surge", "score": _cap((ratio - 1) / 0.6),
            "findings": [f"Issues in {ctx['month']} were {ratio:.0%} of the {window}-month average."],
            "citations": [f"stock#{r['id']}"]}


def record_error(store, ctx, window):
    r = _row(store, ctx, ctx["month"])
    base = _baseline(store, ctx, window)
    if not r or base <= 0:
        return {"hypothesis": "record_error", "score": 0.0, "findings": ["No baseline available."], "citations": []}
    reported = r["reported_stockout_days"] >= 5
    normal_use = r["consumed"] >= 0.85 * base
    stock_left = r["closing"] >= 0.25 * base
    # A record conflict needs stock to actually remain at month end. If nothing is left, the stock-out is real.
    score = 1.0 if (reported and normal_use and stock_left) else 0.5 if (reported and stock_left) else 0.0
    return {"hypothesis": "record_error", "score": score,
            "findings": [f"Reported {r['reported_stockout_days']} stock-out day(s), but issues were {r['consumed'] / base:.0%} of normal and {r['closing']:.0f} units remained at month end."
                         if reported else "No stock-out reported, so no record conflict."],
            "citations": [f"stock#{r['id']}"]}


def expiry(store, ctx, window):
    base = _baseline(store, ctx, window)
    rows = [x for x in (_row(store, ctx, ctx["month"]), _row(store, ctx, shift(ctx["month"], -1))) if x]
    if not rows or base <= 0:
        return {"hypothesis": "expiry", "score": 0.0, "findings": ["No baseline available."], "citations": []}
    w = max(rows, key=lambda x: x["wastage"])
    return {"hypothesis": "expiry", "score": _cap(w["wastage"] / base / 0.5),
            "findings": [f"{w['wastage']:.0f} units written off in {w['month']} ({w['wastage'] / base:.0%} of a normal month's use)."],
            "citations": [f"stock#{w['id']}"]}


def national_disruption(store, ctx, window):
    drop, cur, hist = _peer_drop(store, ctx)
    months = {shift(ctx["month"], -k) for k in range(0, 3)}
    hits = [n for n in store.web_notes() if n["commodity"] == ctx["commodity"] and n["month"] in months]
    factor = 1.0 if hits else 0.25
    f = [f"County-wide median fill for this commodity was {cur:.0%} versus a typical {hist:.0%}."]
    f += [f"Public notice found: {n['title']} ({n['source']})." for n in hits] or ["No public notice found for this commodity in the period."]
    return {"hypothesis": "national_disruption", "score": _cap(drop * factor), "findings": f,
            "citations": [n["url"] for n in hits]}


EVIDENCE = {
    "late_order": late_order, "supplier_underfill": supplier_underfill, "payment_arrears": payment_arrears,
    "demand_surge": demand_surge, "record_error": record_error, "expiry": expiry,
    "national_disruption": national_disruption,
}
