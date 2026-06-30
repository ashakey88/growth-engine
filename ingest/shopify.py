"""Real Shopify Admin API extractor.

Used automatically when SHOPIFY_STORE and SHOPIFY_ACCESS_TOKEN are set.
Returns the same schema as mock_source.generate_orders() so nothing downstream
needs to change. Untested without live credentials — treat as a starting point.
"""
from __future__ import annotations

import time

import pandas as pd
import requests

import config

API_VERSION = "2024-04"


def _orders_url() -> str:
    return f"https://{config.SHOPIFY_STORE}/admin/api/{API_VERSION}/orders.json"


def fetch_orders(days: int = 120) -> pd.DataFrame:
    """Page through orders via the Admin REST API and flatten to order level."""
    headers = {"X-Shopify-Access-Token": config.SHOPIFY_ACCESS_TOKEN}
    params = {
        "status": "any",
        "limit": 250,
        "created_at_min": (pd.Timestamp.utcnow() - pd.Timedelta(days=days)).isoformat(),
    }
    url = _orders_url()
    rows: list[dict] = []

    while url:
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        if resp.status_code == 429:  # rate limited — back off and retry
            time.sleep(float(resp.headers.get("Retry-After", 2)))
            continue
        resp.raise_for_status()

        for o in resp.json().get("orders", []):
            gross = sum(
                float(li["price"]) * li["quantity"] for li in o.get("line_items", [])
            )
            discounts = float(o.get("total_discounts", 0) or 0)
            net = gross - discounts
            rows.append(
                {
                    "order_id": o["id"],
                    "created_at": o["created_at"],
                    "customer_id": (o.get("customer") or {}).get("id"),
                    "channel": (o.get("source_name") or "unknown"),
                    "country": ((o.get("shipping_address") or {}).get("country_code")),
                    "gross_sales": round(gross, 2),
                    "discounts": round(discounts, 2),
                    "net_sales": round(net, 2),
                    # COGS is not in the orders payload; needs InventoryItem cost.
                    # Placeholder until that extractor is built.
                    "cogs": round(gross * 0.45, 2),
                    "shipping": float(o.get("total_shipping_price_set", {})
                                      .get("shop_money", {}).get("amount", 0) or 0),
                    "total_price": float(o.get("total_price", 0) or 0),
                    "currency": o.get("currency", "GBP"),
                }
            )

        # Shopify cursor pagination via the Link header.
        url, params = _next_page(resp), None

    return pd.DataFrame(rows)


def _next_page(resp: requests.Response) -> str | None:
    link = resp.headers.get("Link", "")
    for part in link.split(","):
        if 'rel="next"' in part:
            return part[part.find("<") + 1 : part.find(">")]
    return None
