#!/usr/bin/env python3
"""
96_fetch_us_activities.py — ACTIVITY-level pull of official US foreign-assistance data for
Nepal, from the same ForeignAssistance.gov system behind the /usforeignaiddata sector treemap.

Endpoint: https://foreignassistance.gov/data_query/results (the site's own Data Query tool,
the target of the country page's "All Activities" button). Each row is one activity x purpose x
account x FY transaction and carries BOTH the USG sector taxonomy the treemap uses
(usg_category_name / usg_sector_name) and the activity's identity (name, description, project
number, implementing channel). That shared taxonomy is what lets the dashboard answer, honestly,
"what exactly constitutes this treemap box" — same system, same money, no invented links.

Quirk: the endpoint returns 406 for a bare "Accept: application/json"; it requires the
browser-style compound header (see ACCEPT below). pageSize is capped at 100 server-side.

Outputs:
  data/raw/us_fa_activities/…       page-1 snapshot per FY (manifest: data/manifest_us_fa_activities.csv)
  data/processed/us_activities.csv  every Disbursements row, FY2015-FY2026

Reconciliation: per-sector-year sums are compared against data/processed/us_by_usg_sector_detail.csv
(the by-usg-sector cut fetched by 86). Run 86 in the same session so both share one data vintage.
"""
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C

SOURCE = "us_fa_activities"
URL = "https://foreignassistance.gov/data_query/results"
PAGE_URL = "https://foreignassistance.gov/data"
# bare "application/json" is refused (406); the compound browser Accept is required
ACCEPT = "application/json, text/plain, */*"
COUNTRY_ID = 524          # Nepal (ISO numeric, same id the site itself sends)
Y0, Y1 = 2015, 2026       # the span the treemap shows
PAGE_SIZE = 100           # server-side cap

FIELDS = ["fiscal_year", "usg_category_name", "usg_sector_name", "activity_id",
          "activity_name", "activity_project_number", "activity_description",
          "channel_name", "channel_category_name", "funding_agency_acronym",
          "funding_account_name", "implementing_agency_acronym", "dac_purpose_name",
          "activity_end_date", "current_amount", "constant_amount"]


def pull_year(session, year):
    rows, page = [], 1
    while True:
        r = C.get(session, URL, accept=ACCEPT, timeout=90,
                  params={"transaction_type": "Disbursements", "fiscal_year": year,
                          "country_id": COUNTRY_ID, "page": page, "pageSize": PAGE_SIZE})
        if r.status_code != 200:
            raise RuntimeError(f"FY{year} page {page}: HTTP {r.status_code}")
        j = r.json()
        if page == 1:
            C.snapshot(SOURCE, f"results_NPL_disb_{year}_p1", r.content, url=r.url,
                       params=f"transaction_type=Disbursements;fiscal_year={year};"
                              f"country_id={COUNTRY_ID};pageSize={PAGE_SIZE}",
                       http_status=r.status_code, ext="json")
        data = j.get("data", [])
        rows += data
        total = j.get("totalCount", 0)
        if page * PAGE_SIZE >= total or not data:
            return rows, total
        page += 1


def main():
    s = C.make_session()
    retrieved = C.utc_now()
    out, kept = [], 0
    for y in range(Y0, Y1 + 1):
        rows, total = pull_year(s, y)
        if len(rows) != total:
            raise RuntimeError(f"FY{y}: fetched {len(rows)} of {total} rows")
        for x in rows:
            out.append({
                "fiscal_year": y,
                "usg_category_name": x.get("usg_category_name") or "",
                "usg_sector_name": x.get("usg_sector_name") or "",
                "activity_id": x.get("activity_id") or "",
                "activity_name": (x.get("activity_name") or "").strip(),
                "activity_project_number": x.get("activity_project_number") or "",
                # official description, trimmed for repo size (the dashboard trims further)
                "activity_description": (x.get("activity_description") or "").strip()[:400],
                "channel_name": x.get("channel_name") or "",
                "channel_category_name": x.get("channel_category_name") or "",
                "funding_agency_acronym": x.get("funding_agency_acronym") or "",
                "funding_account_name": x.get("funding_account_name") or "",
                "implementing_agency_acronym": x.get("implementing_agency_acronym") or "",
                "dac_purpose_name": x.get("dac_purpose_name") or "",
                "activity_end_date": x.get("activity_end_date") or "",
                "current_amount": round(float(x.get("current_amount") or 0), 2),
                "constant_amount": round(float(x.get("constant_amount") or 0), 2),
            })
        kept += len(rows)
        print(f"  FY{y}: {len(rows)} rows")
    # deterministic order: year, category, sector, amount desc, activity id
    out.sort(key=lambda r: (r["fiscal_year"], r["usg_category_name"], r["usg_sector_name"],
                            -r["current_amount"], r["activity_id"]))

    path = C.PROCESSED / "us_activities.csv"
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS + ["source", "source_url", "retrieved_at"])
        w.writeheader()
        for r in out:
            w.writerow({**r, "source": SOURCE, "source_url": PAGE_URL, "retrieved_at": retrieved})
    print(f"wrote {path} ({len(out)} rows)")

    # ---- reconciliation vs the by-usg-sector cut (the treemap's own numbers) ----
    ref = C.PROCESSED / "us_by_usg_sector_detail.csv"
    if not ref.exists():
        print("NOTE: us_by_usg_sector_detail.csv missing — run 86 for the reconciliation check.")
        return
    want = defaultdict(float)
    with ref.open() as fh:
        for r in csv.DictReader(fh):
            if r["flow_stage"] == "disbursement" and Y0 <= int(r["year"]) <= Y1:
                want[(r["usg_category"], r["usg_sector"], int(r["year"]))] += float(r["amount_usd"])
    got = defaultdict(float)
    for r in out:
        got[(r["usg_category_name"], r["usg_sector_name"], r["fiscal_year"])] += r["current_amount"]
    keys = set(want) | set(got)
    bad = sorted((k for k in keys if abs(want.get(k, 0) - got.get(k, 0)) > 5000),
                 key=lambda k: -abs(want.get(k, 0) - got.get(k, 0)))
    print(f"reconciliation vs by-usg-sector: {len(keys) - len(bad)}/{len(keys)} sector-years "
          f"match within $5k")
    for k in bad[:12]:
        c, sec, y = k
        print(f"  MISMATCH FY{y} {c}/{sec}: sector-cut ${want.get(k,0):,.0f} vs "
              f"activities ${got.get(k,0):,.0f}")
    if bad:
        print("  (small drift can be data-vintage skew — rerun 86 in the same session)")


if __name__ == "__main__":
    main()
