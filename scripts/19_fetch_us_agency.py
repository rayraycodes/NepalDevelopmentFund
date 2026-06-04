#!/usr/bin/env python3
"""
19_fetch_us_agency.py — US assistance to Nepal BY FUNDING AGENCY, from the official
ForeignAssistance.gov data-api (the by-funding-agency cut behind /cd/nepal).

This is an ALTERNATIVE breakdown of the same US totals as 15_fetch_us.py (by sector), so it is
NOT added to core_long (that would double-count US). It is written as a derived, sourced,
snapshotted artifact for the agency view: data/processed/us_by_agency.csv. It shows the shift
from USAID/State toward the Millennium Challenge Corporation around the 2025 restructuring.
"""
import csv
import collections
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C

SOURCE = "us_fa_agency"
API = "https://foreignassistance.gov/data-api/by-funding-agency.json"
FLOW = {"Obligations": "commitment", "Disbursements": "disbursement"}
MIN_YEAR = 2015
OUT = C.PROCESSED / "us_by_agency.csv"


def main():
    s = C.make_session()
    rows, page = [], 1
    while True:
        r = C.get(s, API, params={"country_code": "NPL", "per_page": 1000, "page": page},
                  accept="application/json", timeout=90)
        j = r.json()
        rows += j["data"]
        pi = j["page_info"]
        if page == 1:
            C.snapshot(SOURCE, "fa_by_funding_agency_NPL_p1", r.content, url=r.url,
                       params="country_code=NPL;per_page=1000;page=1",
                       http_status=r.status_code, ext="json")
        if page >= pi["total_pages"]:
            break
        page += 1

    agg = collections.defaultdict(float)  # (acronym, name, year, flow) -> current_usd
    for x in rows:
        tt = x.get("transaction_type_name")
        if tt not in FLOW:
            continue
        try:
            year = int(x["fiscal_year"])
        except (TypeError, ValueError):
            continue
        if year < MIN_YEAR:
            continue
        cur = x.get("current_amount")
        if cur in (None, ""):
            continue
        key = (x.get("funding_agency_acronym", ""), x.get("funding_agency_name", ""),
               year, FLOW[tt])
        agg[key] += float(cur)

    C.PROCESSED.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["agency_acronym", "agency_name", "year", "flow_stage", "amount_usd",
                    "source", "source_url", "retrieved_at"])
        ret = C.utc_now()
        for (ac, nm, yr, fl), v in sorted(agg.items(), key=lambda kv: (kv[0][2], -kv[1])):
            w.writerow([ac, nm, yr, fl, round(v, 2), SOURCE,
                        "https://foreignassistance.gov/cd/nepal", ret])
    print(f"{SOURCE}: {len(rows)} API rows -> {OUT.name}")
    # show disbursement-by-agency recent years
    dy = collections.defaultdict(lambda: collections.defaultdict(float))
    for (ac, nm, yr, fl), v in agg.items():
        if fl == "disbursement":
            dy[ac][yr] += v
    tops = sorted(dy, key=lambda a: -sum(dy[a].values()))[:6]
    yrs = list(range(2022, 2027))
    print("  disbursements by agency (USD m): " + " ".join(f"FY{y}" for y in yrs))
    for a in tops:
        print(f"    {a:12s}" + " ".join(f"{dy[a].get(y, 0)/1e6:6.1f}" for y in yrs))


if __name__ == "__main__":
    main()
