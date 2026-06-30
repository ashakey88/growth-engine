"""Generates realistic Shopify-shaped order data so the whole pipeline runs
end-to-end with no external accounts or cost.

The schema deliberately matches what the real Shopify extractor produces, so
the transform and dashboard layers don't care whether data is mock or real.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta

import pandas as pd

# Channels roughly mirror the sources we'll connect for real later.
CHANNELS = [
    ("google", 0.28),
    ("meta", 0.26),
    ("tiktok", 0.10),
    ("microsoft", 0.05),
    ("klaviyo-email", 0.12),
    ("organic", 0.11),
    ("direct", 0.08),
]
COUNTRIES = [("GB", 0.7), ("US", 0.15), ("IE", 0.08), ("DE", 0.07)]


def _weighted_choice(options):
    r, cum = random.random(), 0.0
    for value, weight in options:
        cum += weight
        if r <= cum:
            return value
    return options[-1][0]


def generate_orders(days: int = 120, seed: int = 42) -> pd.DataFrame:
    """Return a dataframe with one row per order over the last `days` days."""
    random.seed(seed)
    rows = []
    order_id = 1000
    customer_pool = list(range(1, 1200))
    start = datetime.utcnow() - timedelta(days=days)

    for day_offset in range(days):
        day = start + timedelta(days=day_offset)
        # Gentle upward trend + weekend lift to look real.
        base = 18 + day_offset * 0.25
        weekend = 1.25 if day.weekday() >= 5 else 1.0
        n_orders = max(1, int(random.gauss(base * weekend, 4)))

        for _ in range(n_orders):
            order_id += 1
            channel = _weighted_choice(CHANNELS)
            gross_sales = round(random.gauss(78, 28), 2)
            gross_sales = max(15.0, gross_sales)
            discount = round(gross_sales * random.choice([0, 0, 0.1, 0.15, 0.2]), 2)
            net_sales = round(gross_sales - discount, 2)
            cogs = round(gross_sales * random.uniform(0.38, 0.52), 2)
            shipping = round(random.choice([0, 0, 3.95, 4.95]), 2)
            ts = day + timedelta(
                hours=random.randint(6, 23), minutes=random.randint(0, 59)
            )
            rows.append(
                {
                    "order_id": order_id,
                    "created_at": ts,
                    "customer_id": random.choice(customer_pool),
                    "channel": channel,
                    "country": _weighted_choice(COUNTRIES),
                    "gross_sales": gross_sales,
                    "discounts": discount,
                    "net_sales": net_sales,
                    "cogs": cogs,
                    "shipping": shipping,
                    "total_price": round(net_sales + shipping, 2),
                    "currency": "GBP",
                }
            )

    return pd.DataFrame(rows)
