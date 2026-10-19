"""One-page web UI (standard library only). The page calls the same run_investigation() the command line uses."""
import json
import re
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from ..pipeline import run_investigation
from ..report import render
from ..trace import Trace

HERE = Path(__file__).resolve().parent


def make_handler(store, memory, data_dir):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _json(self, obj, code=200):
            body = json.dumps(obj, default=str).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path, _, query = self.path.partition("?")
            if path in ("/", "/index.html"):
                body = (HERE / "index.html").read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif path == "/api/options":
                rows = store.query(f"SELECT facility_id, commodity, month, reported_stockout_days FROM {store.t('stock')} "
                                   "WHERE reported_stockout_days > 0 ORDER BY reported_stockout_days DESC LIMIT 80")
                self._json({"backend": store.name, "dataset": str(data_dir),
                            "memory": getattr(memory, "name", None), "stockouts": rows})
            elif path == "/api/source":
                ref = dict(p.split("=", 1) for p in query.split("&") if "=" in p).get("ref", "")
                ref = ref.replace("%23", "#")
                m = re.fullmatch(r"(stock|orders|payments)#(\d+)", ref)
                if not m:
                    return self._json({"error": "unknown reference"}, 400)
                rows = store.query(f"SELECT * FROM {store.t(m.group(1))} WHERE id=?", (int(m.group(2)),))
                self._json({"ref": ref, "row": rows[0] if rows else None})
            else:
                self._json({"error": "not found"}, 404)

        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n) or b"{}")
            if self.path == "/api/investigate":
                q = {k: str(body.get(k, "")) for k in ("facility_id", "commodity", "month")}
                if not all(q.values()):
                    return self._json({"error": "facility_id, commodity and month are required"}, 400)
                trace = Trace("logs", "ui")
                res = run_investigation(store, q, trace, memory=memory)
                self._json({"result": res, "report_md": render(res), "events": trace.events})
            elif self.path == "/api/decision":
                decision = body.get("decision")
                if decision not in ("approve", "reject"):
                    return self._json({"error": "decision must be approve or reject"}, 400)
                rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "decision": decision, "question": body.get("question"),
                       "memo": body.get("memo"), "edited": bool(body.get("edited"))}
                Path("logs").mkdir(exist_ok=True)
                with open("logs/decisions.jsonl", "a") as fh:
                    fh.write(json.dumps(rec) + "\n")
                note = None
                mid = body.get("memory_id")
                if memory is not None and mid:
                    try:
                        memory.feedback(mid, "helpful" if decision == "approve" else "not_helpful")
                        note = "Feedback sent to Meterless H-MEM."
                    except Exception as exc:  # noqa: BLE001
                        note = f"Memory feedback failed: {exc}"
                self._json({"ok": True, "note": note})
            else:
                self._json({"error": "not found"}, 404)

    return H


def serve(store, memory, data_dir, port=8000, host="127.0.0.1"):
    srv = ThreadingHTTPServer((host, port), make_handler(store, memory, data_dir))
    print(f"StockWhy UI on http://{'localhost' if host in ('127.0.0.1', '0.0.0.0') else host}:{port}  (Ctrl+C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
