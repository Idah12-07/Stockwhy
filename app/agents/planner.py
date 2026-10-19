"""Agent 1: Planner. Turns the question into hypotheses to test."""
from ..hypotheses import HYPOTHESES


def plan(store, ctx):
    row = store.query(f"SELECT * FROM {store.t('stock')} WHERE facility_id=? AND commodity=? AND month=?",
                      (ctx["facility_id"], ctx["commodity"], ctx["month"]))
    if not row:
        return {"ok": False, "reason": "No stock record for that facility, commodity and month."}
    r = row[0]
    reported = r["reported_stockout_days"]
    if reported <= 0:
        return {"ok": False, "reason": f"No stock-out reported for {ctx['facility_id']} in {ctx['month']}; nothing to investigate."}
    return {"ok": True, "reported_stockout_days": reported, "hypotheses": list(HYPOTHESES), "stock_row": f"stock#{r['id']}"}
