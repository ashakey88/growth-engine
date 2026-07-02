"""The Growth Engine — Streamlit app (Malleson Labs styling).

Two parts, mirroring the eCommerce app:
  • Report     — KPI report with period + comparison: Summary cards, Trends,
                 Channels / Regions / Devices sections.
  • Data Table — a simplified flexible table (any dimensions x metrics + export).
Plus Connect sources and Targets utilities. All metric logic lives in
semantics.py / analytics.py.
"""
import calendar
import datetime as dt
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
.block-container, [data-testid="stMainBlockContainer"] { padding-top:2rem !important; }
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

/* KPI cards */
[data-testid="stVerticalBlockBorderWrapper"] { transition:box-shadow .15s, transform .15s; }
[data-testid="stVerticalBlockBorderWrapper"]:hover { box-shadow:0 6px 20px rgba(17,24,39,0.08); transform:translateY(-2px); }
.kpi-name { font-size:11px; color:#64748B; font-weight:600; text-transform:uppercase; letter-spacing:0.06em; }
.kpi-value { font-family:'DM Serif Display',serif; font-size:30px; color:#111827; line-height:1.1; margin:2px 0 8px; }
/* Tap/click-friendly KPI tooltip: a native <details> disclosure rather than a
   Streamlit widget (no extra layout, no rerun). Reveals in normal document
   flow rather than as a floating popup — a floating popup got silently
   clipped by the KPI card's own bordered container. */
.kpi-tip summary.kpi-head { display:flex; align-items:center; justify-content:space-between;
  cursor:pointer; list-style:none; }
.kpi-tip summary.kpi-head::-webkit-details-marker { display:none; }
.kpi-info { color:#CBD2DE; font-size:13px; line-height:1; }
.kpi-tip[open] .kpi-info { color:#2563EB; }
.kpi-tip-body { margin:6px 0 2px; padding:8px 10px; background:#F7F8FA; border:1px solid #E4E8EF;
  border-radius:8px; font-size:12px; font-weight:400; line-height:1.4; color:#374151; }
.pill { display:inline-block; border-radius:999px; padding:3px 10px; font-size:11px; font-weight:700; margin:0 6px 4px 0; white-space:nowrap; }
.pill.up { background:#DCFCE7; color:#15803D; }
.pill.down { background:#FEE2E2; color:#B91C1C; }
.pill.neutral { background:#F1F5F9; color:#64748B; }
.spark-caption { font-size:10px; color:#94A3B8; text-align:right; margin-top:-4px; }

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

/* Small HTML tables (used where a row label itself needs a real hover tooltip,
   e.g. a "Metric" column listing AOV/ROAS/etc. — st.dataframe can't do per-cell
   tooltips, so these render as plain HTML with a title attribute). */
.ml-html-table { width:100%; border-collapse:collapse; font-size:14px; margin:4px 0 8px; }
.ml-html-table th { text-align:left; font-size:12px; font-weight:600; color:#64748B;
  border-bottom:1px solid #E4E8EF; padding:8px 10px; white-space:nowrap; }
.ml-html-table td { padding:8px 10px; border-bottom:1px solid #F1F3F7; color:#111827; }
.ml-html-table tr:last-child td { border-bottom:none; }
.ml-html-table tr.ml-total td { font-weight:700; border-top:1.5px solid #CBD2DE; background:#F7F8FA; }
.ml-tip { border-bottom:1px dotted #94A3B8; cursor:help; }
.ml-up { color:#15803D; font-weight:600; }
.ml-down { color:#B91C1C; font-weight:600; }
</style>
""", unsafe_allow_html=True)

KPI_GROUPS = {
    "Business Summary": ["revenue", "visits", "orders", "conversion_rate", "aov"],
    "Conversion Funnel": ["engagement_rate", "add_to_cart_rate", "checkout_rate",
                         "checkout_completion_rate", "cart_abandonment_rate"],
    # Not shown on the eCommerce summary — it duplicates the dedicated Paid Media
    # report. Kept here so it still appears in the Trends metric picker below.
    "Paid Funnel": ["spend", "roas", "cost_per_visit", "cost_per_add_to_cart",
                    "cost_per_checkout", "cost_per_order"],
}
SUMMARY_GROUPS = ["Business Summary", "Conversion Funnel"]
ALL_KPIS = [m for g in KPI_GROUPS.values() for m in g]

SECTIONS = {
    "Reports": ["eCommerce", "Profitability", "Customers", "Product", "Paid Media",
                "Forecast"],
    "Analysis": ["Order Insight", "SEO"],
    "Intelligence": ["Exec Digest", "AI Analyst", "Benchmarks", "Data Trust"],
    "Utility": ["Data Table", "Connect sources", "Targets"],
}
PERIOD_PAGES = {"eCommerce", "Profitability", "Customers", "Product", "Paid Media",
                "Forecast", "Order Insight", "SEO", "Benchmarks", "Data Table",
                "Exec Digest", "AI Analyst"}

# Filters relevant to each report (not the same set everywhere).
PAGE_FILTERS = {
    "eCommerce": ["marketing_channel_group", "marketing_channel", "paid_ad_platform", "geo_region", "device"],
    "Profitability": ["geo_region", "marketing_channel_group"],
    "Paid Media": ["paid_ad_platform", "paid_campaign_type", "geo_region"],
    "SEO": [],
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


def money2(v):
    """2dp currency — for small per-unit values (e.g. revenue per recipient)."""
    return "—" if v is None or v != v else f"£{v:,.2f}"


def num(v):
    return "—" if v is None or v != v else f"{v:,.0f}"


def pctv(v, dp=1):
    return "—" if v is None or v != v else f"{v * 100:.{dp}f}%"


def ratio(v):
    return "—" if v is None or v != v else f"{v:.2f}"


def metrics_row(items):
    """items: list of (label, value_str, help_or_None) or, to show a vs-period
    change arrow, (label, value_str, help_or_None, delta_pct_or_None,
    direction) where direction is 'standard' (higher=good, default) or
    'reverse' (higher=bad, e.g. spend, returns, CAC)."""
    cols = st.columns(len(items))
    for c, it in zip(cols, items):
        help_ = it[2] if len(it) > 2 else None
        delta = None
        delta_color = "normal"
        if len(it) > 3 and it[3] is not None:
            delta = f"{it[3]:+.0f}%"
            direction = it[4] if len(it) > 4 else "standard"
            delta_color = "inverse" if direction == "reverse" else "normal"
        c.metric(it[0], it[1], delta=delta, delta_color=delta_color, help=help_)


def _tips(help_map: dict):
    """Column header tooltips for st.dataframe: {column_name: definition}."""
    return {c: st.column_config.Column(help=h) for c, h in help_map.items()}


def _metric_direction(metric: str) -> str:
    """'reverse' if higher is worse for this metric, else 'standard'."""
    try:
        return "reverse" if sem.metric_meta(metric).get("cf") == "reverse" else "standard"
    except Exception:
        return "standard"


def _pct_color_class(formatted: str, direction: str = "standard") -> str:
    """Colour class for a signed-% string like '+12%'/'-5%'. direction=
    'standard' means positive is good; 'reverse' means negative is good.
    Returns '' for anything that isn't a signed percentage."""
    if not formatted or formatted[0] not in "+-":
        return ""
    good = formatted.startswith("-") if direction == "reverse" else formatted.startswith("+")
    return "ml-up" if good else "ml-down"


def _html_table(rows: list[dict], key_field: str, tip_lookup, pct_cols=()):
    """Render `rows` as a small HTML table so the first column (typically a
    metric name like 'AOV') can carry a real hover tooltip — st.dataframe has
    no way to attach a tooltip to an individual cell. Each row dict needs a
    `key_field` entry holding the raw metric id (used for the tooltip text and
    to auto-pick colour direction); it is not rendered as a column.
    `tip_lookup(key)` returns the definition string for that key.
    `pct_cols` colour-codes columns of signed-% strings: pass a plain column
    name to auto-derive direction from the row's metric, or (name, 'standard'|
    'reverse') to force a direction (e.g. when the % was pre direction-corrected)."""
    if not rows:
        return
    pct_map = {(pc[0] if isinstance(pc, tuple) else pc):
               (pc[1] if isinstance(pc, tuple) else None) for pc in pct_cols}
    cols = [c for c in rows[0].keys() if c != key_field]
    thead = "".join(f"<th>{c}</th>" for c in cols)
    body = ""
    for r in rows:
        key = r.get(key_field)
        cells = ""
        for i, c in enumerate(cols):
            val = r.get(c, "—")
            if i == 0 and key is not None:
                cells += f'<td><span class="ml-tip" title="{tip_lookup(key)}">{val}</span></td>'
            elif c in pct_map:
                direction = pct_map[c] or _metric_direction(key)
                cls = _pct_color_class(str(val), direction)
                cells += f'<td class="{cls}">{val}</td>' if cls else f"<td>{val}</td>"
            else:
                cells += f"<td>{val}</td>"
        body += f"<tr>{cells}</tr>"
    st.markdown(f'<table class="ml-html-table"><thead><tr>{thead}</tr></thead>'
                f'<tbody>{body}</tbody></table>', unsafe_allow_html=True)


def _in_range(df, start, end, col="date"):
    m = (df[col] >= pd.Timestamp(start)) & (df[col] <= pd.Timestamp(end))
    return df[m]


def _in_period(df, col="date"):
    return _in_range(df, cur[0], cur[1], col)


def _vs_pct(cur_val, cmp_val):
    if not cmp_enabled:
        return None
    return analytics.pct_change(cur_val, cmp_val)


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


_CMP_NOTE = {"LY": "last year", "Prior": "the prior period", "Custom": "the custom comparison period"}


def _cmp_note():
    return _CMP_NOTE.get(cmp_label, "the comparison period")


ICONS = {
    "Reports": "📊", "Analysis": "🔬", "Intelligence": "✨", "Utility": "⚙️",
    "eCommerce": "🛒", "Profitability": "💷", "Customers": "👥", "Product": "📦",
    "Paid Media": "📣", "Forecast": "🎯", "Orderbank": "📥", "Order Insight": "🧾",
    "SEO": "🔎", "Exec Digest": "📌",
    "AI Analyst": "🤖", "Benchmarks": "📐", "Data Trust": "🛡️", "Data Table": "🔎",
    "Connect sources": "🔌", "Targets": "🎚️",
}
BASE_DESC = {
    "revenue": "Total revenue taken from customers — after discounts, before returns.",
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
        return sem.fmt(m, value)  # small values: respect the metric's own dp (e.g. cost-per-X)
    return sem.fmt(m, value)


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
targets = get_targets()


COMPARE_OPTIONS = ["vs Last Year", "vs Prior Period", "None", "Custom…"]
CUSTOM_PERIOD = "Custom…"


def _bounded_range(value, lo, hi, key):
    """A compact date-range picker; returns (start, end), falling back to
    `value` while the user has only picked one end of the range so far.
    Clamps the default into [lo, hi] since e.g. a prior-period default can
    fall before the data's earliest date, which st.date_input rejects."""
    default = (max(lo, min(hi, value[0])), max(lo, min(hi, value[1])))
    picked = st.date_input(" ", value=default, min_value=lo, max_value=hi,
                           key=key, label_visibility="collapsed")
    return picked if isinstance(picked, tuple) and len(picked) == 2 else default


def _fmt_range(r):
    s, e = r
    if s == e:
        return f"{s:%-d %b %Y}"
    s_fmt = "%-d %b %Y" if s.year != e.year else "%-d %b"
    return f"{s:{s_fmt}} – {e:%-d %b %Y}"


def _period_bar():
    """Period / comparison / filters — two compact expanders under the report
    title, matching each other's pattern: collapsed by default, with the
    current selection summarised right in the header so it's clear at a
    glance without opening it. Sets the module-level cur/cmp/filters/etc
    used throughout each page."""
    global period, comparison, filters, cur, cmp, cmp_label, cmp_enabled
    lo, hi = analytics.date_bounds(fact)

    # Collapsed-header summary, read from session_state the same way the
    # Filters expander below counts "active" filters before its widgets run.
    period_val = st.session_state.get("period_ctrl", "Month to Date")
    if period_val == CUSTOM_PERIOD:
        pr = st.session_state.get(f"custom_period_{page}")
        period_txt = _fmt_range(pr) if pr else "Custom period"
    else:
        period_txt = period_val
    cmp_val = st.session_state.get("cmp_ctrl", "vs Last Year")
    if cmp_val == CUSTOM_PERIOD:
        cr = st.session_state.get(f"custom_cmp_{page}")
        cmp_txt = f"vs {_fmt_range(cr)}" if cr else "vs Custom"
    elif cmp_val == "None":
        cmp_txt = "no comparison"
    else:
        cmp_txt = cmp_val

    c1, c2 = st.columns([1.4, 1], gap="small")
    with c1:
        with st.expander(f"📅 {period_txt}   ·   ⚖️ {cmp_txt}", expanded=False):
            period = st.selectbox("Period", analytics.PERIODS + [CUSTOM_PERIOD],
                                  index=analytics.PERIODS.index("Month to Date"),
                                  format_func=lambda p: f"📅 {p}", key="period_ctrl",
                                  label_visibility="collapsed")
            comparison = st.selectbox("Compare against", COMPARE_OPTIONS,
                                      format_func=lambda c: f"⚖️ {c}", key="cmp_ctrl",
                                      label_visibility="collapsed")
            if period == CUSTOM_PERIOD:
                cur = _bounded_range((max(lo, ref - dt.timedelta(days=29)), ref), lo, hi,
                                     key=f"custom_period_{page}")
            else:
                cur = analytics.resolve_period(period, ref)

            if comparison == CUSTOM_PERIOD:
                cmp = _bounded_range(analytics.prior_period(*cur), lo, hi, key=f"custom_cmp_{page}")
                cmp_label, cmp_enabled = "Custom", True
            elif comparison == "None":
                cmp = analytics.prior_period(*cur)  # computed but not shown — see cmp_enabled
                cmp_label, cmp_enabled = None, False
            else:
                cmp = analytics.ly_range(*cur) if comparison == "vs Last Year" else analytics.prior_period(*cur)
                cmp_label = "LY" if comparison == "vs Last Year" else "Prior"
                cmp_enabled = True

    spec = PAGE_FILTERS.get(page, [])
    filters = {}
    with c2:
        if spec:
            fkeys = {dim: f"flt_{page}_{dim}" for dim in spec}  # per-page keys → independent
            active = sum(len(st.session_state.get(k, [])) for k in fkeys.values())
            with st.expander(f"🔎 Filters{f'  ·  {active} active' if active else ''}",
                             expanded=False):
                for dim in spec:
                    opts = _filter_options(dim)
                    sel = st.multiselect(sem.nice(dim), opts, key=fkeys[dim])
                    if sel:
                        filters[dim] = sel


def _page_header(title, icon):
    """Icon + title, then — for pages with a period — the period / compare /
    filters row right underneath, plus a one-line data-freshness caption."""
    st.title(f"{icon} {title}")
    if page in PERIOD_PAGES:
        _period_bar()
        live = conn_state().get("active_source") == "shopify"
        status = "Live via Shopify" if live else "Demo data"
        st.caption(f"Data available up to {ref:%-d %b %Y} · {status}")


# ── Report sections ──────────────────────────────────────────────
def render_summary():
    for group in SUMMARY_GROUPS:
        metrics = KPI_GROUPS[group]
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


_TOOLTIP_NOUN = {"Daily": "Day", "Weekly": "Week", "Monthly": "Month"}


def _spark_chart(spark, metric, freq_label):
    color = "#2563EB"
    grad = alt.Gradient(gradient="linear",
                        stops=[alt.GradientStop(color="#FFFFFF", offset=0),
                               alt.GradientStop(color="#93C5FD", offset=1)],
                        x1=1, x2=1, y1=1, y2=0)
    base = alt.Chart(spark).encode(
        x=alt.X("period:T", axis=None),
        y=alt.Y(f"{metric}:Q", axis=None, scale=alt.Scale(zero=False)),
        tooltip=[alt.Tooltip("period:T", title=_TOOLTIP_NOUN.get(freq_label, freq_label)),
                 alt.Tooltip(f"{metric}:Q", title=sem.nice(metric), format=",.0f")],
    )
    area = base.mark_area(color=grad, opacity=0.5)
    line = base.mark_line(color=color, strokeWidth=2.5)
    return (area + line).properties(height=56).configure_view(strokeWidth=0)


def _spark_caption(start_ts, end_ts, freq):
    label = analytics.FREQ_LABEL[freq]
    cross_year = start_ts.year != end_ts.year
    start_fmt = "%d %b %Y" if cross_year else "%d %b"
    return f"{label} · {start_ts.strftime(start_fmt)} → {end_ts.strftime('%d %b %Y')}"


def _kpi_card(row):
    m = row["metric"]
    pills = _pill(m, row["delta_pct"], cmp_label) if cmp_enabled else ""
    if row.get("target") is not None:  # only show the target pill when a target exists
        pills += _pill(m, row["vtarg_pct"], "Targ")
    with st.container(border=True):
        st.markdown(
            f'<details class="kpi-tip"><summary class="kpi-head">'
            f'<span class="kpi-name">{sem.nice(m)}</span><span class="kpi-info">ⓘ</span>'
            f'</summary>'
            f'<div class="kpi-tip-body">{metric_help(m)}</div>'
            f'</details>'
            f'<div class="kpi-value" title="{sem.fmt(m, row["value"])}">{compact(m, row["value"])}</div>'
            f'<div>{pills}</div>',
            unsafe_allow_html=True)
        spark = analytics.sparkline(fact, m, cur[0], cur[1], filters)
        if len(spark) > 1:
            start_ts, end_ts, freq = analytics.spark_window(cur[0], cur[1])
            st.altair_chart(_spark_chart(spark, m, analytics.FREQ_LABEL[freq]), use_container_width=True)
            st.markdown(f'<div class="spark-caption">{_spark_caption(start_ts, end_ts, freq)}</div>',
                       unsafe_allow_html=True)


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


_TOTAL_ROW_STYLE = "font-weight:700;background-color:#F7F8FA;border-top:1.5px solid #CBD2DE;"


def _style_pct_cell(val, direction):
    cls = _pct_color_class(str(val), direction)
    if cls == "ml-up":
        return "color:#15803D;font-weight:600;"
    if cls == "ml-down":
        return "color:#B91C1C;font-weight:600;"
    return ""


def _comparison_section(dimension, metrics):
    view = analytics.apply_filters(fact, cur[0], cur[1], filters)
    if view.empty:
        _empty()
        return
    dcol = sem.nice(dimension)
    tbl = analytics.comparison_table(fact, dimension, metrics, cur, cmp, filters)
    disp = pd.DataFrame({dcol: tbl[dimension]})
    tips, vs_cols = {}, {}
    for m in metrics:
        mcol = sem.nice(m)
        disp[mcol] = tbl[m].map(lambda v, mm=m: sem.fmt(mm, v))
        tips[mcol] = metric_help(m)
        if cmp_enabled:
            vcol = f"{mcol} vs {cmp_label}"
            disp[vcol] = tbl[f"{m}__vs%"].map(fmt_pct)
            tips[vcol] = f"Change vs {_cmp_note()}"
            vs_cols[vcol] = _metric_direction(m)
    styler = disp.style.apply(
        lambda row: [_TOTAL_ROW_STYLE if row[dcol] == "Total" else "" for _ in row], axis=1)
    for vcol, direction in vs_cols.items():
        styler = styler.map(lambda v, d=direction: _style_pct_cell(v, d), subset=[vcol])
    st.dataframe(styler, use_container_width=True, hide_index=True, column_config=_tips(tips))


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
    _page_header("eCommerce", "🛒")
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
    _page_header("Data Table", "🔎")
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
    _page_header("Profitability", "💷")
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


# ── Customers & Retention ────────────────────────────────────────
def page_customers():
    _page_header("Customers & Retention", "👥")
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

    cp = o[(o["date"] >= pd.Timestamp(cmp[0])) & (o["date"] <= pd.Timestamp(cmp[1]))]
    if not cp.empty:
        cmp_custs = cp["customer_id"].nunique()
        cmp_is_new = cp["first_order"].between(pd.Timestamp(cmp[0]), pd.Timestamp(cmp[1]))
        cmp_new = cp.loc[cmp_is_new, "customer_id"].nunique()
        cmp_orders_ct, cmp_revenue = len(cp), cp["net_sales"].sum()
        cmp_spend = analytics.totals(analytics.apply_filters(fact, cmp[0], cmp[1], filters), ["spend"])["spend"]
        cmp_cac = cmp_spend / cmp_new if cmp_new else None
    else:
        cmp_custs = cmp_new = cmp_orders_ct = cmp_revenue = cmp_cac = None

    metrics_row([
        ("Customers", num(custs), "Distinct customers who ordered this period", _vs_pct(custs, cmp_custs)),
        ("New customers", num(new), "First-ever order fell in this period", _vs_pct(new, cmp_new)),
        ("Repeat rate", pctv((custs - new) / custs if custs else None), "Returning ÷ all customers",
         _vs_pct((custs - new) / custs if custs else None,
                (cmp_custs - cmp_new) / cmp_custs if cmp_custs else None)),
        ("Orders / customer", ratio(orders_ct / custs if custs else None), "Orders this period ÷ customers who ordered",
         _vs_pct(orders_ct / custs if custs else None, cmp_orders_ct / cmp_custs if cmp_custs else None)),
    ])
    metrics_row([
        ("AOV", money(revenue / orders_ct if orders_ct else None), "Average order value = Revenue ÷ Orders",
         _vs_pct(revenue / orders_ct if orders_ct else None, cmp_revenue / cmp_orders_ct if cmp_orders_ct else None)),
        ("Avg LTV", money(ltv), "Average lifetime net revenue per customer"),
        ("Blended CAC", money(cac), "Marketing spend ÷ new customers", _vs_pct(cac, cmp_cac), "reverse"),
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
            e_cmp = _in_range(em, cmp[0], cmp[1])
            g = e.groupby(["type", "name"]).agg(recipients=("recipients", "sum"),
                orders=("orders", "sum"), revenue=("revenue", "sum")).reset_index()
            g["rev / recipient"] = g["revenue"] / g["recipients"].replace(0, np.nan)
            tot_rev, tot_recip, tot_ord = g["revenue"].sum(), g["recipients"].sum(), g["orders"].sum()
            cmp_rev = e_cmp["revenue"].sum() if not e_cmp.empty else None
            metrics_row([
                ("Email revenue", money(tot_rev), "Revenue attributed to Klaviyo flows and campaigns",
                 _vs_pct(tot_rev, cmp_rev)),
                ("Email orders", num(tot_ord), "Orders attributed to Klaviyo flows and campaigns"),
                ("Rev / recipient", money2(tot_rev / tot_recip if tot_recip else None),
                 "Email revenue ÷ recipients — efficiency per send"),
            ])
            disp = g.sort_values("revenue", ascending=False).copy()
            disp["revenue"] = disp["revenue"].map(money)
            disp["rev / recipient"] = disp["rev / recipient"].map(money2)
            disp["recipients"] = disp["recipients"].map(num)
            disp["orders"] = disp["orders"].map(num)
            disp.columns = ["Type", "Name", "Recipients", "Orders", "Revenue", "Rev / Recipient"]
            total_row = {"Type": "Total", "Name": "", "Recipients": num(tot_recip), "Orders": num(tot_ord),
                        "Revenue": money(tot_rev), "Rev / Recipient": money2(tot_rev / tot_recip if tot_recip else None)}
            disp = pd.concat([disp, pd.DataFrame([total_row])], ignore_index=True)
            styler = disp.style.apply(
                lambda row: [_TOTAL_ROW_STYLE if row["Type"] == "Total" else "" for _ in row], axis=1)
            st.dataframe(styler, use_container_width=True, hide_index=True, column_config=_tips({
                "Type": "Flow (always-on) or one-off campaign",
                "Recipients": "Number of people the send reached",
                "Rev / Recipient": "Revenue ÷ recipients — efficiency per send",
            }))


# ── Product / Merchandising ──────────────────────────────────────
_PRODUCT_EXTRA_COLS = ["product_views", "product_add_to_carts", "on_hand", "returned_units", "refund_amount"]


def _product_agg(df):
    for c in _PRODUCT_EXTRA_COLS:
        if c not in df:
            df[c] = 0
    return df.groupby(["product_id", "product_title", "category"]).agg(
        units=("units", "sum"), revenue=("revenue", "sum"), gross_sales=("gross_sales", "sum"),
        discounts=("discounts", "sum"), gross_profit=("gross_profit", "sum"),
        views=("product_views", "sum"), atc=("product_add_to_carts", "sum"),
        on_hand=("on_hand", "last"), returned=("returned_units", "sum"),
        refund=("refund_amount", "sum"),
    ).reset_index().fillna(0)


def page_product():
    _page_header("Product / Merchandising", "📦")
    fp = get_product_fact()
    if fp is None or fp.empty:
        _empty("No product data.")
        return
    p = _filt(_in_period(fp), filters)
    if p.empty:
        _empty()
        return
    agg = _product_agg(p)
    weeks = max(1.0, ((cur[1] - cur[0]).days + 1) / 7)

    p_cmp = _filt(_in_range(fp, cmp[0], cmp[1]), filters)
    agg_cmp = _product_agg(p_cmp) if not p_cmp.empty else agg.iloc[0:0].copy()
    vs_label = f"vs {cmp_label}"

    t1, t2, t3, t4 = st.tabs(["Sales & Margin", "Funnel", "Stock", "Returns"])

    # ── Sales & Margin ────────────────────────────────────────────
    with t1:
        tot = agg[["revenue", "units", "gross_sales", "discounts", "gross_profit"]].sum()
        cmp_tot = (agg_cmp[["revenue", "gross_sales", "discounts", "gross_profit"]].sum()
                  if not agg_cmp.empty else None)
        cmp_disc_pct = (cmp_tot["discounts"] / cmp_tot["gross_sales"]
                       if cmp_tot is not None and cmp_tot["gross_sales"] else None)
        metrics_row([
            ("Revenue", money(tot["revenue"]), "Total product revenue in this period",
             _vs_pct(tot["revenue"], cmp_tot["revenue"] if cmp_tot is not None else None)),
            ("Units", num(tot["units"]), "Total units sold"),
            ("ASP", money(tot["revenue"] / tot["units"] if tot["units"] else None), "Average selling price = Revenue ÷ Units"),
            ("Gross margin", pctv(tot["gross_profit"] / tot["revenue"] if tot["revenue"] else None), "Gross profit ÷ revenue",
             _vs_pct(tot["gross_profit"] / tot["revenue"] if tot["revenue"] else None,
                    cmp_tot["gross_profit"] / cmp_tot["revenue"] if cmp_tot is not None and cmp_tot["revenue"] else None)),
            ("Discount %", pctv(tot["discounts"] / tot["gross_sales"] if tot["gross_sales"] else None), "Discounts ÷ gross sales",
             _vs_pct(tot["discounts"] / tot["gross_sales"] if tot["gross_sales"] else None, cmp_disc_pct), "reverse"),
        ])
        cat = agg.groupby("category").agg(revenue=("revenue", "sum"), units=("units", "sum"),
            gross_sales=("gross_sales", "sum"), discounts=("discounts", "sum"),
            gross_profit=("gross_profit", "sum")).reset_index()
        st.bar_chart(cat.set_index("category"), y="revenue", height=240)

        cat_cmp = (agg_cmp.groupby("category").agg(revenue=("revenue", "sum"),
                   gross_profit=("gross_profit", "sum")).to_dict("index") if not agg_cmp.empty else {})
        vcol_rev, vcol_gm = f"Revenue {vs_label}", f"GM % {vs_label}"
        disp = pd.DataFrame({"Category": cat["category"]})
        disp["Revenue"] = cat["revenue"].map(money)
        disp["Units"] = cat["units"].map(num)
        disp["ASP"] = (cat["revenue"] / cat["units"].replace(0, np.nan)).map(money)
        disp["Disc %"] = (cat["discounts"] / cat["gross_sales"].replace(0, np.nan)).map(pctv)
        disp["GM %"] = (cat["gross_profit"] / cat["revenue"].replace(0, np.nan)).map(pctv)
        disp["GM £"] = cat["gross_profit"].map(money)
        tips = {
            "ASP": "Average selling price = Revenue ÷ Units",
            "Disc %": "Discounts ÷ gross sales",
            "GM %": "Gross profit ÷ revenue",
            "GM £": "Revenue minus COGS",
        }
        total_row = {
            "Category": "Total", "Revenue": money(tot["revenue"]), "Units": num(tot["units"]),
            "ASP": money(tot["revenue"] / tot["units"] if tot["units"] else None),
            "Disc %": pctv(tot["discounts"] / tot["gross_sales"] if tot["gross_sales"] else None),
            "GM %": pctv(tot["gross_profit"] / tot["revenue"] if tot["revenue"] else None),
            "GM £": money(tot["gross_profit"]),
        }
        if cmp_enabled:
            disp[vcol_rev] = [fmt_pct(_vs_pct(rev, cat_cmp.get(c, {}).get("revenue")))
                              for c, rev in zip(cat["category"], cat["revenue"])]
            disp[vcol_gm] = [
                fmt_pct(_vs_pct((gp / rev) if rev else None,
                               (cat_cmp.get(c, {}).get("gross_profit") / cat_cmp.get(c, {}).get("revenue"))
                               if cat_cmp.get(c, {}).get("revenue") else None))
                for c, rev, gp in zip(cat["category"], cat["revenue"], cat["gross_profit"])
            ]
            total_row[vcol_rev] = fmt_pct(_vs_pct(tot["revenue"], cmp_tot["revenue"] if cmp_tot is not None else None))
            total_row[vcol_gm] = fmt_pct(_vs_pct(
                tot["gross_profit"] / tot["revenue"] if tot["revenue"] else None,
                cmp_tot["gross_profit"] / cmp_tot["revenue"] if cmp_tot is not None and cmp_tot["revenue"] else None))
            tips[vcol_rev] = f"Revenue change vs {_cmp_note()}"
            tips[vcol_gm] = f"Gross margin change vs {_cmp_note()}"
        disp = pd.concat([disp, pd.DataFrame([total_row])], ignore_index=True)
        styler = disp.style.apply(
            lambda row: [_TOTAL_ROW_STYLE if row["Category"] == "Total" else "" for _ in row], axis=1)
        if cmp_enabled:
            styler = styler.map(lambda v: _style_pct_cell(v, "standard"), subset=[vcol_rev, vcol_gm])
        st.dataframe(styler, use_container_width=True, hide_index=True, column_config=_tips(tips))

    # ── Funnel ──────────────────────────────────────────────────────
    with t2:
        f = agg.copy()
        f["atc_rate"] = f["atc"] / f["views"].replace(0, np.nan)
        f["conv_rate"] = f["units"] / f["views"].replace(0, np.nan)
        top = f.sort_values("views", ascending=False).head(20).copy()

        prod_cmp = (agg_cmp.set_index("product_id")[["views", "units"]].to_dict("index")
                    if not agg_cmp.empty else {})
        vcol_conv = f"Conversion % {vs_label}"
        disp = pd.DataFrame({"Product": top["product_title"]})
        disp["Views"] = top["views"].map(num)
        disp["Add to Carts"] = top["atc"].map(num)
        disp["ATC %"] = top["atc_rate"].map(pctv)
        disp["Units"] = top["units"].map(num)
        disp["Conversion %"] = top["conv_rate"].map(pctv)
        tot_views, tot_atc, tot_units_f = f["views"].sum(), f["atc"].sum(), f["units"].sum()
        cmp_views = agg_cmp["views"].sum() if not agg_cmp.empty else None
        cmp_units_f = agg_cmp["units"].sum() if not agg_cmp.empty else None
        tips = {
            "Views": "GA4 product page views",
            "ATC %": "Add to carts ÷ views",
            "Conversion %": "Units sold ÷ views",
        }
        total_row = {
            "Product": "Total", "Views": num(tot_views), "Add to Carts": num(tot_atc),
            "ATC %": pctv(tot_atc / tot_views if tot_views else None), "Units": num(tot_units_f),
            "Conversion %": pctv(tot_units_f / tot_views if tot_views else None),
        }
        if cmp_enabled:
            disp[vcol_conv] = [
                fmt_pct(_vs_pct(conv, (prod_cmp[pid]["units"] / prod_cmp[pid]["views"])
                               if pid in prod_cmp and prod_cmp[pid]["views"] else None))
                for pid, conv in zip(top["product_id"], top["conv_rate"])
            ]
            total_row[vcol_conv] = fmt_pct(_vs_pct(tot_units_f / tot_views if tot_views else None,
                                                   cmp_units_f / cmp_views if cmp_views else None))
            tips[vcol_conv] = f"Conversion rate change vs {_cmp_note()}"
        disp = pd.concat([disp, pd.DataFrame([total_row])], ignore_index=True)
        st.caption("Product-level funnel: views → add-to-cart rate → conversion. Showing the top 20 by "
                   "views; Total reflects every product.")
        styler = disp.style.apply(
            lambda row: [_TOTAL_ROW_STYLE if row["Product"] == "Total" else "" for _ in row], axis=1)
        if cmp_enabled:
            styler = styler.map(lambda v: _style_pct_cell(v, "standard"), subset=[vcol_conv])
        st.dataframe(styler, use_container_width=True, hide_index=True, column_config=_tips(tips))

    # ── Stock ─────────────────────────────────────────────────────
    with t3:
        s = agg.copy()
        s["weeks_cover"] = s["on_hand"] / (s["units"] / weeks).replace(0, np.nan)
        avail = (s["on_hand"] > 0).mean()
        cmp_avail = (agg_cmp["on_hand"] > 0).mean() if not agg_cmp.empty else None
        metrics_row([
            ("In-stock availability", pctv(avail), "Share of products with stock on hand",
             _vs_pct(avail, cmp_avail)),
            ("Avg weeks cover", ratio(s["weeks_cover"].replace([np.inf], np.nan).mean()), "On hand ÷ weekly sell-through"),
            ("Out of stock", num((s["on_hand"] <= 0).sum()), "Products currently showing zero units on hand"),
        ])
        low = s[(s["weeks_cover"] <= 3) | (s["on_hand"] <= 0)].sort_values("weeks_cover")
        st.caption("Products with ≤ 3 weeks cover (or out of stock) at the current rate. Total reflects "
                   "stock on hand across every product.")
        disp = pd.DataFrame({"Product": low["product_title"].head(20).values})
        disp["Category"] = low["category"].head(20).values
        disp["On hand"] = [num(v) for v in low["on_hand"].head(20).values]
        disp["Weeks cover"] = ["—" if pd.isna(v) else f"{v:.1f}" for v in low["weeks_cover"].head(20).values]
        total_row = {"Product": "Total", "Category": "", "On hand": num(s["on_hand"].sum()), "Weeks cover": ""}
        disp = pd.concat([disp, pd.DataFrame([total_row])], ignore_index=True)
        styler = disp.style.apply(
            lambda row: [_TOTAL_ROW_STYLE if row["Product"] == "Total" else "" for _ in row], axis=1)
        st.dataframe(styler, use_container_width=True, hide_index=True, column_config=_tips({
            "Weeks cover": "On hand ÷ average weekly units sold — weeks of stock left at this rate",
            "On hand": "Units currently in stock (Total = across every product, not just those shown)",
        }))
        if low.empty:
            st.success("No products low on stock. 🎉")

    # ── Returns ───────────────────────────────────────────────────
    with t4:
        r = agg.copy()
        tot_u, tot_r, tot_rev, tot_ref = r["units"].sum(), r["returned"].sum(), r["revenue"].sum(), r["refund"].sum()
        cmp_u = agg_cmp["units"].sum() if not agg_cmp.empty else None
        cmp_r = agg_cmp["returned"].sum() if not agg_cmp.empty else None
        metrics_row([
            ("Return rate (items)", pctv(tot_r / tot_u if tot_u else None), "Returned units ÷ units sold",
             _vs_pct(tot_r / tot_u if tot_u else None, cmp_r / cmp_u if cmp_u else None), "reverse"),
            ("Return rate (value)", pctv(tot_ref / tot_rev if tot_rev else None), "Refund value ÷ revenue"),
            ("Refunds", money(tot_ref), "Total refund value for returns in this period"),
        ])
        r["return_rate"] = r["returned"] / r["units"].replace(0, np.nan)
        worst = r[r["returned"] > 0].sort_values("return_rate", ascending=False).head(15)
        disp = pd.DataFrame({"Product": worst["product_title"].values})
        disp["Category"] = worst["category"].values
        disp["Units"] = [num(v) for v in worst["units"].values]
        disp["Returned"] = [num(v) for v in worst["returned"].values]
        disp["Return %"] = [pctv(v) for v in worst["return_rate"].values]
        total_row = {"Product": "Total", "Category": "", "Units": num(tot_u), "Returned": num(tot_r),
                     "Return %": pctv(tot_r / tot_u if tot_u else None)}
        disp = pd.concat([disp, pd.DataFrame([total_row])], ignore_index=True)
        st.caption("Total reflects returns across every product, not just those shown.")
        styler = disp.style.apply(
            lambda row: [_TOTAL_ROW_STYLE if row["Product"] == "Total" else "" for _ in row], axis=1)
        st.dataframe(styler, use_container_width=True, hide_index=True, column_config=_tips({
            "Return %": "Returned units ÷ units sold, for this product",
        }))
        rets = get_returns()
        if rets is not None and not rets.empty:
            rr = _filt(_in_period(rets), filters)
            if not rr.empty and "reason" in rr:
                st.markdown("**Return reasons**")
                st.bar_chart(rr.groupby("reason").size().sort_values(ascending=False), height=240)


# ── Paid Media ───────────────────────────────────────────────────
def page_paid_media():
    _page_header("Paid Media", "📣")
    cur_df = analytics.apply_filters(fact, cur[0], cur[1], filters)
    total_rev = analytics.totals(cur_df, ["revenue"])["revenue"]
    orders = analytics.totals(cur_df, ["orders"])["orders"]
    paid = cur_df[cur_df["paid_ad_platform"] != sem.NA]
    if paid.empty:
        _empty("No paid media data.")
        return
    spend = paid["spend"].sum()
    conv_val = paid["platform_conversion_value_7d"].sum()

    cmp_df = analytics.apply_filters(fact, cmp[0], cmp[1], filters)
    cmp_paid = cmp_df[cmp_df["paid_ad_platform"] != sem.NA]
    cmp_spend = cmp_paid["spend"].sum() if not cmp_paid.empty else None
    cmp_total_rev = analytics.totals(cmp_df, ["revenue"])["revenue"] if not cmp_df.empty else None
    cmp_orders = analytics.totals(cmp_df, ["orders"])["orders"] if not cmp_df.empty else None
    cmp_conv_val = cmp_paid["platform_conversion_value_7d"].sum() if not cmp_paid.empty else None

    metrics_row([
        ("Total spend", money(spend), "Total ad spend across all platforms",
         _vs_pct(spend, cmp_spend), "reverse"),
        ("Blended MER", ratio(total_rev / spend) if spend else "—", "Total revenue ÷ total ad spend",
         _vs_pct(total_rev / spend if spend else None, cmp_total_rev / cmp_spend if cmp_spend else None)),
        ("Blended CAC", money(spend / orders) if orders else "—", "Spend ÷ orders",
         _vs_pct(spend / orders if orders else None, cmp_spend / cmp_orders if cmp_orders else None), "reverse"),
        ("Platform ROAS", ratio(conv_val / spend) if spend else "—", "Platform-reported value ÷ spend",
         _vs_pct(conv_val / spend if spend else None, cmp_conv_val / cmp_spend if cmp_spend else None)),
    ])
    g = paid.groupby("paid_ad_platform").agg(spend=("spend", "sum"),
        impressions=("impressions", "sum"), clicks=("clicks", "sum"),
        conv=("platform_conversions_7d", "sum"),
        conv_val=("platform_conversion_value_7d", "sum")).reset_index()
    g["roas"] = g["conv_val"] / g["spend"].replace(0, np.nan)
    st.bar_chart(g.set_index("paid_ad_platform"), y="spend", height=260)

    g_cmp = (cmp_paid.groupby("paid_ad_platform").agg(spend=("spend", "sum"),
             conv_val=("platform_conversion_value_7d", "sum")).to_dict("index")
             if not cmp_paid.empty else {})
    vcol_spend, vcol_roas = f"Spend vs {cmp_label}", f"ROAS vs {cmp_label}"
    disp = pd.DataFrame({"Platform": g["paid_ad_platform"]})
    disp["Spend"] = g["spend"].map(money)
    disp["Conversions"] = g["conv"].map(num)
    disp["ROAS"] = g["roas"].map(ratio)
    disp["CTR %"] = (g["clicks"] / g["impressions"].replace(0, np.nan)).map(pctv)
    disp["CPC"] = (g["spend"] / g["clicks"].replace(0, np.nan)).map(money2)
    disp["CPA"] = (g["spend"] / g["conv"].replace(0, np.nan)).map(money2)
    tips = {
        "Conversions": "Platform-reported conversions (7-day window)",
        "ROAS": "Platform-reported conversion value ÷ spend",
        "CTR %": "Clicks ÷ impressions",
        "CPC": "Spend ÷ clicks",
        "CPA": "Spend ÷ conversions",
    }
    total_row = {
        "Platform": "Total", "Spend": money(spend), "Conversions": num(g["conv"].sum()),
        "ROAS": ratio(conv_val / spend if spend else None),
        "CTR %": pctv(g["clicks"].sum() / g["impressions"].sum() if g["impressions"].sum() else None),
        "CPC": money2(spend / g["clicks"].sum() if g["clicks"].sum() else None),
        "CPA": money2(spend / g["conv"].sum() if g["conv"].sum() else None),
    }
    if cmp_enabled:
        disp[vcol_spend] = [fmt_pct(_vs_pct(s, g_cmp.get(pl, {}).get("spend")))
                            for pl, s in zip(g["paid_ad_platform"], g["spend"])]
        disp[vcol_roas] = [
            fmt_pct(_vs_pct(r, (g_cmp.get(pl, {}).get("conv_val") / g_cmp.get(pl, {}).get("spend"))
                           if g_cmp.get(pl, {}).get("spend") else None))
            for pl, r in zip(g["paid_ad_platform"], g["roas"])
        ]
        total_row[vcol_spend] = fmt_pct(_vs_pct(spend, cmp_spend))
        total_row[vcol_roas] = fmt_pct(_vs_pct(conv_val / spend if spend else None,
                                               cmp_conv_val / cmp_spend if cmp_spend else None))
        tips[vcol_spend] = f"Spend change vs {_cmp_note()}"
        tips[vcol_roas] = f"ROAS change vs {_cmp_note()}"
    disp = pd.concat([disp, pd.DataFrame([total_row])], ignore_index=True)
    styler = disp.style.apply(
        lambda row: [_TOTAL_ROW_STYLE if row["Platform"] == "Total" else "" for _ in row], axis=1)
    if cmp_enabled:
        styler = (styler.map(lambda v: _style_pct_cell(v, "reverse"), subset=[vcol_spend])
                        .map(lambda v: _style_pct_cell(v, "standard"), subset=[vcol_roas]))
    st.dataframe(styler, use_container_width=True, hide_index=True, column_config=_tips(tips))
    st.caption("Channel truth: these are *platform-reported* conversions (Meta/Google over-report). "
               "True channel-level revenue needs GA4→sales reconciliation — a next step.")


# ── SEO (Analysis) ───────────────────────────────────────────────
def page_seo():
    _page_header("SEO", "🔎")
    seo = get_seo_fact()
    if seo is None or seo.empty:
        st.info("🔌 Connect Search Console to light up SEO.")
        return
    s = _in_period(seo)
    if s.empty:
        _empty()
        return
    s_cmp = _in_range(seo, cmp[0], cmp[1])
    cmp_clicks = s_cmp["clicks"].sum() if not s_cmp.empty else None
    cmp_impr = s_cmp["impressions"].sum() if not s_cmp.empty else None
    cmp_pos = s_cmp["position"].mean() if not s_cmp.empty else None
    metrics_row([
        ("Clicks", num(s["clicks"].sum()), "Organic search clicks (Search Console)",
         _vs_pct(s["clicks"].sum(), cmp_clicks)),
        ("Impressions", num(s["impressions"].sum()), "Times your pages appeared in search results",
         _vs_pct(s["impressions"].sum(), cmp_impr)),
        ("Avg position", ratio(s["position"].mean()), "Average search ranking position — lower is better",
         _vs_pct(s["position"].mean(), cmp_pos), "reverse"),
        ("CTR", pctv(s["clicks"].sum() / s["impressions"].sum() if s["impressions"].sum() else None, 2),
         "Clicks ÷ impressions"),
    ])
    if "branded" in s:
        b = s.groupby("branded").agg(clicks=("clicks", "sum")).reset_index()
        b["branded"] = b["branded"].map({True: "Branded", False: "Non-branded"})
        st.bar_chart(b.set_index("branded"), y="clicks", height=220)

    q_full = s.groupby("query").agg(clicks=("clicks", "sum"), impressions=("impressions", "sum"),
        position=("position", "mean")).reset_index()
    q = q_full.sort_values("clicks", ascending=False).head(15)
    q_cmp = s_cmp.groupby("query")["clicks"].sum().to_dict() if not s_cmp.empty else {}
    vcol_clicks = f"Clicks vs {cmp_label}"
    disp = pd.DataFrame({"Query": q["query"]})
    disp["Clicks"] = q["clicks"].map(num)
    disp["Impressions"] = q["impressions"].map(num)
    disp["Avg position"] = q["position"].map(lambda v: "—" if pd.isna(v) else f"{v:.1f}")
    tot_pos = q_full["position"].mean() if len(q_full) else None
    tips = {"Avg position": "Average ranking position for this query — lower is better"}
    total_row = {
        "Query": "Total", "Clicks": num(q_full["clicks"].sum()), "Impressions": num(q_full["impressions"].sum()),
        "Avg position": "—" if tot_pos is None or pd.isna(tot_pos) else f"{tot_pos:.1f}",
    }
    if cmp_enabled:
        disp[vcol_clicks] = [fmt_pct(_vs_pct(c, q_cmp.get(qq))) for qq, c in zip(q["query"], q["clicks"])]
        total_row[vcol_clicks] = fmt_pct(_vs_pct(q_full["clicks"].sum(), cmp_clicks))
        tips[vcol_clicks] = f"Clicks change vs {_cmp_note()}"
    disp = pd.concat([disp, pd.DataFrame([total_row])], ignore_index=True)
    st.caption("Showing the top 15 queries by clicks; Total reflects every query.")
    styler = disp.style.apply(
        lambda row: [_TOTAL_ROW_STYLE if row["Query"] == "Total" else "" for _ in row], axis=1)
    if cmp_enabled:
        styler = styler.map(lambda v: _style_pct_cell(v, "standard"), subset=[vcol_clicks])
    st.dataframe(styler, use_container_width=True, hide_index=True, column_config=_tips(tips))


# ── Forecast & Pacing (Perf vs Budget + run-rate) ────────────────
def page_forecast():
    _page_header("Forecast & Pacing", "🎯")
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
                "_key": m, "Metric": sem.nice(m), "Actual": sem.fmt(m, actual),
                "Budget": sem.fmt(m, budget) if budget else "—",
                "v Budget": fmt_pct((actual / budget - 1) * 100) if budget else "—",
                "LY": sem.fmt(m, lyv),
                "v LY": fmt_pct((actual / lyv - 1) * 100) if lyv else "—",
            })
        _html_table(rows, "_key", metric_help, pct_cols=["v Budget", "v LY"])
        st.caption("Hover a metric name for its definition.")
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
            rows.append({"_key": m, "Metric": sem.nice(m), "MTD actual": sem.fmt(m, actual),
                         "Projected month": sem.fmt(m, proj),
                         "Month budget": sem.fmt(m, tgt) if tgt else "—",
                         "Projected vs budget": fmt_pct((proj / tgt - 1) * 100) if tgt else "—"})
        _html_table(rows, "_key", metric_help, pct_cols=["Projected vs budget"])
        st.caption(f"Day {elapsed} of {dim}. Linear run-rate projection. Hover a metric name for its definition.")


# ── Orderbank ────────────────────────────────────────────────────
def page_orderbank():
    _page_header("Orderbank", "📥")
    st.caption("Open sales orders taken but not yet invoiced.")
    ob = get_orderbank()
    if ob is None or ob.empty:
        _empty("No orderbank data.")
        return
    latest = ob["date"].max()
    snap = ob[ob["date"] == latest]
    metrics_row([
        ("Open value", money(snap["open_value"].sum()), "Value of orders not yet invoiced"),
        ("Open orders", num(snap["open_orders"].sum()), "Number of orders taken but not yet invoiced"),
        ("Open items", num(snap["open_items"].sum()), "Units within those open orders"),
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
    _page_header("Order Insight", "🧾")
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

    l_cmp = _filt(_in_range(li, cmp[0], cmp[1], col="created_at"), filters)
    if not l_cmp.empty:
        orders_cmp = l_cmp.groupby("order_id").agg(value=("net_sales", "sum"), items=("quantity", "sum")).reset_index()
        cmp_order_ct, cmp_aov = len(orders_cmp), orders_cmp["value"].mean()
        cmp_avg_items, cmp_units = orders_cmp["items"].mean(), l_cmp["quantity"].sum()
    else:
        cmp_order_ct = cmp_aov = cmp_avg_items = cmp_units = None

    metrics_row([
        ("Orders", num(len(orders)), "Orders placed in this period", _vs_pct(len(orders), cmp_order_ct)),
        ("AOV", money(orders["value"].mean()), "Average order value = Revenue ÷ Orders",
         _vs_pct(orders["value"].mean(), cmp_aov)),
        ("Median order", money(orders["value"].median()), "Half of orders are below this"),
        ("P90 order", money(orders["value"].quantile(0.9)), "Top 10% of orders exceed this"),
    ])
    metrics_row([
        ("Avg items / order", ratio(orders["items"].mean()), "Units ÷ orders",
         _vs_pct(orders["items"].mean(), cmp_avg_items)),
        ("Single-item orders", pctv((orders["items"] == 1).mean()), "Share of orders containing exactly one item"),
        ("Units sold", num(l["quantity"].sum()), "Total units across all orders in this period",
         _vs_pct(l["quantity"].sum(), cmp_units)),
    ])
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
    _page_header("Exec Digest", "📌")
    st.caption("The Monday-morning one-pager — the numbers that matter and what moved.")
    _kpi_grid(["revenue", "contribution", "gross_margin_pct", "mer"])
    _kpi_grid(["orders", "aov", "spend", "roas"])
    st.markdown("#### What changed")
    if not cmp_enabled:
        st.caption("Pick a comparison period above to see what moved.")
    else:
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
    _page_header("AI Analyst", "🤖")
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
    if cmp_enabled:
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
    _page_header("Benchmarks", "📐")
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
        rows.append({"_key": m, "Metric": sem.nice(m), "You": sem.fmt(m, actual),
                     "Benchmark": sem.fmt(m, bench), "vs Benchmark": fmt_pct(gap)})
    _html_table(rows, "_key", metric_help, pct_cols=[("vs Benchmark", "standard")])
    st.caption("Positive = better than benchmark (direction-aware for cost/abandonment metrics). "
               "Hover a metric name for its definition.")


PAGES = {
    "eCommerce": page_report, "Profitability": page_profitability,
    "Customers": page_customers, "Product": page_product,
    "Paid Media": page_paid_media, "Forecast": page_forecast,
    "Order Insight": page_order_insight, "SEO": page_seo, "Exec Digest": page_exec_digest,
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
