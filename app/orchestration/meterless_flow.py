"""Orchestration layer.

Today: a local thread pool with retries, so the pipeline runs with no sponsor access.
TODO (Meterless): replace run_branches() with the Meterless workflow that plans,
branches (one branch per hypothesis), retries and hands off. Keep the signature.
"""
from concurrent.futures import ThreadPoolExecutor


def run_branches(items, fn, trace=None, retries=2, workers=7):
    def guarded(item):
        last = None
        for attempt in range(retries + 1):
            try:
                out = fn(item)
                if trace:
                    trace.event("branch_done", branch=item, attempt=attempt + 1)
                return out
            except Exception as exc:  # noqa: BLE001
                last = exc
                if trace:
                    trace.event("branch_retry", branch=item, attempt=attempt + 1, error=str(exc))
        return {"hypothesis": item, "score": 0.0, "findings": [f"Branch failed: {last}"], "citations": [], "failed": True}

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(guarded, items))
