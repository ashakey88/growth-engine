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

/* Tabs + tables */
.stTabs [data-baseweb="tab-list"] { gap:4px; border-bottom:1px solid #E4E8EF; }
.stTabs [data-baseweb="tab"] { font-weight:600; color:#64748B; }
.stTabs [aria-selected="true"] { color:#2563EB; }
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
    "Reports": ["eCommerce", "Profitability", "Customers", "Product", "Acquisition", "Forecast"],
    "Analysis": ["Order Insight"],
    "Intelligence": ["Exec Digest", "AI Analyst", "Benchmarks", "Data Trust"],
    "Utility": ["Data Table", "Connect sources", "Targets"],
}
PERIOD_PAGES = {"eCommerce", "Profitability", "Customers", "Product", "Acquisition",
                "Forecast", "Order Insight", "Benchmarks", "Data Table"}


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


def conn_state() -> dict:
    return storage.read_json(config.CONNECTIONS_KEY) or {"active_source": "mock", "shopify_store": None}


def reset_caches():
    get_fact.clear()
    _bootstrap.clear()


ICONS = {
    "Reports": "📊", "Analysis": "🔬", "Intelligence": "✨", "Utility": "⚙️",
    "eCommerce": "🛒", "Profitability": "💷", "Customers": "👥", "Product": "📦",
    "Acquisition": "📣", "Forecast": "🎯", "Order Insight": "🧾", "Exec Digest": "📌",
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
    section = st.radio("Section", list(SECTIONS.keys()),
                       format_func=lambda s: f"{ICONS.get(s, '')}  {s}",
                       label_visibility="collapsed")
    st.caption(section.upper())
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
        fkeys = {dim: f"flt_{dim}" for dim in FILTER_DIMS}
        active = sum(len(st.session_state.get(k, [])) for k in fkeys.values())
        filters = {}
        with st.expander(f"🔎 Filters{f'  ·  {active} active' if active else ''}",
                         expanded=bool(active)):
            for dim in FILTER_DIMS:
                opts = sorted([v for v in fact[dim].dropna().unique() if v != sem.NA])
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
    with st.container(border=True):
        st.markdown(
            f'<div class="kpi-head"><span class="kpi-name">{sem.nice(m)}</span>'
            f'<span class="info" title="{metric_help(m)}">ⓘ</span></div>'
            f'<div class="kpi-value" title="{sem.fmt(m, row["value"])}">{compact(m, row["value"])}</div>'
            f'<div>{_pill(m, row["delta_pct"], cmp_label)}'
            f'{_pill(m, row["vtarg_pct"], "Targ")}</div>',
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

    st.markdown("#### Contribution waterfall")
    cur_df = analytics.apply_filters(fact, cur[0], cur[1], filters)
    t = analytics.totals(cur_df, ["gross_sales", "discounts", "revenue", "cogs",
                                  "gross_profit", "spend"])
    contribution = t["gross_profit"] - t["spend"]
    steps = [("Gross Sales", t["gross_sales"]), ("Discounts", -t["discounts"]),
             ("Net Revenue", t["revenue"]), ("COGS", -t["cogs"]),
             ("Gross Profit", t["gross_profit"]), ("Marketing", -t["spend"]),
             ("Contribution (CM2)", contribution)]
    wf = pd.DataFrame({"Line": [s[0] for s in steps],
                       "£": [f"£{s[1]:,.0f}" for s in steps]})
    st.table(wf)
    st.caption("Contribution = Gross Profit − Marketing spend. Fulfilment, payment "
               "fees and returns (CM3) come once those data sources are connected.")

    st.markdown("#### Contribution & MER over time")
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


def page_customers():
    _stub("Customers & Retention",
          "Are your customers worth more than they cost? Where profit compounds.",
          ["LTV, LTV:CAC ratio and payback period",
           "New vs returning revenue split",
           "Cohort retention curves + repeat rate",
           "Email / CRM section (flows, campaigns, revenue per recipient)"],
          "Shopify customer history (have it) · Klaviyo for the Email/CRM section")


def page_product():
    _stub("Product / Merchandising",
          "What's really driving your margin? Everything, per product.",
          ["Sales & margin by product / category (discount depth per SKU)",
           "Product funnel: views → add-to-cart rate → checkout → conversion",
           "Stock & availability: sell-through, days of cover, lost sales from OOS",
           "Returns: rate, reasons and margin impact by product"],
          "GA4 item-level events · Shopify inventory · Shopify returns/refunds")


def page_acquisition():
    _stub("Acquisition / Paid Media",
          "Where should your next £ of spend go?",
          ["CAC and new-customer ROAS by channel / campaign",
           "Payback period and marginal efficiency",
           "Channel truth: platform-reported vs actual (reconciliation)",
           "SEO section: organic performance by landing page / query"],
          "Search Console for the SEO section")


def page_forecast():
    _stub("Forecast & Pacing",
          "Are we going to hit plan?",
          ["Run-rate vs target for the period",
           "Projected month / quarter / year-end",
           "Simple what-if scenarios (spend, AOV, conversion)"],
          "Uses your Targets — no new data needed")


def page_order_insight():
    _stub("Order Insight",
          "Operator analysis bench — explore, find the story, roll findings into the monthly reports.",
          ["Order value distribution (median, P90, threshold effects)",
           "AOV contributors: units per order × price × mix",
           "Basket composition and cross-sell (what's bought together)",
           "Free-shipping / promo threshold impact on AOV"],
          "Shopify line-item data for basket/mix analysis", tier="Analysis")


def page_exec_digest():
    _stub("Exec Digest",
          "The Monday-morning one-pager: the 2–3 numbers that moved, and why.",
          ["Headline P&L + growth vs LY / target",
           "Automatic 'what changed' callouts (alerts)",
           "Roll-up of the key signal from every report"],
          "Composes the other reports — built after they land", tier="layer")


def page_ai_analyst():
    _stub("AI Analyst",
          "Ask anything about your commercial data in plain English.",
          ["Natural-language questions → answers over the fact model",
           "On-demand deeper analysis",
           "Explains the 'why' behind any metric move"],
          "Text-to-SQL over semantics.py — built once the fact model is stable", tier="layer")


def page_benchmarks():
    _stub("Benchmarks",
          "Is this good? Context that turns your numbers into judgement.",
          ["Your key metrics vs category benchmarks (conversion, AOV, margin, returns)",
           "Where you sit on the efficiency curve as you scale",
           "Powered by Malleson Labs research"],
          "Benchmark dataset from Malleson research", tier="layer")


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
