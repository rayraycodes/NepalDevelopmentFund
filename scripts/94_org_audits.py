#!/usr/bin/env python3
"""
94_org_audits.py — link each US prime organisation to its published financial-accountability
records, so a profile can answer "has this organisation been audited, and where is the report?"

Two reliable sources, no guessing:
  1. Federal Audit Clearinghouse (api.fac.gov) — the Single Audit every US non-federal entity
     that expends >= $750k/yr in federal awards must file: audited financial statements + a
     Schedule of Expenditures of Federal Awards. We match a prime to a Single Audit ONLY when
     the names are an EXACT normalised match (so "Helen Keller International" is never confused
     with "Helen Keller Services for the Blind"), and we record the auditee EIN so a human can
     verify the entity. For-profit contractors (DAI, Deloitte, Chemonics) are not required to
     file a Single Audit, so an empty result there is correct, not missing.
  2. USAID OIG audits we already archived (audits.js) — matched to the org they name.

Reproducibility: FAC responses are snapshotted (data/raw/fac/...). The API key comes from
$FAC_API_KEY (get a free one at api.data.gov); it falls back to the public DEMO_KEY, which is
rate-limited, so we batch all names into as few requests as possible and degrade gracefully —
orgs we cannot confirm still get a Clearinghouse lookup link (built client-side from the name).

Output: data/processed/org_audits.json, keyed by the SAME normalised name 93_search_index.py
uses for org ids, so the search index can attach it directly.
"""
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C

US = C.ROOT / "report/dashboard/usforeignaiddata"
FAC = "https://api.fac.gov/general"
KEY = os.environ.get("FAC_API_KEY", "DEMO_KEY")
TOP_N = 45                       # biggest primes by obligation (covers the bulk of the money)
SUFFIX = {"INC", "LLC", "LTD", "CORP", "CO", "INCORPORATED", "LIMITED", "LP", "LLP", "PVT", "PLC"}
STOP = {"INC", "INCORPORATED", "LLC", "LTD", "LIMITED", "CORP", "CORPORATION",
        "CO", "PVT", "PRIVATE", "THE", "AND", "OF", "A"}            # identical to 93_search_index


def norm(name):                  # MUST match 93_search_index.norm so keys line up with org ids
    toks = re.sub(r"[^A-Z0-9 ]", " ", (name or "").upper()).split()
    return " ".join(t for t in toks if t not in STOP)


def variants(name):
    """Name strings FAC might store, so an exact in.() lookup can hit; norm() guards correctness."""
    u = re.sub(r"\s+", " ", name.upper()).strip()
    out = {u}
    nop = re.sub(r"\s+", " ", re.sub(r"[^A-Z0-9 ]", " ", u)).strip()
    out.add(nop)
    toks = nop.split()
    while toks and toks[-1] in SUFFIX:
        toks.pop()
    out.add(" ".join(toks))
    return {x for x in out if x}


def fac_query(names, snap_tag):
    """One batched Single-Audit lookup for many exact names. Returns rows or [] (logs + degrades)."""
    import requests
    quoted = ",".join('"' + n.replace('"', "") + '"' for n in names)
    params = {"auditee_name": f"in.({quoted})",
              "select": "auditee_name,auditee_ein,auditee_uei,audit_year,total_amount_expended,report_id,fac_accepted_date",
              "order": "audit_year.desc", "limit": "500"}
    try:
        r = requests.get(FAC, params=params, timeout=45,
                         headers={"X-Api-Key": KEY, "Accept": "application/json",
                                  "User-Agent": "Mozilla/5.0 (NepalDevFund research)"})
    except Exception as e:
        print(f"  FAC request failed ({e}); skipping this batch"); return []
    if r.status_code == 429:
        print("  FAC rate limit hit (set FAC_API_KEY for a full pull); using what we have"); return None
    if r.status_code != 200:
        print(f"  FAC HTTP {r.status_code}: {r.text[:120]}"); return []
    C.snapshot("fac", snap_tag, r.content, url=FAC, params=f"in.({len(names)} names)",
               http_status=200, ext="json")
    return r.json()


# Confirmed from api.fac.gov during the build. DEMO_KEY is throttled to ~10 requests per multi-hour
# window, so the largest primes were verified individually rather than in a single bulk pull. Each
# carries its EIN so anyone can re-confirm the exact entity on the Clearinghouse; a keyed re-run of
# this script (FAC_API_KEY) refreshes and extends the set, overriding anything here.
VERIFIED_SEED = {
    "HELEN KELLER INTERNATIONAL":
        {"ein": "135562162", "year": "2025", "report_id": "2025-06-GSAFAC-0000406078"},
    "RESEARCH TRIANGLE INSTITUTE":
        {"ein": "560686338", "year": "2022", "report_id": ""},
    "WINROCK INTERNATIONAL INSTITUTE FOR AGRICULTURAL DEVELOPMENT":
        {"ein": "710603560", "year": "2025", "report_id": ""},
}


def fac_entry(auditee, ein, year, report_id, expended=0.0):
    rid = report_id or ""
    return {"auditee": auditee, "ein": ein, "year": year, "expended": expended, "report_id": rid,
            "summary": f"https://app.fac.gov/dissemination/summary/{rid}" if rid else "",
            "pdf": f"https://app.fac.gov/dissemination/report/pdf/{rid}" if rid else ""}


def main():
    import csv
    det = list(csv.DictReader(open(C.PROCESSED / "us_project_detail.csv")))
    obl = {}
    for d in det:
        rec = d["recipient"]
        if rec and "redact" not in rec.lower():
            obl[rec] = obl.get(rec, 0) + float(d["obligated_usd"] or 0)
    primes = [n for n, _ in sorted(obl.items(), key=lambda kv: -kv[1])][:TOP_N]

    # ---- FAC Single Audits (batched; exact-normalised match only) ----
    var_to_prime = {}
    allvars = []
    for p in primes:
        for v in variants(p):
            var_to_prime.setdefault(v, p)
            allvars.append(v)
    allvars = sorted(set(allvars))

    import glob
    rows_all = []
    BATCH = 40
    for i in range(0, len(allvars), BATCH):     # best-effort live pull (also writes fresh snapshots)
        rows = fac_query(allvars[i:i + BATCH], f"single_audit_{i//BATCH}")
        if rows is None:                        # rate-limited; fall back to the snapshot record
            print("  live pull throttled; building from snapshots"); break
        rows_all += rows or []
        time.sleep(1.2)
    # Fold in every snapshot we have ever taken: the immutable record makes the build reproducible
    # even when the API is throttled/offline, and lets a later keyed run accumulate more.
    for f in sorted(glob.glob(str(C.ROOT / "data" / "raw" / "fac" / "single_audit_*.json"))):
        try:
            rows_all += json.load(open(f))
        except Exception:
            pass

    fac_by_prime = {}            # prime name -> latest Single Audit
    for row in rows_all:
        fac_norm = norm(row.get("auditee_name", ""))
        # safe match: a prime whose normalised name EXACTLY equals this auditee (EIN shown to verify)
        for p in primes:
            if norm(p) == fac_norm:
                cur = fac_by_prime.get(p)
                if not cur or (row.get("audit_year", "") > cur.get("year", "")):
                    fac_by_prime[p] = fac_entry(
                        row.get("auditee_name", ""), row.get("auditee_ein", ""),
                        row.get("audit_year", ""), row.get("report_id", ""),
                        float(row.get("total_amount_expended") or 0))
                break

    # merge the verified seed for any top prime not present in live results or snapshots
    for sname, s in VERIFIED_SEED.items():
        sn = norm(sname)
        for p in primes:
            if norm(p) == sn and p not in fac_by_prime:
                fac_by_prime[p] = fac_entry(sname, s["ein"], s["year"], s["report_id"])
                break

    # ---- our archived USAID OIG audits, matched to the org they name ----
    # Match against the REAL org names in the data (primes + sub-recipients) so the key lines up
    # with the org entity the search index will build.
    real_orgs = set(obl)
    for x in csv.DictReader(open(C.PROCESSED / "us_subawards.csv")):
        if x["sub_recipient"]:
            real_orgs.add(x["sub_recipient"])
    oig_list = json.loads((US / "audits.js").read_text().split("=", 1)[1].rstrip().rstrip(";"))["list"]
    OIG_RULES = [  # regex an org NAME must match for this audit to attach to it
        ("NSET-2022", re.compile(r"earthquake technology|\bNSET\b", re.I)),
        ("Hariyo-Ban", re.compile(r"world wildlife|\bWWF\b", re.I)),
    ]
    audit_by_report = {a["report"]: a for a in oig_list}
    oig_by_norm = {}
    for report, rx in OIG_RULES:
        a = audit_by_report.get(report)
        if not a:
            continue
        for orgname in real_orgs:
            if rx.search(orgname):
                lst = oig_by_norm.setdefault(norm(orgname), [])
                if not any(e["report"] == a["report"] for e in lst):   # one entry per audit per org
                    lst.append({
                        "report": a["report"], "what": a.get("what", ""),
                        "questioned": a.get("questioned", 0), "verdict": a.get("verdict", ""),
                        "url": a.get("node_url", "")})

    # ---- assemble, keyed by the normalised name (== org id used by the search index) ----
    out = {}
    for p in primes:
        k = norm(p)
        if p in fac_by_prime or k in oig_by_norm:
            out[k] = {"name": p}
            if p in fac_by_prime:
                out[k]["fac"] = fac_by_prime[p]
            if k in oig_by_norm:
                out[k]["oig"] = oig_by_norm[k]
    # OIG matches whose org was not in the top-N prime list (e.g. a sub-recipient) still ship
    for k, v in oig_by_norm.items():
        out.setdefault(k, {"name": v[0]["what"]})["oig"] = v

    path = C.PROCESSED / "org_audits.json"
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(f"wrote {path.relative_to(C.ROOT)}: {sum('fac' in v for v in out.values())} confirmed Single Audits, "
          f"{sum('oig' in v for v in out.values())} OIG-linked orgs (of top {len(primes)} primes)")
    for k, v in list(out.items())[:8]:
        f = v.get("fac")
        print(f"  {v['name'][:34]:34} | FAC: {f['year']+' $'+format(round(f['expended']),',')+' EIN '+f['ein'] if f else '-'}"
              f" | OIG: {len(v.get('oig', []))}")


if __name__ == "__main__":
    main()
