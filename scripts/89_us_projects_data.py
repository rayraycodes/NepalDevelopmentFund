#!/usr/bin/env python3
"""
89_us_projects_data.py — the FULL US project ledger for Nepal, triaged.

Pulls EVERY award (assistance + contracts) with place of performance Nepal, FY2015+,
from the official USASpending.gov API, and triages each by its period of performance:
  completed   ended before the restructuring window
  ended 25/26 end date falls in the restructuring window (2025-01-20 .. today) — may
              include natural completions AND early terminations; the public data does
              not distinguish, and the page says so
  active      end date after today
  undated     missing dates

Cross-check: IATI activities published by US-GOV publishers (from the local d-portal
snapshots) carry explicit activity-status codes; their distribution is reported alongside.

Outputs:
  data/processed/us_projects_all.csv                   every award
  report/dashboard/usforeignaiddata/us_projects.js     summary + list (>= $1m) for the page
"""
import csv
import glob
import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C

SOURCE = "usaspending_all"
B = "https://api.usaspending.gov/api/v2/search/spending_by_award"
LINK = "https://www.usaspending.gov/award/"
FILT = {"place_of_performance_locations": [{"country": "NPL"}],
        "time_period": [{"start_date": "2014-10-01", "end_date": "2026-09-30"}]}
GROUPS = {"assistance": ["02", "03", "04", "05"], "contracts": ["A", "B", "C", "D"]}
FIELDS = ["Award ID", "Recipient Name", "Award Amount", "Description",
          "Start Date", "End Date", "Awarding Sub Agency", "generated_internal_id"]
TODAY = date.fromisoformat(C.US_DATA_ASOF)   # data vintage (common.py), was an inconsistent local date
RESTRUCT_START = date(2025, 1, 20)
HIDDEN = ("REDACTED", "MISCELLANEOUS")


def tc(name):
    keep = {"LLC", "LLP", "INC.", "INC", "DAI", "FHI", "UN", "WWF", "USA", "USAID"}
    return " ".join(w if w in keep else w.title() for w in (name or "").split())


def pdate(s):
    try:
        return date.fromisoformat(s[:10])
    except (TypeError, ValueError):
        return None


def triage(start, end):
    if end is None:
        return "undated"
    if end > TODAY:
        return "active"
    if end >= RESTRUCT_START:
        return "ended_2526"
    return "completed"


def main():
    s = C.make_session()
    s.headers["Content-Type"] = "application/json"
    retrieved = C.utc_now()
    awards = []
    for gname, codes in GROUPS.items():
        page = 1
        while True:
            r = s.post(B, json={"filters": {**FILT, "award_type_codes": codes},
                                "fields": FIELDS, "limit": 100, "page": page,
                                "sort": "Award Amount", "order": "desc"}, timeout=90)
            r.raise_for_status()
            j = r.json()
            if page == 1:
                C.snapshot(SOURCE, f"all_awards_{gname}_p1", r.content, url=B,
                           params=f"group={gname};limit=100", http_status=r.status_code, ext="json")
            for x in j.get("results", []):
                st, en = pdate(x.get("Start Date")), pdate(x.get("End Date"))
                rec, desc = x.get("Recipient Name") or "", (x.get("Description") or "").strip()
                redacted = any(h in (rec + desc).upper() for h in HIDDEN)
                awards.append({
                    "group": gname,
                    "recipient": "Recipient redacted in source" if redacted else tc(rec),
                    "usd": float(x.get("Award Amount") or 0),
                    "desc": ("(redacted at source)" if redacted else
                             (desc.title() if desc.isupper() else desc))[:140],
                    "start": str(st or ""), "end": str(en or ""),
                    "status": triage(st, en),
                    "agency": x.get("Awarding Sub Agency") or "",
                    "link": LINK + x["generated_internal_id"] if x.get("generated_internal_id") else "",
                })
            if not j.get("page_metadata", {}).get("hasNext"):
                break
            page += 1
        print(f"{gname}: pulled through page {page}")
    print(f"total awards: {len(awards)}")

    # CSV (full ledger)
    with (C.PROCESSED / "us_projects_all.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(awards[0].keys()) + ["retrieved_at"])
        w.writeheader()
        for a in sorted(awards, key=lambda a: -a["usd"]):
            w.writerow({**a, "retrieved_at": retrieved})

    # summary
    summ = defaultdict(lambda: {"n": 0, "usd": 0.0})
    for a in awards:
        summ[a["status"]]["n"] += 1
        summ[a["status"]]["usd"] += a["usd"]
    for k, v in sorted(summ.items()):
        print(f"  {k:12s} n={v['n']:4d}  ${v['usd']/1e6:,.1f}m")

    # projects active per FY (count overlap of period with FY window)
    cohorts = []
    for fy in range(2015, 2027):
        w0, w1 = date(fy - 1, 10, 1), date(fy, 9, 30)
        n = sum(1 for a in awards if a["start"] and a["end"]
                and date.fromisoformat(a["start"]) <= w1 and date.fromisoformat(a["end"]) >= w0)
        cohorts.append({"fy": fy, "n": n})

    # IATI cross-check: US-GOV publishers' activity status from local d-portal snapshots
    st_names = {"1": "pipeline", "2": "implementation", "3": "finalisation",
                "4": "closed", "5": "cancelled", "6": "suspended"}
    seen, iati = set(), defaultdict(int)
    for f in glob.glob(str(C.RAW / "iati_dportal" / "*.json")):
        try:
            jj = json.load(open(f))
        except json.JSONDecodeError:
            continue
        for act in jj.get("activities", []):
            ref = str(act.get("reporting_ref") or "")
            aid = act.get("aid")
            if ref.startswith("US-") and aid not in seen:
                seen.add(aid)
                iati[st_names.get(str(act.get("status_code")), "unknown")] += 1
    print("IATI US-GOV activity status:", dict(iati))

    data = {"meta": {"retrieved_at": retrieved, "today": str(TODAY),
                     "restruct_start": str(RESTRUCT_START), "n_total": len(awards)},
            "summary": {k: {"n": v["n"], "usd": round(v["usd"] / 1e6, 1)} for k, v in summ.items()},
            "cohorts": cohorts,
            "iati_check": dict(iati),
            "list": [dict(a, usd=round(a["usd"] / 1e6, 2))
                     for a in sorted(awards, key=lambda a: -a["usd"]) if a["usd"] >= 1e6]}
    out = C.ROOT / "report" / "dashboard" / "usforeignaiddata" / "us_projects.js"
    out.write_text("window.US_PROJECTS = " + json.dumps(data) + ";\n")
    print(f"list >=$1m: {len(data['list'])} | wrote {out.name} ({out.stat().st_size:,}B)")


if __name__ == "__main__":
    main()
