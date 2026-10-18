"""TODO (NVIDIA): reasoning and extraction on NVIDIA-hosted models.

Planned uses: (1) the Critic weighs conflicting evidence and writes the explanation in plain
language, (2) a smaller model extracts fields from payment and tender documents.
Record tokens, cost and latency per call in the trace.
"""
import os


def reason(prompt):
    if not os.environ.get("NVIDIA_API_KEY"):
        return None  # offline: deterministic baseline wording is used instead
    raise NotImplementedError("Wire up the NVIDIA client here.")
