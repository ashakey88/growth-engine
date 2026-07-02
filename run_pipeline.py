"""ELT runner, split into two stages so they can run as separate workflows.

  ingest  ->  integrations write raw parquet (one per source)
  build   ->  transform raw parquet into the fact tables

  python run_pipeline.py ingest     # stage 1: raw tables
  python run_pipeline.py build      # stage 2: fact tables
  python run_pipeline.py            # both (local convenience)
  python run_pipeline.py shopify    # real Shopify pull + rebuild

ingest_mock()/run_mock()/sync_shopify() are also called by the app's connect
screen and local bootstrap.
"""
from __future__ import annotations

import sys

import config
from ingest import mock_source, storage
from transform import build_fact


# ── Stage 1: ingest (integrations -> raw parquet) ────────────────
def ingest_mock() -> None:
    """Write every source's raw parquet, as if pulled from each API."""
    catalog = mock_source.products()
    lines = mock_source.shopify_line_items(catalog)

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
    storage.write_df(mock_source.order_bank(catalog), config.ORDERBANK_KEY)
    storage.write_df(mock_source.targets(), config.TARGETS_KEY)
    print("ingest: raw parquet written for all sources.")


# ── Stage 2: build (raw parquet -> fact tables) ──────────────────
def build() -> int:
    """Transform the raw parquet into every fact table."""
    return build_fact.build_all()


# ── Convenience: both stages ─────────────────────────────────────
def run_mock() -> int:
    ingest_mock()
    return build()


def _ensure_marketing_mock() -> None:
    """Seed the full mock universe if the raw sources aren't there yet."""
    if not storage.exists(config.GA4_KEY):
        run_mock()


def sync_shopify(store: str, token: str) -> int:
    """Pull real Shopify orders, keep mock marketing lanes, rebuild the fact table."""
    from ingest import shopify

    _ensure_marketing_mock()
    storage.write_df(shopify.fetch_orders(store=store, token=token), config.SHOPIFY_KEY)
    return build_fact.build_all()


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    print(f"=== Growth Engine ELT · {mode} · backend={config.STORAGE_BACKEND} ===")
    if mode == "ingest":
        ingest_mock()
    elif mode == "build":
        n = build()
        print(f"build: {n:,} marketing fact rows.")
    elif mode == "shopify":
        if not config.shopify_configured():
            raise SystemExit("Set SHOPIFY_STORE and SHOPIFY_ACCESS_TOKEN first.")
        sync_shopify(config.SHOPIFY_STORE, config.SHOPIFY_ACCESS_TOKEN)
    else:
        run_mock()
    print("Done.")


if __name__ == "__main__":
    main()
