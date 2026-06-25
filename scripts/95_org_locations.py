#!/usr/bin/env python3
"""
95_org_locations.py — where each US prime organisation is actually based.

USAspending's award record carries the prime recipient's registered address (country, state,
city, street). Knowing whether a partner is a US contractor in Washington, a UN agency, or a
locally-registered organisation makes the money far easier to read, so we pull that location
once per unique recipient and expose it everywhere the org appears.

Note: the sub-award feed does NOT include a sub-recipient address, so we can only place the
PRIME organisations here. We never guess a country from a name.

Output: data/processed/org_locations.json, keyed by the same normalised name 93_search_index.py
uses, so the search index can attach it directly.
"""
import csv
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C

A = "https://api.usaspending.gov/api/v2"
SOURCE = "usaspending_location"
norm = C.norm_org                # single source in common.py; keys line up with the search index


def tc(s):                       # title-case for display, leaving short codes (NY) alone
    s = (s or "").strip()
    return s if (len(s) <= 3 and s.isupper()) else s.title()


def main():
    det = list(csv.DictReader(open(C.PROCESSED / "us_project_detail.csv")))
    one_award = {}               # unique recipient -> one of its award ids
    for d in det:
        rec = d["recipient"]
        if rec and "redact" not in rec.lower() and rec not in one_award:
            one_award[rec] = d["award_id"]
    print(f"locating {len(one_award)} unique prime organisations...")

    s = C.make_session()
    out, snapped = {}, False
    for i, (rec, aid) in enumerate(sorted(one_award.items())):
        try:
            d = s.get(f"{A}/awards/{aid}/", timeout=40).json()
        except Exception:
            continue
        loc = (d.get("recipient") or {}).get("location") or {}
        if not snapped:
            C.snapshot(SOURCE, "example_award", json.dumps(d).encode(), url=f"{A}/awards/{aid}/",
                       http_status=200, ext="json")
            snapped = True
        country = tc(loc.get("country_name") or "")
        entry = {"cc": loc.get("location_country_code") or "",
                 "country": country, "state": (loc.get("state_code") or "").strip(),
                 "city": tc(loc.get("city_name") or ""),
                 "addr": tc(loc.get("address_line1") or "")}
        if entry["country"] or entry["city"]:
            out[norm(rec)] = entry
        if (i + 1) % 25 == 0:
            print(f"  {i+1}/{len(one_award)} ...")
        time.sleep(0.08)

    path = C.PROCESSED / "org_locations.json"
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    from collections import Counter
    by_c = Counter(v["country"] for v in out.values())
    print(f"wrote {path.relative_to(C.ROOT)}: {len(out)} located")
    print("  by country:", dict(by_c.most_common(8)))


if __name__ == "__main__":
    main()
