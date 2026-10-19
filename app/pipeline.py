"""One investigation, end to end. Used by run.py, the back-test and (later) the UI/API."""
import time

from .agents import critic, drafter, investigator, planner
from .memory import case_text
from .orchestration.meterless_flow import run_branches


def run_investigation(store, question, trace=None, memory=None):
    t0 = time.time()
    ctx = dict(question)
    if trace:
        trace.event("question", **ctx, backend=store.name)
    plan = planner.plan(store, ctx)
    if trace:
        trace.event("plan", **plan)
    if not plan["ok"]:
        return {"question": ctx, "status": "nothing_to_investigate", "reason": plan["reason"]}

    prior = []
    memory_note = None
    if memory is not None:
        try:
            prior = memory.recall_cases(ctx["facility_id"], ctx["commodity"])
            if trace:
                trace.event("memory_recall", engine=memory.name, prior_cases=len(prior))
        except Exception as exc:  # noqa: BLE001
            memory_note = f"Memory unavailable: {exc}"
            memory = None
            if trace:
                trace.event("memory_error", error=str(exc))

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
    top = verdict["ranked"][0]
    same_month = [c for c in prior if c["month"] == ctx["month"] and c["commodity"] == ctx["commodity"]]
    earlier = [c for c in prior if c["commodity"] == ctx["commodity"] and c["month"] < ctx["month"]]
    repeats = [c for c in earlier if c["cause"] == top["hypothesis"]]
    memory_info = None
    if memory is not None or memory_note:
        memory_info = {"engine": getattr(memory, "name", None), "prior_cases": earlier, "repeat_issue": bool(repeats) and not verdict["escalate"],
                       "repeat_cases": repeats, "stored_id": None, "note": memory_note}
        if memory is not None and not verdict["escalate"]:
            try:
                if same_month:
                    memory_info["stored_id"] = same_month[0]["memory_id"]
                else:
                    memory_info["stored_id"] = memory.remember(case_text(ctx, top["hypothesis"], verdict["confidence"]), f"stockwhy:{ctx['month']}")
                if trace:
                    trace.event("memory_store", memory_id=memory_info["stored_id"], repeat_issue=memory_info["repeat_issue"])
            except Exception as exc:  # noqa: BLE001
                memory_info["note"] = f"Memory write failed: {exc}"
    action = None if verdict["escalate"] else drafter.draft(store, ctx, verdict)
    if action and memory_info and memory_info["repeat_issue"]:
        action["process_fix"] = (f"REPEAT ISSUE: the same cause ({top['name'].lower()}) was found at this facility before "
                                 f"({', '.join(c['month'] for c in repeats)}). Raise it with the facility in-charge. " + action["process_fix"])
    out = {"question": ctx, "status": "escalated_to_human" if verdict["escalate"] else "ok", "plan": plan,
           "verdict": verdict, "revised": revised, "failed_branches": failed, "memory": memory_info, "action": action, "seconds": round(time.time() - t0, 2)}
    if trace:
        trace.event("done", status=out["status"], seconds=out["seconds"])
    return out
