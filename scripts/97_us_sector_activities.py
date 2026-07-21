#!/usr/bin/env python3
"""
97_us_sector_activities.py — build the treemap drill-down data file from the committed
activity-level CSV (no network; stdlib only, so CI can run it).

Reads  data/processed/us_activities.csv          (fetched by 96_fetch_us_activities.py)
Writes report/dashboard/usforeignaiddata/us_sector_acts.js   (window.US_SECTOR_ACTS)

Shape: {meta:{retrieved_at, source}, y:{ "<FY>": { "<category>|<sector>": [entry, ...] } }}
entry: {a: US$ (merged across purposes/accounts), n: activity name, c: channel (partner),
        ag: funding agency acronym, e: end date, id: activity_id, d: description (>= $1m only)}

Within one FY x sector, rows are merged by activity_id (one activity can disburse under
several DAC purposes / funding accounts); entries are sorted by amount desc. Every row from
the CSV is kept — the drawer's sum therefore equals the treemap box by construction
(96 verifies that CSV sums reconcile with the by-usg-sector cut to within $5k).
"""
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C

SRC = C.PROCESSED / "us_activities.csv"
OUT = C.ROOT / "report" / "dashboard" / "usforeignaiddata" / "us_sector_acts.js"
DESC_MIN_USD = 1_000_000     # ship the (heavy) official description only for entries >= $1m
DESC_LEN = 220


def main():
    if not SRC.exists():
        sys.exit(f"missing {SRC} — run scripts/96_fetch_us_activities.py first")
    # (year, cat|sec, activity_id) -> merged entry
    merged = {}
    retrieved = ""
    with SRC.open() as fh:
        for r in csv.DictReader(fh):
            retrieved = r["retrieved_at"]
            y = r["fiscal_year"]
            key = (y, r["usg_category_name"] + "|" + r["usg_sector_name"], r["activity_id"])
            e = merged.get(key)
            if e is None:
                e = merged[key] = {"a": 0.0, "n": r["activity_name"] or "(unnamed activity)",
                                   "c": r["channel_name"], "ag": r["funding_agency_acronym"],
                                   "e": r["activity_end_date"], "id": r["activity_id"],
                                   "d": r["activity_description"]}
            e["a"] += float(r["current_amount"])
            if not e["d"]:
                e["d"] = r["activity_description"]

    tree = defaultdict(lambda: defaultdict(list))
    for (y, sec, _aid), e in merged.items():
        tree[y][sec].append(e)

    out_y = {}
    n_entries = 0
    for y in sorted(tree):
        out_y[y] = {}
        for sec in sorted(tree[y]):
            entries = sorted(tree[y][sec], key=lambda e: (-e["a"], e["id"]))
            rows = []
            for e in entries:
                row = {"a": round(e["a"]), "n": e["n"], "c": e["c"], "ag": e["ag"]}
                if e["e"]:
                    row["e"] = e["e"]
                if e["id"]:
                    row["id"] = e["id"]
                if e["d"] and abs(e["a"]) >= DESC_MIN_USD:
                    row["d"] = e["d"][:DESC_LEN]
                rows.append(row)
            out_y[y][sec] = rows
            n_entries += len(rows)

    data = {"meta": {"retrieved_at": retrieved,
                     "source": "https://foreignassistance.gov/data (Data Query, Disbursements)"},
            "y": out_y}
    OUT.write_text("window.US_SECTOR_ACTS = " + json.dumps(data) + ";\n")
    print(f"wrote {OUT} ({OUT.stat().st_size:,} bytes; {n_entries} activity entries "
          f"across {sum(len(v) for v in out_y.values())} sector-years)")


if __name__ == "__main__":
    main()
