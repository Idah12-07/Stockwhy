"""TODO (Zetaris): federate stock, orders and payments through MCP.

Implement ZetarisStore with the same .query(sql, params) and .web_notes() methods as
app.store.LocalStore, reading ZETARIS_* settings from the environment (see .env.example).
"""
import os


class ZetarisStore:
    name = "zetaris (not implemented yet)"

    def __init__(self):
        if not os.environ.get("ZETARIS_MCP_URL"):
            raise RuntimeError("ZETARIS_MCP_URL is not set. Use --mode offline or fill in .env")
        raise NotImplementedError("Wire up the Zetaris MCP client here.")
