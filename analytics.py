"""analytics.py — the app's data brain (no Streamlit; unit-testable).

Reads the conformed fact table and targets, and provides period resolution,
filtering, aggregation and the TY / LY / target comparison engine that the
report views are built on. Derived metrics are computed from base-metric SUMS
via semantics.compute, so query-time maths always matches definitions.yaml.
"""
from __future__ import annotations

import calendar
import datetime as dt

import pandas as pd

import config
import semantics as sem
from ingest import storage


# ── Loading ──────────────────────────────────────────────────────
def load_fact() -> pd.DataFrame | None:
    df = storage.read_df(config.FACT_KEY)
    if df is None:
        return None
    df["date"] = pd.to_datetime(df["date"])
    return df


def load_targets() -> pd.DataFrame | None:
    df = storage.read_df(config.TARGETS_KEY)
    if df is None:
        return None
    df["date"] = pd.to_datetime(df["date"])
    return df


def _load_dated(key: str) -> pd.DataFrame | None:
    df = storage.read_df(key)
    if df is None:
        return None
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    return df


def load_product_fact():
    return _load_dated(config.FACT_PRODUCT_KEY)


def load_email_fact():
    return _load_dated(config.FACT_EMAIL_KEY)


def load_seo_fact():
    return _load_dated(config.FACT_SEO_KEY)


def date_bounds(fact: pd.DataFrame):
    return fact["date"].min().date(), fact["date"].max().date()


# ── Period resolution (the quick selectors from the brief) ───────
PERIODS = [
    "Yesterday", "Week to Date", "Last Week", "Last 7 Days",
    "Month to Date", "Last Month", "Quarter to Date", "Last Quarter",
    "Year to Date", "Last Year", "Last 30 Days", "Last 90 Days",
]


def _q_start(d: dt.date) -> dt.date:
    return dt.date(d.year, 3 * ((d.month - 1) // 3) + 1, 1)


def resolve_period(name: str, ref: dt.date) -> tuple[dt.date, dt.date]:
    """Return (start, end) for a quick-selector name, as of reference date `ref`."""
    if name == "Yesterday":
        return ref, ref
    if name == "Week to Date":
        return ref - dt.timedelta(days=ref.weekday()), ref
    if name == "Last Week":
        this_mon = ref - dt.timedelta(days=ref.weekday())
        return this_mon - dt.timedelta(days=7), this_mon - dt.timedelta(days=1)
    if name == "Last 7 Days":
        return ref - dt.timedelta(days=6), ref
    if name == "Month to Date":
        return ref.replace(day=1), ref
    if name == "Last Month":
        first = ref.replace(day=1)
        last_prev = first - dt.timedelta(days=1)
        return last_prev.replace(day=1), last_prev
    if name == "Quarter to Date":
        return _q_start(ref), ref
    if name == "Last Quarter":
        qs = _q_start(ref)
        prev_end = qs - dt.timedelta(days=1)
        return _q_start(prev_end), prev_end
    if name == "Year to Date":
        return dt.date(ref.year, 1, 1), ref
    if name == "Last Year":
        return dt.date(ref.year - 1, 1, 1), dt.date(ref.year - 1, 12, 31)
    if name == "Last 30 Days":
        return ref - dt.timedelta(days=29), ref
    if name == "Last 90 Days":
        return ref - dt.timedelta(days=89), ref
    return ref.replace(day=1), ref


def ly_range(start: dt.date, end: dt.date) -> tuple[dt.date, dt.date]:
    """Same period last year, shifted 364 days to keep weekday alignment."""
    return start - dt.timedelta(days=364), end - dt.timedelta(days=364)


def prior_period(start: dt.date, end: dt.date) -> tuple[dt.date, dt.date]:
    """The equal-length block immediately before [start, end]."""
    length = (end - start).days + 1
    new_end = start - dt.timedelta(days=1)
    return new_end - dt.timedelta(days=length - 1), new_end


# ── Filtering + aggregation ──────────────────────────────────────
def apply_filters(fact, date_from, date_to, filters: dict | None = None) -> pd.DataFrame:
    m = (fact["date"] >= pd.Timestamp(date_from)) & (fact["date"] <= pd.Timestamp(date_to))
    df = fact[m]
    for dim, values in (filters or {}).items():
        if values and dim in df.columns:  # ignore filters that don't apply to this frame
            df = df[df[dim].isin(values)]
    return df


def _sums(df: pd.DataFrame) -> pd.DataFrame:
    return df[sem.BASE_METRICS].sum().to_frame().T


def totals(df: pd.DataFrame, metrics: list[str]) -> dict:
    s = _sums(df)
    return {m: float(sem.compute(s, m).iloc[0]) for m in metrics}


def breakdown(df, dimension: str, metrics: list[str]) -> pd.DataFrame:
    grouped = df.groupby(dimension, observed=True)[sem.BASE_METRICS].sum()
    out = pd.DataFrame(index=grouped.index)
    for m in metrics:
        out[m] = sem.compute(grouped, m).values
    out = out.reset_index()
    if metrics:
        out = out.sort_values(metrics[0], ascending=False)
    return out.reset_index(drop=True)


def aggregate(df, group_cols: list[str], metrics: list[str]) -> pd.DataFrame:
    grouped = df.groupby(group_cols, observed=True)[sem.BASE_METRICS].sum()
    out = pd.DataFrame(index=grouped.index)
    for m in metrics:
        out[m] = sem.compute(grouped, m).values
    return out.reset_index()


def trend(df, metric: str, freq: str = "D") -> pd.DataFrame:
    g = df.copy()
    g["period"] = g["date"].dt.to_period(freq).dt.start_time
    grouped = g.groupby("period")[sem.BASE_METRICS].sum()
    out = pd.DataFrame({"period": grouped.index})
    out[metric] = sem.compute(grouped, metric).values
    return out


# ── KPI comparison engine (TY / LY / target) ─────────────────────
def _pct(cur, cmp):
    if cmp in (None, 0) or pd.isna(cmp):
        return None
    return (cur / cmp - 1) * 100


def kpi_rows(fact, metrics, cur, cmp, targets, filters=None) -> list[dict]:
    """For each metric: current value, comparison value + %, target + %."""
    cur_df = apply_filters(fact, cur[0], cur[1], filters)
    cmp_df = apply_filters(fact, cmp[0], cmp[1], filters)
    cur_t = totals(cur_df, metrics)
    cmp_t = totals(cmp_df, metrics)
    rows = []
    for m in metrics:
        tgt = target_total(targets, cur[0], cur[1], m)
        rows.append({
            "metric": m,
            "value": cur_t[m],
            "cmp": cmp_t[m],
            "delta_pct": _pct(cur_t[m], cmp_t[m]),
            "target": tgt,
            "vtarg_pct": _pct(cur_t[m], tgt) if tgt else None,
        })
    return rows


def sparkline(fact, metric, end: dt.date, weeks: int = 8, filters=None) -> pd.DataFrame:
    """Weekly series for the last `weeks` weeks ending at `end` (for a sparkline)."""
    start = end - dt.timedelta(days=weeks * 7 - 1)
    df = apply_filters(fact, start, end, filters)
    if df.empty:
        return pd.DataFrame({"period": [], metric: []})
    return trend(df, metric, "W")


def comparison_table(fact, dimension, metrics, cur, cmp, filters=None) -> pd.DataFrame:
    """Per dimension value: current, comparison and % change for each metric."""
    cur_df = apply_filters(fact, cur[0], cur[1], filters)
    cmp_df = apply_filters(fact, cmp[0], cmp[1], filters)
    a = aggregate(cur_df, [dimension], metrics).set_index(dimension)
    b = aggregate(cmp_df, [dimension], metrics).set_index(dimension)
    idx = a.index.union(b.index)
    out = pd.DataFrame(index=idx)
    for m in metrics:
        out[m] = a[m].reindex(idx)
        out[f"{m}__vs%"] = [_pct(a[m].reindex(idx).iloc[i], b[m].reindex(idx).iloc[i])
                            for i in range(len(idx))]
    if metrics:
        out = out.sort_values(metrics[0], ascending=False)
    return out.reset_index().rename(columns={"index": dimension})


# ── Targets ──────────────────────────────────────────────────────
def config_target_map() -> dict:
    return sem.D.get("targets", {}).get("column_map", {})


def target_total(targets, date_from, date_to, metric: str):
    if targets is None:
        return None
    col = next((tc for tc, mn in config_target_map().items()
                if mn == metric and tc in targets.columns), None)
    if col is None:
        return None
    m = (targets["date"] >= pd.Timestamp(date_from)) & (targets["date"] <= pd.Timestamp(date_to))
    return float(targets.loc[m, col].sum())


def validate_targets(df: pd.DataFrame) -> tuple[bool, str]:
    if "date" not in df.columns:
        return False, "File must have a 'date' column (YYYY-MM-DD)."
    known = set(config_target_map().keys())
    matched = [c for c in df.columns if c in known]
    if not matched:
        return False, f"No target columns recognised. Expected any of: {', '.join(sorted(known))}."
    return True, f"OK — {len(df)} rows, target columns: {', '.join(matched)}."
