"""Central configuration for the Growth Engine.

Everything is driven by environment variables (see .env.example) so the same
code runs locally at zero cost or against Cloudflare R2 without changes. On
Streamlit Community Cloud, secrets are injected as environment variables.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ── Storage keys (same layout on local disk or in R2) ────────────
SHOPIFY_KEY = "shopify/shopify_data.parquet"
GA4_KEY = "ga4/ga4_data.parquet"
META_KEY = "meta/meta_data.parquet"
GOOGLE_KEY = "google_ads/google_ads_data.parquet"
FACT_KEY = "fact/fact.parquet"
TARGETS_KEY = "targets/targets_ecommerce.parquet"
CONNECTIONS_KEY = "connections.json"

# ── Storage backend ──────────────────────────────────────────────
STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local").lower()

R2_ENDPOINT = os.getenv("R2_ENDPOINT", "")
R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID", "")
R2_BUCKET = os.getenv("R2_BUCKET", "growth-engine")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID", "")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY", "")

# ── Shopify ──────────────────────────────────────────────────────
SHOPIFY_STORE = os.getenv("SHOPIFY_STORE", "")
SHOPIFY_ACCESS_TOKEN = os.getenv("SHOPIFY_ACCESS_TOKEN", "")

CLIENT_ID = os.getenv("CLIENT_ID", "demo-brand")


def shopify_configured() -> bool:
    return bool(SHOPIFY_STORE and SHOPIFY_ACCESS_TOKEN)
