"""analytics.py — the app's data brain (no Streamlit; unit-testable).

Reads the conformed fact table and targets, and provides filtering + aggregation
+ metric computation. Derived metrics are computed from base-metric SUMS via
semantics.compute, so query-time maths always matches definitions.yaml.
"""
from __future__ import annotations

import pandas as pd

import config
import semantics as sem
from ingest import storage


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


def date_bounds(fact: pd.DataFrame):
    return fact["date"].min().date(), fact["date"].max().date()


def apply_filters(fact: pd.DataFrame, date_from, date_to, filters: dict | None = None) -> pd.DataFrame:
    m = (fact["date"] >= pd.Timestamp(date_from)) & (fact["date"] <= pd.Timestamp(date_to))
    df = fact[m]
    for dim, values in (filters or {}).items():
        if values:
            df = df[df[dim].isin(values)]
    return df


def _sums(df: pd.DataFrame) -> pd.DataFrame:
    """One-row frame of base-metric sums (NaNs skipped)."""
    return df[sem.BASE_METRICS].sum().to_frame().T


def totals(df: pd.DataFrame, metrics: list[str]) -> dict:
    """Total value of each metric across the whole (filtered) frame."""
    s = _sums(df)
    out = {}
    for mname in metrics:
        out[mname] = float(sem.compute(s, mname).iloc[0])
    return out


def breakdown(df: pd.DataFrame, dimension: str, metrics: list[str]) -> pd.DataFrame:
    """Aggregate by one dimension; return numeric metrics per group (raw column
    names kept, so charts and formatting stay simple)."""
    grouped = df.groupby(dimension, observed=True)[sem.BASE_METRICS].sum()
    out = pd.DataFrame(index=grouped.index)
    for mname in metrics:
        out[mname] = sem.compute(grouped, mname).values
    out = out.reset_index()  # `dimension` stays as its raw column name
    if metrics:
        out = out.sort_values(metrics[0], ascending=False)
    return out.reset_index(drop=True)


def aggregate(df: pd.DataFrame, group_cols: list[str], metrics: list[str]) -> pd.DataFrame:
    """Group by several dimensions; return numeric metrics (raw column names)."""
    grouped = df.groupby(group_cols, observed=True)[sem.BASE_METRICS].sum()
    out = pd.DataFrame(index=grouped.index)
    for mname in metrics:
        out[mname] = sem.compute(grouped, mname).values
    return out.reset_index()


def trend(df: pd.DataFrame, metric: str, freq: str = "D") -> pd.DataFrame:
    """Metric over time at the chosen frequency (D/W/M)."""
    g = df.copy()
    g["period"] = g["date"].dt.to_period(freq).dt.start_time
    grouped = g.groupby("period")[sem.BASE_METRICS].sum()
    out = pd.DataFrame({"period": grouped.index})
    out[metric] = sem.compute(grouped, metric).values
    return out


def target_total(targets: pd.DataFrame, date_from, date_to, metric: str):
    """Sum of the target for `metric` over the range, or None if not targeted."""
    if targets is None:
        return None
    col = None
    for tcol, mname in config_target_map().items():
        if mname == metric and tcol in targets.columns:
            col = tcol
            break
    if col is None:
        return None
    m = (targets["date"] >= pd.Timestamp(date_from)) & (targets["date"] <= pd.Timestamp(date_to))
    return float(targets.loc[m, col].sum())


def config_target_map() -> dict:
    return sem.D.get("targets", {}).get("column_map", {})


def validate_targets(df: pd.DataFrame) -> tuple[bool, str]:
    """Check an uploaded targets frame has a date column and at least one target."""
    if "date" not in df.columns:
        return False, "File must have a 'date' column (YYYY-MM-DD)."
    known = set(config_target_map().keys())
    matched = [c for c in df.columns if c in known]
    if not matched:
        return False, f"No target columns recognised. Expected any of: {', '.join(sorted(known))}."
    return True, f"OK — {len(df)} rows, target columns: {', '.join(matched)}."
