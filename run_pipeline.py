"""End-to-end ELT runner.

  Extract (mock or real)  ->  per-source parquet  ->  build_fact  ->  fact.parquet

  python run_pipeline.py            # all-mock, zero cost
  python run_pipeline.py shopify    # real Shopify (needs env creds) + mock marketing

The run_mock() / sync_shopify() helpers are also called by the app's connect
screen.
"""
from __future__ import annotations

import sys

import config
from ingest import mock_source, storage
from transform import build_fact


def _ensure_marketing_mock() -> None:
    """Populate GA4/Meta/Google/targets with mock data if not already present,
    so the dashboard is fully populated even when only Shopify is connected."""
    if not storage.exists(config.GA4_KEY):
        storage.write_df(mock_source.ga4_data(), config.GA4_KEY)
    if not storage.exists(config.META_KEY):
        storage.write_df(mock_source.meta_data(), config.META_KEY)
    if not storage.exists(config.GOOGLE_KEY):
        storage.write_df(mock_source.google_ads_data(), config.GOOGLE_KEY)
    if not storage.exists(config.TARGETS_KEY):
        storage.write_df(mock_source.targets(), config.TARGETS_KEY)


def run_mock() -> int:
    """Write mock data for every source + targets, then build the fact table."""
    storage.write_df(mock_source.shopify_orders(), config.SHOPIFY_KEY)
    storage.write_df(mock_source.ga4_data(), config.GA4_KEY)
    storage.write_df(mock_source.meta_data(), config.META_KEY)
    storage.write_df(mock_source.google_ads_data(), config.GOOGLE_KEY)
    storage.write_df(mock_source.targets(), config.TARGETS_KEY)
    return build_fact.build()


def sync_shopify(store: str, token: str) -> int:
    """Pull real Shopify orders, keep mock marketing lanes, rebuild the fact table."""
    from ingest import shopify

    _ensure_marketing_mock()
    storage.write_df(shopify.fetch_orders(store=store, token=token), config.SHOPIFY_KEY)
    return build_fact.build()


def main() -> None:
    print("=== Growth Engine ELT ===")
    if len(sys.argv) > 1 and sys.argv[1] == "shopify":
        if not config.shopify_configured():
            raise SystemExit("Set SHOPIFY_STORE and SHOPIFY_ACCESS_TOKEN first.")
        n = sync_shopify(config.SHOPIFY_STORE, config.SHOPIFY_ACCESS_TOKEN)
    else:
        print("› Generating mock data for all sources …")
        n = run_mock()
    print(f"Done. {n:,} fact rows. Run:  streamlit run app/streamlit_app.py")


if __name__ == "__main__":
    main()
