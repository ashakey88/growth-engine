"""Transform layer: DuckDB reads raw Parquet and builds the modelled marts the
dashboard and AI analyst query. This is where the commercial logic lives.

raw orders  ->  fct_orders  ->  mart_daily / mart_channel / mart_customers
"""
from __future__ import annotations

import duckdb

import config
from ingest import storage


def _connect() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(str(config.DUCKDB_PATH))
    if config.STORAGE_BACKEND == "r2":
        con.execute("INSTALL httpfs; LOAD httpfs;")
        con.execute(
            f"""
            CREATE OR REPLACE SECRET r2 (
                TYPE S3,
                KEY_ID '{config.R2_ACCESS_KEY_ID}',
                SECRET '{config.R2_SECRET_ACCESS_KEY}',
                ENDPOINT '{config.R2_ENDPOINT.replace("https://", "")}',
                URL_STYLE 'path'
            );
            """
        )
    return con


def build() -> None:
    orders_glob = storage.read_glob("shopify", "orders")
    con = _connect()

    # ── Fact table: one clean row per order ──────────────────────
    con.execute(
        f"""
        CREATE OR REPLACE TABLE fct_orders AS
        SELECT
            order_id,
            CAST(created_at AS TIMESTAMP)        AS created_at,
            CAST(created_at AS DATE)             AS order_date,
            customer_id,
            channel,
            country,
            gross_sales,
            discounts,
            net_sales,
            cogs,
            shipping,
            total_price,
            net_sales - cogs                     AS gross_profit
        FROM read_parquet('{orders_glob}', hive_partitioning = true);
        """
    )

    # First order date per customer -> new vs returning.
    con.execute(
        """
        CREATE OR REPLACE TABLE dim_customer AS
        SELECT customer_id, MIN(order_date) AS first_order_date
        FROM fct_orders GROUP BY customer_id;
        """
    )

    # ── Daily mart ───────────────────────────────────────────────
    con.execute(
        """
        CREATE OR REPLACE TABLE mart_daily AS
        SELECT
            order_date,
            COUNT(*)                                   AS orders,
            ROUND(SUM(net_sales), 2)                   AS net_sales,
            ROUND(SUM(gross_profit), 2)                AS gross_profit,
            ROUND(SUM(discounts), 2)                   AS discounts,
            ROUND(SUM(net_sales) / COUNT(*), 2)        AS aov,
            ROUND(100 * SUM(gross_profit) / NULLIF(SUM(net_sales), 0), 1)  AS margin_pct,
            ROUND(100 * SUM(discounts) / NULLIF(SUM(gross_sales), 0), 1)   AS discount_rate
        FROM fct_orders
        GROUP BY order_date ORDER BY order_date;
        """
    )

    # ── Channel mart ─────────────────────────────────────────────
    con.execute(
        """
        CREATE OR REPLACE TABLE mart_channel AS
        SELECT
            channel,
            COUNT(*)                                   AS orders,
            ROUND(SUM(net_sales), 2)                   AS net_sales,
            ROUND(SUM(gross_profit), 2)                AS gross_profit,
            ROUND(100 * SUM(gross_profit) / NULLIF(SUM(net_sales), 0), 1)  AS margin_pct,
            ROUND(100 * SUM(net_sales) / SUM(SUM(net_sales)) OVER (), 1)   AS revenue_share
        FROM fct_orders
        GROUP BY channel ORDER BY net_sales DESC;
        """
    )

    # ── New vs returning revenue by day ──────────────────────────
    con.execute(
        """
        CREATE OR REPLACE TABLE mart_customers AS
        SELECT
            o.order_date,
            CASE WHEN o.order_date = c.first_order_date THEN 'new' ELSE 'returning' END AS cohort,
            COUNT(*)                  AS orders,
            ROUND(SUM(o.net_sales),2) AS net_sales
        FROM fct_orders o
        JOIN dim_customer c USING (customer_id)
        GROUP BY 1, 2 ORDER BY 1;
        """
    )

    n = con.execute("SELECT COUNT(*) FROM fct_orders").fetchone()[0]
    con.close()
    print(f"  built marts from {n:,} orders -> {config.DUCKDB_PATH}")


if __name__ == "__main__":
    build()
