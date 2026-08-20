"""Seed the Asset catalog with equities, cryptoassets and REITs.

CA: S&P/TSX Composite constituents (Wikipedia) — the largest clean, freely
scrapable CA list found for this pass; it's large/mid-cap TSX only, it does
not cover TSXV. US: S&P 500 (Wikipedia). Idempotent — safe to re-run, upserts
by (symbol, exchange).

Enrichment (via yfinance, one get_info() call per asset) fills both the
Asset profile (sector/industry/country/website/logo) and today's
Fundamentals snapshot (price/PE/PB/ROE/D-E/dividend yield/...). Resumable:
each successfully-enriched asset is committed immediately, and a re-run only
retries assets still missing a website, so an interrupted run picks up where
it left off instead of redoing work.

Usage:
    python scripts/seed_universe.py                    # seed + enrich
    python scripts/seed_universe.py --skip-enrichment   # seed symbols/names only
    python scripts/seed_universe.py --limit 20          # cap enrichment calls (smoke test)
    python scripts/seed_universe.py --supplements-only --skip-enrichment
"""
import argparse
import os
import sys
from datetime import date
from io import StringIO

import pandas as pd
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import create_app
from src.data.asset_catalog import CRYPTO_ASSETS, ETF_ASSETS, REIT_ASSETS, SUPPLEMENTAL_ASSETS
from src.extensions import db
from src.models import Asset, Fundamentals, infer_asset_category
from src.resources.jobs._common import get_or_create_snapshot
from src.services.market_data import get_provider

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}
TSX_COMPOSITE_URL = "https://en.wikipedia.org/wiki/S%26P/TSX_Composite_Index"
SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"


def _persisted_category(row):
    return infer_asset_category(
        symbol=row.get('symbol'),
        exchange=row.get('exchange'),
        name=row.get('name'),
        sector=row.get('sector'),
        industry=row.get('industry'),
    )


def _fetch_tables(url):
    resp = requests.get(url, headers=_HEADERS, timeout=20)
    resp.raise_for_status()
    return pd.read_html(StringIO(resp.text))


def fetch_tsx_composite():
    """~220 TSX large/mid-caps (Wikipedia table has no TSXV coverage)."""
    table = _fetch_tables(TSX_COMPOSITE_URL)[3]
    table.columns = ['ticker', 'company', 'sector', 'industry']
    table = table.dropna(subset=['ticker']).drop_duplicates(subset=['ticker'])
    rows = [
        {
            'symbol': row.ticker.strip(),
            'name': row.company.strip() if isinstance(row.company, str) else row.ticker.strip(),
            'sector': row.sector.strip() if isinstance(row.sector, str) else None,
            'industry': row.industry.strip() if isinstance(row.industry, str) else None,
            'exchange': 'TSX',
            'currency': 'CAD',
            # Same class/unit-suffix rule as US (BRK.B -> BRK-B): Wikipedia's
            # ticker for dual-class shares and trust units uses a dot
            # (BBD.B, AP.UN), Yahoo's symbol uses a dash (BBD-B.TO, AP-UN.TO).
            'yahoo_symbol': f"{row.ticker.strip().replace('.', '-')}.TO",
        }
        for row in table.itertuples()
    ]
    for row in rows:
        row['category'] = _persisted_category(row)
    return rows


def fetch_sp500():
    table = _fetch_tables(SP500_URL)[0][['Symbol', 'Security', 'GICS Sector', 'GICS Sub-Industry']]
    table.columns = ['symbol', 'name', 'sector', 'industry']
    table = table.dropna(subset=['symbol']).drop_duplicates(subset=['symbol'])
    rows = [
        {
            'symbol': row.symbol.strip(),
            'name': row.name.strip(),
            'sector': row.sector.strip() if isinstance(row.sector, str) else None,
            'industry': row.industry.strip() if isinstance(row.industry, str) else None,
            # Wikipedia's S&P 500 table doesn't say NYSE vs. NASDAQ per row,
            # and this pass doesn't have a verified free source that does —
            # 'US' is an honest placeholder rather than a guessed split.
            'exchange': 'US',
            'currency': 'USD',
            # Yahoo uses '-' where the ticker itself has a class suffix, e.g. BRK.B -> BRK-B.
            'yahoo_symbol': row.symbol.strip().replace('.', '-'),
        }
        for row in table.itertuples()
    ]
    for row in rows:
        row['category'] = _persisted_category(row)
    return rows


def upsert_asset(row):
    asset = Asset.query.filter_by(symbol=row['symbol'], exchange=row['exchange']).first()
    if asset is None:
        asset = Asset(is_active=True, **row)
        db.session.add(asset)
    else:
        asset.name = row['name']
        asset.yahoo_symbol = row['yahoo_symbol']
        asset.currency = row['currency']
        asset.category = row['category']
        asset.sector = asset.sector or row['sector']
        asset.industry = asset.industry or row['industry']
        asset.country = asset.country or row.get('country')
        asset.is_active = True
    return asset


def _guess_ir_website(website):
    """Best-effort: check the two most common IR path conventions and keep
    whichever answers with a non-error status. Never raises."""
    base = website.rstrip('/')
    for path in ('/investor-relations', '/investors'):
        candidate = f"{base}{path}"
        try:
            resp = requests.head(candidate, headers=_HEADERS, timeout=5, allow_redirects=True)
            if resp.status_code < 400:
                return candidate
        except requests.RequestException:
            continue
    return None


def enrich_assets(assets, provider):
    """Profile (sector/website/...) AND today's Fundamentals snapshot
    (price/PE/ROE/...) from a single get_info() call per asset — calling
    get_profile() and get_fundamentals() separately would fetch the same
    Yahoo payload twice for no reason."""
    enriched, failed = 0, 0
    for i, asset in enumerate(assets, start=1):
        profile, fundamentals_data = provider.get_profile_and_fundamentals(asset.yahoo_symbol)
        if not profile:
            failed += 1
        else:
            if profile.get('sector'):
                asset.sector = profile['sector']
            if profile.get('industry'):
                asset.industry = profile['industry']
            if profile.get('country'):
                asset.country = profile['country']
            if profile.get('website'):
                asset.website = profile['website']
                asset.ir_website = _guess_ir_website(profile['website'])
            if profile.get('logo_url'):
                asset.logo_url = profile['logo_url']
            if profile.get('description'):
                asset.description = profile['description']

            if fundamentals_data:
                snapshot = get_or_create_snapshot(asset.id)
                for key, value in fundamentals_data.items():
                    setattr(snapshot, key, value)

            enriched += 1
            db.session.commit()  # commit per-asset so an interrupted run keeps its progress

        if i % 25 == 0 or i == len(assets):
            print(f"  ...{i}/{len(assets)} ({enriched} enriched, {failed} failed so far)")

    return enriched, failed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skip-enrichment', action='store_true', help="Seed symbols/names only, skip the yfinance profile pass")
    parser.add_argument('--limit', type=int, default=None, help="Cap how many assets to enrich (smoke testing)")
    parser.add_argument(
        '--supplements-only', action='store_true',
        help="Seed only the built-in crypto/REIT catalog (no Wikipedia requests)",
    )
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        if args.supplements_only:
            ca_rows, us_rows = [], []
        else:
            print("Fetching S&P/TSX Composite (CA)...")
            ca_rows = fetch_tsx_composite()
            print(f"  {len(ca_rows)} CA tickers")

            print("Fetching S&P 500 (US)...")
            us_rows = fetch_sp500()
            print(f"  {len(us_rows)} US tickers")

        assets = [upsert_asset(row) for row in ca_rows + us_rows + list(SUPPLEMENTAL_ASSETS)]
        db.session.commit()
        print(
            f"Upserted {len(assets)} assets ({len(ca_rows)} index CA + {len(us_rows)} index US + "
            f"{len(CRYPTO_ASSETS)} crypto + {len(REIT_ASSETS)} REIT + {len(ETF_ASSETS)} ETF catalog rows)."
        )

        if args.skip_enrichment:
            print("Skipping enrichment (--skip-enrichment).")
            return

        provider = get_provider()
        todays_snapshots = {
            row[0] for row in
            db.session.query(Fundamentals.asset_id).filter_by(as_of_date=date.today()).all()
        }
        # `website` only ever comes from the provider profile call, never
        # from the Wikipedia seed; a missing snapshot for today means the
        # fundamentals half specifically is still outstanding (e.g. an asset
        # profiled by an older run, before this script also wrote snapshots).
        # Either gap alone is enough to re-target the asset.
        targets = [a for a in assets if a.website is None or a.id not in todays_snapshots]
        if args.limit:
            targets = targets[:args.limit]
        print(f"Enriching {len(targets)} assets via {provider.__class__.__name__} "
              f"(already-enriched assets skipped)...")
        enriched, failed = enrich_assets(targets, provider)
        print(f"Enrichment done: {enriched} succeeded, {failed} failed (no data / rate-limited).")


if __name__ == '__main__':
    main()
