"""Central configuration for the Growth Engine prototype.

Everything is driven by environment variables (see .env.example) so the same
code runs locally at zero cost or against Cloudflare R2 without changes.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
DUCKDB_PATH = DATA_DIR / "growth_engine.duckdb"

RAW_DIR.mkdir(parents=True, exist_ok=True)

# ── Storage ──────────────────────────────────────────────────────
STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local").lower()

R2_ENDPOINT = os.getenv("R2_ENDPOINT", "")
R2_BUCKET = os.getenv("R2_BUCKET", "growth-engine")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID", "")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY", "")

# ── Shopify ──────────────────────────────────────────────────────
SHOPIFY_STORE = os.getenv("SHOPIFY_STORE", "")
SHOPIFY_ACCESS_TOKEN = os.getenv("SHOPIFY_ACCESS_TOKEN", "")

# For a real multi-tenant build this becomes the per-client identifier.
# For the prototype we use a single fixed tenant.
CLIENT_ID = os.getenv("CLIENT_ID", "demo-brand")


def shopify_configured() -> bool:
    return bool(SHOPIFY_STORE and SHOPIFY_ACCESS_TOKEN)
