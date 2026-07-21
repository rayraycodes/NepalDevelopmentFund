#!/usr/bin/env python3
"""
98_fetch_dfims.py — Nepal MOF DFIMS official project ledger (recipient-government side).

SOURCE = dfims_mof.  https://dfims.mof.gov.np  (Development Finance Information
Management System, Ministry of Finance / IECCD).  Anonymous public dashboard API:
the production JS bundle registers these endpoints with authenticated:false and the
UI sends no token.  This is the GoN-side ledger that donor-side sources (IATI,
OECD CRS, FA.gov) cannot give us: on/off-budget classification, GoN counterpart
ministries, MOF-verified project status, expenditure (not just donor-reported
disbursement), province/district/municipality targeting, SDG mapping, and DFIMS's
own USD totals.

Writes:
  data/raw/dfims_mof/*.json           immutable snapshots (dir is git-ignored like the
                                      other regenerable raw dirs; the manifest fragment
                                      data/manifest_dfims_mof.csv IS committed)
  data/processed/dfims_projects.csv   one row per report row, clean snake_case columns
  data/processed/dfims_meta.json      run metadata + the API's own totals (read by 99,
                                      which must stay stdlib-only/no-network for CI)

WHY A CUSTOM RETRY LOOP instead of C.get: dfims.mof.gov.np (103.163.70.180, GIDC
subnet 103.163.70.0/24) sits behind a middlebox that accepts TCP+TLS but silently
drops MOST request payloads to foreign clients — observed live success rate on
2026-07-20 was roughly 1 request in 4-6, dead attempts hanging until timeout.
Once a response starts flowing it completes fine (the ~6.6 MB ledger arrived in
~19 s).  The right shape is therefore modest per-attempt timeouts + MANY attempts +
a small capped sleep.  C.get's uncapped 2**attempt backoff would sleep ~17 min by
attempt 10, so we keep C.make_session()/C.snapshot() but do the retrying here.

RESPONSE SHAPE (verified live 2026-07-20): /api/v2/report/project_report/ IGNORES
page/page_size and returns the ENTIRE ledger as ONE column-oriented payload:
    {"total_projects": N, "total_commitment": .., "total_disbursement": ..,
     "total_expenditure": .., "<Display Name>": {"<row_index>": value, ...}, ...}
Column keys are UI display names; the inner dict keys are report ROW INDICES
("0".."N-1"), NOT project ids.  The unique integer in the "Project" column is the
DFIMS project number (kept below as project_code); whether that number is the
<id> the v1 per-project endpoints take is UNVERIFIED — probes timed out — so we
record it without claiming deep-link semantics.  The 2025-04-03 production bundle
documents a paginated {count,next_page,results,total} envelope as the alternative
shape; if the API ever reverts to that we STOP with a clear message rather than
guess at row-key names and silently emit a wrong CSV.

CURRENCY: USD.  The DFIMS UI labels report amounts "(USD)" / "Amount in $", and
ships its own precision caveat (verbatim string in the production bundle), which we
carry into dfims_meta.json instead of hiding it.

MULTI-VALUE CELLS (sectors, partners, agencies, SDGs, locations) are joined with
" | " VERBATIM — no dedup here, because Province/District/Municipality look like
parallel arrays whose pairing we must not destroy.  Dedup (a set view) happens only
in 99, the dashboard emitter.  DFIMS's own spellings (e.g. "Chitawan",
"Nawalparasi East") are kept untouched.
"""
import csv
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C

SOURCE = "dfims_mof"
BASE = "https://dfims.mof.gov.np"
REPORT_URL = BASE + "/api/v2/report/project_report/"
# Kept for the day the API starts honouring pagination; today these are ignored and
# the full ledger comes back in one shot — which suits us fine (one lucky request
# beats fifteen gambles through the lossy middlebox).
REPORT_PARAMS = {"page": "1", "page_size": "200"}

# Cheap cross-check endpoints. Best-effort: each is another gamble through the
# middlebox, so a timeout here must NOT fail the run — meta records null instead.
OPTIONAL_URLS = {
    "project_count": BASE + "/api/v2/core/project_count/",
    "projects_status_count": BASE + "/api/v2/core/projects_status_count/",
    "projects_budget_type_count": BASE + "/api/v2/core/projects_budget_type_count/",
    "projects_assistance_type_count": BASE + "/api/v2/core/projects_assistance_type_count/",
}

# DFIMS's own words, verbatim from the 2025-04-03 production bundle — surfaced in
# meta so the dashboard can repeat it instead of implying false precision.
DFIMS_EXPENDITURE_CAVEAT = (
    "The displayed USD expenditure might not be precise as it's converted from "
    "NRB's API based on the synced date."
)

# (API display name, csv column) in output order. "Project" is the DFIMS project
# number; the dict key (report row index) becomes report_row.
COLMAP = [
    ("Project", "project_code"),
    ("Project name", "project_name"),
    ("Project status", "project_status"),
    ("Project type", "budget_type"),               # "On Budget" / "Off Budget"
    ("Total Commitment", "commitment_usd"),
    ("Total Disbursement", "disbursement_usd"),
    ("Total Expenditure", "expenditure_usd"),
    ("Financial Progress", "financial_progress_pct"),
    ("Sectors", "sectors"),
    ("Development partners", "development_partners"),
    ("Government agencies", "government_agencies"),
    ("Implementing agencies", "implementing_agencies"),
    ("Executing agencies", "executing_agencies"),
    ("Sdg", "sdg"),
    ("Sdg target", "sdg_target"),
    ("Climate marker", "climate_marker"),
    ("Gender marker", "gender_marker"),
    ("Disability marker", "disability_marker"),
    ("Humanitarian aid", "humanitarian_aid"),
    ("Agreement date", "agreement_date"),
    ("Proposed start date", "proposed_start_date"),
    ("Actual start date", "actual_start_date"),
    ("Effectiveness date", "effectiveness_date"),
    ("Planned completion date", "planned_completion_date"),
    ("Wind up date", "wind_up_date"),
    ("Completion date", "completion_date"),
    ("Budget head", "budget_head"),
    ("Iati identifier", "iati_identifier"),
    ("Project input", "project_input"),
    ("Project output", "project_output"),
    ("Project outcome", "project_outcome"),
    ("Project impact", "project_impact"),
    ("Nation", "nation"),
    ("Province", "provinces"),
    ("District", "districts"),
    ("Municipality", "municipalities"),
]


def patient_get(session, url, params=None, *, attempts, read_timeout=60,
                sleep_s=4.0, label=""):
    """Many quick gambles beat few patient ones against a payload-dropping middlebox.
    Returns the Response on any status < 500 (a real answer), None if every attempt
    timed out / 5xx'd."""
    import requests  # lazy like common.py, so schema-only imports stay dependency-free
    for i in range(1, attempts + 1):
        try:
            r = session.get(url, params=params, timeout=(10, read_timeout))
            if r.status_code < 500:
                print(f"  {label}: HTTP {r.status_code} on attempt {i} "
                      f"({len(r.content):,} bytes)", flush=True)
                return r
            print(f"  {label}: HTTP {r.status_code} on attempt {i}, retrying", flush=True)
        except requests.RequestException as e:
            print(f"  {label}: attempt {i}/{attempts} failed ({type(e).__name__})",
                  flush=True)
        time.sleep(sleep_s)
    return None


def cell_to_csv(v):
    """One API cell -> one CSV cell. None -> '' (missing); lists joined ' | '
    verbatim (see module docstring on why no dedup); bools lowered; strings
    stripped of outer whitespace only — inner text is MOF's, we don't edit it."""
    if v is None:
        return ""
    if isinstance(v, list):
        return " | ".join(str(x).strip() for x in v)
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, str):
        return v.strip()
    return v  # int/float pass through; csv module renders them


def main():
    session = C.make_session()
    print(f"Fetching DFIMS project ledger from {REPORT_URL} ...")
    print("(host drops most foreign requests — expect several failed attempts; "
          "each costs up to ~70 s)")

    r = patient_get(session, REPORT_URL, REPORT_PARAMS,
                    attempts=60, read_timeout=60, label="project_report")
    if r is None or r.status_code != 200:
        sys.exit("ERROR: /api/v2/report/project_report/ unreachable after 60 attempts "
                 "(or non-200). The GIDC middlebox may be fully dark again — rerun "
                 "later; nothing was written.")

    retrieved = C.utc_now()
    C.snapshot(SOURCE, "project_report_full", r.content,
               url=REPORT_URL + "?page=1&page_size=200",
               params=str(REPORT_PARAMS), http_status=r.status_code, ext="json")

    data = r.json()
    if isinstance(data, dict) and isinstance(data.get("results"), list):
        # The bundle-documented paginated envelope. We have never seen a live page
        # of it, so its row-key names are unverified — refuse to guess.
        sys.exit("ERROR: API returned the paginated {count,next_page,results} "
                 "envelope instead of the column-oriented full dump this parser "
                 "was verified against (2026-07-20). Snapshot saved; inspect it "
                 "and extend the parser before trusting any output.")
    if not (isinstance(data, dict) and "total_projects" in data):
        sys.exit(f"ERROR: unrecognised response shape (top-level keys: "
                 f"{list(data)[:8] if isinstance(data, dict) else type(data)}). "
                 "Snapshot saved for inspection.")

    cols = {k: v for k, v in data.items() if isinstance(v, dict)}
    missing = [d for d, _ in COLMAP if d not in cols]
    if missing:
        sys.exit(f"ERROR: expected report columns missing: {missing} — schema "
                 "changed; snapshot saved, update COLMAP after inspecting it.")
    extra = sorted(set(cols) - {d for d, _ in COLMAP})
    if extra:
        print(f"  NOTE: new columns not in COLMAP (ignored, present in snapshot): {extra}")

    # All column dicts must share one row-index keyset, else the pivot would
    # silently misalign values across columns.
    row_ids = sorted(cols["Project name"].keys(), key=int)
    for disp, _ in COLMAP:
        if set(cols[disp].keys()) != set(row_ids):
            sys.exit(f"ERROR: column {disp!r} keyset differs from 'Project name' — "
                     "refusing to pivot misaligned data.")

    # ---- pivot columnar -> per-project CSV rows --------------------------------
    out_path = C.PROCESSED / "dfims_projects.csv"
    fieldnames = ["report_row"] + [c for _, c in COLMAP] + ["retrieved_at"]
    n = 0
    with out_path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        for rid in row_ids:
            row = {"report_row": int(rid), "retrieved_at": retrieved}
            for disp, colname in COLMAP:
                row[colname] = cell_to_csv(cols[disp].get(rid))
            w.writerow(row)
            n += 1

    # ---- self-checks: our pivot must reproduce the API's own totals ------------
    def col_sum(disp):
        return sum(v for v in cols[disp].values() if isinstance(v, (int, float)))

    checks = []
    for disp, api_key in (("Total Commitment", "total_commitment"),
                          ("Total Disbursement", "total_disbursement"),
                          ("Total Expenditure", "total_expenditure")):
        ours, theirs = col_sum(disp), float(data[api_key])
        drift = abs(ours - theirs) / theirs if theirs else 0.0
        checks.append((api_key, ours, theirs, drift))
        flag = "OK" if drift < 1e-9 else f"DRIFT {drift:.2e}"
        print(f"  reconcile {api_key}: ours ${ours:,.0f} vs API ${theirs:,.0f} [{flag}]")
    if n != int(data["total_projects"]):
        print(f"  WARNING: wrote {n} rows but API says total_projects="
              f"{data['total_projects']}")
    codes = list(cols["Project"].values())
    if len(codes) != len(set(codes)):
        print(f"  WARNING: {len(codes) - len(set(codes))} duplicate project_code values")

    # ---- best-effort cross-check endpoints -------------------------------------
    crosschecks = {}
    for name, url in OPTIONAL_URLS.items():
        rr = patient_get(session, url, attempts=6, read_timeout=25, label=name)
        if rr is not None and rr.status_code == 200:
            C.snapshot(SOURCE, name, rr.content, url=url,
                       http_status=rr.status_code, ext="json")
            try:
                crosschecks[name] = rr.json()
            except ValueError:
                crosschecks[name] = None
        else:
            crosschecks[name] = None  # honest null: the middlebox ate it this run

    notes = []
    pc = crosschecks.get("project_count") or {}
    if pc.get("count") is not None and int(pc["count"]) != int(data["total_projects"]):
        notes.append(f"DFIMS's own endpoints disagree: /core/project_count/ says "
                     f"{pc['count']} while project_report says "
                     f"{data['total_projects']} — we ship the ledger's own count.")

    meta = {
        "source": "DFIMS — Development Finance Information Management System, "
                  "Ministry of Finance, Government of Nepal",
        "site": BASE,
        "source_url": REPORT_URL,
        "retrieved_at": retrieved,
        "currency": "USD",
        "dfims_expenditure_caveat": DFIMS_EXPENDITURE_CAVEAT,
        "total_projects": int(data["total_projects"]),
        "api_totals_usd": {
            "commitment": data["total_commitment"],
            "disbursement": data["total_disbursement"],
            "expenditure": data["total_expenditure"],
        },
        "crosschecks": crosschecks,
        "notes": notes,
        "id_note": "report_row is the report's own row index; project_code is the "
                   "DFIMS 'Project' number (unique). Whether project_code is the id "
                   "the v1 per-project endpoints accept is UNVERIFIED.",
    }
    meta_path = C.PROCESSED / "dfims_meta.json"
    meta_path.write_text(json.dumps(meta, indent=1, ensure_ascii=False) + "\n")

    print(f"\n{SOURCE}: wrote {out_path} ({n} rows) and {meta_path}")
    top = sorted(((v, k) for k, v in cols["Total Commitment"].items()
                  if isinstance(v, (int, float))), reverse=True)[:5]
    print("Top 5 by commitment (USD):")
    for amt, rid in top:
        print(f"  ${amt:>15,.0f}  {cols['Project name'][rid].strip()[:70]}  "
              f"[{' / '.join(cols['Development partners'][rid])[:50]}]")


if __name__ == "__main__":
    main()
