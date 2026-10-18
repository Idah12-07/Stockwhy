"""One investigation, end to end. Used by run.py, the back-test and (later) the UI/API."""
import time

from .agents import critic, drafter, investigator, planner
from .orchestration.meterless_flow import run_branches


def run_investigation(store, question, trace=None):
    t0 = time.time()
    ctx = dict(question)
    if trace:
        trace.event("question", **ctx, backend=store.name)
    plan = planner.plan(store, ctx)
    if trace:
        trace.event("plan", **plan)
    if not plan["ok"]:
        return {"question": ctx, "status": "nothing_to_investigate", "reason": plan["reason"]}

    results = run_branches(plan["hypotheses"], lambda h: investigator.investigate(store, ctx, h, window=3), trace)
    verdict = critic.rank(results)
    revised = False
    if critic.needs_revision(verdict):
        revised = True
        weak = critic.weak_hypotheses(verdict)
        if trace:
            trace.event("revision", reason="close call or weak evidence", hypotheses=weak, window=6)
        again = run_branches(weak, lambda h: investigator.investigate(store, ctx, h, window=6), trace)
        merged = {r["hypothesis"]: r for r in results}
        for r in again:
            merged[r["hypothesis"]] = r
        verdict = critic.rank(list(merged.values()))
    if trace:
        trace.event("verdict", confidence=verdict["confidence"], escalate=verdict["escalate"],
                    ranking=[(r["hypothesis"], round(r["score"], 2)) for r in verdict["ranked"]])

    failed = [r["hypothesis"] for r in verdict["ranked"] if r.get("failed")]
    if failed:
        verdict["escalate"] = True  # a branch could not be checked, so do not act on a partial picture
        if trace:
            trace.event("degraded", failed_branches=failed)
    action = None if verdict["escalate"] else drafter.draft(store, ctx, verdict)
    out = {"question": ctx, "status": "escalated_to_human" if verdict["escalate"] else "ok", "plan": plan,
           "verdict": verdict, "revised": revised, "failed_branches": failed, "action": action, "seconds": round(time.time() - t0, 2)}
    if trace:
        trace.event("done", status=out["status"], seconds=out["seconds"])
    return out
