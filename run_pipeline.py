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
    """Populate all non-Shopify sources with mock data if not already present,
    so the platform is fully populated even when only Shopify is connected."""
    if not storage.exists(config.GA4_KEY):
        run_mock()  # simplest: (re)generate the full mock universe


def run_mock() -> int:
    """Generate a full mock dataset across every source, then build all facts.

    This simulates being integrated with all the relevant APIs: each source is
    written as raw parquet, then the fact tables are built from them.
    """
    catalog = mock_source.products()
    lines = mock_source.shopify_line_items(catalog)

    # Raw per-source (as if pulled from each API)
    storage.write_df(catalog, config.SHOPIFY_PRODUCTS_KEY)
    storage.write_df(lines, config.SHOPIFY_LINEITEMS_KEY)
    storage.write_df(mock_source.shopify_orders_from_lines(lines), config.SHOPIFY_KEY)
    storage.write_df(mock_source.shopify_inventory(catalog), config.SHOPIFY_INVENTORY_KEY)
    storage.write_df(mock_source.shopify_returns(lines), config.SHOPIFY_RETURNS_KEY)
    storage.write_df(mock_source.ga4_data(), config.GA4_KEY)
    storage.write_df(mock_source.ga4_items(catalog), config.GA4_ITEMS_KEY)
    storage.write_df(mock_source.meta_data(), config.META_KEY)
    storage.write_df(mock_source.google_ads_data(), config.GOOGLE_KEY)
    storage.write_df(mock_source.microsoft_ads_data(), config.MICROSOFT_KEY)
    storage.write_df(mock_source.tiktok_ads_data(), config.TIKTOK_KEY)
    storage.write_df(mock_source.klaviyo_data(), config.KLAVIYO_KEY)
    storage.write_df(mock_source.search_console_data(), config.GSC_KEY)
    storage.write_df(mock_source.targets(), config.TARGETS_KEY)

    # Build all fact tables from the raw parquet
    return build_fact.build_all()


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
