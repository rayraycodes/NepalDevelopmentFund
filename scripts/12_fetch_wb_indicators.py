#!/usr/bin/env python3
"""
12_fetch_wb_indicators.py — World Bank net ODA received (DT.ODA.ODAT.CD), the ANCHOR.

This is OECD-sourced, current US$, recipient-side total. We do NOT sum it into the
headline (counts_in_headline=False); it is the benchmark every donor-side sum is
checked against.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C

SOURCE = "wb_indicators"
BASE = "https://api.worldbank.org/v2/country/NPL/indicator/DT.ODA.ODAT.CD"
PARAMS = {"format": "json", "date": "2015:2024", "per_page": "100"}
URL = BASE + "?format=json&date=2015:2024&per_page=100"


def main():
    s = C.make_session()
    r = C.get(s, BASE, params=PARAMS)
    C.snapshot(SOURCE, "DT.ODA.ODAT.CD_NPL", r.content, url=URL,
               params=str(PARAMS), http_status=r.status_code, ext="json")
    payload = r.json()
    if not isinstance(payload, list) or len(payload) < 2 or payload[1] is None:
        raise SystemExit(f"unexpected WB response: {str(payload)[:200]}")

    rows, retrieved = [], C.utc_now()
    for e in payload[1]:
        val = e.get("value")
        if val is None:
            continue
        year = int(e["date"])
        rows.append(C.new_row(
            side="donor", source=SOURCE,
            source_record_id=f"DT.ODA.ODAT.CD-NPL-{year}",
            donor_name="All donors (net ODA received, OECD/DAC via World Bank)",
            flow_stage="disbursement", instrument="",
            amount_usd=float(val), amount_original=float(val),
            currency_original="USD", price_base="current",
            year=year, fiscal_basis="calendar",
            status="REPORTED", confidence="high",
            counts_in_headline=False,
            source_url=URL, retrieved_at=retrieved,
            notes="net ODA received, current US$; ANCHOR benchmark (not summed)",
        ))
    C.write_interim(SOURCE, rows)
    print(f"{SOURCE}: {len(rows)} year-rows")
    for r_ in sorted(rows, key=lambda x: x["year"]):
        print(f"  {r_['year']}: ${r_['amount_usd']:,.0f}")


if __name__ == "__main__":
    main()
