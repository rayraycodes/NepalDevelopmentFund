# AGENTS.md

Guidance for AI coding agents working in this repository. Human contributors may find it
useful too, but the audience here is automated agents.

## What this repository is

A reproducible dataset (and an offline, bilingual dashboard) of external development finance
flowing **to Nepal**, 2015–present. It captures **both ledger sides** — what donors report
giving and what the Government of Nepal reports receiving — and compares them rather than
merging them. See `README.md` for the full narrative and `report/report.md` for methodology.

The pipeline is a set of numbered Python scripts that **fetch** raw source data, **normalize**
it into one canonical long-format schema, **reconcile/build** a core table, **validate** it, and
render **figures** + **dashboard data**. The dashboard itself is plain static HTML/JS.

## Core principle: provenance over completeness

This is the single most important rule in the repo. **Never invent, estimate, or fill in data
to make output look complete.**

- Every figure carries its source, dataset version, exact query/URL, and retrieval date.
- Every row is tagged `REPORTED` / `ESTIMATED` / `MISSING` with a confidence level.
- Gaps are left blank and labelled `MISSING` — never backfilled with plausible-looking numbers.
- Raw snapshots under `data/raw/` are **immutable**; never edit them. Re-fetch instead.

If a task would require guessing a value, stop and surface the gap rather than fabricating it.

## Layout

| Path | Contents |
|---|---|
| `config/` | source registry (`sources.yaml`), donor/sector crosswalks, FX rates, Nepal FY calendar |
| `scripts/common.py` | canonical schema, validators, browser-UA HTTP session, snapshot + manifest writer |
| `scripts/NN_fetch_*.py` | one fetch+normalize script per source (numbered by phase) |
| `scripts/40–60_*.py` | dedupe, reconcile, assemble `core_long` |
| `scripts/80–95_*.py` | figures, dashboard data, validation, search indexes |
| `data/raw/` | immutable dated source snapshots (never edited; many are git-ignored + regenerable) |
| `data/interim/` | per-source normalized long CSVs |
| `data/processed/` | `core_long.csv`/`.json`, aggregates, reconciliation, data dictionary |
| `report/report.md` | the cited narrative report |
| `report/dashboard/` | self-contained offline ECharts dashboard (bilingual EN/नेपाली) |

## Environment setup

```bash
pip install -r requirements.txt   # requests, pandas, matplotlib
```

Node is only needed to run the dashboard's JS unit tests (no npm dependencies).

## Build & run commands

The `Makefile` is the source of truth for the pipeline. Phases run in order:

```bash
make smoke            # validate the common module / schema (no network)
make anchor           # Phase 1: World Bank net-ODA anchor + OECD DAC2A (verified core)
make fetch            # Phase 2: remaining donor sources (network required)
make build            # Phase 3: dedupe, reconcile, assemble core_long
make validate         # integrity assertions — MUST pass
make figures          # generate report/figures/*.png
make dashboard-data   # rebuild report/dashboard/*.js from committed CSVs
make serve            # build dashboard data + serve dashboard at http://127.0.0.1:8848
make all              # anchor + fetch + build + validate + figures + dashboard-data
make clean            # wipe data/interim, data/processed, manifests
```

Notes:
- `fetch` targets hit live external APIs (OECD, World Bank, IATI, ADB, USAspending,
  ForeignAssistance.gov). In a sandbox without network access these will fail — prefer working
  from committed CSVs and rebuilding only the offline steps.
- Scripts `86`/`87` need live USAspending/ForeignAssistance APIs and are intentionally manual.
- OECD blocks default user agents; `common.py` provides a browser-UA session — always fetch
  through `common.make_session()` / `common.get()`, never a bare `requests.get`.

## Validation (do this before finishing)

1. `make smoke` — schema/common module sanity.
2. `make validate` — runs `scripts/90_validate.py` integrity assertions.
3. If you touched anything the dashboard reads, rebuild and confirm no drift:
   ```bash
   make dashboard-data
   git diff --exit-code -- report/dashboard/data.js \
     report/dashboard/search_index.js report/dashboard/search_index_us.js \
     report/dashboard/usforeignaiddata/us_subawards.js \
     report/dashboard/usforeignaiddata/us_detail.js \
     report/dashboard/usforeignaiddata/us_projmeta.js
   ```
   CI (`.github/workflows/deploy.yml`) runs exactly this and **fails on stale committed JS**.
   The committed dashboard `*.js` files must always equal a fresh rebuild — never hand-edit them.
4. Dashboard JS unit tests:
   ```bash
   node report/dashboard/tests/sector-summary.test.js
   ```

CI rebuilds `data.js` and the search indexes from committed CSVs, runs `90_validate.py`, and
checks the committed JS matches. Keep the pipeline the only writer of generated files.

## Conventions for agents

- **The schema is central.** All rows conform to `CORE_COLUMNS` in `scripts/common.py` and are
  built via `common.new_row(...)`, which validates enums and required fields. Do not write CSV
  rows by hand — go through the builder so validation and `obs_id`/`dedup_key` hashing stay
  consistent. If you add a column, update `CORE_COLUMNS`, `_DEFAULTS`, and downstream consumers.
- **One fetch script per source**, named `NN_fetch_<source>.py`. Each writes an immutable dated
  snapshot via `common.snapshot(...)` (which records a SHA-256 + URL + retrieved_at manifest row)
  and a normalized `data/interim/<source>_long.csv` via `common.write_interim(...)`.
- **Determinism.** Builds should be reproducible. Tie vintage-sensitive values (e.g.
  `US_DATA_ASOF`, `DATASET_VERSION`) to the data vintage, not the wall clock.
- **Org-name normalization** must go through `common.norm_org()`; scripts 91/93/94/95 and the
  dashboard's `dash-utils.js` all depend on identical keys or joins silently break.
- **Generated files are not source.** `report/dashboard/data.js`, the `search_index*.js`, and the
  `us_*.js` data files are pipeline outputs. Edit the scripts/CSVs, then regenerate.
- **Follow existing style.** Match the surrounding Python (stdlib-first, lazy `requests` import,
  descriptive module docstrings). Keep changes minimal and focused.

## Security / deployment awareness

- The dashboard can be deployed to Cloudflare Workers (password-gated via `_worker.js` +
  `SITE_PASSWORD` secret) or Vercel (public). See `DEPLOY.md`. Never commit secrets/passwords.
- The repo is private. Do not add third-party script/font/CDN references without updating the
  Content-Security-Policy in `report/dashboard/_worker.js` and `vercel.json`.
