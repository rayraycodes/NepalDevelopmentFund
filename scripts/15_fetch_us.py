#!/usr/bin/env python3
"""
15_fetch_us.py — US foreign assistance to Nepal from the OFFICIAL ForeignAssistance.gov
data-api (the source behind https://foreignassistance.gov/cd/nepal), replacing the earlier
community-mirror snapshot.

Endpoint (paginated, JSON): https://foreignassistance.gov/data-api/by-usg-sector.json?country_code=NPL
Each record: usg_category/usg_sector, transaction_type, fiscal_year, current_amount, constant_amount.
We keep only ACTUAL FLOWS: transaction types "Obligations" (-> commitment) and "Disbursements"
(-> disbursement). Budget types ("Appropriated and Planned", "President's Budget Requests") are
NOT aid flows and are excluded. US fiscal year (Oct-Sep), so fiscal_basis=donor_fy.
side=donor, counts_in_headline=False (donor-side headline is OECD), confidence=med.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C

SOURCE = "us_fa"
API = "https://foreignassistance.gov/data-api/by-usg-sector.json"
PAGE_URL = "https://foreignassistance.gov/cd/nepal"  # human-facing source for citations
FLOW = {"Obligations": "commitment", "Disbursements": "disbursement"}
MIN_YEAR = 2015  # project window; source covers 2001+


def main():
    s = C.make_session()
    rows_api, page = [], 1
    while True:
        r = C.get(s, API, params={"country_code": "NPL", "per_page": 1000, "page": page},
                  accept="application/json", timeout=90)
        j = r.json()
        rows_api += j["data"]
        pi = j["page_info"]
        if page == 1:
            C.snapshot(SOURCE, "fa_by_usg_sector_NPL_p1", r.content, url=r.url,
                       params="country_code=NPL;per_page=1000;page=1",
                       http_status=r.status_code, ext="json")
        if page >= pi["total_pages"]:
            break
        page += 1
    total_expected = pi["total_records"]
    if len(rows_api) != total_expected:
        print(f"WARN: pulled {len(rows_api)} != reported {total_expected}")

    out, retrieved, kept = [], C.utc_now(), 0
    for x in rows_api:
        tt = x.get("transaction_type_name")
        if tt not in FLOW:
            continue
        try:
            year = int(x["fiscal_year"])
        except (TypeError, ValueError):
            continue
        if year < MIN_YEAR:
            continue
        cur, con = x.get("current_amount"), x.get("constant_amount")
        cat, sec = x.get("usg_category_name", ""), x.get("usg_sector_name", "")
        kept += 1
        out.append(C.new_row(
            side="donor", source=SOURCE, source_record_id=f"FA|{x['id']}",
            donor_name="United States", donor_dac_code="USA", donor_iati_id="US-GOV",
            sector="", sector_raw=f"{cat} / {sec}".strip(" /"),
            flow_stage=FLOW[tt], instrument="grant",
            amount_usd=float(cur) if cur not in (None, "") else "",
            amount_usd_constant=float(con) if con not in (None, "") else "",
            amount_original=float(cur) if cur not in (None, "") else "",
            currency_original="USD", price_base="current",
            year=year, fiscal_basis="donor_fy",
            status="REPORTED", confidence="med", counts_in_headline=False,
            source_url=PAGE_URL, retrieved_at=retrieved,
            notes=f"ForeignAssistance.gov by-usg-sector; {tt}; USG sector {cat}/{sec}; "
                  f"constant_amount is ForeignAssistance.gov constant US$",
        ))
    C.write_interim(SOURCE, out)
    print(f"{SOURCE}: {len(rows_api)} API rows -> {kept} flow rows (Obligations+Disbursements, FY>={MIN_YEAR})")
    import collections
    dy = collections.defaultdict(float)
    for r_ in out:
        if r_["flow_stage"] == "disbursement" and r_["amount_usd"] != "":
            dy[r_["year"]] += float(r_["amount_usd"])
    print("  US disbursements by fiscal year (current US$):")
    for y in sorted(dy):
        print(f"    FY{y}: ${dy[y]:,.0f}")


if __name__ == "__main__":
    main()
