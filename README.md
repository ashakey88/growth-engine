# The Growth Engine

A commercial intelligence platform for ecommerce brands. Multiple sources are
pulled into parquet (local disk or Cloudflare R2), conformed into one "stacked
fact" table, and reported on via a Streamlit app styled to Malleson Labs.

```
Shopify (sales)  ─┐
GA4 (traffic)     ─┤   extract → per-source parquet
Meta / Google (ads)┘            │
                                ▼
                    build_fact.py + semantics.py  (definitions.yaml)
                                │
                         fact/fact.parquet  ── stacked conformed grain
                                │
                                ▼
                    Streamlit app  (Overview · Breakdown · Trend · Explorer · Targets)
```

## Core principle: one definitions file drives everything

`definitions.yaml` holds every dimension rule and metric formula. `semantics.py`
reads it; **both** the transform and the app import `semantics.py`, so the
pipeline and the dashboard can never disagree. To change a channel rule, geo
bucket, or metric formula, edit `definitions.yaml` only.

## The stacked fact model

One long table. Every source contributes rows tagged with `source`, filling only
the metric columns in its lane; the rest are null. Derived metrics (AOV, ROAS,
conversion rate, margin…) are computed at query time from the base sums.

- **sales lane** — Shopify (source of truth for orders / revenue / margin)
- **traffic lane** — GA4 (visits, engaged visits, add-to-carts, checkouts)
- **platform lane** — Meta + Google (spend, impressions, clicks, conversions)

Never sum a metric across sources that both report it without filtering `source`.

## Run it (no accounts, no cost)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # defaults to local storage + mock data
python run_pipeline.py        # mock every source → build fact
streamlit run app/streamlit_app.py
```

Mock data for all four sources is generated so every page is populated instantly.

## Deploy live (free)

Streamlit Community Cloud: repo `ashakey88/growth-engine`, branch `main`, main
file `app/streamlit_app.py`. It self-bootstraps with mock data on first load.

## Real data

- **Shopify** — the app's **Connect sources** screen; paste a store domain +
  Admin API token and it pulls real orders and rebuilds the fact table.
- **Cloudflare R2** — set `STORAGE_BACKEND=r2` + the `R2_*` values (secrets on
  Streamlit Cloud). Parquet then lives in R2 instead of local disk.

## Layout

| Path | Role |
|------|------|
| `definitions.yaml` | Single source of truth: dimensions + metrics |
| `semantics.py` | Reads definitions; dimension derivation + metric compute/format |
| `ingest/storage.py` | Parquet + JSON store, local or R2 |
| `ingest/mock_source.py` | Per-source mock data (matches real schemas) |
| `ingest/shopify.py` | Real Shopify Admin API extractor |
| `transform/build_fact.py` | Maps each source to the conformed grain → `fact.parquet` |
| `analytics.py` | Data brain: periods, TY/LY/target comparisons, KPIs, sparklines |
| `app/streamlit_app.py` | Report UI: Exec Summary, KPI Overview, KPI Trends, Channels, Regions, Devices, Data Explorer, Connect, Targets |
| `run_pipeline.py` | Runs the full ELT (mock or real Shopify) |

## What's not here yet

- Real extractors for GA4 / Meta / Google / TikTok / Microsoft (source pull
  scripts exist as a reference pattern; only Shopify is wired into the app).
- GA4→Shopify reconciliation for channel-split revenue (Shopify owns revenue by
  geo today; channel splits come from GA4 traffic + ad spend).
- Multi-tenancy / per-client auth and secure credential storage.
- The AI commercial analyst.
- Orchestration (scheduled daily refresh via GitHub Actions).
