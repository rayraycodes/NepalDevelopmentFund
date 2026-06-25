#!/usr/bin/env python3
"""
90_validate.py — integrity assertions on data/processed/core_long.csv. Exit non-zero on failure.
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C

errors, warns = [], []


def main():
    fp = C.PROCESSED / "core_long.csv"
    if not fp.exists():
        raise SystemExit("run 60_build_core.py first")
    df = pd.read_csv(fp, dtype=str, keep_default_na=False)

    # 1. schema
    if list(df.columns) != C.CORE_COLUMNS:
        errors.append(f"columns mismatch: {set(C.CORE_COLUMNS) ^ set(df.columns)}")

    # 2. provenance on every row
    for col in ("source_url", "retrieved_at"):
        n = int((df[col].astype(str).str.len() == 0).sum())
        if n:
            errors.append(f"{n} rows missing {col}")

    # 3. enums
    for field, allowed in C.ENUMS.items():
        bad = set(df[field].unique()) - allowed
        if bad:
            errors.append(f"{field} has invalid values {bad}")

    # 4. obs_id unique
    dup = int(df["obs_id"].duplicated().sum())
    if dup:
        errors.append(f"{dup} duplicate obs_id")

    # 5. headline firewall
    hl = df["counts_in_headline"].astype(str).str.lower() == "true"
    dsrc = set(df[hl & (df["side"] == "donor")]["source"])
    if dsrc - {"oecd_dac2a"}:
        errors.append(f"donor-side headline must be oecd_dac2a only, found {dsrc}")
    rsrc = set(df[hl & (df["side"] == "recipient")]["source"])
    if rsrc - {"nepal_dcr"}:
        errors.append(f"recipient-side headline must be nepal_dcr only, found {rsrc}")

    # 6. headline rows must carry a real value and never be MISSING. This is the set the public
    #    dashboards sum, so an incomplete/empty official figure here is a FAILURE, not a warning
    #    (data integrity is the project's stated top priority).
    miss_hl = int((hl & (df["status"] == "MISSING")).sum())
    if miss_hl:
        errors.append(f"{miss_hl} headline rows are MISSING (must never reach the headline set)")
    noval = int((hl & (df["amount_usd"].astype(str).str.len() == 0)).sum())
    if noval:
        errors.append(f"{noval} headline rows have empty amount_usd")

    print(f"core_long: {len(df)} rows, {df['source'].nunique()} sources, "
          f"{int(hl.sum())} headline")
    for w in warns:
        print(f"  WARN: {w}")
    if errors:
        for e in errors:
            print(f"  FAIL: {e}")
        sys.exit(1)
    print("VALIDATION PASSED")


if __name__ == "__main__":
    main()
