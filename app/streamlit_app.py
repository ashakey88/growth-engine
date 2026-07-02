"""The Growth Engine — Streamlit app (Malleson Labs styling).

Two parts, mirroring the eCommerce app:
  • Report     — KPI report with period + comparison: Summary cards, Trends,
                 Channels / Regions / Devices sections.
  • Data Table — a simplified flexible table (any dimensions x metrics + export).
Plus Connect sources and Targets utilities. All metric logic lives in
semantics.py / analytics.py.
"""
import calendar
import os
import sys

# Local modules must win over any same-named site-packages ("analytics",
# "semantics"), so insert the project root at the FRONT of sys.path.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

import altair as alt  # noqa: E402
import numpy as np  # noqa: E402
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
#MainMenu, footer, [data-testid="stDecoration"] { visibility:hidden; }
[data-testid="stSidebar"] { background:#F7F8FA; border-right:1px solid #E4E8EF; }
.stButton>button,.stDownloadButton>button { background:#2563EB; color:#fff; border:none; border-radius:8px; font-weight:600; padding:8px 18px; transition:all .15s; }
.stButton>button:hover,.stDownloadButton>button:hover { background:#1D4ED8; color:#fff; transform:translateY(-1px); }
.ml-brand { font-family:'DM Serif Display',serif; font-size:22px; color:#111827; }
.ml-eyebrow { font-size:11px; font-weight:700; letter-spacing:0.14em; text-transform:uppercase; color:#2563EB; margin-bottom:2px; }

/* Sidebar radios -> clean nav menu */
section[data-testid="stSidebar"] div[role="radiogroup"] { gap:2px; }
section[data-testid="stSidebar"] div[role="radiogroup"] > label {
  display:flex; align-items:center; width:100%; margin:0; padding:8px 12px;
  border-radius:8px; cursor:pointer; font-size:14px; font-weight:500; color:#374151;
  transition:background .12s,color .12s;
}
section[data-testid="stSidebar"] div[role="radiogroup"] > label:hover { background:#EEF2FF; color:#2563EB; }
section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) { background:#2563EB; color:#fff; }
section[data-testid="stSidebar"] div[role="radiogroup"] > label > div:first-child { display:none; }

/* Chips (context bar) */
.chip-row { display:flex; flex-wrap:wrap; gap:8px; margin:6px 0 18px; }
.chip { display:inline-flex; align-items:center; gap:6px; background:#F1F5F9; border:1px solid #E4E8EF;
  color:#475569; border-radius:999px; padding:4px 12px; font-size:12px; font-weight:600; }
.chip.accent { background:#EFF6FF; border-color:#BFDBFE; color:#2563EB; }
.chip.live { background:#ECFDF5; border-color:#A7F3D0; color:#059669; }

/* KPI cards */
[data-testid="stVerticalBlockBorderWrapper"] { transition:box-shadow .15s, transform .15s; }
[data-testid="stVerticalBlockBorderWrapper"]:hover { box-shadow:0 6px 20px rgba(17,24,39,0.08); transform:translateY(-2px); }
.kpi-head { display:flex; align-items:center; justify-content:space-between; }
.kpi-name { font-size:11px; color:#64748B; font-weight:600; text-transform:uppercase; letter-spacing:0.06em; }
.kpi-value { font-family:'DM Serif Display',serif; font-size:30px; color:#111827; line-height:1.1; margin:2px 0 8px; }
.info { color:#CBD2DE; font-size:12px; cursor:help; }
.pill { display:inline-block; border-radius:999px; padding:3px 10px; font-size:11px; font-weight:700; margin:0 6px 4px 0; white-space:nowrap; }
.pill.up { background:#DCFCE7; color:#15803D; }
.pill.down { background:#FEE2E2; color:#B91C1C; }
.pill.neutral { background:#F1F5F9; color:#64748B; }

/* Sidebar section label */
.nav-section { font-size:10px; font-weight:700; letter-spacing:0.14em; color:#94A3B8;
  text-transform:uppercase; margin:14px 0 4px; }

/* Tabs — spaced out so they read as tabs */
.stTabs [data-baseweb="tab-list"] { gap:28px; border-bottom:1px solid #E4E8EF; }
.stTabs [data-baseweb="tab"] { padding:10px 2px 12px; font-size:15px; font-weight:600; color:#64748B; }
.stTabs [data-baseweb="tab"]:hover { color:#2563EB; }
.stTabs [aria-selected="true"] { color:#2563EB; }
.stTabs [data-baseweb="tab-highlight"] { background:#2563EB; height:2px; }
[data-testid="stDataFrame"] { border:1px solid #E4E8EF; border-radius:10px; }
.ml-footer { color:#94A3B8; font-size:12px; text-align:center; margin-top:40px; padding-top:16px; border-top:1px solid #E4E8EF; }
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

SECTIONS = {
    "Reports": ["eCommerce", "Profitability", "Customers", "Product", "Acquisition",
                "Forecast"],
    "Analysis": ["Order Insight"],
    "Intelligence": ["Exec Digest", "AI Analyst", "Benchmarks", "Data Trust"],
    "Utility": ["Data Table", "Connect sources", "Targets"],
}
PERIOD_PAGES = {"eCommerce", "Profitability", "Customers", "Product", "Acquisition",
                "Forecast", "Order Insight", "Benchmarks", "Data Table",
                "Exec Digest", "AI Analyst"}

# Filters relevant to each report (not the same set everywhere).
PAGE_FILTERS = {
    "eCommerce": ["marketing_channel_group", "marketing_channel", "paid_ad_platform", "geo_region", "device"],
    "Profitability": ["geo_region", "marketing_channel_group"],
    "Acquisition": ["paid_ad_platform", "paid_campaign_type", "geo_region"],
    "Forecast": ["geo_region"],
    "Exec Digest": ["geo_region"],
    "Benchmarks": ["geo_region"],
    "AI Analyst": ["paid_ad_platform", "geo_region"],
    "Data Table": ["marketing_channel_group", "marketing_channel", "paid_ad_platform",
                   "geo_region", "geo_market", "device"],
    "Product": ["category"],
    "Order Insight": ["category"],
    "Customers": [],
}


@st.cache_resource(show_spinner="Setting up demo data…")
def _bootstrap():
    # The app is a READER. On local storage it self-seeds mock data for
    # convenience; on R2 the pipeline (GitHub Action / local run) owns the data,
    # so the app never writes there — it just reads what the pipeline built.
    if storage.exists(config.FACT_KEY):
        return True
    if config.STORAGE_BACKEND == "local":
        run_pipeline.run_mock()
    return True


@st.cache_resource(show_spinner="Loading data…")
def get_fact():
    return analytics.load_fact()


def get_targets():
    return analytics.load_targets()


@st.cache_resource
def get_product_fact():
    return analytics.load_product_fact()


@st.cache_resource
def get_email_fact():
    return analytics.load_email_fact()


@st.cache_resource
def get_seo_fact():
    return analytics.load_seo_fact()


@st.cache_resource
def get_orders():
    return analytics._load_dated(config.SHOPIFY_KEY)


@st.cache_resource
def get_line_items():
    df = storage.read_df(config.SHOPIFY_LINEITEMS_KEY)
    if df is not None:
        df["created_at"] = pd.to_datetime(df["created_at"])
    return df


@st.cache_resource
def get_returns():
    return analytics._load_dated(config.SHOPIFY_RETURNS_KEY)


@st.cache_resource
def get_orderbank():
    return analytics.load_orderbank()


def conn_state() -> dict:
    return storage.read_json(config.CONNECTIONS_KEY) or {"active_source": "mock", "shopify_store": None}


def reset_caches():
    for fn in (get_fact, get_product_fact, get_email_fact, get_seo_fact,
               get_orders, get_line_items, get_returns, get_orderbank, _bootstrap):
        fn.clear()


# ── Plain formatters for domain tables (outside the marketing definitions) ──
def money(v):
    return "—" if v is None or v != v else f"£{v:,.0f}"


def num(v):
    return "—" if v is None or v != v else f"{v:,.0f}"


def pctv(v, dp=1):
    return "—" if v is None or v != v else f"{v * 100:.{dp}f}%"


def ratio(v):
    return "—" if v is None or v != v else f"{v:.2f}"


def metrics_row(items):
    """items: list of (label, value_str, help_or_None)."""
    cols = st.columns(len(items))
    for c, it in zip(cols, items):
        c.metric(it[0], it[1], help=it[2] if len(it) > 2 else None)


def _in_period(df, col="date"):
    m = (df[col] >= pd.Timestamp(cur[0])) & (df[col] <= pd.Timestamp(cur[1]))
    return df[m]


def _filter_options(dim):
    """Options for a per-report filter, from whichever table owns that dimension."""
    if dim == "category":
        fp = get_product_fact()
        return sorted(fp["category"].dropna().unique()) if fp is not None and "category" in fp else []
    if dim in fact.columns:
        return sorted([v for v in fact[dim].dropna().unique() if v != sem.NA])
    return []


def _filt(df, filters):
    """Apply categorical filters to whichever columns the frame actually has."""
    for k, v in (filters or {}).items():
        if v and k in df.columns:
            df = df[df[k].isin(v)]
    return df


ICONS = {
    "Reports": "📊", "Analysis": "🔬", "Intelligence": "✨", "Utility": "⚙️",
    "eCommerce": "🛒", "Profitability": "💷", "Customers": "👥", "Product": "📦",
    "Acquisition": "📣", "Forecast": "🎯", "Orderbank": "📥", "Order Insight": "🧾", "Exec Digest": "📌",
    "AI Analyst": "🤖", "Benchmarks": "📐", "Data Trust": "🛡️", "Data Table": "🔎",
    "Connect sources": "🔌", "Targets": "🎚️",
}
BASE_DESC = {
    "revenue": "Net sales (after discounts). Shopify is the source of truth.",
    "gross_sales": "Sales before discounts.",
    "discounts": "Total discount value given away.",
    "cogs": "Cost of goods sold.",
    "gross_profit": "Revenue minus COGS.",
    "orders": "Number of orders placed.",
    "visits": "Sessions (GA4).",
    "engaged_visits": "Sessions that engaged (GA4).",
    "add_to_carts": "Sessions with an add-to-cart.",
    "checkouts": "Sessions that reached checkout.",
    "spend": "Total ad spend across platforms.",
    "impressions": "Ad impressions.", "clicks": "Ad clicks.",
}


def metric_help(m: str) -> str:
    meta = sem.metric_meta(m)
    if meta["kind"] == "derived":
        f = meta["formula"].replace("/", "÷").replace("*", "×").replace("-", "−")
        for tok in sorted(sem.BASE_METRICS, key=len, reverse=True):
            f = f.replace(tok, sem.nice(tok))
        return f"{sem.nice(m)} = {f}"
    return BASE_DESC.get(m, sem.nice(m))


def fmt_pct(p):
    return "—" if p is None else f"{p:+.0f}%"


def compact(m: str, value) -> str:
    """Compact card value: £1.2M / 12.3k for big numbers; full format otherwise."""
    meta = sem.metric_meta(m)
    if value is None or (isinstance(value, float) and value != value):
        return "—"
    if meta["format"] in ("currency", "number"):
        sign = "-" if value < 0 else ""
        v, pre = abs(value), ("£" if meta["format"] == "currency" else "")
        if v >= 1_000_000:
            return f"{sign}{pre}{v/1_000_000:.1f}M"
        if v >= 10_000:
            return f"{sign}{pre}{v/1_000:.0f}k"
        if v >= 1_000:
            return f"{sign}{pre}{v/1_000:.1f}k"
        return f"{sign}{pre}{v:,.0f}"
    return sem.fmt(m, value)


def chips(items):
    """items: list of (label, css_class). Render a context chip row."""
    html = '<div class="chip-row">' + "".join(
        f'<span class="chip {c}">{lbl}</span>' for lbl, c in items) + "</div>"
    st.markdown(html, unsafe_allow_html=True)


def report_header(title):
    live = conn_state().get("active_source") == "shopify"
    st.markdown(f'<div class="ml-eyebrow">{ICONS.get(title,"")} Report</div>', unsafe_allow_html=True)
    st.title(title)
    chips([
        (f"📅 {period}", "accent"),
        (comparison, ""),
        (f"Data through {ref}", ""),
        ("● Live · Shopify" if live else "● Demo data", "live" if live else ""),
    ])


_bootstrap()

with st.sidebar:
    st.markdown('<div class="ml-eyebrow">Malleson Labs</div>'
                '<div class="ml-brand">The Growth Engine</div>', unsafe_allow_html=True)
    st.markdown("---")
    # Section = a dropdown (the "workspace"); pages = the menu below it. Two
    # different controls so the hierarchy reads clearly.
    section = st.selectbox("Workspace", list(SECTIONS.keys()),
                           format_func=lambda s: f"{ICONS.get(s, '')}  {s}",
                           label_visibility="collapsed")
    st.markdown(f'<div class="nav-section">{section}</div>', unsafe_allow_html=True)
    page = st.radio(section, SECTIONS[section],
                    format_func=lambda p: f"{ICONS.get(p, '•')}  {p}",
                    label_visibility="collapsed")

fact = get_fact()
if fact is None or fact.empty:
    if config.STORAGE_BACKEND == "r2":
        st.warning("No data found in R2 yet. Run the pipeline to populate it — "
                   "either the **Build data → R2** GitHub Action, or "
                   "`STORAGE_BACKEND=r2 python run_pipeline.py` locally.")
    else:
        st.error("No data yet. Run `python run_pipeline.py` or reconnect a source.")
    st.stop()

ref = fact["date"].max().date()
FILTER_DIMS = ["marketing_channel_group", "marketing_channel", "paid_ad_platform",
               "geo_region", "geo_market", "device"]

if page in PERIOD_PAGES:
    with st.sidebar:
        st.markdown("---")
        period = st.selectbox("📅 Period", analytics.PERIODS,
                              index=analytics.PERIODS.index("Month to Date"),
                              help="The reporting window, relative to the latest data.")
        comparison = st.selectbox("⚖️ Compare against", ["vs Last Year", "vs Prior Period"],
                                  help="What every % change is measured against.")
        spec = PAGE_FILTERS.get(page, [])
        fkeys = {dim: f"flt_{page}_{dim}" for dim in spec}  # per-page keys → independent
        active = sum(len(st.session_state.get(k, [])) for k in fkeys.values())
        filters = {}
        if spec:
            with st.expander(f"🔎 Filters{f'  ·  {active} active' if active else ''}",
                             expanded=bool(active)):
                for dim in spec:
                    opts = _filter_options(dim)
                    sel = st.multiselect(sem.nice(dim), opts, key=fkeys[dim])
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
    grad = alt.Gradient(gradient="linear",
                        stops=[alt.GradientStop(color="#FFFFFF", offset=0),
                               alt.GradientStop(color="#93C5FD", offset=1)],
                        x1=1, x2=1, y1=1, y2=0)
    base = alt.Chart(spark).encode(
        x=alt.X("period:T", axis=None),
        y=alt.Y(f"{metric}:Q", axis=None, scale=alt.Scale(zero=False)),
        tooltip=[alt.Tooltip("period:T", title="Week"),
                 alt.Tooltip(f"{metric}:Q", title=sem.nice(metric), format=",.0f")],
    )
    area = base.mark_area(color=grad, opacity=0.5)
    line = base.mark_line(color=color, strokeWidth=2.5)
    return (area + line).properties(height=56).configure_view(strokeWidth=0)


def _kpi_card(row):
    m = row["metric"]
    pills = _pill(m, row["delta_pct"], cmp_label)
    if row.get("target") is not None:  # only show the target pill when a target exists
        pills += _pill(m, row["vtarg_pct"], "Targ")
    with st.container(border=True):
        st.markdown(
            f'<div class="kpi-head"><span class="kpi-name">{sem.nice(m)}</span>'
            f'<span class="info" title="{metric_help(m)}">ⓘ</span></div>'
            f'<div class="kpi-value" title="{sem.fmt(m, row["value"])}">{compact(m, row["value"])}</div>'
            f'<div>{pills}</div>',
            unsafe_allow_html=True)
        spark = analytics.sparkline(fact, m, cur[1], 8, filters)
        if len(spark) > 1:
            st.altair_chart(_spark_chart(spark, m), use_container_width=True)


def render_trends():
    c1, c2 = st.columns(2)
    metric = c1.selectbox("Metric", ALL_KPIS, index=ALL_KPIS.index("revenue"),
                          format_func=sem.nice, key="tr_metric",
                          help="Pick any KPI to chart this year vs last year.")
    freq = c2.selectbox("Frequency", ["Weekly", "Daily", "Monthly"], key="tr_freq")
    st.caption(metric_help(metric))
    fmap = {"Daily": "D", "Weekly": "W", "Monthly": "M"}
    cur_df = analytics.apply_filters(fact, cur[0], cur[1], filters)
    if cur_df.empty:
        _empty()
        return
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


def _empty(msg="No data for this period and these filters."):
    st.info(f"🔍 {msg} Try a wider period or clearing filters.")


def _comparison_section(dimension, metrics):
    view = analytics.apply_filters(fact, cur[0], cur[1], filters)
    if view.empty:
        _empty()
        return
    tbl = analytics.comparison_table(fact, dimension, metrics, cur, cmp, filters)
    disp = pd.DataFrame({sem.nice(dimension): tbl[dimension]})
    for m in metrics:
        disp[sem.nice(m)] = tbl[m].map(lambda v, mm=m: sem.fmt(mm, v))
        disp[f"vs {cmp_label}"] = tbl[f"{m}__vs%"].map(fmt_pct)
    st.dataframe(disp, use_container_width=True, hide_index=True)


BIZ = ["revenue", "visits", "orders", "conversion_rate", "aov", "spend", "roas"]


def _period_caption():
    return (f"{period} · {cur[0]} → {cur[1]}  ·  {comparison.lower()}"
            + ("" if conn_state()["active_source"] == "shopify" else "  ·  demo data"))


def _kpi_grid(metrics):
    rows = analytics.kpi_rows(fact, metrics, cur, cmp, targets, filters)
    cols = st.columns(min(len(metrics), 4))
    for i, row in enumerate(rows):
        with cols[i % len(cols)]:
            _kpi_card(row)


def page_report():
    report_header("eCommerce")
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
    st.markdown('<div class="ml-eyebrow">🔎 Utility</div>', unsafe_allow_html=True)
    st.title("Data Table")
    chips([(f"📅 {period}", "accent"), (f"{cur[0]} → {cur[1]}", "")])
    view = analytics.apply_filters(fact, cur[0], cur[1], filters)
    dims = ["date", "source", "marketing_channel_group", "marketing_channel",
            "paid_ad_platform", "geo_region", "geo_market", "device"]
    c1, c2 = st.columns(2)
    gdims = c1.multiselect("Dimensions", dims, default=["marketing_channel"], format_func=sem.nice,
                           help="Group the table by one or more dimensions.")
    metrics = c2.multiselect("Metrics", sem.ALL_METRICS,
                             default=["revenue", "orders", "spend", "roas"], format_func=sem.nice,
                             help="Add any base or derived metric.")
    if not gdims or not metrics:
        st.info("Pick at least one dimension and one metric.")
        return
    if view.empty:
        _empty()
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


# ── Profitability (flagship — built from data in hand) ───────────
def page_profitability():
    report_header("Profitability")
    st.markdown("#### Headline")
    _kpi_grid(["revenue", "gross_profit", "gross_margin_pct", "contribution"])
    _kpi_grid(["contribution_margin", "spend", "mer", "discount_rate"])

    st.markdown("#### Finance waterfall")
    cur_df = analytics.apply_filters(fact, cur[0], cur[1], filters)
    t = analytics.totals(cur_df, ["gross_sales", "discounts", "revenue", "cogs",
                                  "gross_profit", "spend"])
    # cancellations + returns value from the raw returns feed (period-scoped)
    cancellations = returns_val = 0.0
    rets = get_returns()
    if rets is not None and not rets.empty and "kind" in rets.columns:
        rp = _in_period(rets)
        cancellations = rp.loc[rp["kind"] == "cancellation", "value"].sum()
        returns_val = rp.loc[rp["kind"] == "return", "value"].sum()
    net = t["revenue"] - cancellations - returns_val
    gp_after = net - t["cogs"]
    contribution = gp_after - t["spend"]
    steps = [("Gross Sales", t["gross_sales"]), ("Less: Discounts", -t["discounts"]),
             ("Less: Cancellations", -cancellations), ("Less: Returns", -returns_val),
             ("Net Revenue", net), ("Less: COGS", -t["cogs"]),
             ("Gross Profit", gp_after), ("Less: Marketing", -t["spend"]),
             ("Contribution (CM2)", contribution)]
    wf = pd.DataFrame({"Line": [s[0] for s in steps], "£": [money(s[1]) for s in steps]})
    st.table(wf)
    st.caption("Modelled on the trading suite's finance waterfall. Fulfilment and "
               "payment fees (CM3) come once those feeds are connected.")

    st.markdown("#### Contribution over time")
    tr = analytics.trend(cur_df, "contribution", "W").set_index("period")
    st.line_chart(tr, y="contribution", height=280)


# ── Data Trust ───────────────────────────────────────────────────
def page_data_trust():
    st.title("Data Trust")
    st.caption("Source connections, freshness and coverage — so you can trust the numbers.")
    conn = conn_state()
    c1, c2, c3 = st.columns(3)
    c1.metric("Data through", str(fact["date"].max().date()))
    c2.metric("Sales source", "Shopify (live)" if conn.get("active_source") == "shopify" else "Demo data")
    c3.metric("Fact rows", f"{len(fact):,}")
    st.markdown("#### Sources")
    sources = [
        ("Shopify (orders)", config.SHOPIFY_KEY), ("Shopify (line items)", config.SHOPIFY_LINEITEMS_KEY),
        ("Shopify (inventory)", config.SHOPIFY_INVENTORY_KEY), ("Shopify (returns)", config.SHOPIFY_RETURNS_KEY),
        ("GA4 (sessions)", config.GA4_KEY), ("GA4 (items)", config.GA4_ITEMS_KEY),
        ("Meta Ads", config.META_KEY), ("Google Ads", config.GOOGLE_KEY),
        ("Microsoft Ads", config.MICROSOFT_KEY), ("TikTok Ads", config.TIKTOK_KEY),
        ("Klaviyo (email)", config.KLAVIYO_KEY), ("Search Console (SEO)", config.GSC_KEY),
        ("Targets", config.TARGETS_KEY),
    ]
    st.dataframe(pd.DataFrame([{"Source": n, "Status": "✅ Connected" if storage.exists(k) else "— Not connected"}
                              for n, k in sources]), use_container_width=True, hide_index=True)

    st.markdown("#### Fact tables")
    facts = [("Marketing (stacked)", config.FACT_KEY), ("Product", config.FACT_PRODUCT_KEY),
             ("Email", config.FACT_EMAIL_KEY), ("SEO", config.FACT_SEO_KEY)]
    st.dataframe(pd.DataFrame([{"Fact table": n, "Built": "✅" if storage.exists(k) else "—"}
                              for n, k in facts]), use_container_width=True, hide_index=True)

    st.markdown("#### Marketing fact by source")
    counts = fact.groupby("source").size().reset_index(name="rows")
    counts.columns = ["Source", "Rows"]
    st.dataframe(counts, use_container_width=True, hide_index=True)


# ── Informative stubs for the rest of the suite ──────────────────
def _stub(title, purpose, sections, needs=None, tier="Report"):
    st.markdown(f'<div class="ml-eyebrow">{ICONS.get(title.split(" ")[0], "✨")} {tier}</div>',
                unsafe_allow_html=True)
    st.title(title)
    st.caption(purpose)
    st.info(f"**Coming next.** This {tier.lower()} is scaffolded — here's what it will contain.")
    st.markdown("**Planned sections**")
    for s in sections:
        st.markdown(f"- {s}")
    if needs:
        st.warning(f"🔌 Unlocks when connected: {needs}")


def _report_top(title, icon):
    st.markdown(f'<div class="ml-eyebrow">{icon} Report</div>', unsafe_allow_html=True)
    st.title(title)
    chips([(f"📅 {period}", "accent"), (comparison, ""), (f"Data through {ref}", "")])


# ── Customers & Retention ────────────────────────────────────────
def page_customers():
    _report_top("Customers & Retention", "👥")
    orders = get_orders()
    if orders is None or orders.empty:
        _empty("No order data.")
        return
    o = orders.copy()
    o["date"] = pd.to_datetime(o["created_at"]) if "created_at" in o else o["date"]
    o = o.sort_values("date")
    o["first_order"] = o.groupby("customer_id")["date"].transform("min")
    p = o[(o["date"] >= pd.Timestamp(cur[0])) & (o["date"] <= pd.Timestamp(cur[1]))]
    if p.empty:
        _empty()
        return
    custs = p["customer_id"].nunique()
    is_new = p["first_order"].between(pd.Timestamp(cur[0]), pd.Timestamp(cur[1]))
    new = p.loc[is_new, "customer_id"].nunique()
    orders_ct, revenue = len(p), p["net_sales"].sum()
    ltv = o.groupby("customer_id")["net_sales"].sum().mean()
    spend = analytics.totals(analytics.apply_filters(fact, cur[0], cur[1], filters), ["spend"])["spend"]
    cac = spend / new if new else None
    metrics_row([
        ("Customers", num(custs), "Distinct customers who ordered this period"),
        ("New customers", num(new), "First-ever order fell in this period"),
        ("Repeat rate", pctv((custs - new) / custs if custs else 0), "Returning ÷ all customers"),
        ("Orders / customer", ratio(orders_ct / custs if custs else 0), None),
    ])
    metrics_row([
        ("AOV", money(revenue / orders_ct if orders_ct else 0), None),
        ("Avg LTV", money(ltv), "Average lifetime net revenue per customer"),
        ("Blended CAC", money(cac), "Marketing spend ÷ new customers"),
        ("LTV : CAC", ratio(ltv / cac) if cac else "—", "Above 3 is healthy"),
    ])
    t1, t2, t3 = st.tabs(["New vs returning", "Cohort retention", "Email / CRM"])
    with t1:
        pv = p.copy()
        pv["cohort"] = np.where(is_new.values, "new", "returning")
        pv["week"] = pv["date"].dt.to_period("W").dt.start_time
        piv = pv.groupby(["week", "cohort"])["net_sales"].sum().unstack(fill_value=0)
        st.area_chart(piv, height=300)
    with t2:
        oo = o.copy()
        oo["cm"] = oo["first_order"].dt.to_period("M")
        oo["om"] = oo["date"].dt.to_period("M")
        oo["ms"] = (oo["om"].dt.year - oo["cm"].dt.year) * 12 + (oo["om"].dt.month - oo["cm"].dt.month)
        size = oo.groupby("cm")["customer_id"].nunique()
        ret = oo.groupby(["cm", "ms"])["customer_id"].nunique().reset_index()
        ret["pct"] = ret.apply(lambda r: r["customer_id"] / size[r["cm"]], axis=1)
        mat = ret.pivot(index="cm", columns="ms", values="pct").tail(12)
        mat.index = mat.index.astype(str)
        st.caption("Share of each monthly cohort still ordering, N months later.")
        st.dataframe((mat * 100).round(0).fillna(""), use_container_width=True)
    with t3:
        em = get_email_fact()
        if em is None or em.empty:
            st.info("🔌 Connect Klaviyo to light up the Email / CRM section.")
        else:
            e = _in_period(em)
            g = e.groupby(["type", "name"]).agg(recipients=("recipients", "sum"),
                orders=("orders", "sum"), revenue=("revenue", "sum")).reset_index()
            g["rev / recipient"] = g["revenue"] / g["recipients"]
            metrics_row([("Email revenue", money(g["revenue"].sum()), None),
                         ("Email orders", num(g["orders"].sum()), None),
                         ("Rev / recipient", money(g["revenue"].sum() / g["recipients"].sum()
                          if g["recipients"].sum() else 0), None)])
            disp = g.sort_values("revenue", ascending=False)
            disp["revenue"] = disp["revenue"].map(money)
            disp["rev / recipient"] = disp["rev / recipient"].map(lambda v: f"£{v:,.2f}")
            disp["recipients"] = disp["recipients"].map(num)
            disp["orders"] = disp["orders"].map(num)
            st.dataframe(disp, use_container_width=True, hide_index=True)


# ── Product / Merchandising ──────────────────────────────────────
def page_product():
    _report_top("Product / Merchandising", "📦")
    fp = get_product_fact()
    if fp is None or fp.empty:
        _empty("No product data.")
        return
    p = _filt(_in_period(fp), filters)
    if p.empty:
        _empty()
        return
    for c in ["product_views", "product_add_to_carts", "on_hand", "returned_units", "refund_amount"]:
        if c not in p:
            p[c] = 0
    agg = p.groupby(["product_id", "product_title", "category"]).agg(
        units=("units", "sum"), revenue=("revenue", "sum"), gross_sales=("gross_sales", "sum"),
        discounts=("discounts", "sum"), gross_profit=("gross_profit", "sum"),
        views=("product_views", "sum"), atc=("product_add_to_carts", "sum"),
        on_hand=("on_hand", "last"), returned=("returned_units", "sum"),
        refund=("refund_amount", "sum"),
    ).reset_index().fillna(0)
    weeks = max(1.0, ((cur[1] - cur[0]).days + 1) / 7)

    def _asp(d):
        return d["revenue"] / d["units"].replace(0, np.nan)

    t1, t2, t3, t4 = st.tabs(["Sales & Margin", "Funnel", "Stock", "Returns"])
    with t1:
        tot = agg[["revenue", "units", "gross_sales", "discounts", "gross_profit"]].sum()
        metrics_row([
            ("Revenue", money(tot["revenue"]), None),
            ("Units", num(tot["units"]), None),
            ("ASP", money(tot["revenue"] / tot["units"] if tot["units"] else 0), "Average selling price = Revenue ÷ Units"),
            ("Gross margin", pctv(tot["gross_profit"] / tot["revenue"] if tot["revenue"] else 0), None),
            ("Discount %", pctv(tot["discounts"] / tot["gross_sales"] if tot["gross_sales"] else 0), "Discounts ÷ gross sales"),
        ])
        cat = agg.groupby("category").agg(revenue=("revenue", "sum"), units=("units", "sum"),
            gross_sales=("gross_sales", "sum"), discounts=("discounts", "sum"),
            gross_profit=("gross_profit", "sum")).reset_index()
        st.bar_chart(cat.set_index("category"), y="revenue", height=240)
        cat["ASP"] = (cat["revenue"] / cat["units"]).map(money)
        cat["Disc %"] = (cat["discounts"] / cat["gross_sales"] * 100).round(1)
        cat["GM %"] = (cat["gross_profit"] / cat["revenue"] * 100).round(1)
        cat["Revenue"] = cat["revenue"].map(money)
        cat["GM £"] = cat["gross_profit"].map(money)
        cat["Units"] = cat["units"].map(num)
        st.dataframe(cat[["category", "Revenue", "Units", "ASP", "Disc %", "GM %", "GM £"]]
                     .rename(columns={"category": "Category"}), use_container_width=True, hide_index=True)
    with t2:
        f = agg.copy()
        f["ATC %"] = (f["atc"] / f["views"].replace(0, np.nan) * 100).round(1)
        f["Conversion %"] = (f["units"] / f["views"].replace(0, np.nan) * 100).round(1)
        f = f.sort_values("views", ascending=False).head(20)
        show = f[["product_title", "views", "atc", "ATC %", "units", "Conversion %"]].copy()
        show.columns = ["Product", "Views", "Add to Carts", "ATC %", "Units", "Conversion %"]
        for c in ["Views", "Add to Carts", "Units"]:
            show[c] = show[c].map(num)
        st.caption("Product-level funnel: views → add-to-cart rate → conversion.")
        st.dataframe(show, use_container_width=True, hide_index=True)
    with t3:
        s = agg.copy()
        s["weeks_cover"] = (s["on_hand"] / (s["units"] / weeks).replace(0, np.nan)).round(1)
        avail = (s["on_hand"] > 0).mean()
        metrics_row([
            ("In-stock availability", pctv(avail), "Share of products with stock on hand"),
            ("Avg weeks cover", ratio(s["weeks_cover"].replace([np.inf], np.nan).mean()), "On hand ÷ weekly sell-through"),
            ("Out of stock", num((s["on_hand"] <= 0).sum()), None),
        ])
        low = s[(s["weeks_cover"] <= 3) | (s["on_hand"] <= 0)].sort_values("weeks_cover")
        st.caption("Products with ≤ 3 weeks cover (or out of stock) at the current rate.")
        show = low[["product_title", "category", "on_hand", "weeks_cover"]].head(20).copy()
        show.columns = ["Product", "Category", "On hand", "Weeks cover"]
        show["On hand"] = show["On hand"].map(num)
        st.dataframe(show, use_container_width=True, hide_index=True)
        if low.empty:
            st.success("No products low on stock. 🎉")
    with t4:
        r = agg.copy()
        tot_u, tot_r, tot_rev, tot_ref = r["units"].sum(), r["returned"].sum(), r["revenue"].sum(), r["refund"].sum()
        metrics_row([
            ("Return rate (items)", pctv(tot_r / tot_u if tot_u else 0), "Returned units ÷ units sold"),
            ("Return rate (value)", pctv(tot_ref / tot_rev if tot_rev else 0), "Refund value ÷ revenue"),
            ("Refunds", money(tot_ref), None),
        ])
        r["Return %"] = (r["returned"] / r["units"].replace(0, np.nan) * 100).round(1)
        worst = r[r["returned"] > 0].sort_values("Return %", ascending=False).head(15)
        show = worst[["product_title", "category", "units", "returned", "Return %"]].copy()
        show.columns = ["Product", "Category", "Units", "Returned", "Return %"]
        show["Units"] = show["Units"].map(num)
        show["Returned"] = show["Returned"].map(num)
        st.dataframe(show, use_container_width=True, hide_index=True)
        rets = get_returns()
        if rets is not None and not rets.empty:
            rr = _filt(_in_period(rets), filters)
            if not rr.empty and "reason" in rr:
                st.markdown("**Return reasons**")
                st.bar_chart(rr.groupby("reason").size().sort_values(ascending=False), height=240)


# ── Acquisition / Paid Media ─────────────────────────────────────
def page_acquisition():
    _report_top("Acquisition / Paid Media", "📣")
    cur_df = analytics.apply_filters(fact, cur[0], cur[1], filters)
    total_rev = analytics.totals(cur_df, ["revenue"])["revenue"]
    paid = cur_df[cur_df["paid_ad_platform"] != sem.NA]
    if paid.empty:
        _empty("No paid media data.")
        return
    spend = paid["spend"].sum()
    metrics_row([
        ("Total spend", money(spend), None),
        ("Blended MER", ratio(total_rev / spend) if spend else "—", "Total revenue ÷ total ad spend"),
        ("Blended CAC", money(spend / analytics.totals(cur_df, ["orders"])["orders"]
         if analytics.totals(cur_df, ["orders"])["orders"] else 0), "Spend ÷ orders"),
        ("Platform ROAS", ratio(paid["platform_conversion_value_7d"].sum() / spend) if spend else "—",
         "Platform-reported value ÷ spend"),
    ])
    t1, t2 = st.tabs(["By platform", "SEO"])
    with t1:
        g = paid.groupby("paid_ad_platform").agg(spend=("spend", "sum"),
            impressions=("impressions", "sum"), clicks=("clicks", "sum"),
            conv=("platform_conversions_7d", "sum"),
            conv_val=("platform_conversion_value_7d", "sum")).reset_index()
        g["ROAS"] = (g["conv_val"] / g["spend"]).round(2)
        g["CTR %"] = (g["clicks"] / g["impressions"] * 100).round(2)
        g["CPC"] = (g["spend"] / g["clicks"]).round(2)
        g["CPA"] = (g["spend"] / g["conv"].replace(0, np.nan)).round(2)
        st.bar_chart(g.set_index("paid_ad_platform"), y="spend", height=260)
        show = g[["paid_ad_platform", "spend", "conv", "ROAS", "CTR %", "CPC", "CPA"]].copy()
        show.columns = ["Platform", "Spend", "Conversions", "ROAS", "CTR %", "CPC", "CPA"]
        show["Spend"] = show["Spend"].map(money)
        show["Conversions"] = show["Conversions"].map(num)
        st.dataframe(show, use_container_width=True, hide_index=True)
        st.caption("Channel truth: these are *platform-reported* conversions (Meta/Google over-report). "
                   "True channel-level revenue needs GA4→sales reconciliation — a next step.")
    with t2:
        seo = get_seo_fact()
        if seo is None or seo.empty:
            st.info("🔌 Connect Search Console to light up SEO.")
        else:
            s = _in_period(seo)
            metrics_row([("Clicks", num(s["clicks"].sum()), None),
                         ("Impressions", num(s["impressions"].sum()), None),
                         ("Avg position", ratio(s["position"].mean()), "Lower is better"),
                         ("CTR", pctv(s["clicks"].sum() / s["impressions"].sum()
                          if s["impressions"].sum() else 0, 2), None)])
            if "branded" in s:
                b = s.groupby("branded").agg(clicks=("clicks", "sum")).reset_index()
                b["branded"] = b["branded"].map({True: "Branded", False: "Non-branded"})
                st.bar_chart(b.set_index("branded"), y="clicks", height=220)
            q = s.groupby("query").agg(clicks=("clicks", "sum"), impressions=("impressions", "sum"),
                position=("position", "mean")).reset_index().sort_values("clicks", ascending=False).head(15)
            q["position"] = q["position"].round(1)
            q["clicks"] = q["clicks"].map(num)
            q["impressions"] = q["impressions"].map(num)
            q.columns = ["Query", "Clicks", "Impressions", "Avg position"]
            st.dataframe(q, use_container_width=True, hide_index=True)


# ── Forecast & Pacing (Perf vs Budget + run-rate) ────────────────
def page_forecast():
    _report_top("Forecast & Pacing", "🎯")
    t1, t2 = st.tabs(["Perf vs Budget", "Run-rate"])
    budget_metrics = ["revenue", "orders", "gross_profit", "spend", "visits"]
    cur_df = analytics.apply_filters(fact, cur[0], cur[1], filters)
    ly = analytics.ly_range(*cur)
    ly_df = analytics.apply_filters(fact, ly[0], ly[1], filters)
    with t1:
        st.caption(f"Selected period ({cur[0]} → {cur[1]}) vs budget and last year.")
        rows = []
        for m in budget_metrics:
            actual = analytics.totals(cur_df, [m])[m]
            budget = analytics.target_total(targets, cur[0], cur[1], m)
            lyv = analytics.totals(ly_df, [m])[m]
            rows.append({
                "Metric": sem.nice(m), "Actual": sem.fmt(m, actual),
                "Budget": sem.fmt(m, budget) if budget else "—",
                "v Budget": fmt_pct((actual / budget - 1) * 100) if budget else "—",
                "LY": sem.fmt(m, lyv),
                "v LY": fmt_pct((actual / lyv - 1) * 100) if lyv else "—",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    with t2:
        st.caption("Pacing the current month to a linear run-rate.")
        month_start = ref.replace(day=1)
        dim = calendar.monthrange(ref.year, ref.month)[1]
        elapsed = ref.day
        mtd = analytics.apply_filters(fact, month_start, ref, filters)
        rows = []
        for m in ["revenue", "orders", "spend", "gross_profit"]:
            actual = analytics.totals(mtd, [m])[m]
            proj = actual / elapsed * dim if elapsed else 0
            tgt = analytics.target_total(targets, month_start, month_start.replace(day=dim), m)
            rows.append({"Metric": sem.nice(m), "MTD actual": sem.fmt(m, actual),
                         "Projected month": sem.fmt(m, proj),
                         "Month budget": sem.fmt(m, tgt) if tgt else "—",
                         "Projected vs budget": fmt_pct((proj / tgt - 1) * 100) if tgt else "—"})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.caption(f"Day {elapsed} of {dim}. Linear run-rate projection.")


# ── Orderbank ────────────────────────────────────────────────────
def page_orderbank():
    _report_top("Orderbank", "📥")
    st.caption("Open sales orders taken but not yet invoiced.")
    ob = get_orderbank()
    if ob is None or ob.empty:
        _empty("No orderbank data.")
        return
    latest = ob["date"].max()
    snap = ob[ob["date"] == latest]
    metrics_row([
        ("Open value", money(snap["open_value"].sum()), "Value of orders not yet invoiced"),
        ("Open orders", num(snap["open_orders"].sum()), None),
        ("Open items", num(snap["open_items"].sum()), None),
    ])
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**By category**")
        st.bar_chart(snap.groupby("category_l1")["open_value"].sum(), height=240)
    with c2:
        st.markdown("**By warehouse**")
        st.bar_chart(snap.groupby("warehouse")["open_value"].sum(), height=240)
    st.markdown("**Open orderbank value — weekly trend**")
    st.line_chart(ob.groupby("date")["open_value"].sum(), height=260)


# ── Order Insight (Analysis) ─────────────────────────────────────
def page_order_insight():
    st.markdown('<div class="ml-eyebrow">🧾 Analysis</div>', unsafe_allow_html=True)
    st.title("Order Insight")
    chips([(f"📅 {period}", "accent"), (f"{cur[0]} → {cur[1]}", "")])
    li = get_line_items()
    if li is None or li.empty:
        _empty("No line-item data.")
        return
    l = li[(li["created_at"] >= pd.Timestamp(cur[0])) & (li["created_at"] <= pd.Timestamp(cur[1]))]
    l = _filt(l, filters)
    if l.empty:
        _empty()
        return
    orders = l.groupby("order_id").agg(value=("net_sales", "sum"), items=("quantity", "sum")).reset_index()
    metrics_row([
        ("Orders", num(len(orders)), None),
        ("AOV", money(orders["value"].mean()), None),
        ("Median order", money(orders["value"].median()), "Half of orders are below this"),
        ("P90 order", money(orders["value"].quantile(0.9)), "Top 10% of orders exceed this"),
    ])
    metrics_row([("Avg items / order", ratio(orders["items"].mean()), None),
                 ("Single-item orders", pctv((orders["items"] == 1).mean()), None),
                 ("Units sold", num(l["quantity"].sum()), None)])
    st.markdown("**Order value distribution**")
    hist = alt.Chart(orders).mark_bar(color="#2563EB", opacity=0.8).encode(
        x=alt.X("value:Q", bin=alt.Bin(maxbins=40), title="Order value (£)"),
        y=alt.Y("count()", title="Orders"),
    ).properties(height=280).configure_view(strokeWidth=0)
    st.altair_chart(hist, use_container_width=True)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Revenue by category**")
        cat = l.groupby("category")["net_sales"].sum().sort_values(ascending=False)
        st.bar_chart(cat, height=260)
    with c2:
        st.markdown("**Top products by revenue**")
        tp = l.groupby("product_title")["net_sales"].sum().sort_values(ascending=False).head(10)
        st.bar_chart(tp, height=260)


# ── Exec Digest (Intelligence) ───────────────────────────────────
def page_exec_digest():
    st.markdown('<div class="ml-eyebrow">📌 Intelligence</div>', unsafe_allow_html=True)
    st.title("Exec Digest")
    chips([(f"📅 {period}", "accent"), (comparison, ""), (f"Data through {ref}", "")])
    st.caption("The Monday-morning one-pager — the numbers that matter and what moved.")
    _kpi_grid(["revenue", "contribution", "gross_margin_pct", "mer"])
    _kpi_grid(["orders", "aov", "spend", "roas"])
    st.markdown("#### What changed")
    rows = analytics.kpi_rows(fact, ["revenue", "contribution", "orders", "spend", "roas",
                                     "gross_margin_pct"], cur, cmp, targets, filters)
    movers = sorted([r for r in rows if r["delta_pct"] is not None],
                    key=lambda r: abs(r["delta_pct"]), reverse=True)
    for r in movers[:4]:
        m, d = r["metric"], r["delta_pct"]
        good = (d >= 0) != (sem.metric_meta(m)["cf"] == "reverse")
        emoji = "🟢" if good else "🔴"
        st.markdown(f"{emoji} **{sem.nice(m)}** {sem.fmt(m, r['value'])} — "
                    f"{fmt_pct(d)} {cmp_label}")


# ── AI Analyst (Intelligence) — deterministic insights for now ───
def page_ai_analyst():
    st.markdown('<div class="ml-eyebrow">🤖 Intelligence</div>', unsafe_allow_html=True)
    st.title("AI Analyst")
    st.caption("Auto-generated insights over your commercial data. Natural-language "
               "questions arrive once an LLM is wired in.")
    st.text_input("Ask a question (coming soon)", placeholder="e.g. why did margin drop last week?",
                  disabled=True)
    st.markdown("#### Insights")
    cur_df = analytics.apply_filters(fact, cur[0], cur[1], filters)
    paid = cur_df[cur_df["paid_ad_platform"] != sem.NA]
    insights = []
    if not paid.empty:
        g = paid.groupby("paid_ad_platform").apply(
            lambda d: d["platform_conversion_value_7d"].sum() / max(d["spend"].sum(), 1)).sort_values()
        if len(g):
            insights.append(f"📉 Lowest platform ROAS: **{g.index[0]}** at {g.iloc[0]:.2f}× — "
                            f"review efficiency or reallocate budget.")
            insights.append(f"📈 Highest platform ROAS: **{g.index[-1]}** at {g.iloc[-1]:.2f}×.")
    rows = analytics.kpi_rows(fact, ["revenue", "gross_margin_pct", "spend", "roas"],
                              cur, cmp, targets, filters)
    mv = max((r for r in rows if r["delta_pct"] is not None),
             key=lambda r: abs(r["delta_pct"]), default=None)
    if mv:
        insights.append(f"🔀 Biggest move: **{sem.nice(mv['metric'])}** {fmt_pct(mv['delta_pct'])} {cmp_label}.")
    for i in insights:
        with st.container(border=True):
            st.markdown(i)
    if not insights:
        _empty("Not enough data to generate insights.")


# ── Benchmarks (Intelligence) — illustrative until research feed ─
BENCHMARKS = {"conversion_rate": 0.025, "aov": 75, "gross_margin_pct": 0.62,
              "roas": 3.0, "cart_abandonment_rate": 0.70}


def page_benchmarks():
    st.markdown('<div class="ml-eyebrow">📐 Intelligence</div>', unsafe_allow_html=True)
    st.title("Benchmarks")
    st.caption("Your numbers vs category benchmarks. Illustrative for now — will be "
               "powered by Malleson Labs research.")
    cur_df = analytics.apply_filters(fact, cur[0], cur[1], filters)
    vals = analytics.totals(cur_df, list(BENCHMARKS.keys()))
    rows = []
    for m, bench in BENCHMARKS.items():
        actual = vals[m]
        gap = (actual / bench - 1) * 100 if bench else None
        if sem.metric_meta(m)["cf"] == "reverse":
            gap = -gap if gap is not None else None
        rows.append({"Metric": sem.nice(m), "You": sem.fmt(m, actual),
                     "Benchmark": sem.fmt(m, bench), "vs Benchmark": fmt_pct(gap)})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.caption("Positive = better than benchmark (direction-aware for cost/abandonment metrics).")


PAGES = {
    "eCommerce": page_report, "Profitability": page_profitability,
    "Customers": page_customers, "Product": page_product,
    "Acquisition": page_acquisition, "Forecast": page_forecast,
    "Order Insight": page_order_insight, "Exec Digest": page_exec_digest,
    "AI Analyst": page_ai_analyst, "Benchmarks": page_benchmarks,
    "Data Trust": page_data_trust, "Data Table": page_data_table,
    "Connect sources": page_connect, "Targets": page_targets,
}
try:
    PAGES[page]()
except Exception as e:
    st.error("Something went wrong rendering this page.")
    st.exception(e)

st.markdown('<div class="ml-footer">The Growth Engine · Malleson Labs — '
            'commercial intelligence for scaling ecommerce brands</div>',
            unsafe_allow_html=True)
