"""End-to-end ELT runner.

  Extract  ->  Load (Parquet to local/R2)  ->  Transform (DuckDB marts)

Uses real Shopify data when credentials are set, otherwise generates mock data
so the whole pipeline runs at zero cost.

    python run_pipeline.py

The run_mock() / run_shopify() helpers are also called directly by the
connect screen in the Streamlit app.
"""
from __future__ import annotations

import config
from ingest import storage
from transform import build_models


def _load_and_build(df) -> int:
    """Write orders to storage and rebuild the DuckDB marts. Returns row count."""
    storage.write_dataframe(df, source="shopify", dataset="orders",
                            date_col="created_at")
    build_models.build()
    return len(df)


def run_mock() -> int:
    """Generate mock orders and build the marts."""
    from ingest import mock_source

    return _load_and_build(mock_source.generate_orders())


def run_shopify(store: str, token: str) -> int:
    """Pull real orders from a Shopify store and build the marts."""
    from ingest import shopify

    return _load_and_build(shopify.fetch_orders(store=store, token=token))


def extract_and_load() -> None:
    if config.shopify_configured():
        print(f"› Extracting orders from Shopify store {config.SHOPIFY_STORE} …")
        n = run_shopify(config.SHOPIFY_STORE, config.SHOPIFY_ACCESS_TOKEN)
    else:
        print("› No Shopify credentials found — generating mock order data …")
        n = run_mock()
    print(f"  loaded {n:,} orders  (backend: {config.STORAGE_BACKEND})")


def main() -> None:
    print("=== Growth Engine ELT ===")
    extract_and_load()
    print("Done. Run the dashboard with:  streamlit run app/streamlit_app.py")


if __name__ == "__main__":
    main()
