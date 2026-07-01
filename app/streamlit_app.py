"""The Growth Engine (prototype).

Two views:
  • Connect sources — source grid; Shopify is a working connection that pulls
    real orders, the rest are placeholders (Tier 1 prototype).
  • Dashboard — the commercial marts built by the ELT pipeline.

Run with:  streamlit run app/streamlit_app.py
"""
import json
import sys
from pathlib import Path

import duckdb
import streamlit as st

# Make the project importable when Streamlit runs this file directly.
sys.path.append(str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402
import run_pipeline  # noqa: E402

st.set_page_config(page_title="The Growth Engine", page_icon="📊", layout="wide")

CONN_FILE = config.DATA_DIR / "connections.json"

# Sources shown on the connect screen. Only Shopify is wired up for real.
SOURCES = [
    {"key": "shopify", "name": "Shopify", "icon": "🛍️", "live": True},
    {"key": "meta", "name": "Meta Ads", "icon": "📘", "live": False},
    {"key": "google_ads", "name": "Google Ads", "icon": "🔍", "live": False},
    {"key": "ga4", "name": "Google Analytics 4", "icon": "📈", "live": False},
    {"key": "microsoft", "name": "Microsoft Ads", "icon": "🅼", "live": False},
    {"key": "tiktok", "name": "TikTok Ads", "icon": "🎵", "live": False},
    {"key": "klaviyo", "name": "Klaviyo", "icon": "✉️", "live": False},
    {"key": "gsc", "name": "Search Console", "icon": "🔎", "live": False},
]


# ── Connection state (persisted to a small JSON file) ────────────
def load_conn() -> dict:
    if CONN_FILE.exists():
        return json.loads(CONN_FILE.read_text())
    return {"active_source": "mock", "shopify_store": None}


def save_conn(data: dict) -> None:
    CONN_FILE.write_text(json.dumps(data))


@st.cache_data(ttl=60)
def q(sql: str):
    con = duckdb.connect(str(config.DUCKDB_PATH), read_only=True)
    try:
        return con.execute(sql).df()
    finally:
        con.close()


@st.cache_resource(show_spinner="Setting up demo data…")
def _bootstrap():
    """Fresh instance with no data -> build mock data so the app is self-contained."""
    if not config.DUCKDB_PATH.exists():
        run_pipeline.run_mock()
    return True


_bootstrap()


# ── Connect sources view ─────────────────────────────────────────
def render_sources():
    conn = load_conn()
    st.title("Connect your data sources")
    st.caption(
        "Link the tools that run your business. We only ever *read* your data — "
        "we never change anything, and you can disconnect any time."
    )

    cols = st.columns(4)
    for i, src in enumerate(SOURCES):
        with cols[i % 4]:
            with st.container(border=True):
                connected = (
                    src["key"] == "shopify" and conn.get("active_source") == "shopify"
                )
                st.markdown(f"### {src['icon']}")
                st.markdown(f"**{src['name']}**")
                if connected:
                    st.success("Connected", icon="✅")
                elif src["live"]:
                    st.caption("Not connected")
                else:
                    st.caption("Coming soon")

                if src["live"]:
                    with st.expander("Connect"):
                        _shopify_connect_form(conn)


def _shopify_connect_form(conn: dict):
    store = st.text_input(
        "Store domain", placeholder="your-store.myshopify.com", key="shp_store"
    )
    token = st.text_input(
        "Admin API access token", type="password", key="shp_token",
        help="Create a custom app in your Shopify admin and copy its Admin API token.",
    )
    st.caption("Use a **dev-store** token — this demo is public, so don't paste a live token.")

    if st.button("Connect & sync", type="primary", key="shp_connect"):
        if not store or not token:
            st.warning("Enter both the store domain and token.")
            return
        try:
            with st.spinner("Pulling your orders from Shopify…"):
                n = run_pipeline.run_shopify(store.strip(), token.strip())
            save_conn({"active_source": "shopify", "shopify_store": store.strip()})
            st.cache_data.clear()
            st.success(f"Connected. Synced {n:,} orders.")
            st.rerun()
        except Exception as e:  # surface the real reason to the user
            st.error(f"Couldn't connect: {e}")

    if conn.get("active_source") == "shopify":
        if st.button("Disconnect & reset to demo data", key="shp_disconnect"):
            with st.spinner("Resetting…"):
                run_pipeline.run_mock()
            save_conn({"active_source": "mock", "shopify_store": None})
            st.cache_data.clear()
            st.rerun()


# ── Dashboard view ───────────────────────────────────────────────
def render_dashboard():
    conn = load_conn()
    st.title("The Growth Engine")
    if conn.get("active_source") == "shopify":
        st.caption(f"Live data from {conn.get('shopify_store')}")
    else:
        st.caption("Showing demo data — connect a source to see your own numbers.")

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

    st.subheader("Revenue & gross profit over time")
    daily = q("SELECT order_date, net_sales, gross_profit FROM mart_daily ORDER BY order_date")
    st.line_chart(daily, x="order_date", y=["net_sales", "gross_profit"])

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


# ── Router ───────────────────────────────────────────────────────
st.sidebar.title("The Growth Engine")
page = st.sidebar.radio("Go to", ["Dashboard", "Connect sources"])

if page == "Connect sources":
    render_sources()
else:
    render_dashboard()
