#!/usr/bin/env python3
"""Does our NVIDIA key work?   python scripts/nvidia_smoke_test.py   (uses 1 request; keep your free credits)"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import load_env  # noqa: E402

load_env()
from app.tools.nvidia_client import NvidiaError, available, chat  # noqa: E402

print("[1] Settings in .env")
for v in ("NVIDIA_API_KEY", "NVIDIA_MODEL"):
    print(f"    {v}: {'set' if os.environ.get(v, '').strip() else 'MISSING'}")
print(f"    NVIDIA_BASE_URL: {os.environ.get('NVIDIA_BASE_URL', 'default (integrate.api.nvidia.com/v1)')}")
if not available():
    print("    Fill in NVIDIA_API_KEY and NVIDIA_MODEL in .env (copy .env.example) and run again.")
    sys.exit(1)
print("[2] One test request")
try:
    r = chat([{"role": "user", "content": "Reply with the single word: ready"}], max_tokens=20)
except NvidiaError as e:
    print("    FAIL:", e)
    sys.exit(1)
print(f"    reply: {r['text'].strip()[:80]!r}\n    model: {r['model']}   tokens: {r['tokens']}   latency: {r['latency_s']}s")
print("    OK: the NVIDIA connection works.")
