"""Agent 3: Critic and Ranker.

Ranks causes, turns scores into contribution shares (evidence-weighted estimates, not
statistics), assigns confidence, and decides whether to re-investigate or escalate.
TODO (NVIDIA): let a reasoning model challenge the ranking and write the explanation.
"""
from ..hypotheses import HYPOTHESES


def rank(results):
    ordered = sorted(results, key=lambda r: r["score"], reverse=True)
    total = sum(r["score"] for r in ordered) or 1.0
    ranked = [{**r, "name": HYPOTHESES[r["hypothesis"]], "weight": r["score"] / total} for r in ordered]
    top = ranked[0]["score"]
    second = ranked[1]["score"] if len(ranked) > 1 else 0.0
    if top < 0.35:
        confidence, unexplained = "low", True
    elif top >= 0.7 and top - second >= 0.2:
        confidence, unexplained = "high", False
    else:
        confidence, unexplained = "medium", False
    return {"ranked": ranked, "confidence": confidence, "unexplained": unexplained,
            "escalate": confidence == "low", "margin": round(top - second, 3)}


def needs_revision(verdict):
    r = verdict["ranked"]
    close_call = len(r) > 1 and r[0]["score"] >= 0.35 and (r[0]["score"] - r[1]["score"]) < 0.15
    return close_call or verdict["unexplained"]


def weak_hypotheses(verdict):
    return [r["hypothesis"] for r in verdict["ranked"][:3]]
