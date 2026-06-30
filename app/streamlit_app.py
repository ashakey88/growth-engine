"""Growth Engine dashboard (prototype).

Reads the DuckDB marts built by run_pipeline.py. Run with:
    streamlit run app/streamlit_app.py
"""
import sys
from pathlib import Path

import duckdb
import streamlit as st

# Make the project importable when Streamlit runs this file directly.
sys.path.append(str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402

st.set_page_config(page_title="The Growth Engine", page_icon="📊", layout="wide")


@st.cache_data(ttl=60)
def q(sql: str):
    con = duckdb.connect(str(config.DUCKDB_PATH), read_only=True)
    try:
        return con.execute(sql).df()
    finally:
        con.close()


@st.cache_resource(show_spinner="Setting up demo data…")
def _bootstrap():
    """On a fresh (hosted) instance with no data, build it from mock data so
    the app is self-contained and deploys with zero external dependencies."""
    if not config.DUCKDB_PATH.exists():
        from run_pipeline import extract_and_load
        from transform import build_models

        extract_and_load()
        build_models.build()
    return True


_bootstrap()

st.title("The Growth Engine")
st.caption(f"Client: {config.CLIENT_ID} · live commercial view")

# ── Headline KPIs ────────────────────────────────────────────────
totals = q(
    """
    SELECT
        SUM(net_sales)   AS net_sales,
        SUM(orders)      AS orders,
        SUM(gross_profit) AS gross_profit,
        ROUND(100 * SUM(gross_profit) / NULLIF(SUM(net_sales),0), 1) AS margin_pct,
        ROUND(SUM(net_sales) / NULLIF(SUM(orders),0), 2) AS aov
    FROM mart_daily
    """
).iloc[0]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Net revenue", f"£{totals.net_sales:,.0f}")
c2.metric("Orders", f"{int(totals.orders):,}")
c3.metric("Gross margin", f"{totals.margin_pct:.1f}%")
c4.metric("AOV", f"£{totals.aov:,.2f}")

# ── Revenue over time ────────────────────────────────────────────
st.subheader("Revenue & gross profit over time")
daily = q("SELECT order_date, net_sales, gross_profit FROM mart_daily ORDER BY order_date")
st.line_chart(daily, x="order_date", y=["net_sales", "gross_profit"])

# ── Channel contribution ─────────────────────────────────────────
left, right = st.columns(2)
with left:
    st.subheader("Channel contribution")
    channel = q("SELECT channel, net_sales, revenue_share, margin_pct FROM mart_channel")
    st.bar_chart(channel, x="channel", y="net_sales")
    st.dataframe(channel, hide_index=True, use_container_width=True)

with right:
    st.subheader("New vs returning revenue")
    cohort = q(
        """
        SELECT order_date, cohort, SUM(net_sales) AS net_sales
        FROM mart_customers GROUP BY 1,2 ORDER BY 1
        """
    ).pivot(index="order_date", columns="cohort", values="net_sales").fillna(0)
    st.area_chart(cohort)
