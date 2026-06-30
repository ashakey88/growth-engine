"""Storage layer: writes raw Parquet either to local disk or Cloudflare R2.

Layout (Hive-partitioned so DuckDB only scans what it needs):
    <root>/<client_id>/<source>/<dataset>/dt=YYYY-MM-DD/data.parquet
"""
from __future__ import annotations

import shutil

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

import config


def _local_root() -> str:
    return str(config.RAW_DIR)


def _r2_filesystem():
    """Return an fsspec S3 filesystem pointed at Cloudflare R2."""
    import s3fs  # imported lazily so local runs need no extra deps

    return s3fs.S3FileSystem(
        key=config.R2_ACCESS_KEY_ID,
        secret=config.R2_SECRET_ACCESS_KEY,
        client_kwargs={"endpoint_url": config.R2_ENDPOINT},
    )


def dataset_path(source: str, dataset: str) -> str:
    """Base path for a dataset, without the date partitions."""
    rel = f"{config.CLIENT_ID}/{source}/{dataset}"
    if config.STORAGE_BACKEND == "r2":
        return f"{config.R2_BUCKET}/{rel}"
    return f"{_local_root()}/{rel}"


def write_dataframe(df: pd.DataFrame, source: str, dataset: str, date_col: str) -> str:
    """Write a dataframe as date-partitioned Parquet. Returns the dataset path."""
    if df.empty:
        raise ValueError(f"Refusing to write empty dataset {source}/{dataset}")

    df = df.copy()
    df["dt"] = pd.to_datetime(df[date_col]).dt.strftime("%Y-%m-%d")
    table = pa.Table.from_pandas(df, preserve_index=False)
    base = dataset_path(source, dataset)

    if config.STORAGE_BACKEND == "r2":
        pq.write_to_dataset(
            table, root_path=base, partition_cols=["dt"],
            filesystem=_r2_filesystem(), existing_data_behavior="delete_matching",
        )
    else:
        # Clean previous run so the prototype is idempotent.
        shutil.rmtree(base, ignore_errors=True)
        pq.write_to_dataset(
            table, root_path=base, partition_cols=["dt"],
            existing_data_behavior="delete_matching",
        )

    return base


def read_glob(source: str, dataset: str) -> str:
    """Glob pattern DuckDB uses to read every partition of a dataset."""
    base = dataset_path(source, dataset)
    if config.STORAGE_BACKEND == "r2":
        return f"s3://{base}/*/*.parquet"
    return f"{base}/*/*.parquet"
