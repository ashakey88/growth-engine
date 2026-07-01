"""semantics.py — the shared brain that reads definitions.yaml.

Used by BOTH the transform (build_fact.py) for dimension derivation, and the
app/analytics for metric computation + formatting. All channel/geo/metric logic
lives here so the pipeline and the dashboard can never disagree. Edit
definitions.yaml, not code.
"""
import os
import re

import numpy as np
import pandas as pd
import yaml

_HERE = os.path.dirname(os.path.abspath(__file__))


def load(path=None):
    with open(path or os.path.join(_HERE, "definitions.yaml")) as f:
        return yaml.safe_load(f)


D = load()
NA = D["sentinels"]["dimension_na"]


def _norm(s):
    return ("" if s is None else str(s)).strip().lower()


def split_source_medium(sm):
    """'google / cpc' -> ('google','cpc')"""
    s = _norm(sm)
    if "/" in s:
        a, b = s.split("/", 1)
        return a.strip(), b.strip()
    return s, ""


# ── GEO (country -> market -> region), names OR 2-letter codes ───
def _build_geo():
    ident_to_market, market_to_name = {}, {}
    for market, idents in D["dimensions"]["geo"]["markets"].items():
        market_to_name[market] = idents[0]
        for i in idents:
            ident_to_market[_norm(i)] = market
    europe = {_norm(c) for c in D["dimensions"]["geo"]["europe_countries"]}
    return ident_to_market, market_to_name, europe


_IDENT_MARKET, _MARKET_NAME, _EUROPE = _build_geo()


def _named_market(country):
    return _IDENT_MARKET.get(_norm(country))


def geo_region(country):
    m = _named_market(country)
    if m == "US":
        return "US"
    if m == "UK":
        return "UK"
    if m in ("FR", "DE", "IT", "ES"):
        return "EU"
    if m in ("CA", "AU"):
        return "ROW"
    if _norm(country) in _EUROPE:
        return "EU"
    return "ROW"


def geo_market(country):
    region = geo_region(country)
    m = _named_market(country)
    if region == "US":
        return "US"
    if region == "UK":
        return "UK"
    if region == "EU":
        return m if m in ("FR", "DE", "IT", "ES") else "ROE"
    return m if m in ("CA", "AU") else "ROW"


def country_name(country):
    k = _norm(country)
    if k in _IDENT_MARKET:
        return _MARKET_NAME[_IDENT_MARKET[k]]
    return "" if country is None else str(country)


# ── MARKETING CHANNEL (standard GA4 grouping from source/medium) ──
_CH = D["dimensions"]["marketing_channel"]
_PAID_RE = re.compile(_CH["paid_medium_regex"])
_CAT = {k: [_norm(x) for x in v] for k, v in _CH["source_categories"].items()}


def _src_match(s, member):
    return s == member or s.startswith(member + ".") or ("." + member) in s


def _source_cats(source):
    s = _norm(source)
    return {cat for cat, members in _CAT.items() if any(_src_match(s, m) for m in members)}


def channel_from_source_medium(sm):
    s, m = split_source_medium(sm)
    cats = _source_cats(s)
    paid = bool(_PAID_RE.match(m))
    search, social, shopping, video = (c in cats for c in ("search", "social", "shopping", "video"))

    if s in ("(direct)", "direct") and m in ("(none)", "(not set)", "none", ""):
        return "Direct"
    if search and paid:   return "Paid Search"
    if shopping and paid: return "Paid Shopping"
    if social and paid:   return "Paid Social"
    if video and paid:    return "Paid Video"
    if m in ("display", "banner", "expandable", "interstitial", "cpm"): return "Display"
    if paid:              return "Paid Other"
    if shopping:          return "Organic Shopping"
    if social or m in ("social", "social-network", "social-media", "sm"):
        return "Organic Social"
    if video or m == "video": return "Organic Video"
    if search or m == "organic": return "Organic Search"
    if m in ("email", "e-mail") or "email" in s or "klaviyo" in s: return "Email"
    if m in ("affiliate", "affiliates"): return "Affiliates"
    if m in ("referral", "app", "link"): return "Referral"
    if s == "sms" or m == "sms": return "SMS"
    return _CH["fallback"]


def channel_group(channel):
    g = D["dimensions"]["marketing_channel_group"]
    return g["paid_label"] if channel in g["paid_channels"] else g["unpaid_label"]


# ── PAID AD PLATFORM (from source/medium, for GA4 rows) ──────────
def platform_from_source_medium(sm):
    src, med = split_source_medium(sm)
    for r in D["dimensions"]["paid_ad_platform"]["rules"]:
        if "source_contains" in r and _norm(r["source_contains"]) not in src:
            continue
        if "medium_in" in r and med not in [_norm(x) for x in r["medium_in"]]:
            continue
        return r["platform"]
    return D["dimensions"]["paid_ad_platform"]["fallback"]


def meta_campaign(name):
    s = "" if name is None else str(name)
    return s.split("_", 1)[0] if "_" in s else s


def campaign_type(name, channel, google_type=None):
    c = D["dimensions"]["paid_campaign_type"]
    n = _norm(name)
    if channel == "Paid Search":
        if c["brand_keyword"] in n:
            return "Brand"
        gt = (google_type or "").upper()
        if gt in c["pmax_types"]:
            return "PMAX"
        if gt in c["search_types"]:
            return "Search"
        return c["paid_search_other"]
    if channel == "Paid Social":
        if c["tofu_keyword"] in n:
            return "ToFu"
        if any(b in n for b in c["bofu_keywords"]):
            return "BoFu"
        return c["paid_social_other"]
    return NA


def device(value):
    m = D["dimensions"]["device"]["map"]
    return m.get(_norm(value), D["dimensions"]["device"]["fallback"])


# ── CONFORMED SCHEMA (fact-table column order) ───────────────────
DIMENSIONS = ["date", "source", "marketing_channel_group", "marketing_channel",
              "marketing_campaign", "paid_ad_platform", "paid_campaign_type",
              "geo_region", "geo_market", "geo_country", "device"]
BASE_METRICS = list(D["metrics"]["base"].keys())
FACT_COLUMNS = DIMENSIONS + BASE_METRICS


def empty_metric_frame(n):
    """All base-metric columns as NaN, for a source to fill its lane."""
    return pd.DataFrame({m: np.full(n, np.nan) for m in BASE_METRICS})


# ── METRIC COMPUTATION + FORMATTING (used by the app) ────────────
def metric_meta(name):
    if name in D["metrics"]["base"]:
        return {"kind": "base", **D["metrics"]["base"][name]}
    if name in D["metrics"]["derived"]:
        return {"kind": "derived", **D["metrics"]["derived"][name]}
    raise KeyError(name)


ALL_METRICS = list(D["metrics"]["base"].keys()) + list(D["metrics"]["derived"].keys())


def compute(grouped, name):
    """Compute a metric over an aggregated frame holding base-metric sums."""
    if name in D["metrics"]["base"]:
        return grouped[name]
    formula = D["metrics"]["derived"][name]["formula"]
    env = {m: grouped[m] for m in BASE_METRICS if m in grouped}
    with np.errstate(divide="ignore", invalid="ignore"):
        out = eval(formula, {"__builtins__": {}}, env)  # formulas are our own config
    return pd.Series(out).replace([np.inf, -np.inf], np.nan)


# ── DISPLAY NAMES ────────────────────────────────────────────────
_DISPLAY = D.get("display", {})
_ACRONYMS = {"aov": "AOV", "roas": "ROAS", "ctr": "CTR", "cpc": "CPC",
             "cpm": "CPM", "cogs": "COGS"}


def nice(key):
    if key in _DISPLAY:
        return _DISPLAY[key]
    words = str(key).replace("_", " ").split()
    return " ".join(_ACRONYMS.get(w.lower(), w[:1].upper() + w[1:]) for w in words)


def _dp(meta):
    return meta.get("dp", {"percent": 1, "ratio": 2}.get(meta["format"], 0))


def fmt(name, value):
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "—"
    meta = metric_meta(name)
    f, dp = meta["format"], _dp(meta)
    if f == "currency":
        return f"£{value:,.{dp}f}"
    if f == "percent":
        return f"{value*100:,.{dp}f}%"
    if f == "ratio":
        return f"{value:,.{dp}f}"
    return f"{value:,.{dp}f}"
