"""The Growth Engine — Streamlit app (Malleson Labs styling).

Report format modelled on the eCommerce reporting brief: Exec Summary (grouped
KPI cards with vs-LY / vs-target + 8-week sparkline), KPI Overview (KPI x period
table), KPI Trends (TY vs LY), Channels / Regions / Devices comparison tables,
Data Explorer, plus Connect sources and Targets. All metric logic lives in
semantics.py / analytics.py.
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
.kpi-card { background:#fff; border:1px solid #E4E8EF; border-radius:12px; padding:16px 18px; box-shadow:0 1px 2px rgba(17,24,39,0.04); margin-bottom:6px; }
.kpi-name { font-size:12px; color:#64748B; font-weight:600; text-transform:uppercase; letter-spacing:0.04em; }
.kpi-value { font-family:'DM Serif Display',serif; font-size:30px; color:#111827; line-height:1.1; margin:4px 0 6px; }
.kpi-delta { font-size:12px; font-weight:600; display:inline-block; margin-right:12px; }
.kpi-sub { font-size:11px; color:#94A3B8; }
</style>
""", unsafe_allow_html=True)

KPI_GROUPS = {
    "Business Summary": ["revenue", "visits", "orders", "conversion_rate", "aov"],
    "eCommerce Funnel": ["engagement_rate", "add_to_cart_rate", "checkout_rate",
                         "checkout_completion_rate", "cart_abandonment_rate"],
    "Paid Funnel": ["spend", "roas", "cost_per_visit", "cost_per_add_to_cart",
                    "cost_per_checkout", "cost_per_order"],
}
ALL_KPIS = [m for group in KPI_GROUPS.values() for m in group]


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
    page = st.radio("Navigate", ["Exec Summary", "KPI Overview", "KPI Trends",
                                 "Channels", "Regions", "Devices", "Data Explorer",
                                 "Connect sources", "Targets"], label_visibility="collapsed")

fact = get_fact()
if fact is None or fact.empty:
    st.error("No data yet. Run `python run_pipeline.py` or reconnect a source.")
    st.stop()

ref = fact["date"].max().date()
REPORT_PAGES = {"Exec Summary", "KPI Overview", "KPI Trends", "Channels", "Regions",
                "Devices", "Data Explorer"}
FILTER_DIMS = ["marketing_channel_group", "marketing_channel", "paid_ad_platform",
               "geo_region", "geo_market", "device"]

if page in REPORT_PAGES:
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


# ── Exec Summary ─────────────────────────────────────────────────
def page_exec():
    st.title("Executive Summary")
    st.caption(f"{period} · {cur[0]} → {cur[1]}  ·  {comparison.lower()}"
               + ("" if conn_state()["active_source"] == "shopify"
                  else "  ·  demo data"))
    for group, metrics in KPI_GROUPS.items():
        st.subheader(group)
        rows = analytics.kpi_rows(fact, metrics, cur, cmp, targets, filters)
        cols = st.columns(min(len(metrics), 5))
        for i, row in enumerate(rows):
            with cols[i % len(cols)]:
                _kpi_card(row)


def _kpi_card(row):
    m = row["metric"]
    dcol = delta_color(m, row["delta_pct"])
    tcol = delta_color(m, row["vtarg_pct"])
    st.markdown(
        f'<div class="kpi-card"><div class="kpi-name">{sem.nice(m)}</div>'
        f'<div class="kpi-value">{sem.fmt(m, row["value"])}</div>'
        f'<span class="kpi-delta" style="color:{dcol}">{fmt_pct(row["delta_pct"])} {cmp_label}</span>'
        f'<span class="kpi-delta" style="color:{tcol}">{fmt_pct(row["vtarg_pct"])} Targ</span>'
        f'<div class="kpi-sub">8-week trend</div></div>', unsafe_allow_html=True)
    spark = analytics.sparkline(fact, m, cur[1], 8, filters)
    if not spark.empty:
        st.line_chart(spark.set_index("period"), y=m, height=90)


# ── KPI Overview (KPI x period table) ────────────────────────────
def page_kpi_overview():
    st.title("KPI Overview")
    st.caption(f"Values as of {ref} · % vs {cmp_label}")
    periods = ["Week to Date", "Month to Date", "Quarter to Date", "Year to Date"]
    records = []
    for group, metrics in KPI_GROUPS.items():
        for m in metrics:
            rec = {"Group": group, "KPI": sem.nice(m)}
            for pname in periods:
                c = analytics.resolve_period(pname, ref)
                cm = analytics.ly_range(*c) if comparison == "vs Last Year" else analytics.prior_period(*c)
                r = analytics.kpi_rows(fact, [m], c, cm, targets, filters)[0]
                rec[pname] = sem.fmt(m, r["value"])
                rec[f"{pname} %"] = fmt_pct(r["delta_pct"])
            records.append(rec)
    df = pd.DataFrame(records)
    st.dataframe(df, use_container_width=True, hide_index=True)


# ── KPI Trends (TY vs LY) ────────────────────────────────────────
def page_trends():
    st.title("KPI Trends")
    c1, c2 = st.columns(2)
    metric = c1.selectbox("Metric", ALL_KPIS, index=ALL_KPIS.index("revenue"), format_func=sem.nice)
    freq = c2.selectbox("Frequency", ["Weekly", "Daily", "Monthly"])
    fmap = {"Daily": "D", "Weekly": "W", "Monthly": "M"}
    cur_df = analytics.apply_filters(fact, cur[0], cur[1], filters)
    ly = analytics.ly_range(*cur)
    ly_df = analytics.apply_filters(fact, ly[0], ly[1], filters)
    ty = analytics.trend(cur_df, metric, fmap[freq]).reset_index(drop=True)
    lyt = analytics.trend(ly_df, metric, fmap[freq]).reset_index(drop=True)
    chart = pd.DataFrame({"TY": ty[metric]})
    if not lyt.empty:
        chart["LY"] = lyt[metric].reindex(range(len(ty))).values if len(lyt) >= len(ty) \
            else list(lyt[metric].values) + [None] * (len(ty) - len(lyt))
    st.subheader(f"{sem.nice(metric)} — {period} ({freq.lower()})")
    st.line_chart(chart, height=360)


# ── Dimension comparison tables (Channels / Regions / Devices) ───
def _comparison_page(title, dimension, metrics):
    st.title(title)
    st.caption(f"{period} · {cur[0]} → {cur[1]}  vs {cmp_label} ({cmp[0]} → {cmp[1]})")
    tbl = analytics.comparison_table(fact, dimension, metrics, cur, cmp, filters)
    disp = pd.DataFrame({sem.nice(dimension): tbl[dimension]})
    for m in metrics:
        disp[sem.nice(m)] = tbl[m].map(lambda v, mm=m: sem.fmt(mm, v))
        disp[f"{sem.nice(m)} vs {cmp_label}"] = tbl[f"{m}__vs%"].map(fmt_pct)
    st.dataframe(disp, use_container_width=True, hide_index=True)


def page_channels():
    _comparison_page("Channels", "marketing_channel",
                     ["revenue", "visits", "orders", "conversion_rate", "aov", "spend", "roas"])


def page_regions():
    _comparison_page("Regions", "geo_market",
                     ["revenue", "visits", "orders", "conversion_rate", "aov", "spend", "roas"])


def page_devices():
    _comparison_page("Devices", "device",
                     ["revenue", "visits", "orders", "conversion_rate", "aov"])


# ── Data Explorer ────────────────────────────────────────────────
def page_explorer():
    st.title("Data Explorer")
    st.caption(f"{period} · {cur[0]} → {cur[1]}")
    view = analytics.apply_filters(fact, cur[0], cur[1], filters)
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
    st.caption("Upload daily eCommerce targets. Reports compare actuals against these.")
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


PAGES = {
    "Exec Summary": page_exec, "KPI Overview": page_kpi_overview, "KPI Trends": page_trends,
    "Channels": page_channels, "Regions": page_regions, "Devices": page_devices,
    "Data Explorer": page_explorer, "Connect sources": page_connect, "Targets": page_targets,
}
try:
    PAGES[page]()
except Exception as e:
    st.error(f"Something went wrong rendering this page: {e}")
    st.exception(e)
