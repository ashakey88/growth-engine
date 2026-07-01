"""The Growth Engine — Streamlit app (Malleson Labs styling).

A thin UI over analytics.py. Pages: Overview, Breakdown, Trend, Data Explorer,
Connect sources, Targets. All metric logic lives in semantics.py / analytics.py.
"""
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parent.parent))
import analytics  # noqa: E402
import config  # noqa: E402
import run_pipeline  # noqa: E402
import semantics as sem  # noqa: E402
from ingest import storage  # noqa: E402

st.set_page_config(page_title="The Growth Engine", page_icon="📊", layout="wide")

# ── Malleson Labs styling ────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=DM+Serif+Display&display=swap');
html, body, [class*="css"], .stApp { font-family: 'Inter', sans-serif; color: #111827; }
.stApp { background: #FFFFFF; }
h1, h2, h3, .ml-serif { font-family: 'DM Serif Display', serif !important; letter-spacing: -0.5px; color: #111827; }
h1 { font-size: 2.2rem !important; }
[data-testid="stSidebar"] { background: #F7F8FA; border-right: 1px solid #E4E8EF; }
[data-testid="stMetric"] {
  background: #FFFFFF; border: 1px solid #E4E8EF; border-radius: 12px;
  padding: 16px 18px; box-shadow: 0 1px 2px rgba(17,24,39,0.04);
}
[data-testid="stMetricLabel"] { color: #64748B; font-weight: 500; }
.stButton>button, .stDownloadButton>button {
  background: #2563EB; color: #fff; border: none; border-radius: 8px;
  font-weight: 600; padding: 8px 18px;
}
.stButton>button:hover, .stDownloadButton>button:hover { background: #1D4ED8; color:#fff; }
.ml-brand { font-family:'DM Serif Display',serif; font-size:22px; color:#111827; }
.ml-eyebrow { font-size:11px; font-weight:700; letter-spacing:0.14em; text-transform:uppercase; color:#2563EB; }
.ml-tile { background:#fff; border:1px solid #E4E8EF; border-radius:12px; padding:18px; text-align:center; }
</style>
""", unsafe_allow_html=True)


@st.cache_resource(show_spinner="Setting up demo data…")
def _bootstrap():
    if not storage.exists(config.FACT_KEY):
        run_pipeline.run_mock()
    return True


@st.cache_resource(show_spinner="Loading data…")
def get_fact():
    return analytics.load_fact()


def get_targets():
    return analytics.load_targets()


def conn_state() -> dict:
    return storage.read_json(config.CONNECTIONS_KEY) or {"active_source": "mock", "shopify_store": None}


def reset_data_caches():
    get_fact.clear()
    _bootstrap.clear()


_bootstrap()

# ── Sidebar: brand + nav + global filters ────────────────────────
with st.sidebar:
    st.markdown('<div class="ml-eyebrow">Malleson Labs</div>'
                '<div class="ml-brand">The Growth Engine</div>', unsafe_allow_html=True)
    st.markdown("---")
    page = st.radio("Navigate", ["Overview", "Breakdown", "Trend", "Data Explorer",
                                 "Connect sources", "Targets"], label_visibility="collapsed")

fact = get_fact()
if fact is None or fact.empty:
    st.error("No data yet. Run `python run_pipeline.py` or reconnect a source.")
    st.stop()

d_min, d_max = analytics.date_bounds(fact)

# Global period + filters live in the sidebar (used by the analytical pages).
FILTER_DIMS = ["geo_region", "marketing_channel", "device", "source"]
if page in ("Overview", "Breakdown", "Trend", "Data Explorer"):
    with st.sidebar:
        st.markdown("**Period**")
        dr = st.date_input("Date range", (d_min, d_max), min_value=d_min, max_value=d_max,
                           label_visibility="collapsed")
        date_from, date_to = (dr if isinstance(dr, tuple) and len(dr) == 2 else (d_min, d_max))
        st.markdown("**Filters**")
        filters = {}
        for dim in FILTER_DIMS:
            opts = sorted([v for v in fact[dim].dropna().unique() if v != sem.NA])
            sel = st.multiselect(sem.nice(dim), opts, default=[])
            if sel:
                filters[dim] = sel
    view = analytics.apply_filters(fact, date_from, date_to, filters)
    targets = get_targets()


# ── Pages ────────────────────────────────────────────────────────
def page_overview():
    st.title("Overview")
    st.caption(f"{date_from} → {date_to}"
               + ("" if conn_state()["active_source"] == "shopify"
                  else "  ·  demo data — connect Shopify for your own numbers"))

    kpi = analytics.totals(view, ["revenue", "orders", "aov", "gross_margin_pct",
                                  "spend", "roas", "conversion_rate", "visits"])
    tgt = {m: analytics.target_total(targets, date_from, date_to, m)
           for m in ("revenue", "orders", "spend", "visits")}

    def card(col, metric):
        val = sem.fmt(metric, kpi[metric])
        delta = None
        if metric in tgt and tgt[metric]:
            pct = (kpi[metric] / tgt[metric] - 1) * 100 if tgt[metric] else 0
            delta = f"{pct:+.0f}% vs target"
        col.metric(sem.nice(metric), val, delta)

    r1 = st.columns(4)
    for c, m in zip(r1, ["revenue", "orders", "aov", "gross_margin_pct"]):
        card(c, m)
    r2 = st.columns(4)
    for c, m in zip(r2, ["spend", "roas", "conversion_rate", "visits"]):
        card(c, m)

    st.subheader("Revenue over time")
    tr = analytics.trend(view, "revenue", "D").set_index("period")
    st.line_chart(tr, y="revenue", height=280)


def page_breakdown():
    st.title("Breakdown")
    dims = ["marketing_channel", "geo_region", "geo_market", "paid_ad_platform",
            "device", "source", "marketing_channel_group"]
    c1, c2 = st.columns([1, 2])
    dim = c1.selectbox("Dimension", dims, format_func=sem.nice)
    metrics = c2.multiselect("Metrics", sem.ALL_METRICS,
                             default=["revenue", "orders", "aov"], format_func=sem.nice)
    if not metrics:
        st.info("Pick at least one metric.")
        return
    tbl = analytics.breakdown(view, dim, metrics)
    st.bar_chart(tbl.set_index(dim), y=metrics[0], height=320)
    _show_table(tbl, [dim], metrics)


def page_trend():
    st.title("Trend")
    c1, c2 = st.columns(2)
    metric = c1.selectbox("Metric", sem.ALL_METRICS,
                          index=sem.ALL_METRICS.index("revenue"), format_func=sem.nice)
    freq = c2.selectbox("Frequency", ["Daily", "Weekly", "Monthly"])
    fmap = {"Daily": "D", "Weekly": "W", "Monthly": "M"}
    tr = analytics.trend(view, metric, fmap[freq]).set_index("period")
    st.subheader(f"{sem.nice(metric)} — {freq.lower()}")
    st.line_chart(tr, y=metric, height=340)


def page_explorer():
    st.title("Data Explorer")
    dims = ["date", "source", "marketing_channel", "geo_region", "geo_market",
            "paid_ad_platform", "device"]
    c1, c2 = st.columns(2)
    gdims = c1.multiselect("Group by", dims, default=["marketing_channel"], format_func=sem.nice)
    metrics = c2.multiselect("Metrics", sem.ALL_METRICS,
                             default=["revenue", "orders", "spend", "roas"], format_func=sem.nice)
    if not gdims or not metrics:
        st.info("Pick at least one dimension and one metric.")
        return
    out = analytics.aggregate(view, gdims, metrics)
    _show_table(out, gdims, metrics)
    raw_csv = out.copy()
    raw_csv.columns = [sem.nice(c) for c in raw_csv.columns]
    st.download_button("Download CSV", raw_csv.to_csv(index=False).encode(),
                       "growth_engine_export.csv", "text/csv")


def _show_table(numeric: pd.DataFrame, dim_cols: list[str], metrics: list[str]):
    """Render a table: metric values formatted to strings, headers as display names."""
    disp = numeric.copy()
    for m in metrics:
        disp[m] = numeric[m].map(lambda v, mm=m: sem.fmt(mm, v))
    disp.columns = [sem.nice(c) for c in disp.columns]
    st.dataframe(disp, use_container_width=True, hide_index=True)


# ── Connect sources ──────────────────────────────────────────────
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


def page_connect():
    conn = conn_state()
    st.title("Connect your data sources")
    st.caption("Link the tools that run your business. We only ever read your data — "
               "never change anything, and you can disconnect any time.")
    cols = st.columns(4)
    for i, src in enumerate(SOURCES):
        with cols[i % 4]:
            with st.container(border=True):
                connected = src["key"] == "shopify" and conn.get("active_source") == "shopify"
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
                        _shopify_form(conn)


def _shopify_form(conn: dict):
    store = st.text_input("Store domain", placeholder="your-store.myshopify.com", key="shp_store")
    token = st.text_input("Admin API access token", type="password", key="shp_token",
                          help="Create a custom app in Shopify admin and copy its Admin API token.")
    st.caption("Use a **dev-store** token — this demo is public.")
    if st.button("Connect & sync", key="shp_go"):
        if not store or not token:
            st.warning("Enter both the store domain and token.")
            return
        try:
            with st.spinner("Pulling your orders from Shopify…"):
                n = run_pipeline.sync_shopify(store.strip(), token.strip())
            storage.write_json({"active_source": "shopify", "shopify_store": store.strip()},
                               config.CONNECTIONS_KEY)
            reset_data_caches()
            st.success(f"Connected. Built {n:,} fact rows.")
            st.rerun()
        except Exception as e:
            st.error(f"Couldn't connect: {e}")
    if conn.get("active_source") == "shopify":
        if st.button("Disconnect & reset to demo data", key="shp_reset"):
            with st.spinner("Resetting…"):
                run_pipeline.run_mock()
            storage.write_json({"active_source": "mock", "shopify_store": None},
                               config.CONNECTIONS_KEY)
            reset_data_caches()
            st.rerun()


# ── Targets ──────────────────────────────────────────────────────
def page_targets():
    st.title("Targets")
    st.caption("Upload daily eCommerce targets. Overview compares actuals against these.")
    cur = get_targets()
    if cur is not None:
        st.write(f"Current targets: **{len(cur)} rows**, "
                 f"{cur['date'].min().date()} → {cur['date'].max().date()}")
    up = st.file_uploader("Targets file (CSV or Parquet)", type=["csv", "parquet"])
    if up:
        df = pd.read_parquet(up) if up.name.endswith("parquet") else pd.read_csv(up)
        ok, msg = analytics.validate_targets(df)
        (st.success if ok else st.error)(msg)
        st.dataframe(df.head(20), use_container_width=True, hide_index=True)
        if ok and st.button("Replace targets"):
            df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
            storage.write_df(df, config.TARGETS_KEY)
            st.success("Targets updated.")
            st.rerun()


PAGES = {
    "Overview": page_overview, "Breakdown": page_breakdown, "Trend": page_trend,
    "Data Explorer": page_explorer, "Connect sources": page_connect, "Targets": page_targets,
}
try:
    PAGES[page]()
except Exception as e:  # diagnostic on Community Cloud; relax later
    st.error(f"Something went wrong rendering this page: {e}")
    st.exception(e)
