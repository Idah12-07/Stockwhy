"""Agent 2: Evidence Investigator. One call = one hypothesis (run as parallel branches)."""
from ..hypotheses import EVIDENCE


def investigate(store, ctx, hypothesis, window=3):
    return EVIDENCE[hypothesis](store, ctx, window)
