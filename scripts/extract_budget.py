#!/usr/bin/env python3
"""Turn text from a county budget report (Controller of Budget) into a clean CSV using an NVIDIA model.

  python scripts/extract_budget.py --text report.txt --out data/real/county_health_budget.csv
  python scripts/extract_budget.py --pdf report.pdf --max-chunks 5          (needs: pip install pypdf)
  python scripts/extract_budget.py --text report.txt --dry-run              (no model calls, shows the plan)

Safety rule: the model may only return numbers that appear VERBATIM in the chunk of text it was given.
Any row whose number or county is not found in the text is dropped and counted in the log. Free credits are
limited, so --max-chunks (default 8) caps the number of model calls.
"""
import argparse
import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import load_env  # noqa: E402

load_env()
from app.tools.nvidia_client import NvidiaError, available, chat  # noqa: E402

SYSTEM = ("You extract figures from Kenyan county government budget reports. Return ONLY a JSON array, nothing else. "
          "Each item: {\"county\": str, \"financial_year\": str, \"item\": short label such as 'health budget allocation' or "
          "'health expenditure' or 'pending bills', \"amount\": the number exactly as written in the text without commas, "
          "\"unit\": str such as 'KSh million'}. Only include a number if it appears verbatim in the text and clearly belongs to that "
          "county, year and item. If unsure, leave it out. If there is nothing relevant, return [].")


def read_text(a):
    if a.text:
        return Path(a.text).read_text(errors="replace")
    try:
        from pypdf import PdfReader
    except ImportError:
        sys.exit("To read a PDF directly, run: pip install pypdf   (or copy the text into a .txt file and use --text)")
    return "\n".join((p.extract_text() or "") for p in PdfReader(a.pdf).pages)


def chunks(text, size):
    parts, cur = [], ""
    for para in re.split(r"\n\s*\n", text):
        if len(cur) + len(para) > size and cur:
            parts.append(cur)
            cur = ""
        cur += para + "\n\n"
    if cur.strip():
        parts.append(cur)
    return parts


def grounded(row, chunk):
    flat = chunk.replace(",", "")
    amount = str(row.get("amount", "")).replace(",", "").strip()
    return bool(amount) and amount in flat and str(row.get("county", "")).strip().lower() in chunk.lower()


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--text")
    g.add_argument("--pdf")
    ap.add_argument("--out", default="data/real/county_health_budget.csv")
    ap.add_argument("--chunk-chars", type=int, default=6000)
    ap.add_argument("--max-chunks", type=int, default=8)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    parts = chunks(read_text(a), a.chunk_chars)
    todo = parts[: a.max_chunks]
    print(f"{len(parts)} chunks of text; will send {len(todo)} (limit --max-chunks {a.max_chunks}).")
    if a.dry_run:
        return
    if not available():
        sys.exit("Set NVIDIA_API_KEY and NVIDIA_MODEL in .env first (python scripts/nvidia_smoke_test.py).")
    kept, dropped, tokens, bad_json = [], 0, 0, 0
    for i, ch in enumerate(todo):
        try:
            r = chat([{"role": "system", "content": SYSTEM}, {"role": "user", "content": ch}], max_tokens=1200)
        except NvidiaError as e:
            sys.exit(f"Stopped at chunk {i}: {e}")
        tokens += r["tokens"] or 0
        m = re.search(r"\[.*\]", r["text"], re.S)
        try:
            rows = json.loads(m.group(0)) if m else []
        except ValueError:
            bad_json += 1
            continue
        for row in rows if isinstance(rows, list) else []:
            if isinstance(row, dict) and grounded(row, ch):
                kept.append({**{k: row.get(k, "") for k in ("county", "financial_year", "item", "amount", "unit")}, "chunk": i})
            else:
                dropped += 1
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["county", "financial_year", "item", "amount", "unit", "chunk"])
        w.writeheader()
        w.writerows(kept)
    log = {"chunks_sent": len(todo), "rows_kept": len(kept), "rows_dropped_not_found_in_text": dropped,
           "chunks_with_unreadable_json": bad_json, "tokens": tokens}
    out.with_suffix(".log.json").write_text(json.dumps(log, indent=1))
    print(json.dumps(log))
    print(f"Wrote {out}. Every kept number was found verbatim in the source text; still spot-check a few against the PDF.")


if __name__ == "__main__":
    main()
