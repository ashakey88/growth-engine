# The Growth Engine — prototype

A zero-cost, end-to-end ELT walking skeleton for the commercial intelligence
platform. Same architecture as production, just smaller and free.

```
Shopify (or mock data)  ->  Parquet (local disk / Cloudflare R2)  ->  DuckDB marts  ->  Streamlit
        extract                       load                              transform        present
```

## Run it (no accounts, no cost)

```bash
cd growth-engine
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # defaults to local storage + mock data
python run_pipeline.py        # extract -> load -> transform
streamlit run app/streamlit_app.py
```

With no credentials set, the pipeline generates ~120 days of realistic
Shopify-shaped order data so every stage runs immediately.

## Swap in real data

- **Shopify:** set `SHOPIFY_STORE` and `SHOPIFY_ACCESS_TOKEN` in `.env`
  (a free Shopify partner dev store works perfectly). The pipeline switches
  from mock to live automatically — nothing downstream changes.
- **Cloudflare R2:** set `STORAGE_BACKEND=r2` plus the `R2_*` values, and
  `pip install s3fs`. Parquet then lands in R2 and DuckDB reads it via httpfs.

## Layout

| Path | Role |
|------|------|
| `config.py` | Env-driven configuration |
| `ingest/mock_source.py` | Synthetic Shopify-shaped data (zero cost) |
| `ingest/shopify.py` | Real Shopify Admin API extractor |
| `ingest/storage.py` | Parquet writer — local or R2, date-partitioned |
| `transform/build_models.py` | DuckDB: raw → fct_orders → marts |
| `app/streamlit_app.py` | Dashboard reading the marts |
| `run_pipeline.py` | Runs the full ELT |

## What's deliberately not here yet

- Other sources (Meta, Google, TikTok, Microsoft, Klaviyo, GSC) — mock as CSV
  next, then add real extractors one at a time.
- Multi-tenancy / per-client auth and the source-connection UI.
- The AI commercial analyst (text-to-SQL over the DuckDB schema).
- Orchestration (a daily scheduled run).
