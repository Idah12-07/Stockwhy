#!/usr/bin/env python3
"""Tests our NVIDIA client and the budget extractor against a FAKE OpenAI-style server (not NVIDIA).
Run: python scripts/test_nvidia_client.py"""
import json
import os
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
GOOD = "nvapi-test"
REPLY = json.dumps([
    {"county": "Nakuru", "financial_year": "2021/22", "item": "health budget allocation", "amount": "1234.5", "unit": "KSh million"},
    {"county": "Nakuru", "financial_year": "2021/22", "item": "health expenditure", "amount": "999.9", "unit": "KSh million"},  # not in the text
])


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        if self.headers.get("Authorization") != f"Bearer {GOOD}":
            self.send_response(401); self.end_headers(); self.wfile.write(b'{"error":"bad key"}'); return
        n = int(self.headers["Content-Length"]); body = json.loads(self.rfile.read(n))
        sys_msg = body["messages"][0]["content"]
        content = REPLY if "extract figures" in sys_msg else "ready"
        out = json.dumps({"model": body["model"], "choices": [{"message": {"content": content}}],
                          "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(out)


srv = ThreadingHTTPServer(("127.0.0.1", 8931), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
os.environ.update(NVIDIA_BASE_URL="http://127.0.0.1:8931/v1", NVIDIA_MODEL="test-model", NVIDIA_API_KEY=GOOD)
from app.tools.nvidia_client import NvidiaError, chat  # noqa: E402

fails = 0


def check(name, ok):
    global fails
    fails += not ok
    print(("PASS " if ok else "FAIL ") + name)


r = chat([{"role": "user", "content": "hi"}])
check("chat returns text, tokens and latency", r["text"] == "ready" and r["tokens"] == 15 and "latency_s" in r)
os.environ["NVIDIA_API_KEY"] = "wrong"
try:
    chat([{"role": "user", "content": "hi"}]); check("bad key raises a clear error", False)
except NvidiaError as e:
    check("bad key raises a clear error", "401" in str(e) and "wrong" not in str(e))
os.environ["NVIDIA_API_KEY"] = GOOD
d = Path(tempfile.mkdtemp())
(d / "r.txt").write_text("Nakuru County health budget allocation FY 2021/22 was KSh 1,234.5 million.\n")
res = subprocess.run([sys.executable, "scripts/extract_budget.py", "--text", str(d / "r.txt"), "--out", str(d / "o.csv")],
                     cwd=ROOT, env=dict(os.environ), capture_output=True, text=True)
rows = (d / "o.csv").read_text().strip().splitlines() if (d / "o.csv").exists() else []
check("extractor keeps the grounded number", any("1234.5" in x for x in rows))
check("extractor drops the number not found in the text", not any("999.9" in x for x in rows) and '"rows_dropped_not_found_in_text": 1' in (d / "o.log.json").read_text())
sys.exit(1 if fails else 0)
