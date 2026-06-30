"""End-to-end ELT runner.

  Extract  ->  Load (Parquet to local/R2)  ->  Transform (DuckDB marts)

Uses real Shopify data when credentials are set, otherwise generates mock data
so the whole pipeline runs at zero cost.

    python run_pipeline.py
"""
from __future__ import annotations

import config
from ingest import storage
from transform import build_models


def extract_and_load() -> None:
    if config.shopify_configured():
        from ingest import shopify

        print(f"› Extracting orders from Shopify store {config.SHOPIFY_STORE} …")
        df = shopify.fetch_orders()
    else:
        from ingest import mock_source

        print("› No Shopify credentials found — generating mock order data …")
        df = mock_source.generate_orders()

    path = storage.write_dataframe(df, source="shopify", dataset="orders",
                                   date_col="created_at")
    print(f"  loaded {len(df):,} orders -> {path}  (backend: {config.STORAGE_BACKEND})")


def main() -> None:
    print("=== Growth Engine ELT ===")
    extract_and_load()
    print("› Transforming …")
    build_models.build()
    print("Done. Run the dashboard with:  streamlit run app/streamlit_app.py")


if __name__ == "__main__":
    main()
