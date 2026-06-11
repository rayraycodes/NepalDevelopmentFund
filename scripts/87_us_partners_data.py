#!/usr/bin/env python3
"""
87_us_partners_data.py — WHO receives US money for Nepal and FOR WHAT named projects,
from the official USASpending.gov award-level API (place of performance = Nepal).

IMPORTANT BASIS CAVEAT (stated on the page): USASpending tracks AWARDS by place of
performance on an obligations basis. It is a different accounting frame from
ForeignAssistance.gov country attribution, so totals here do NOT reconcile 1:1 with the
by-account/by-sector views. It is used for granularity (partners, named projects), not totals.

Outputs:
  data/processed/us_partners.csv   top recipients (place of performance Nepal, FY2015+)
  data/processed/us_awards.csv     top assistance + contract awards with descriptions
  report/dashboard/usforeignaiddata/us_partners.js
"""
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C

SOURCE = "usaspending"
B = "https://api.usaspending.gov/api/v2/search/"
LINK = "https://www.usaspending.gov/award/"
FILT = {"place_of_performance_locations": [{"country": "NPL"}],
        "time_period": [{"start_date": "2014-10-01", "end_date": "2026-09-30"}]}
ASSIST = ["02", "03", "04", "05"]          # grants / cooperative agreements
CONTRACT = ["A", "B", "C", "D"]            # contracts
ALL_TYPES = CONTRACT + ASSIST + ["06", "07", "08", "09", "10", "11"]
HIDDEN = ("REDACTED", "MISCELLANEOUS FOREIGN AWARDEES")


def post(s, ep, body, snap_name):
    import requests
    r = s.post(B + ep, json=body, timeout=90)
    r.raise_for_status()
    C.snapshot(SOURCE, snap_name, r.content, url=B + ep,
               params=json.dumps(body)[:300], http_status=r.status_code, ext="json")
    return r.json()


def tc(name):
    """SHOUTING CASE -> Title Case, keeping known acronyms."""
    keep = {"LLC", "LLP", "INC.", "INC", "DAI", "FHI", "UN", "WWF", "PACT,", "IFES"}
    return " ".join(w if w in keep else w.title() for w in name.split())


def main():
    s = C.make_session()
    s.headers["Content-Type"] = "application/json"
    retrieved = C.utc_now()

    # ---- top recipients, all award types ----
    j = post(s, "spending_by_category/recipient",
             {"filters": {**FILT, "award_type_codes": ALL_TYPES}, "limit": 24, "page": 1},
             "top_recipients_NPL")
    partners, hidden_total = [], 0.0
    for x in j.get("results", []):
        if any(h in x["name"] for h in HIDDEN):
            hidden_total += x["amount"]
            continue
        partners.append({"name": tc(x["name"]), "usd": round(x["amount"] / 1e6, 1)})
    partners = partners[:14]

    # ---- top awards with descriptions (assistance + contracts) ----
    FIELDS = ["Award ID", "Recipient Name", "Award Amount", "Description",
              "Start Date", "End Date", "Awarding Sub Agency", "generated_internal_id"]

    def top_awards(codes, name):
        jj = post(s, "spending_by_award",
                  {"filters": {**FILT, "award_type_codes": codes}, "fields": FIELDS,
                   "limit": 15, "page": 1, "sort": "Award Amount", "order": "desc"},
                  f"top_awards_{name}_NPL")
        out = []
        for x in jj.get("results", []):
            desc = (x.get("Description") or "").strip()
            rec = x.get("Recipient Name") or ""
            redacted = any(h in (rec + desc).upper() for h in HIDDEN)
            out.append({
                "recipient": "Recipient redacted in source" if redacted else tc(rec),
                "usd": round((x.get("Award Amount") or 0) / 1e6, 1),
                "desc": ("Details redacted at source (PII rule)" if redacted
                         else (desc[:160].title() if desc.isupper() else desc[:160])),
                "start": (x.get("Start Date") or "")[:7],
                "end": (x.get("End Date") or "")[:7],
                "agency": x.get("Awarding Sub Agency") or "",
                "link": LINK + x["generated_internal_id"] if x.get("generated_internal_id") else "",
            })
        return out

    awards = {"assistance": top_awards(ASSIST, "assistance"),
              "contracts": top_awards(CONTRACT, "contracts")}

    # ---- CSVs ----
    with (C.PROCESSED / "us_partners.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["recipient", "amount_usd_millions", "basis", "source_url", "retrieved_at"])
        for p in partners:
            w.writerow([p["name"], p["usd"], "obligations, place of performance NPL, FY2015-FY2026",
                        "https://api.usaspending.gov/api/v2/search/spending_by_category/recipient", retrieved])
    with (C.PROCESSED / "us_awards.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["award_group", "recipient", "amount_usd_millions", "description",
                    "start", "end", "awarding_sub_agency", "award_url", "retrieved_at"])
        for g, rows in awards.items():
            for a in rows:
                w.writerow([g, a["recipient"], a["usd"], a["desc"], a["start"], a["end"],
                            a["agency"], a["link"], retrieved])

    data = {"meta": {"retrieved_at": retrieved, "hidden_total_m": round(hidden_total / 1e6, 1),
                     "basis": "USASpending.gov awards, obligations, place of performance = Nepal, FY2015-FY2026"},
            "partners": partners, "awards": awards}
    out = C.ROOT / "report" / "dashboard" / "usforeignaiddata" / "us_partners.js"
    out.write_text("window.US_PARTNERS = " + json.dumps(data) + ";\n")

    print(f"partners: {len(partners)} named (+${hidden_total/1e6:,.0f}m redacted/miscellaneous)")
    for p in partners[:8]:
        print(f"   ${p['usd']:7.1f}m  {p['name']}")
    print(f"awards: {len(awards['assistance'])} assistance + {len(awards['contracts'])} contracts")
    for a in awards["assistance"][:5]:
        print(f"   ${a['usd']:6.1f}m  {a['recipient'][:34]:34s}  {a['desc'][:58]}")
    print(f"wrote {out.name} ({out.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
