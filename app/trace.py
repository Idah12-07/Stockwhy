"""Agent trace: one JSON line per event, written to logs/."""
import json
import threading
import time
from pathlib import Path


class Trace:
    def __init__(self, log_dir="logs", name="run"):
        Path(log_dir).mkdir(parents=True, exist_ok=True)
        self.path = Path(log_dir) / f"{time.strftime('%Y%m%d-%H%M%S')}_{name}.jsonl"
        self.t0 = time.time()
        self._lock = threading.Lock()

    def event(self, kind, **data):
        rec = {"t": round(time.time() - self.t0, 3), "event": kind, **data}
        with self._lock, open(self.path, "a") as fh:
            fh.write(json.dumps(rec, default=str) + "\n")
