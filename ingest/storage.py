"""Storage layer — one parquet per key, on local disk or Cloudflare R2.

The same keys (e.g. "shopify/shopify_data.parquet", "fact/fact.parquet") work
against either backend, so nothing else in the codebase cares where data lives.
R2 credentials are read from env vars (works in GitHub Actions and on Streamlit
Cloud, which injects secrets as env vars).
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

import config


# ── R2 (S3-compatible) client, created lazily ────────────────────
def _r2():
    import boto3

    endpoint = config.R2_ENDPOINT or (
        f"https://{config.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
    )
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=config.R2_ACCESS_KEY_ID,
        aws_secret_access_key=config.R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )


def _local_path(key: str) -> Path:
    p = config.DATA_DIR / key
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _use_r2() -> bool:
    return config.STORAGE_BACKEND == "r2"


# ── Parquet ──────────────────────────────────────────────────────
def write_df(df: pd.DataFrame, key: str) -> None:
    if _use_r2():
        local = _local_path(key)
        df.to_parquet(local, index=False)
        _r2().upload_file(str(local), config.R2_BUCKET, key)
    else:
        df.to_parquet(_local_path(key), index=False)


def read_df(key: str) -> pd.DataFrame | None:
    """Return the dataframe at `key`, or None if it doesn't exist."""
    if _use_r2():
        local = _local_path(key)
        try:
            _r2().download_file(config.R2_BUCKET, key, str(local))
        except Exception:
            return None
        return pd.read_parquet(local)
    p = _local_path(key)
    return pd.read_parquet(p) if p.exists() else None


def exists(key: str) -> bool:
    if _use_r2():
        try:
            _r2().head_object(Bucket=config.R2_BUCKET, Key=key)
            return True
        except Exception:
            return False
    return _local_path(key).exists()


# ── Small JSON (connection state) ────────────────────────────────
def write_json(obj: dict, key: str) -> None:
    if _use_r2():
        local = _local_path(key)
        local.write_text(json.dumps(obj))
        _r2().upload_file(str(local), config.R2_BUCKET, key)
    else:
        _local_path(key).write_text(json.dumps(obj))


def read_json(key: str) -> dict | None:
    if _use_r2():
        local = _local_path(key)
        try:
            _r2().download_file(config.R2_BUCKET, key, str(local))
        except Exception:
            return None
        return json.loads(local.read_text())
    p = _local_path(key)
    return json.loads(p.read_text()) if p.exists() else None
