"""Case memory helpers. Memory text is structured so it can be parsed back, never trusted blindly."""
import re

CASE_RE = re.compile(r"CASE facility=(\S+) commodity=(.+?) month=(\d{4}-\d{2}) cause=(\w+) confidence=(\w+)")


def case_text(ctx, cause, confidence):
    return f"CASE facility={ctx['facility_id']} commodity={ctx['commodity']} month={ctx['month']} cause={cause} confidence={confidence}"


def parse_case(content):
    m = CASE_RE.search(content or "")
    if not m:
        return None
    f, c, mo, cause, conf = m.groups()
    return {"facility_id": f, "commodity": c, "month": mo, "cause": cause, "confidence": conf}
