#!/usr/bin/env python3
"""
50_reconcile.py — triangulate donor-side vs recipient-side vs the World Bank anchor.

Writes:
  data/processed/reconciliation_donor_vs_recipient.csv  (per-year gaps)
  data/processed/coverage_matrix.csv                    (donor-only / recipient-only / both)

Donor-side and recipient-side are COMPARED, never summed. Recipient-side (Nepal DCR) is on
Nepal fiscal years; we align by the calendar year the Nepal FY starts (year column) and label
the comparison approximate.
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C


def main():
    fp = C.PROCESSED / "core_long.csv"
    if not fp.exists():
        raise SystemExit("run 60_build_core.py first")
    df = pd.read_csv(fp, dtype=str, keep_default_na=False)
    df["usd"] = pd.to_numeric(df["amount_usd"].replace("", "0"), errors="coerce").fillna(0.0)
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    hl = df["counts_in_headline"].astype(str).str.lower() == "true"
    disb = df["flow_stage"] == "disbursement"

    donor = df[hl & (df["side"] == "donor") & disb].groupby("year")["usd"].sum()
    recip = df[hl & (df["side"] == "recipient") & disb].groupby("year")["usd"].sum()
    anchor = df[df["source"] == "wb_indicators"].groupby("year")["usd"].sum()

    years = sorted(set(donor.index) | set(recip.index) | set(anchor.index))
    rows = []
    for y in years:
        if pd.isna(y):
            continue
        d, r, a = donor.get(y), recip.get(y), anchor.get(y)
        gap_abs = (d - r) if (d and r) else None
        gap_pct = (gap_abs / r * 100) if (gap_abs is not None and r) else None
        resid = ((d - a) / a * 100) if (d and a) else None
        verdict = ""
        if resid is not None:
            verdict = "CONSISTENT" if abs(resid) <= 5 else "DISCREPANCY"
        rows.append({
            "year": int(y),
            "donor_side_usd": round(d, 0) if d else "",
            "recipient_side_usd": round(r, 0) if r else "",
            "anchor_usd": round(a, 0) if a else "",
            "gap_abs_usd": round(gap_abs, 0) if gap_abs is not None else "",
            "gap_pct": round(gap_pct, 1) if gap_pct is not None else "",
            "anchor_residual_pct": round(resid, 1) if resid is not None else "",
            "donor_vs_anchor": verdict,
            "note": "donor=OECD DAC2A leaf donors; recipient=Nepal DCR (Nepal FY, approx align); "
                    "anchor=WB net ODA received",
        })
    out = pd.DataFrame(rows)
    out.to_csv(C.PROCESSED / "reconciliation_donor_vs_recipient.csv", index=False)

    # coverage matrix
    dset = set(df[(df["side"] == "donor") & hl]["donor_name"]) - {""}
    rset = set(df[(df["side"] == "recipient")]["donor_name"]) - {""}
    cov = []
    for name in sorted(dset | rset):
        cov.append({"donor_name": name,
                    "donor_side": name in dset, "recipient_side": name in rset,
                    "coverage": "both" if name in dset and name in rset
                    else ("donor_only" if name in dset else "recipient_only")})
    pd.DataFrame(cov).to_csv(C.PROCESSED / "coverage_matrix.csv", index=False)

    print("Reconciliation (USD):")
    print(out.to_string(index=False) if len(out) else "  (no headline rows yet)")
    ronly = [c["donor_name"] for c in cov if c["coverage"] == "recipient_only"]
    print(f"\nRecipient-only donors (OECD misses these): {ronly or '(none yet — DCR not loaded)'}")


if __name__ == "__main__":
    main()
