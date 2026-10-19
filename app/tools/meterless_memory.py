"""Meterless H-MEM as the agents' shared case memory.

Meterless's open-source H-MEM engine (TypeScript, Apache-2.0) runs in a small Node process (meterless/bridge.ts).
This client talks to it with one JSON line per request. If Node or the bridge is missing, MemoryUnavailable is
raised and the pipeline carries on without memory (and says so).
"""
import json
import os
import queue
import shutil
import subprocess
import threading
from pathlib import Path

from ..memory import parse_case

ROOT = Path(__file__).resolve().parent.parent.parent


class MemoryUnavailable(RuntimeError):
    pass


class MeterlessMemory:
    name = "Meterless H-MEM"

    def __init__(self, state_dir=None, timeout=30):
        npx = shutil.which("npx")
        bridge = ROOT / "meterless" / "bridge.ts"
        tsx = ROOT / "meterless" / "node_modules" / ".bin" / ("tsx.cmd" if os.name == "nt" else "tsx")
        if not shutil.which("node") or not npx:
            raise MemoryUnavailable("Node.js is not installed (needed for Meterless H-MEM). Install Node 18+ from nodejs.org.")
        if not bridge.exists():
            raise MemoryUnavailable("meterless/bridge.ts not found.")
        if not tsx.exists():
            raise MemoryUnavailable("Run once: cd meterless && npm install")
        env = dict(os.environ)
        env["MEMORY_DIR"] = str(state_dir or ROOT / ".meterless_state")
        self.timeout = timeout
        self._id = 0
        self._lock = threading.Lock()
        self._q = queue.Queue()
        self._p = subprocess.Popen([str(tsx), "bridge.ts"], cwd=ROOT / "meterless", env=env, stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)
        threading.Thread(target=self._read, daemon=True).start()
        self.info = self._call({"op": "ping"})

    def _read(self):
        for line in self._p.stdout:
            try:
                self._q.put(json.loads(line))
            except ValueError:
                pass

    def _call(self, req):
        with self._lock:
            self._id += 1
            req["id"] = self._id
            self._p.stdin.write(json.dumps(req) + "\n")
            self._p.stdin.flush()
            try:
                while True:
                    resp = self._q.get(timeout=self.timeout)
                    if resp.get("id") == self._id:
                        break
            except queue.Empty:
                raise MemoryUnavailable("Meterless bridge did not answer in time.")
        if not resp.get("ok"):
            raise MemoryUnavailable(resp.get("error", "bridge error"))
        return resp

    def remember(self, text, source="stockwhy:case"):
        return self._call({"op": "remember", "content": text, "source": source})["memoryId"]

    def recall_cases(self, facility_id, commodity):
        res = self._call({"op": "recall", "query": f"CASE {facility_id} {commodity}", "topN": 12, "threshold": 0.05})
        cases = []
        for m in res["memories"]:
            c = parse_case(m["content"])
            if c and c["facility_id"] == facility_id:
                cases.append({**c, "memory_id": m["id"], "relevance": round(m["relevance"], 2)})
        return cases

    def feedback(self, memory_id, kind):
        self._call({"op": "feedback", "memoryId": memory_id, "kind": kind})

    def audit(self, memory_id):
        return self._call({"op": "audit", "memoryId": memory_id})["history"]

    def close(self):
        try:
            self._p.stdin.close()
            self._p.terminate()
        except Exception:  # noqa: BLE001
            pass
