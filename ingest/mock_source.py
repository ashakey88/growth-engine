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
            "target_gross_profit": round(random.uniform(6500, 10000), 2),
            "target_engaged_visits": random.randint(4000, 6500),
            "target_add_to_carts": random.randint(700, 1200),
            "target_checkouts": random.randint(300, 600),
        })
    return pd.DataFrame(rows)


# ── Product catalog + line items (Shopify) ───────────────────────
# (category_l2, price_lo, price_hi, category_l1)
CATEGORIES = [
    ("Helmets", 280, 480, "Moto"), ("Apparel", 45, 120, "Other"),
    ("Accessories", 15, 60, "Moto"), ("Bags", 60, 140, "Other"),
    ("Electronics", 90, 260, "Snow"), ("Spares", 8, 40, "Other"),
]
WAREHOUSES = ["UK", "EU", "US"]
SIZES = ["S", "M", "L", "XL"]


def products(seed: int = 5) -> pd.DataFrame:
    """Catalog with a light hierarchy: L1 (Moto/Snow/Other) > category (L2) > style."""
    random.seed(seed)
    rows, pid = [], 0
    for cat, lo, hi, l1 in CATEGORIES:
        for i in range(1, 8):  # ~7 products per category
            pid += 1
            price = round(random.uniform(lo, hi), 2)
            rows.append({
                "product_id": f"P{pid:04d}",
                "product_title": f"{cat[:-1] if cat.endswith('s') else cat} {i}",
                "category_l1": l1,
                "category": cat,
                "style": f"{cat[:3].upper()}{i}",
                "sized": cat == "Helmets" or cat == "Apparel",
                "price": price,
                "unit_cost": round(price * random.uniform(0.38, 0.55), 2),
            })
    return pd.DataFrame(rows)


def shopify_line_items(catalog: pd.DataFrame, days: int = 450, seed: int = 42) -> pd.DataFrame:
    """Order line items — the grain that feeds product/margin/returns analysis."""
    random.seed(seed)
    cat = catalog.to_dict("records")
    rows, oid = [], 100000
    for i, day in enumerate(_days(days)):
        n = max(1, int(random.gauss(22 + i * 0.05, 4) * (1.25 if day.weekday() >= 5 else 1)))
        for _ in range(n):
            oid += 1
            created = day + timedelta(hours=random.randint(6, 23))
            customer = random.randint(1, 1400)
            country = _pick(COUNTRIES)
            for _ in range(random.randint(1, 3)):  # 1-3 lines per order
                p = random.choice(cat)
                qty = random.randint(1, 2)
                disc_rate = random.choice([0, 0, 0, 0.1, 0.15, 0.2])
                gross = round(p["price"] * qty, 2)
                disc = round(gross * disc_rate, 2)
                size = random.choice(SIZES) if p.get("sized") else "One Size"
                rows.append({
                    "order_id": oid, "created_at": created, "customer_id": customer,
                    "country": country, "product_id": p["product_id"],
                    "product_title": p["product_title"], "category_l1": p["category_l1"],
                    "category": p["category"], "style": p["style"], "size": size,
                    "sku": f"{p['product_id']}-{size.replace(' ', '')}",
                    "quantity": qty, "unit_price": p["price"],
                    "gross_sales": gross, "discounts": disc,
                    "net_sales": round(gross - disc, 2),
                    "cogs": round(p["unit_cost"] * qty, 2),
                })
    return pd.DataFrame(rows)


def shopify_orders_from_lines(lines: pd.DataFrame) -> pd.DataFrame:
    """Roll line items up to the order-level schema used by the marketing fact."""
    g = lines.groupby("order_id").agg(
        created_at=("created_at", "min"), customer_id=("customer_id", "first"),
        country=("country", "first"), gross_sales=("gross_sales", "sum"),
        discounts=("discounts", "sum"), net_sales=("net_sales", "sum"),
        cogs=("cogs", "sum"),
    ).reset_index()
    g["shipping"] = [random.choice([0, 0, 3.95, 4.95]) for _ in range(len(g))]
    g["total_price"] = (g["net_sales"] + g["shipping"]).round(2)
    g["currency"] = "GBP"
    return g


def shopify_inventory(catalog: pd.DataFrame, days: int = 450, seed: int = 8) -> pd.DataFrame:
    """Daily on-hand + in-transit stock per product per warehouse (random walk),
    with a stock value per unit for stock-value reporting."""
    random.seed(seed)
    cost = {r["product_id"]: r["unit_cost"] for _, r in catalog.iterrows()}
    stock = {(r["product_id"], w): random.randint(60, 500)
             for _, r in catalog.iterrows() for w in WAREHOUSES}
    rows = []
    for day in _days(days):
        d = day.strftime("%Y-%m-%d")
        for (pid, w), on_hand in stock.items():
            on_hand -= random.randint(0, 10)
            if on_hand < 30 and random.random() < 0.3:
                on_hand += random.randint(100, 300)
            stock[(pid, w)] = max(0, on_hand)
            rows.append({"date": d, "product_id": pid, "warehouse": w,
                         "on_hand": stock[(pid, w)],
                         "in_transit": random.choice([0, 0, 0, 50, 120, 250]),
                         "stock_value_per_unit": cost[pid]})
    return pd.DataFrame(rows)


RETURN_REASONS = ["Too small", "Too large", "Not as described", "Faulty",
                  "Changed mind", "Arrived late", "Better price elsewhere"]


def shopify_returns(lines: pd.DataFrame, seed: int = 11) -> pd.DataFrame:
    """~14% of line items are a return, cancellation or exchange, each with a
    reason and value (kind lets the finance waterfall separate them)."""
    random.seed(seed)
    sample = lines.sample(frac=0.14, random_state=seed)
    rows = []
    for _, r in sample.iterrows():
        kind = random.choices(["return", "cancellation", "exchange"], weights=[0.6, 0.25, 0.15])[0]
        rows.append({
            "return_id": f"R{random.randint(100000, 999999)}",
            "order_id": r["order_id"],
            "date": (pd.to_datetime(r["created_at"]) + pd.Timedelta(days=random.randint(3, 20))
                     ).strftime("%Y-%m-%d"),
            "product_id": r["product_id"], "category": r["category"],
            "country": r["country"], "kind": kind, "quantity": r["quantity"],
            "value": r["net_sales"], "reason": random.choice(RETURN_REASONS),
        })
    return pd.DataFrame(rows)


def order_bank(catalog: pd.DataFrame, weeks: int = 12, seed: int = 44) -> pd.DataFrame:
    """Open orders taken but not yet invoiced, by category_l1 × warehouse × week
    (for the Orderbank report's snapshot + weekly trend)."""
    random.seed(seed)
    l1s = sorted(catalog["category_l1"].unique())
    rows = []
    start = datetime.utcnow() - timedelta(weeks=weeks - 1)
    for wk in range(weeks):
        d = (start + timedelta(weeks=wk)).strftime("%Y-%m-%d")
        for l1 in l1s:
            for w in WAREHOUSES:
                orders = random.randint(5, 60)
                rows.append({"date": d, "category_l1": l1, "warehouse": w,
                             "open_orders": orders, "open_items": orders * random.randint(1, 3),
                             "open_value": round(orders * random.uniform(120, 340), 2)})
    return pd.DataFrame(rows)


def ga4_items(catalog: pd.DataFrame, days: int = 450, seed: int = 17) -> pd.DataFrame:
    """Item-level GA4 funnel: product views and add-to-carts per product per day."""
    random.seed(seed)
    cat = catalog.to_dict("records")
    rows = []
    for day in _days(days):
        for p in random.sample(cat, k=int(len(cat) * 0.7)):  # not every product every day
            views = random.randint(20, 600)
            atc = int(views * random.uniform(0.04, 0.13))
            rows.append({
                "date": day.strftime("%Y-%m-%d"), "product_id": p["product_id"],
                "product_title": p["product_title"], "category": p["category"],
                "item_views": views, "item_add_to_carts": atc,
                "item_purchases": int(atc * random.uniform(0.25, 0.55)),
            })
    return pd.DataFrame(rows)


def microsoft_ads_data(days: int = 450, seed: int = 23) -> pd.DataFrame:
    random.seed(seed)
    rows = []
    campaigns = [("Brand_Search_MS", "SEARCH"), ("Generic_Search_MS", "SEARCH")]
    for day in _days(days):
        d = day.strftime("%Y-%m-%d")
        for name, gtype in campaigns:
            spend = round(random.uniform(15, 120), 2)
            imp = int(spend * random.uniform(120, 240))
            clk = int(imp * random.uniform(0.02, 0.05))
            conv = round(random.uniform(0.5, 6), 1)
            rows.append({"date": d, "campaign_name": name, "campaign_type": gtype,
                         "country": _pick(COUNTRIES), "spend": spend, "impressions": imp,
                         "clicks": clk, "conversions": conv,
                         "conversions_value": round(conv * random.uniform(70, 120), 2)})
    return pd.DataFrame(rows)


def tiktok_ads_data(days: int = 450, seed: int = 29) -> pd.DataFrame:
    random.seed(seed)
    rows = []
    campaigns = ["TOFU_Awareness_TT", "BOFU_Conversion_TT"]
    for day in _days(days):
        d = day.strftime("%Y-%m-%d")
        for camp in campaigns:
            spend = round(random.uniform(20, 180), 2)
            imp = int(spend * random.uniform(300, 600))
            clk = int(imp * random.uniform(0.006, 0.015))
            conv = round(random.uniform(0.5, 7), 1)
            rows.append({"date": d, "campaign_name": camp, "country": _pick(COUNTRIES),
                         "spend": spend, "impressions": imp, "clicks": clk,
                         "conversions_7d": conv,
                         "conversion_value_7d": round(conv * random.uniform(70, 110), 2)})
    return pd.DataFrame(rows)


def klaviyo_data(days: int = 450, seed: int = 31) -> pd.DataFrame:
    """Email/CRM: flows (always-on) + weekly campaigns."""
    random.seed(seed)
    flows = ["Welcome", "Abandoned Cart", "Browse Abandon", "Post-Purchase", "Win-back"]
    rows = []
    for day in _days(days):
        d = day.strftime("%Y-%m-%d")
        for f in flows:  # flows fire daily
            recips = random.randint(200, 1500)
            opens = int(recips * random.uniform(0.35, 0.6))
            clicks = int(opens * random.uniform(0.08, 0.2))
            orders = int(clicks * random.uniform(0.05, 0.15))
            rows.append({"date": d, "name": f, "type": "flow", "recipients": recips,
                         "opens": opens, "clicks": clicks, "orders": orders,
                         "revenue": round(orders * random.uniform(60, 110), 2)})
        if day.weekday() == 2:  # weekly campaign on Wednesdays
            recips = random.randint(8000, 20000)
            opens = int(recips * random.uniform(0.25, 0.45))
            clicks = int(opens * random.uniform(0.05, 0.15))
            orders = int(clicks * random.uniform(0.03, 0.1))
            rows.append({"date": d, "name": f"Campaign {day.strftime('%d %b')}",
                         "type": "campaign", "recipients": recips, "opens": opens,
                         "clicks": clicks, "orders": orders,
                         "revenue": round(orders * random.uniform(60, 110), 2)})
    return pd.DataFrame(rows)


SEO_QUERIES = [
    ("brand name", True), ("brand name helmet", True), ("brand review", True),
    ("motorcycle helmet", False), ("smart helmet", False), ("bluetooth helmet", False),
    ("lightweight helmet", False), ("carbon helmet", False), ("ski helmet", False),
    ("best motorcycle helmet", False), ("helmet with camera", False),
    ("waterproof motorcycle bag", False), ("motorcycle accessories", False),
]


def search_console_data(days: int = 450, seed: int = 37) -> pd.DataFrame:
    """SEO: clicks/impressions/position per query per day (Search Console shape)."""
    random.seed(seed)
    rows = []
    for day in _days(days):
        d = day.strftime("%Y-%m-%d")
        for query, branded in SEO_QUERIES:
            imp = random.randint(200, 6000) if not branded else random.randint(400, 3000)
            pos = round(random.uniform(1.2, 4.5) if branded else random.uniform(3, 25), 1)
            ctr = (0.35 if branded else 0.03) * random.uniform(0.6, 1.4) / max(1, pos / 3)
            clicks = int(imp * min(0.6, ctr))
            rows.append({"date": d, "query": query, "branded": branded,
                         "clicks": clicks, "impressions": imp, "position": pos})
    return pd.DataFrame(rows)
