"""The Growth Engine — Streamlit app (Malleson Labs styling).

Two parts, mirroring the eCommerce app:
  • Report     — KPI report with period + comparison: Summary cards, Trends,
                 Channels / Regions / Devices sections.
  • Data Table — a simplified flexible table (any dimensions x metrics + export).
Plus Connect sources and Targets utilities. All metric logic lives in
semantics.py / analytics.py.
"""
import os
import sys

# Local modules must win over any same-named site-packages ("analytics",
# "semantics"), so insert the project root at the FRONT of sys.path.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

import altair as alt  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

import analytics  # noqa: E402
import config  # noqa: E402
import run_pipeline  # noqa: E402
import semantics as sem  # noqa: E402
from ingest import storage  # noqa: E402

st.set_page_config(page_title="The Growth Engine", page_icon="📊", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=DM+Serif+Display&display=swap');
html, body, [class*="css"], .stApp { font-family:'Inter',sans-serif; color:#111827; }
.stApp { background:#FFFFFF; }
h1,h2,h3,.ml-serif { font-family:'DM Serif Display',serif !important; letter-spacing:-0.5px; color:#111827; }
h1 { font-size:2.1rem !important; }
[data-testid="stSidebar"] { background:#F7F8FA; border-right:1px solid #E4E8EF; }
.stButton>button,.stDownloadButton>button { background:#2563EB; color:#fff; border:none; border-radius:8px; font-weight:600; padding:8px 18px; }
.stButton>button:hover,.stDownloadButton>button:hover { background:#1D4ED8; color:#fff; }
.ml-brand { font-family:'DM Serif Display',serif; font-size:22px; color:#111827; }
.ml-eyebrow { font-size:11px; font-weight:700; letter-spacing:0.14em; text-transform:uppercase; color:#2563EB; }
.kpi-name { font-size:11px; color:#64748B; font-weight:600; text-transform:uppercase; letter-spacing:0.06em; }
.kpi-value { font-family:'DM Serif Display',serif; font-size:30px; color:#111827; line-height:1.1; margin:2px 0 8px; }
.pill { display:inline-block; border-radius:999px; padding:3px 10px; font-size:11px; font-weight:700; margin:0 6px 4px 0; white-space:nowrap; }
.pill.up { background:#DCFCE7; color:#15803D; }
.pill.down { background:#FEE2E2; color:#B91C1C; }
.pill.neutral { background:#F1F5F9; color:#64748B; }
</style>
""", unsafe_allow_html=True)

KPI_GROUPS = {
    "Business Summary": ["revenue", "visits", "orders", "conversion_rate", "aov"],
    "eCommerce Funnel": ["engagement_rate", "add_to_cart_rate", "checkout_rate",
                         "checkout_completion_rate", "cart_abandonment_rate"],
    "Paid Funnel": ["spend", "roas", "cost_per_visit", "cost_per_add_to_cart",
                    "cost_per_checkout", "cost_per_order"],
}
ALL_KPIS = [m for g in KPI_GROUPS.values() for m in g]


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


def reset_caches():
    get_fact.clear()
    _bootstrap.clear()


def fmt_pct(p):
    return "—" if p is None else f"{p:+.0f}%"


def delta_color(metric, pct):
    if pct is None:
        return "#94A3B8"
    good = pct >= 0
    if sem.metric_meta(metric)["cf"] == "reverse":
        good = not good
    return "#16A34A" if good else "#DC2626"


_bootstrap()

with st.sidebar:
    st.markdown('<div class="ml-eyebrow">Malleson Labs</div>'
                '<div class="ml-brand">The Growth Engine</div>', unsafe_allow_html=True)
    st.markdown("---")
    page = st.radio("Navigate", ["Report", "Data Table", "Connect sources", "Targets"],
                    label_visibility="collapsed")

fact = get_fact()
if fact is None or fact.empty:
    st.error("No data yet. Run `python run_pipeline.py` or reconnect a source.")
    st.stop()

ref = fact["date"].max().date()
FILTER_DIMS = ["marketing_channel_group", "marketing_channel", "paid_ad_platform",
               "geo_region", "geo_market", "device"]

if page in ("Report", "Data Table"):
    with st.sidebar:
        st.markdown("**Period**")
        period = st.selectbox("Period", analytics.PERIODS,
                              index=analytics.PERIODS.index("Month to Date"),
                              label_visibility="collapsed")
        comparison = st.selectbox("Compare", ["vs Last Year", "vs Prior Period"],
                                  label_visibility="collapsed")
        st.markdown("**Filters**")
        filters = {}
        for dim in FILTER_DIMS:
            opts = sorted([v for v in fact[dim].dropna().unique() if v != sem.NA])
            sel = st.multiselect(sem.nice(dim), opts, default=[])
            if sel:
                filters[dim] = sel
    cur = analytics.resolve_period(period, ref)
    cmp = analytics.ly_range(*cur) if comparison == "vs Last Year" else analytics.prior_period(*cur)
    cmp_label = "LY" if comparison == "vs Last Year" else "Prior"
    targets = get_targets()


# ── Report sections ──────────────────────────────────────────────
def render_summary():
    for group, metrics in KPI_GROUPS.items():
        st.markdown(f"#### {group}")
        rows = analytics.kpi_rows(fact, metrics, cur, cmp, targets, filters)
        cols = st.columns(min(len(metrics), 5))
        for i, row in enumerate(rows):
            with cols[i % len(cols)]:
                _kpi_card(row)


def _pill(metric, pct, label):
    if pct is None:
        return f'<span class="pill neutral">— {label}</span>'
    good = pct >= 0
    if sem.metric_meta(metric)["cf"] == "reverse":
        good = not good
    cls = "up" if good else "down"
    arrow = "▲" if pct >= 0 else "▼"
    return f'<span class="pill {cls}">{arrow} {abs(pct):.0f}% {label}</span>'


def _spark_chart(spark, metric):
    color = "#2563EB"
    base = alt.Chart(spark).encode(
        x=alt.X("period:T", axis=None),
        y=alt.Y(f"{metric}:Q", axis=None, scale=alt.Scale(zero=False)),
    )
    area = base.mark_area(opacity=0.12, color=color)
    line = base.mark_line(color=color, strokeWidth=2.5)
    return (area + line).properties(height=56).configure_view(strokeWidth=0)


def _kpi_card(row):
    m = row["metric"]
    with st.container(border=True):
        st.markdown(
            f'<div class="kpi-name">{sem.nice(m)}</div>'
            f'<div class="kpi-value">{sem.fmt(m, row["value"])}</div>'
            f'<div>{_pill(m, row["delta_pct"], cmp_label)}'
            f'{_pill(m, row["vtarg_pct"], "Targ")}</div>',
            unsafe_allow_html=True)
        spark = analytics.sparkline(fact, m, cur[1], 8, filters)
        if len(spark) > 1:
            st.altair_chart(_spark_chart(spark, m), use_container_width=True)


def render_trends():
    c1, c2 = st.columns(2)
    metric = c1.selectbox("Metric", ALL_KPIS, index=ALL_KPIS.index("revenue"),
                          format_func=sem.nice, key="tr_metric")
    freq = c2.selectbox("Frequency", ["Weekly", "Daily", "Monthly"], key="tr_freq")
    fmap = {"Daily": "D", "Weekly": "W", "Monthly": "M"}
    cur_df = analytics.apply_filters(fact, cur[0], cur[1], filters)
    ly = analytics.ly_range(*cur)
    ly_df = analytics.apply_filters(fact, ly[0], ly[1], filters)
    ty = analytics.trend(cur_df, metric, fmap[freq]).reset_index(drop=True)
    lyt = analytics.trend(ly_df, metric, fmap[freq]).reset_index(drop=True)
    chart = pd.DataFrame({"TY": ty[metric]}) if not ty.empty else pd.DataFrame({"TY": []})
    if not lyt.empty and not ty.empty:
        vals = list(lyt[metric].values)[:len(ty)]
        vals += [None] * (len(ty) - len(vals))
        chart["LY"] = vals
    st.markdown(f"**{sem.nice(metric)} — {period} ({freq.lower()}), TY vs LY**")
    st.line_chart(chart, height=340)


def _comparison_section(dimension, metrics):
    tbl = analytics.comparison_table(fact, dimension, metrics, cur, cmp, filters)
    disp = pd.DataFrame({sem.nice(dimension): tbl[dimension]})
    for m in metrics:
        disp[sem.nice(m)] = tbl[m].map(lambda v, mm=m: sem.fmt(mm, v))
        disp[f"vs {cmp_label}"] = tbl[f"{m}__vs%"].map(fmt_pct)
    st.caption(f"{cur[0]} → {cur[1]}  vs {cmp_label} ({cmp[0]} → {cmp[1]})")
    st.dataframe(disp, use_container_width=True, hide_index=True)


BIZ = ["revenue", "visits", "orders", "conversion_rate", "aov", "spend", "roas"]


def page_report():
    st.title("Report")
    st.caption(f"{period} · {cur[0]} → {cur[1]}  ·  {comparison.lower()}"
               + ("" if conn_state()["active_source"] == "shopify" else "  ·  demo data"))
    tabs = st.tabs(["Summary", "Trends", "Channels", "Regions", "Devices"])
    with tabs[0]:
        render_summary()
    with tabs[1]:
        render_trends()
    with tabs[2]:
        _comparison_section("marketing_channel", BIZ)
    with tabs[3]:
        _comparison_section("geo_market", BIZ)
    with tabs[4]:
        _comparison_section("device", ["revenue", "visits", "orders", "conversion_rate", "aov"])


# ── Data Table (simplified explorer) ─────────────────────────────
def page_data_table():
    st.title("Data Table")
    st.caption(f"{period} · {cur[0]} → {cur[1]}")
    view = analytics.apply_filters(fact, cur[0], cur[1], filters)
    dims = ["date", "source", "marketing_channel_group", "marketing_channel",
            "paid_ad_platform", "geo_region", "geo_market", "device"]
    c1, c2 = st.columns(2)
    gdims = c1.multiselect("Dimensions", dims, default=["marketing_channel"], format_func=sem.nice)
    metrics = c2.multiselect("Metrics", sem.ALL_METRICS,
                             default=["revenue", "orders", "spend", "roas"], format_func=sem.nice)
    if not gdims or not metrics:
        st.info("Pick at least one dimension and one metric.")
        return
    out = analytics.aggregate(view, gdims, metrics)
    disp = out.copy()
    for m in metrics:
        disp[m] = out[m].map(lambda v, mm=m: sem.fmt(mm, v))
    disp.columns = [sem.nice(c) for c in disp.columns]
    st.dataframe(disp, use_container_width=True, hide_index=True)
    csv = out.copy()
    csv.columns = [sem.nice(c) for c in csv.columns]
    st.download_button("Download CSV", csv.to_csv(index=False).encode(),
                       "growth_engine_export.csv", "text/csv")


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


def _shopify_form(conn):
    store = st.text_input("Store domain", placeholder="your-store.myshopify.com", key="shp_store")
    token = st.text_input("Admin API access token", type="password", key="shp_token")
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
            reset_caches()
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
            reset_caches()
            st.rerun()


# ── Targets ──────────────────────────────────────────────────────
def page_targets():
    st.title("Targets")
    st.caption("Upload daily eCommerce targets. The Report compares actuals against these.")
    cur_t = get_targets()
    if cur_t is not None:
        st.write(f"Current targets: **{len(cur_t)} rows**, "
                 f"{cur_t['date'].min().date()} → {cur_t['date'].max().date()}")
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


PAGES = {"Report": page_report, "Data Table": page_data_table,
         "Connect sources": page_connect, "Targets": page_targets}
try:
    PAGES[page]()
except Exception as e:
    st.error("Something went wrong rendering this page.")
    st.exception(e)
