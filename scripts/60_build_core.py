#!/usr/bin/env python3
"""
60_build_core.py — assemble all interim/*_long.csv into the processed deliverables:
  data/processed/core_long.csv / .json   (the canonical machine-readable table)
  data/processed/agg_by_donor_year.csv    (headline donor-side + recipient-side, by year)
  data/processed/agg_by_sector_year.csv   (from sources carrying sector, e.g. CRS)
  data/processed/data_dictionary.json     (field + code definitions)
  data/manifest.csv                        (merged from per-source manifest fragments)
Merges whatever interim files currently exist (safe to run mid-build).
"""
import glob
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C

NUM = ["amount_usd", "amount_usd_constant", "amount_original"]
# defensive: any donor name matching these is an aggregate/total, never a headline leaf
import re as _re
AGG_NAME = _re.compile(
    r"all develop|all donor|all partner|official donor|\btotal\b|by sector|"
    r"signed oda|dac countries|dac members|multilateral.* organis|g7\b|developing countries",
    _re.I)


def load_all() -> pd.DataFrame:
    files = sorted(glob.glob(str(C.INTERIM / "*_long.csv")))
    if not files:
        raise SystemExit("no interim files yet")
    frames = []
    for f in files:
        df = pd.read_csv(f, dtype=str, keep_default_na=False)
        frames.append(df)
        print(f"  loaded {Path(f).name}: {len(df)} rows")
    df = pd.concat(frames, ignore_index=True)
    for c in C.CORE_COLUMNS:
        if c not in df.columns:
            df[c] = ""
    return df[C.CORE_COLUMNS]


def num(df, col):
    return pd.to_numeric(df[col].replace("", "0"), errors="coerce").fillna(0.0)


def main():
    df = load_all()
    C.PROCESSED.mkdir(parents=True, exist_ok=True)

    # defensive aggregate firewall: no hierarchy total may count in a headline sum
    agg_mask = df["donor_name"].astype(str).apply(lambda s: bool(AGG_NAME.search(s)))
    flipped = int((agg_mask & (df["counts_in_headline"].astype(str).str.lower() == "true")).sum())
    df.loc[agg_mask, "counts_in_headline"] = False
    if flipped:
        print(f"  firewall: forced {flipped} aggregate-named rows to counts_in_headline=False")
    # drop any fully-duplicate obs_id (keep first) as a last-resort integrity guard
    dups = int(df["obs_id"].duplicated().sum())
    if dups:
        df = df.drop_duplicates(subset="obs_id", keep="first")
        print(f"  dropped {dups} duplicate obs_id rows")

    df.to_csv(C.PROCESSED / "core_long.csv", index=False)
    # JSON with numeric coercion for the money fields
    recs = df.to_dict(orient="records")
    for r in recs:
        for k in NUM:
            r[k] = float(r[k]) if str(r[k]).strip() not in ("", "nan") else None
        for k in ("is_multilateral_outflow", "counts_in_headline"):
            r[k] = str(r[k]).lower() in ("true", "1")
    (C.PROCESSED / "core_long.json").write_text(json.dumps(recs, indent=1))

    hl = (df["counts_in_headline"].astype(str).str.lower() == "true")
    df["_usd"] = num(df, "amount_usd")

    # by-donor: headline rows only (donor-side = OECD leaf; recipient-side = DCR)
    dy = df[hl].groupby(["side", "donor_name", "year", "flow_stage"], as_index=False)["_usd"].sum()
    dy.rename(columns={"_usd": "amount_usd"}, inplace=True)
    dy.to_csv(C.PROCESSED / "agg_by_donor_year.csv", index=False)

    # by-sector: rows carrying a real sector (exclude the CRS 'all_sectors' aggregate,
    # which equals each donor's total and would double the column)
    sec = df[(df["sector"].astype(str).str.len() > 0) & (df["sector"] != "all_sectors")]
    sy = sec.groupby(["source", "sector", "year", "flow_stage"], as_index=False)["_usd"].sum()
    sy.rename(columns={"_usd": "amount_usd"}, inplace=True)
    sy.to_csv(C.PROCESSED / "agg_by_sector_year.csv", index=False)

    # merge manifest fragments
    frags = sorted(glob.glob(str(C.DATA / "manifest_*.csv")))
    if frags:
        man = pd.concat([pd.read_csv(f, dtype=str, keep_default_na=False) for f in frags],
                        ignore_index=True)
        man.to_csv(C.DATA / "manifest.csv", index=False)

    write_data_dictionary()

    print(f"\ncore_long: {len(df)} rows from {df['source'].nunique()} sources")
    print(df.groupby("source").size().to_string())
    print(f"headline rows: {int(hl.sum())}  |  donor-side: {int((hl & (df['side']=='donor')).sum())}"
          f"  recipient-side: {int((hl & (df['side']=='recipient')).sum())}")


def write_data_dictionary():
    dd = {
        "schema_version": C.DATASET_VERSION,
        "grain": "one row = one (source, record, flow_stage, year) observation",
        "fields": {
            "obs_id": "deterministic sha1(source|record|flow_stage|year)[:16], primary key",
            "side": "donor = reported by donor/multilateral; recipient = reported by Gov. of Nepal",
            "source": "dataset id (oecd_dac2a, oecd_crs, wb_projects, wb_indicators, iati_dportal, "
                      "adb_iati, us_fa, nepal_dcr, aiddata_gcdf)",
            "source_record_id": "native unique id within the source",
            "donor_name": "canonical donor display name",
            "donor_dac_code": "OECD donor identifier as published (ISO-3 alpha in current SDMX)",
            "donor_iati_id": "IATI reporting-org ref where applicable",
            "recipient": "always NPL (Nepal)",
            "sector": "common taxonomy mapped from DAC purpose prefix (see config/sector_crosswalk.csv)",
            "sector_raw": "original sector/purpose value as published",
            "flow_stage": "commitment | disbursement (never mixed; summed separately)",
            "instrument": "grant | concessional_loan | oof | other | '' (unclassified)",
            "amount_usd": "absolute current (nominal) USD — the PRIMARY measure",
            "amount_usd_constant": "absolute constant USD where source provides it",
            "price_base_year": "base year for the constant figure (e.g. 2024)",
            "amount_original": "amount in the original reporting currency",
            "currency_original": "ISO-4217 of amount_original",
            "price_base": "current | constant — describes amount_usd as published",
            "year": "calendar or fiscal year NUMBER as published (NOT converted)",
            "fiscal_basis": "nepal_fy (mid-Jul..mid-Jul) | donor_fy | calendar — what 'year' means",
            "period_start/period_end": "explicit Gregorian bounds of the reporting period",
            "status": "REPORTED | ESTIMATED (derived/FX-converted) | MISSING (known gap)",
            "confidence": "high | med | low with rationale in the report",
            "dataset_version": "pipeline build tag",
            "dedup_key": "key dedupe operates on; for IATI = iati-identifier",
            "is_multilateral_outflow": "true for multilaterals' own disbursements to Nepal",
            "counts_in_headline": "true only for the non-double-counted headline set FOR ITS SIDE "
                                  "(donor-side headline = OECD DAC2A leaf donors; recipient-side = DCR)",
            "source_url": "exact endpoint/permalink retrieved",
            "retrieved_at": "ISO-8601 UTC retrieval timestamp",
            "notes": "row-level caveats",
        },
        "headline_rule": "Donor-side and recipient-side headline series are COMPARED, never added. "
                         "All non-OECD donor sources are counts_in_headline=False (detail/fill).",
    }
    (C.PROCESSED / "data_dictionary.json").write_text(json.dumps(dd, indent=2))


if __name__ == "__main__":
    main()
