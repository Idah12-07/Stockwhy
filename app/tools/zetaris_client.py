"""Zetaris integration: the same Store interface as app.store.LocalStore, but every query
runs through Zetaris (federated, in place) over REST.

Settings come from environment variables (put them in .env, never in code):
  ZETARIS_REST_URL   API base ending in /api/v1.0        (direct REST route, default)
  ZETARIS_ORG_ID     numeric organisation ID (Management > Organisation in the Zetaris UI)
  ZETARIS_API_KEY    API key (Management > API Tokens in the Zetaris UI)
  ZETARIS_SCHEMA     the source/database that holds our tables, e.g. TEAM1_STOCKWHY (so SQL reads TEAM1_STOCKWHY.stock)
Optional route: ZETARIS_ROUTE=proxy with ZETARIS_BASE_URL (web UI origin) instead of REST_URL.

Zetaris REST returns values as strings and (as far as the public docs show) rows without
column names, so we derive column names from the SELECT list and convert types ourselves.
"""
import json
import os
import re
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..store import SCHEMAS

_TYPES = {}
for _cols in SCHEMAS.values():
    for _c in _cols.split(","):
        _name, _typ = _c.strip().split()
        _TYPES[_name] = _typ


class ZetarisError(RuntimeError):
    pass


def _inline(sql, params):
    """Replace ? placeholders with safely quoted literals (Zetaris REST takes plain SQL text)."""
    it = iter(params)

    def lit(_):
        v = next(it)
        if v is None:
            return "NULL"
        if isinstance(v, (int, float)):
            return repr(v)
        return "'" + str(v).replace("'", "''") + "'"

    out = re.sub(r"\?", lit, sql)
    try:
        next(it)
        raise ZetarisError("More parameters than placeholders.")
    except StopIteration:
        return out


def _split_top(text):
    parts, depth, cur = [], 0, ""
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    return [p.strip() for p in parts if p.strip()]


def _columns_from_sql(sql):
    m = re.match(r"\s*SELECT\s+(.*?)\s+FROM\s+([\w.]+)", sql, re.I | re.S)
    if not m:
        raise ZetarisError("Cannot work out the column names for: " + sql[:80])
    cols = []
    for item in _split_top(m.group(1)):
        if item == "*":
            table = m.group(2).split(".")[-1]
            cols += [c.strip().split()[0] for c in SCHEMAS[table].split(",")]
            continue
        alias = re.search(r"\s+AS\s+(\w+)\s*$", item, re.I)
        cols.append(alias.group(1) if alias else item.split(".")[-1].strip())
    return cols


def _coerce(name, val):
    if val is None or val == "":
        return None
    typ = _TYPES.get(name)
    if typ == "TEXT":
        return str(val)
    try:
        f = float(val)
    except (TypeError, ValueError):
        return str(val)
    if typ == "INTEGER":
        return int(f)
    return f


class ZetarisStore:
    name = "zetaris (federated, REST)"

    def __init__(self, data_dir=None):
        self.route = os.environ.get("ZETARIS_ROUTE", "rest")
        self.key = self._need("ZETARIS_API_KEY")
        self.org = self._need("ZETARIS_ORG_ID")
        self.schema = os.environ.get("ZETARIS_SCHEMA", "").strip()
        if self.route == "proxy":
            self.base = self._need("ZETARIS_BASE_URL").rstrip("/")
        else:
            self.base = self._need("ZETARIS_REST_URL").rstrip("/")
        self.limit = int(os.environ.get("ZETARIS_QUERY_LIMIT", "10000"))
        self.data_dir = Path(data_dir) if data_dir else None
        self.last_raw = None  # kept so the smoke test can show the raw response shape

    @staticmethod
    def _need(var):
        v = os.environ.get(var, "").strip()
        if not v:
            raise ZetarisError(f"{var} is not set. Copy .env.example to .env and fill it in (see README).")
        return v

    def t(self, table):
        return f"{self.schema}.{table}" if self.schema else table

    def _post(self, path, body):
        req = Request(self.base + path, data=json.dumps(body).encode(), method="POST", headers={
            "Authorization": f"Bearer {self.key}", "X-Org-ID": self.org,
            "X-Request-ID": str(uuid.uuid4()), "Content-Type": "application/json"})
        try:
            with urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode() or "null")
        except HTTPError as e:
            hint = {401: "API key rejected: create a fresh key.", 400: "Check ZETARIS_ORG_ID and that ids are UUIDs.",
                    404: "Wrong URL for this route."}.get(e.code, "")
            raise ZetarisError(f"HTTP {e.code} from Zetaris. {hint} {e.read(300).decode(errors='replace')}") from e
        except (URLError, OSError) as e:
            raise ZetarisError(f"Cannot reach {self.base}: {getattr(e, 'reason', e)}") from e

    def raw(self, sql):
        """Run one SQL statement and return Zetaris's raw JSON response."""
        if self.route == "proxy":
            out = self._post("/api/proxy/sql-editor/sqls/run-query", {"sql": sql, "limit": self.limit})
        else:
            out = self._post("/sql-editor/sqls/run", {"queryId": str(uuid.uuid4()), "sql": sql,
                                                      "source": "SqlEditor", "limit": self.limit})
        self.last_raw = out
        return out

    def query(self, sql, params=()):
        text = _inline(sql, params)
        out = self.raw(text)
        rows = out.get("data") if isinstance(out, dict) else None
        if rows is None:
            raise ZetarisError("Unexpected response shape (no 'data'). Run scripts/zetaris_smoke_test.py and share the output.")
        names = _columns_from_sql(text)
        result = []
        for r in rows:
            if isinstance(r, dict):
                result.append({k: _coerce(k, v) for k, v in r.items()})
            else:
                result.append({n: _coerce(n, v) for n, v in zip(names, r)})
        return result

    def web_notes(self):
        # Public web notices come from Bright Data (or its offline cache), not from Zetaris tables.
        if self.data_dir and (self.data_dir / "web_notes.json").exists():
            return json.loads((self.data_dir / "web_notes.json").read_text())
        return []
