"""SEC EDGAR filings client.

Kept out of `market_data` on purpose: EDGAR serves regulatory filings, not
price/fundamentals, so it doesn't fit the MarketDataProvider interface.

SEC's fair access policy requires a descriptive User-Agent identifying the app
and a contact email (config `SEC_EDGAR_USER_AGENT`), and caps traffic at 10
requests/second.
"""
import time

import requests
from flask import current_app

TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession}/{document}"

DEFAULT_FORMS = ("8-K", "10-Q", "10-K")

_TICKER_MAP_TTL_SECONDS = 86400
_ticker_map_cache: tuple[float, dict[str, str]] | None = None
_MIN_INTERVAL_SECONDS = 0.15
_last_call = 0.0


def _get(url: str):
    global _last_call
    wait = _MIN_INTERVAL_SECONDS - (time.monotonic() - _last_call)
    if wait > 0:
        time.sleep(wait)
    _last_call = time.monotonic()

    headers = {"User-Agent": current_app.config["SEC_EDGAR_USER_AGENT"]}
    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()
    return resp.json()


def _ticker_map() -> dict[str, str]:
    global _ticker_map_cache
    if _ticker_map_cache and (time.monotonic() - _ticker_map_cache[0]) < _TICKER_MAP_TTL_SECONDS:
        return _ticker_map_cache[1]

    data = _get(TICKER_MAP_URL)
    mapping = {
        entry["ticker"].upper(): str(entry["cik_str"]).zfill(10)
        for entry in data.values()
    }
    _ticker_map_cache = (time.monotonic(), mapping)
    return mapping


def resolve_cik(symbol: str) -> str | None:
    """Zero-padded 10-digit CIK for a US ticker, or None if SEC doesn't list it."""
    return _ticker_map().get(symbol.upper())


def get_recent_filings(cik: str, forms=DEFAULT_FORMS, limit: int = 20) -> list[dict]:
    data = _get(SUBMISSIONS_URL.format(cik=cik))
    recent = data.get("filings", {}).get("recent", {})

    accessions = recent.get("accessionNumber", [])
    filings = []
    for i, accession in enumerate(accessions):
        form = recent.get("form", [])[i]
        if forms and form not in forms:
            continue
        document = recent.get("primaryDocument", [])[i]
        filings.append({
            "form": form,
            "filing_date": recent.get("filingDate", [])[i],
            "accession_number": accession,
            "url": ARCHIVES_URL.format(
                cik_int=int(cik),
                accession=accession.replace("-", ""),
                document=document,
            ),
        })
        if len(filings) >= limit:
            break
    return filings
