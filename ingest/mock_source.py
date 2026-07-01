"""Realistic per-source mock data so the whole pipeline (build_fact + semantics)
runs end-to-end with no accounts or cost. Each generator matches the schema of
the real extractor for that source, so downstream code is identical for mock or
live data.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta

import pandas as pd

COUNTRIES = [("GB", 0.55), ("US", 0.20), ("DE", 0.08), ("FR", 0.07),
             ("IE", 0.05), ("AU", 0.05)]
GA4_SOURCE_MEDIUMS = [
    ("google / organic", 0.20), ("(direct) / (none)", 0.16),
    ("google / cpc", 0.18), ("facebook / paid_social", 0.16),
    ("tiktok / paid_social", 0.08), ("klaviyo / email", 0.10),
    ("bing / cpc", 0.04), ("instagram / referral", 0.08),
]
DEVICES = [("mobile", 0.62), ("desktop", 0.31), ("tablet", 0.07)]
META_CAMPAIGNS = ["TOFU_Prospecting", "BOFU_Retargeting", "MOFU_Consideration", "Brand_Always_On"]
GOOGLE_CAMPAIGNS = [("Brand_Search", "SEARCH"), ("Generic_Search", "SEARCH"),
                    ("PMax_All", "PERFORMANCE_MAX"), ("Shopping_Feed", "SHOPPING")]


def _pick(options):
    r, cum = random.random(), 0.0
    for value, weight in options:
        cum += weight
        if r <= cum:
            return value
    return options[-1][0]


def _days(days):
    start = datetime.utcnow() - timedelta(days=days)
    return [start + timedelta(days=i) for i in range(days)]


def shopify_orders(days: int = 450, seed: int = 42) -> pd.DataFrame:
    """Order-level Shopify data (the sales source of truth)."""
    random.seed(seed)
    rows, oid = [], 1000
    for i, day in enumerate(_days(days)):
        n = max(1, int(random.gauss(22 + i * 0.05, 4) * (1.25 if day.weekday() >= 5 else 1)))
        for _ in range(n):
            oid += 1
            gross = max(15.0, round(random.gauss(82, 30), 2))
            disc = round(gross * random.choice([0, 0, 0.1, 0.15, 0.2]), 2)
            rows.append({
                "order_id": oid,
                "created_at": day + timedelta(hours=random.randint(6, 23)),
                "customer_id": random.randint(1, 1400),
                "country": _pick(COUNTRIES),
                "gross_sales": gross,
                "discounts": disc,
                "net_sales": round(gross - disc, 2),
                "cogs": round(gross * random.uniform(0.38, 0.52), 2),
                "shipping": round(random.choice([0, 0, 3.95, 4.95]), 2),
                "total_price": round(gross - disc + random.choice([0, 3.95]), 2),
                "currency": "GBP",
            })
    return pd.DataFrame(rows)


def ga4_data(days: int = 450, seed: int = 7) -> pd.DataFrame:
    random.seed(seed)
    rows = []
    for i, day in enumerate(_days(days)):
        d = day.strftime("%Y%m%d")
        for _ in range(random.randint(14, 22)):
            sessions = random.randint(20, 900)
            eng = int(sessions * random.uniform(0.55, 0.85))
            atc = int(sessions * random.uniform(0.05, 0.14))
            chk = int(atc * random.uniform(0.4, 0.7))
            pur = int(chk * random.uniform(0.4, 0.75))
            rows.append({
                "event_date": d,
                "source_medium": _pick(GA4_SOURCE_MEDIUMS),
                "campaign": random.choice(META_CAMPAIGNS + ["(not set)"]),
                "device": _pick(DEVICES),
                "country": _pick(COUNTRIES),
                "sessions": sessions,
                "engaged_sessions": eng,
                "sessions_with_atc": atc,
                "sessions_with_checkout": chk,
                "purchases": pur,
                "purchase_revenue": round(pur * random.uniform(60, 110), 2),
            })
    return pd.DataFrame(rows)


def meta_data(days: int = 450, seed: int = 13) -> pd.DataFrame:
    random.seed(seed)
    rows = []
    for day in _days(days):
        d = day.strftime("%Y-%m-%d")
        for camp in META_CAMPAIGNS:
            spend = round(random.uniform(40, 400), 2)
            imp = int(spend * random.uniform(180, 320))
            clk = int(imp * random.uniform(0.008, 0.02))
            p7 = round(random.uniform(1, 12), 1)
            rows.append({
                "date": d, "campaign_name": camp, "country": _pick(COUNTRIES),
                "spend": spend, "impressions": imp, "clicks": clk,
                "link_clicks": int(clk * 0.85), "reach": int(imp * 0.6),
                "purchase_1d": round(p7 * 0.7, 1), "purchase_7d": p7,
                "purchase_28d": round(p7 * 1.2, 1),
                "purchase_value_1d": round(p7 * 0.7 * 85, 2),
                "purchase_value_7d": round(p7 * 85, 2),
                "purchase_value_28d": round(p7 * 1.2 * 85, 2),
            })
    return pd.DataFrame(rows)


def google_ads_data(days: int = 450, seed: int = 21) -> pd.DataFrame:
    random.seed(seed)
    rows = []
    for day in _days(days):
        d = day.strftime("%Y-%m-%d")
        for name, gtype in GOOGLE_CAMPAIGNS:
            spend = round(random.uniform(30, 350), 2)
            imp = int(spend * random.uniform(120, 260))
            clk = int(imp * random.uniform(0.02, 0.05))
            conv = round(random.uniform(1, 14), 1)
            rows.append({
                "date": d, "campaign_name": name, "campaign_type": gtype,
                "country": _pick(COUNTRIES), "spend": spend, "impressions": imp,
                "clicks": clk, "conversions": conv,
                "conversions_value": round(conv * random.uniform(70, 120), 2),
            })
    return pd.DataFrame(rows)


def targets(days: int = 450, seed: int = 99) -> pd.DataFrame:
    """Daily eCommerce targets, matching the targets column map in definitions.yaml."""
    random.seed(seed)
    rows = []
    for day in _days(days):
        rows.append({
            "date": day.strftime("%Y-%m-%d"),
            "target_spend": round(random.uniform(700, 1100), 2),
            "target_visits": random.randint(6000, 9000),
            "target_orders": random.randint(120, 200),
            "target_revenue": round(random.uniform(11000, 17000), 2),
            "target_engaged_visits": random.randint(4000, 6500),
            "target_add_to_carts": random.randint(700, 1200),
            "target_checkouts": random.randint(300, 600),
        })
    return pd.DataFrame(rows)
