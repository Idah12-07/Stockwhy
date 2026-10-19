"""Agent 4: Action Drafter. Drafts actions for a human to approve. Never sends anything."""
import math

from ..months import shift

FIXES = {
    "late_order": "Move this facility's order submission earlier in the cycle and add a reminder before the cut-off.",
    "supplier_underfill": "Escalate the short delivery to the supplier and request a back-order or substitution.",
    "payment_arrears": "Raise the unpaid supplier invoices with the county finance office; fill rates are unlikely to recover until they are cleared.",
    "demand_surge": "Review the facility's reorder quantity and add a safety buffer for the higher demand.",
    "record_error": "Verify the physical count and correct the stock report before any emergency order is placed.",
    "expiry": "Review stock rotation and near-expiry redistribution at this facility.",
    "national_disruption": "Check the supplier notice, seek alternative sources, and ration stock across facilities.",
}


def _km(a, b):
    r = 6371
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dphi, dl = p2 - p1, math.radians(b[1] - a[1])
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def draft(store, ctx, verdict):
    top = verdict["ranked"][0]
    prev = shift(ctx["month"], -1)
    coords = {r["facility_id"]: (r["lat"], r["lon"]) for r in store.query(f"SELECT * FROM {store.t('facilities')}")}
    three = [shift(ctx["month"], -k) for k in (1, 2, 3)]
    base_rows = store.query(f"SELECT AVG(consumed) AS a FROM {store.t('stock')} WHERE facility_id=? AND commodity=? AND month IN (?,?,?)",
                            (ctx["facility_id"], ctx["commodity"], *three))
    normal = base_rows[0]["a"] or 0
    prev3 = [shift(prev, -k) for k in (1, 2, 3)]
    use = {r["facility_id"]: r["avg_use"] for r in store.query(
        f"SELECT facility_id, AVG(consumed) AS avg_use FROM {store.t('stock')} WHERE commodity=? AND month IN (?,?,?) GROUP BY facility_id",
        (ctx["commodity"], *prev3))}
    peers = [{**r, "avg_use": use.get(r["facility_id"])} for r in store.query(
        f"SELECT id, facility_id, closing FROM {store.t('stock')} WHERE commodity=? AND month=? AND facility_id<>?",
        (ctx["commodity"], prev, ctx["facility_id"]))]
    options = []
    for p in peers:
        if p["avg_use"] and p["closing"] / p["avg_use"] >= 1.2:
            options.append({**p, "months": p["closing"] / p["avg_use"],
                            "km": _km(coords[ctx["facility_id"]], coords[p["facility_id"]])})
    options.sort(key=lambda o: o["km"])
    transfer = None
    if options and normal:
        o = options[0]
        qty = int(min(o["closing"] * 0.4, normal))
        transfer = {"from": o["facility_id"], "to": ctx["facility_id"], "commodity": ctx["commodity"], "quantity": qty,
                    "distance_km": round(o["km"], 1), "donor_months_of_stock": round(o["months"], 1), "citation": f"stock#{o['id']}"}
    note = "Treat as a draft: this facility's stock report conflicts with its issues data." if top["hypothesis"] == "record_error" else None
    memo = (f"DRAFT for approval. Subject: {ctx['commodity']} stock-out at {ctx['facility_id']} ({ctx['month']}). "
            f"Most likely cause: {top['name'].lower()} (confidence {verdict['confidence']}). "
            + (f"Requested: transfer of {transfer['quantity']} units from {transfer['from']} ({transfer['distance_km']} km, {transfer['donor_months_of_stock']} months of stock). " if transfer and top["hypothesis"] != "record_error" else "")
            + (f"Emergency requisition suggested: {int(normal * 1.5)} units (1.5 months of normal use). " if normal and top["hypothesis"] != "record_error" else "")
            + (note or ""))
    return {"transfer": transfer if top["hypothesis"] != "record_error" else None, "memo": memo,
            "process_fix": FIXES[top["hypothesis"]], "requires_human_approval": True}
