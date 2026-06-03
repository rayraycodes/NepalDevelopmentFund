#!/usr/bin/env python3
"""
40_dedupe_iati.py — collapse IATI non-additivity before assembly.

IATI is a publishing standard, not an additive database: the same activity (same
iati-identifier) can be published by the donor, the implementer, and a secondary
publisher, and d-portal can return identical rows across pages. We:
  1. drop exact duplicate (dedup_key, flow_stage, year, amount) rows within d-portal;
  2. where an iati-identifier is also published ADB-direct (XM-DAC-46004), drop the
     d-portal copy (publisher priority: original donor/agency > d-portal mirror).
Rewrites data/interim/iati_dportal_long.csv in place (idempotent; raw snapshot preserved).
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C

IATI = C.INTERIM / "iati_dportal_long.csv"
ADB = C.INTERIM / "adb_iati_long.csv"


def load(p):
    return list(csv.DictReader(open(p))) if p.exists() else []


def main():
    if not IATI.exists():
        print("no iati_dportal interim; nothing to dedupe")
        return
    rows = load(IATI)
    n0 = len(rows)

    # ADB-direct iati-identifiers take priority over the d-portal copy
    adb_ids = {r["dedup_key"] for r in load(ADB) if r.get("dedup_key")}

    seen, out, dropped_dup, dropped_adb = set(), [], 0, 0
    for r in rows:
        if r["dedup_key"] in adb_ids:
            dropped_adb += 1
            continue
        amt = r["amount_usd"]
        try:
            amt = round(float(amt), 2)
        except ValueError:
            amt = amt
        key = (r["dedup_key"], r["flow_stage"], r["year"], amt)
        if key in seen:
            dropped_dup += 1
            continue
        seen.add(key)
        out.append(r)

    with IATI.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=C.CORE_COLUMNS, extrasaction="ignore")
        w.writeheader()
        w.writerows(out)
    print(f"iati dedupe: {n0} -> {len(out)} rows "
          f"(dropped {dropped_dup} exact dups, {dropped_adb} ADB-direct overlaps)")


if __name__ == "__main__":
    main()
