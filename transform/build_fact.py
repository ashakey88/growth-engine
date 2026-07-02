"""build_fact.py — the data-modelling step.

Reads each source's raw parquet, maps it onto the conformed "stacked fact" grain
via semantics.py, unions into one long table, and writes fact/fact.parquet.

One row per source per dimension-combination per day. A source only fills the
metric columns in its lane; everything else is null. The app GROUP BYs the
dimensions it wants and computes derived metrics from the base columns.

Lanes:  sales -> Shopify (source of truth) | traffic -> GA4 | platform -> Meta+Google
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402
import semantics as sem  # noqa: E402
from ingest import storage  # noqa: E402


def _assemble(dims: dict, n: int) -> pd.DataFrame:
    out = sem.empty_metric_frame(n)
    for k, v in dims.items():
        out[k] = v
    return out


# ── SHOPIFY (sales source of truth) — aggregate orders to date x country ──
def map_shopify(orders: pd.DataFrame) -> pd.DataFrame:
    if orders is None or orders.empty:
        return pd.DataFrame(columns=sem.FACT_COLUMNS)
    df = orders.copy()
    df["date"] = pd.to_datetime(df["created_at"]).dt.strftime("%Y-%m-%d")
    g = df.groupby(["date", "country"], dropna=False).agg(
        orders=("order_id", "nunique"),
        revenue=("net_sales", "sum"),
        gross_sales=("gross_sales", "sum"),
        discounts=("discounts", "sum"),
        cogs=("cogs", "sum"),
    ).reset_index()

    out = _assemble({
        "date": g["date"].values,
        "source": "shopify",
        "marketing_channel": sem.NA,
        "marketing_channel_group": sem.NA,
        "marketing_campaign": sem.NA,
        "paid_ad_platform": sem.NA,
        "paid_campaign_type": sem.NA,
        "geo_market": g["country"].map(sem.geo_market).values,
        "geo_region": g["country"].map(sem.geo_region).values,
        "geo_country": g["country"].map(sem.country_name).values,
        "device": sem.NA,
    }, len(g))
    out["orders"] = g["orders"].values
    out["revenue"] = g["revenue"].round(2).values
    out["gross_sales"] = g["gross_sales"].round(2).values
    out["discounts"] = g["discounts"].round(2).values
    out["cogs"] = g["cogs"].round(2).values
    out["gross_profit"] = (g["revenue"] - g["cogs"]).round(2).values
    return out[sem.FACT_COLUMNS]


# ── GA4 (traffic/funnel only; Shopify owns orders/revenue) ───────
def map_ga4(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=sem.FACT_COLUMNS)
    sm = df["source_medium"]
    channel = sm.map(sem.channel_from_source_medium)
    platform = sm.map(sem.platform_from_source_medium)
    camp_raw = df["campaign"].fillna("")
    campaign = np.where(platform.values == "Meta",
                        camp_raw.map(sem.meta_campaign), camp_raw)
    ctype = [sem.campaign_type(n, ch) for n, ch in zip(camp_raw, channel)]

    out = _assemble({
        "date": df["event_date"].astype(str).map(lambda s: f"{s[:4]}-{s[4:6]}-{s[6:]}" if len(s) == 8 else s),
        "source": "ga4",
        "marketing_channel": channel.values,
        "marketing_channel_group": channel.map(sem.channel_group).values,
        "marketing_campaign": campaign,
        "paid_ad_platform": platform.values,
        "paid_campaign_type": ctype,
        "geo_market": df["country"].map(sem.geo_market).values,
        "geo_region": df["country"].map(sem.geo_region).values,
        "geo_country": df["country"].map(sem.country_name).values,
        "device": df["device"].map(sem.device).values,
    }, len(df))
    out["visits"] = df["sessions"].values
    out["engaged_visits"] = df["engaged_sessions"].values
    out["add_to_carts"] = df["sessions_with_atc"].values
    out["checkouts"] = df["sessions_with_checkout"].values
    return out[sem.FACT_COLUMNS]


# ── META (platform lane) ─────────────────────────────────────────
def map_meta(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=sem.FACT_COLUMNS)
    name = df["campaign_name"].fillna("")
    channel = "Paid Social"
    ctype = [sem.campaign_type(n, channel) for n in name]

    out = _assemble({
        "date": df["date"].astype(str),
        "source": "meta",
        "marketing_channel": channel,
        "marketing_channel_group": "Paid",
        "marketing_campaign": name.map(sem.meta_campaign).values,
        "paid_ad_platform": "Meta",
        "paid_campaign_type": ctype,
        "geo_market": df["country"].map(sem.geo_market).values,
        "geo_region": df["country"].map(sem.geo_region).values,
        "geo_country": df["country"].map(sem.country_name).values,
        "device": sem.NA,
    }, len(df))
    out["spend"] = df["spend"].values
    out["impressions"] = df["impressions"].values
    out["clicks"] = df["clicks"].values
    out["link_clicks"] = df.get("link_clicks", np.nan)
    out["reach"] = df.get("reach", np.nan)
    out["platform_conversions_1d"] = df.get("purchase_1d", np.nan)
    out["platform_conversions_7d"] = df.get("purchase_7d", np.nan)
    out["platform_conversions_28d"] = df.get("purchase_28d", np.nan)
    out["platform_conversion_value_1d"] = df.get("purchase_value_1d", np.nan)
    out["platform_conversion_value_7d"] = df.get("purchase_value_7d", np.nan)
    out["platform_conversion_value_28d"] = df.get("purchase_value_28d", np.nan)
    return out[sem.FACT_COLUMNS]


# ── GOOGLE ADS (platform lane; conversions in the 7d headline) ───
def map_google(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=sem.FACT_COLUMNS)
    name = df["campaign_name"].fillna("")
    channel = "Paid Search"
    gtype = df.get("campaign_type", pd.Series([""] * len(df)))
    ctype = [sem.campaign_type(n, channel, g) for n, g in zip(name, gtype)]

    out = _assemble({
        "date": df["date"].astype(str),
        "source": "google_ads",
        "marketing_channel": channel,
        "marketing_channel_group": "Paid",
        "marketing_campaign": name.values,
        "paid_ad_platform": "Google",
        "paid_campaign_type": ctype,
        "geo_market": df["country"].map(sem.geo_market).values,
        "geo_region": df["country"].map(sem.geo_region).values,
        "geo_country": df["country"].map(sem.country_name).values,
        "device": sem.NA,
    }, len(df))
    out["spend"] = df["spend"].values
    out["impressions"] = df["impressions"].values
    out["clicks"] = df["clicks"].values
    out["platform_conversions_7d"] = df["conversions"].values
    out["platform_conversion_value_7d"] = df["conversions_value"].values
    return out[sem.FACT_COLUMNS]


def map_microsoft(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=sem.FACT_COLUMNS)
    name = df["campaign_name"].fillna("")
    channel = "Paid Search"
    gtype = df.get("campaign_type", pd.Series([""] * len(df)))
    ctype = [sem.campaign_type(n, channel, g) for n, g in zip(name, gtype)]
    out = _assemble({
        "date": df["date"].astype(str), "source": "microsoft",
        "marketing_channel": channel, "marketing_channel_group": "Paid",
        "marketing_campaign": name.values, "paid_ad_platform": "Microsoft",
        "paid_campaign_type": ctype,
        "geo_market": df["country"].map(sem.geo_market).values,
        "geo_region": df["country"].map(sem.geo_region).values,
        "geo_country": df["country"].map(sem.country_name).values, "device": sem.NA,
    }, len(df))
    out["spend"] = df["spend"].values
    out["impressions"] = df["impressions"].values
    out["clicks"] = df["clicks"].values
    out["platform_conversions_7d"] = df["conversions"].values
    out["platform_conversion_value_7d"] = df["conversions_value"].values
    return out[sem.FACT_COLUMNS]


def map_tiktok(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=sem.FACT_COLUMNS)
    name = df["campaign_name"].fillna("")
    channel = "Paid Social"
    ctype = [sem.campaign_type(n, channel) for n in name]
    out = _assemble({
        "date": df["date"].astype(str), "source": "tiktok",
        "marketing_channel": channel, "marketing_channel_group": "Paid",
        "marketing_campaign": name.map(sem.meta_campaign).values, "paid_ad_platform": "Tiktok",
        "paid_campaign_type": ctype,
        "geo_market": df["country"].map(sem.geo_market).values,
        "geo_region": df["country"].map(sem.geo_region).values,
        "geo_country": df["country"].map(sem.country_name).values, "device": sem.NA,
    }, len(df))
    out["spend"] = df["spend"].values
    out["impressions"] = df["impressions"].values
    out["clicks"] = df["clicks"].values
    out["platform_conversions_7d"] = df["conversions_7d"].values
    out["platform_conversion_value_7d"] = df["conversion_value_7d"].values
    return out[sem.FACT_COLUMNS]


def build() -> int:
    """Read every source parquet, conform, union, write fact/fact.parquet."""
    parts = [
        map_shopify(storage.read_df(config.SHOPIFY_KEY)),
        map_ga4(storage.read_df(config.GA4_KEY)),
        map_meta(storage.read_df(config.META_KEY)),
        map_google(storage.read_df(config.GOOGLE_KEY)),
        map_microsoft(storage.read_df(config.MICROSOFT_KEY)),
        map_tiktok(storage.read_df(config.TIKTOK_KEY)),
    ]
    fact = pd.concat(parts, ignore_index=True)

    for c in sem.DIMENSIONS:
        if fact[c].dtype == object:
            fact[c] = fact[c].fillna(sem.NA)
    fact = fact.sort_values(["date", "source"]).reset_index(drop=True)

    storage.write_df(fact, config.FACT_KEY)
    print(f"fact rows: {len(fact)} | range: {fact['date'].min()} -> {fact['date'].max()}")
    print(fact.groupby("source").size().to_string())
    return len(fact)


# ── Product fact (date x product) — sales/margin + funnel + stock + returns ──
def build_product() -> int:
    lines = storage.read_df(config.SHOPIFY_LINEITEMS_KEY)
    if lines is None or lines.empty:
        return 0
    lines = lines.copy()
    lines["date"] = pd.to_datetime(lines["created_at"]).dt.strftime("%Y-%m-%d")
    grp = ["date", "product_id", "product_title", "category_l1", "category", "style"]
    grp = [c for c in grp if c in lines.columns]
    base = lines.groupby(grp).agg(
        units=("quantity", "sum"), revenue=("net_sales", "sum"),
        gross_sales=("gross_sales", "sum"), discounts=("discounts", "sum"),
        cogs=("cogs", "sum"),
    ).reset_index()
    base["gross_profit"] = (base["revenue"] - base["cogs"]).round(2)

    items = storage.read_df(config.GA4_ITEMS_KEY)
    if items is not None and not items.empty:
        it = items.groupby(["date", "product_id"]).agg(
            product_views=("item_views", "sum"),
            product_add_to_carts=("item_add_to_carts", "sum")).reset_index()
        base = base.merge(it, on=["date", "product_id"], how="left")

    inv = storage.read_df(config.SHOPIFY_INVENTORY_KEY)
    if inv is not None and not inv.empty:
        iv = inv.copy()
        iv["stock_value"] = iv["on_hand"] * iv.get("stock_value_per_unit", 0)
        agg = {"on_hand": ("on_hand", "sum"), "stock_value": ("stock_value", "sum")}
        if "in_transit" in iv.columns:
            agg["in_transit"] = ("in_transit", "sum")
        iv = iv.groupby(["date", "product_id"]).agg(**agg).reset_index()
        base = base.merge(iv, on=["date", "product_id"], how="left")

    rets = storage.read_df(config.SHOPIFY_RETURNS_KEY)
    if rets is not None and not rets.empty and "kind" in rets.columns:
        only = rets[rets["kind"] == "return"]
        rt = only.groupby(["date", "product_id"]).agg(
            returned_units=("quantity", "sum"),
            refund_amount=("value", "sum")).reset_index()
        base = base.merge(rt, on=["date", "product_id"], how="left")

    storage.write_df(base, config.FACT_PRODUCT_KEY)
    print(f"fact_product rows: {len(base)}")
    return len(base)


def build_orderbank() -> int:
    df = storage.read_df(config.ORDERBANK_KEY)
    if df is None or df.empty:
        return 0
    storage.write_df(df, config.FACT_ORDERBANK_KEY)
    print(f"fact_orderbank rows: {len(df)}")
    return len(df)


# ── Email fact (Klaviyo) and SEO fact (Search Console): light pass-through ──
def build_email() -> int:
    df = storage.read_df(config.KLAVIYO_KEY)
    if df is None or df.empty:
        return 0
    storage.write_df(df, config.FACT_EMAIL_KEY)
    print(f"fact_email rows: {len(df)}")
    return len(df)


def build_seo() -> int:
    df = storage.read_df(config.GSC_KEY)
    if df is None or df.empty:
        return 0
    storage.write_df(df, config.FACT_SEO_KEY)
    print(f"fact_seo rows: {len(df)}")
    return len(df)


def build_all() -> int:
    n = build()
    build_product()
    build_email()
    build_seo()
    build_orderbank()
    return n


if __name__ == "__main__":
    build_all()
