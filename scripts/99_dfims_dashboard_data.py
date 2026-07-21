#!/usr/bin/env python3
"""
99_dfims_dashboard_data.py — build the DFIMS ledger data file for the dashboard
(no network; stdlib only, so CI can rerun it and diff the committed output).

Reads  data/processed/dfims_projects.csv    (fetched by 98_fetch_dfims.py)
       data/processed/dfims_meta.json       (same run; API totals + provenance)
Writes report/dashboard/dfims_projects.js   (window.DFIMS_PROJECTS)

Shape: {meta:{...}, list:[row, ...]}.  Rows are sorted commitment desc (rows with
no commitment last), then report_row asc — deterministic across rebuilds so the
committed file diffs clean in CI.

Row keys (short on purpose; EMPTY/ABSENT means "not reported by MOF", never zero):
  i   report row index (int)          c   DFIMS project number ("Project" column)
  n   project name                    st  project status ("Completed"/"On-Going")
  bt  "on"/"off" budget               fp  financial progress %
  cm/db/ex  commitment/disbursement/expenditure, USD, rounded to whole dollars
            (0 is kept — "0 disbursed" is information; key absent = not reported)
  se  sectors[]                       dp  development partners[]
  ga  GoN counterpart ministries[]    sdg SDG goal names[]
  ad  agreement date                  cd  completion date (DFIMS "Completion date")
  pv  provinces[] (deduped)           dt  districts[] (deduped, DFIMS's own spellings)
  hu  1 = humanitarian aid            cl/gm climate/gender marker (ABSENT = "Neutral")
  ii  IATI identifier as recorded by MOF — provenance only, NOT verified against
      IATI; per project policy never silently join datasets on it
  d   first non-empty of outcome/impact/output/input, whitespace-collapsed,
      trimmed to 200 chars

The full untrimmed record set stays in data/processed/dfims_projects.csv.
This file is ~1 MB — the frontend MUST lazy-load it exactly like search_index.js
(the P1 pattern); do not add a blocking <script> tag.
"""
import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C

SRC_CSV = C.PROCESSED / "dfims_projects.csv"
SRC_META = C.PROCESSED / "dfims_meta.json"
OUT = C.ROOT / "report" / "dashboard" / "dfims_projects.js"
DESC_LEN = 200
LAZY_THRESHOLD = 250_000  # bytes; above this the frontend must lazy-load


def split_list(cell):
    """CSV ' | '-joined cell -> list (98 joins verbatim; empty cell -> [])."""
    return [p for p in (s.strip() for s in cell.split(" | ")) if p] if cell else []


def uniq(seq):
    """Dedup preserving first-seen order (98 keeps location duplicates on purpose
    to preserve pairing; the dashboard wants the set view)."""
    seen, out = set(), []
    for x in seq:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def num(cell):
    return float(cell) if cell not in ("", None) else None


def main():
    if not SRC_CSV.exists() or not SRC_META.exists():
        sys.exit(f"missing {SRC_CSV} / {SRC_META} — run scripts/98_fetch_dfims.py first")
    meta_in = json.loads(SRC_META.read_text())

    rows = []
    with SRC_CSV.open() as fh:
        for r in csv.DictReader(fh):
            e = {"i": int(r["report_row"]), "c": int(r["project_code"]),
                 "n": r["project_name"].strip()}
            if r["project_status"]:
                e["st"] = r["project_status"]
            # "On Budget"/"Off Budget" -> "on"/"off" (meta.legend documents this)
            bt = r["budget_type"].strip().lower()
            if bt.startswith("on"):
                e["bt"] = "on"
            elif bt.startswith("off"):
                e["bt"] = "off"
            for key, col in (("cm", "commitment_usd"), ("db", "disbursement_usd"),
                             ("ex", "expenditure_usd")):
                v = num(r[col])
                if v is not None:
                    e[key] = round(v)
            fp = num(r["financial_progress_pct"])
            if fp is not None:
                e["fp"] = round(fp, 1)
            for key, col in (("se", "sectors"), ("dp", "development_partners"),
                             ("ga", "government_agencies"), ("sdg", "sdg")):
                vals = split_list(r[col])
                if vals:
                    e[key] = vals
            for key, col in (("ad", "agreement_date"), ("cd", "completion_date")):
                if r[col]:
                    e[key] = r[col]
            for key, col in (("pv", "provinces"), ("dt", "districts")):
                vals = uniq(split_list(r[col]))
                if vals:
                    e[key] = vals
            if r["humanitarian_aid"] == "true":
                e["hu"] = 1
            for key, col in (("cl", "climate_marker"), ("gm", "gender_marker")):
                if r[col] and r[col] != "Neutral":
                    e[key] = r[col]
            if r["iati_identifier"]:
                e["ii"] = r["iati_identifier"]
            for col in ("project_outcome", "project_impact",
                        "project_output", "project_input"):
                txt = re.sub(r"\s+", " ", r[col]).strip()
                if txt:
                    e["d"] = txt[:DESC_LEN] + ("…" if len(txt) > DESC_LEN else "")
                    break
            rows.append(e)

    # commitment desc, no-commitment rows last, then report_row — deterministic.
    rows.sort(key=lambda e: (0, -e["cm"], e["i"]) if "cm" in e else (1, 0, e["i"]))

    data = {
        "meta": {
            "source": meta_in["source"],
            "site": meta_in["site"],
            "source_url": meta_in["source_url"],
            "retrieved_at": meta_in["retrieved_at"],
            "n": len(rows),
            "currency": meta_in["currency"],
            "api_totals_usd": {k: round(v)
                               for k, v in meta_in["api_totals_usd"].items()},
            "caveat": meta_in["dfims_expenditure_caveat"],
            "notes": meta_in.get("notes", []),
            "legend": {"bt": "on/off budget", "hu": "1 = humanitarian aid",
                       "cl_gm_absent": "Neutral",
                       "amounts": "USD, whole dollars; key absent = not reported"},
        },
        "list": rows,
    }
    OUT.write_text("window.DFIMS_PROJECTS = "
                   + json.dumps(data, ensure_ascii=False, separators=(",", ":"))
                   + ";\n", encoding="utf-8")
    size = OUT.stat().st_size
    print(f"wrote {OUT} ({size:,} bytes; {len(rows)} projects)")
    if size > LAZY_THRESHOLD:
        print(f"  NOTE: > {LAZY_THRESHOLD:,} bytes — frontend must lazy-load this "
              "file (same pattern as search_index.js), not block on it.")


if __name__ == "__main__":
    main()
