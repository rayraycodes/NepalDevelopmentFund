# External Development Funding to Nepal — a verifiable, fully-sourced dataset

A reproducible dataset of official development finance flowing **to Nepal** (ODA grants
and concessional loans, other official flows, and where visible blended/vertical-fund
finance), 2015 to present. It captures **both ledger sides** and compares them rather
than merging:

- **Donor side** — what donors and multilaterals report giving (OECD DAC, IATI, World
  Bank, ADB, US).
- **Recipient side** — what the Government of Nepal reports receiving (Ministry of
  Finance Development Cooperation Report), which uniquely includes China and India.

Provenance and reproducibility come first. Every figure carries its source, dataset
version, exact query/URL, and retrieval date, and is tagged REPORTED / ESTIMATED /
MISSING with a confidence level. Gaps are left blank and labelled MISSING — never filled
with plausible-looking estimates.

## Reproduce

```bash
pip install -r requirements.txt
make smoke      # validate the common module / schema
make anchor     # Phase 1: World Bank net-ODA anchor + OECD DAC2A (verified core)
make fetch      # Phase 2: remaining donor sources
make build      # Phase 3: dedupe, reconcile, assemble core_long
make validate   # integrity assertions
make figures    # generate report/figures/*.png
make serve      # build dashboard data + serve the interactive dashboard at :8848
```

An interactive, self-contained dashboard (ECharts, works offline) lives in
[`report/dashboard/`](report/dashboard/index.html): donor vs recipient triangulation, top
donors by ledger side, the China commitments-vs-disbursements story, sectors, the gap, and the
full discrepancy log and source list. It is **bilingual (English / नेपाली**, toggle in the
header), mobile-friendly, and built for accessibility: a plain-language "How to read this"
guide, a glossary, ARIA-labelled charts, keyboard focus, and reduced-motion support. Run
`make serve` and open http://127.0.0.1:8848.

A second page, [`/usforeignaiddata`](report/dashboard/usforeignaiddata/index.html), is a
**US deep dive** built from three mutually-reconciling cuts of the official
ForeignAssistance.gov data-api (FY2001–FY2026): the 25-year promised-vs-delivered arc (current
and constant-2024 dollars), budget-account plumbing (stacked + agency→account sankey), a
category→program treemap, funding vs implementing agencies, and an account-by-account table of
the 2025–26 restructuring (18 active accounts in FY2024 → 7 in FY2026; MCC becomes the dominant
channel). Also bilingual and mobile-friendly.

Each fetch writes an **immutable, dated raw snapshot** under `data/raw/<source>/` and a
SHA-256 row to `data/manifest_<source>.csv`. Outputs land in `data/processed/`.

## Layout

| Path | Contents |
|---|---|
| `config/` | source registry (`sources.yaml`), donor/sector crosswalks, FX rates, Nepal FY calendar |
| `scripts/common.py` | canonical schema, validators, browser-UA HTTP session, snapshot + manifest writer |
| `scripts/NN_fetch_*.py` | one fetch+normalize script per source |
| `data/raw/` | immutable dated source snapshots (never edited) |
| `data/interim/` | per-source normalized long CSVs |
| `data/processed/` | `core_long.csv` / `.json`, aggregates, reconciliation, data dictionary |
| `report/report.md` | the cited narrative report (8 deliverables) |

## Headline anchor (verified 2026-06-03)

OECD DAC2A "Official donors" total reconciles to the World Bank net-ODA-received series
(both OECD-sourced) and to the sum of individual (leaf) donors. Net ODA received, current US$:

| Year | Net ODA received (US$ bn) |
|---|---|
| 2020 | 1.76 |
| 2021 | 1.60 |
| 2022 | 1.20 |
| 2023 | 1.17 (WB) / 1.21 (OECD, later vintage) |

Sources: [World Bank DT.ODA.ODAT.CD](https://api.worldbank.org/v2/country/NPL/indicator/DT.ODA.ODAT.CD?format=json) ·
OECD DAC2A via [SDMX](https://sdmx.oecd.org/public/rest/data/OECD.DCD.FSD,DSD_DAC2@DF_DAC2A,/.NPL...).

## Key caveats

- OECD CRS largely excludes non-DAC donors (China, India, Gulf funds) — covered via the
  Nepal Development Cooperation Report and AidData.
- Nepal's fiscal year runs mid-July to mid-July (Bikram Sambat), not the calendar year.
- IATI is a publishing standard, not an additive database — deduplicated by iati-identifier.
- US foreign aid was heavily restructured in 2025; US figures are treated as volatile.

See `report/report.md` for the full methodology, discrepancy log, and limitations.
