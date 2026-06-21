#!/usr/bin/env python3
"""
90_us_project_detail.py — granular spending INSIDE each large US project for Nepal.

For every award >= $1m in the ledger (us_projects.js), pull from USASpending:
  - award profile:  obligated vs OUTLAYED (what was actually spent) -> a real spend rate
  - sub-awards:     the money passed onward to sub-recipients (often Nepali NGOs), with
                    the district extracted from each sub-award's description

Outputs:
  data/processed/us_project_detail.csv   per project: obligated, outlayed, spend_rate, sub-total
  data/processed/us_subawards.csv        every sub-award: prime, sub-recipient, amount, district
  report/dashboard/usforeignaiddata/us_detail.js   summary + top sub-recipients for the page

Honesty: the sub-awards endpoint has no recipient-country field, so we do NOT claim a precise
"share to Nepali organisations". We report what is solid: how much each prime passed ONWARD to
sub-recipients vs retained, and the named sub-recipients (many visibly Nepali) with their district.
"""
import csv
import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C

SOURCE = "usaspending_detail"
A = "https://api.usaspending.gov/api/v2"
DIST = re.compile(r"\bIN\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)?)\s+DISTRICT", re.I)


def main():
    s = C.make_session()
    s.headers["Content-Type"] = "application/json"
    proj = json.loads((C.ROOT / "report/dashboard/usforeignaiddata/us_projects.js")
                      .read_text().split("=", 1)[1].rstrip().rstrip(";"))
    awards = [a for a in proj["list"] if a.get("link")]
    print(f"detailing {len(awards)} awards (>=$1m)...")

    details, subs, snapped = [], [], False
    for i, a in enumerate(awards):
        aid = a["link"].split("/award/")[1].strip("/")
        try:
            d = s.get(f"{A}/awards/{aid}/", timeout=40).json()
        except Exception:
            continue
        obl = float(d.get("total_obligation") or 0)
        out = float(d.get("total_outlay") or d.get("total_account_outlay") or 0)
        # sub-awards (paginate)
        sub_rows, page = [], 1
        while True:
            try:
                j = s.post(f"{A}/subawards/", json={"award_id": aid, "limit": 100, "page": page,
                                                    "sort": "amount", "order": "desc"}, timeout=40).json()
            except Exception:
                break
            if not snapped:
                C.snapshot(SOURCE, "example_subawards", json.dumps(j).encode(), url=f"{A}/subawards/",
                           params=f"award_id={aid}", http_status=200, ext="json")
                snapped = True
            sub_rows += j.get("results", [])
            if not j.get("page_metadata", {}).get("hasNext"):
                break
            page += 1
            time.sleep(0.05)
        sub_tot = sum(float(x.get("amount") or 0) for x in sub_rows)
        for x in sub_rows:
            m = DIST.search(x.get("description") or "")
            subs.append({"prime": a["recipient"], "prime_award": aid,
                         "sub_recipient": x.get("recipient_name") or "",
                         "amount_usd": round(float(x.get("amount") or 0), 2),
                         "district": (m.group(1).title() if m else ""),
                         "action_date": x.get("action_date") or "",
                         "description": (x.get("description") or "")[:120]})
        details.append({"award_id": aid, "recipient": a["recipient"], "desc": a["desc"],
                        "group": a["group"], "status": a["status"],
                        "obligated_usd": round(obl, 2), "outlayed_usd": round(out, 2),
                        "spend_rate_pct": round(100 * out / obl, 1) if obl else None,
                        "subawarded_usd": round(sub_tot, 2), "n_subawards": len(sub_rows)})
        if (i + 1) % 25 == 0:
            print(f"  {i+1}/{len(awards)} ...")
        time.sleep(0.08)

    # write CSVs
    with (C.PROCESSED / "us_project_detail.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(details[0].keys()))
        w.writeheader(); w.writerows(details)
    with (C.PROCESSED / "us_subawards.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(subs[0].keys()) if subs else
                           ["prime", "prime_award", "sub_recipient", "amount_usd", "district",
                            "action_date", "description"])
        w.writeheader(); w.writerows(subs)

    # NOTE: the localisation summary (us_detail.js) is built from these CSVs by
    # 91_us_localization.py, which applies the Nepal-district whitelist. This script only
    # pulls + writes the raw CSVs (separation of fetch from presentation).
    print(f"wrote us_project_detail.csv ({len(details)}), us_subawards.csv ({len(subs)})")


if __name__ == "__main__":
    main()
