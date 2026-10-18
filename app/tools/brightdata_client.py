"""TODO (Bright Data): fetch public web evidence (KEMSA notices, tenders, news).

Offline mode reads data/<dataset>/web_notes.json instead. Live mode should fetch pages,
extract title/source/url/month/commodity, and return the same note dicts.
"""
import os


def fetch_notes(commodity, months):
    if not os.environ.get("BRIGHTDATA_API_KEY"):
        raise RuntimeError("BRIGHTDATA_API_KEY is not set. Use offline mode or fill in .env")
    raise NotImplementedError("Wire up the Bright Data client here.")
