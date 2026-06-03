#!/usr/bin/env python3
"""
11_fetch_wb_projects.py — World Bank Projects (commitments/approvals) for Nepal.

Fetches all Nepal projects from the WB search API (~280 projects total).
Each project is one commitment row, with:
  - flow_stage = 'commitment'
  - amount_usd from totalamt (fallback: idacommamt + grantamt)
  - instrument: grantamt > 0 -> 'grant'
                else idacommamt > 0 -> 'concessional_loan'
                else -> 'other'
  - year from boardapprovaldate (first 4 chars), fallback approvalfy
  - donor_name = "World Bank (IDA/IBRD)", donor_iati_id = "44000"
  - side = 'donor', is_multilateral_outflow = True, counts_in_headline = False

Amounts in the API are already absolute USD (not millions).
Projects with no usable year or zero amount are included with status MISSING/REPORTED
as appropriate so the project count is accurate.

Self-check printed at end: project count and total commitment by year.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C

SOURCE = "wb_projects"
BASE_URL = "https://search.worldbank.org/api/v3/projects"
PAGE_SIZE = 500   # API supports up to 500
DONOR_NAME = "World Bank (IDA/IBRD)"
DONOR_IATI_ID = "44000"


def fetch_all_projects(session) -> tuple[list[dict], bytes]:
    """
    Paginate through all Nepal projects. Returns (project_list, raw_bytes_of_all_pages).
    Snapshots each page individually; concatenates raw JSON for the manifest.
    """
    projects: dict[str, dict] = {}
    offset = 0
    all_raw_parts = []
    page_num = 0

    while True:
        params = {
            "format": "json",
            "countrycode_exact": "NP",
            "rows": PAGE_SIZE,
            "os": offset,
        }
        url = BASE_URL + (
            f"?format=json&countrycode_exact=NP&rows={PAGE_SIZE}&os={offset}"
        )
        r = C.get(session, BASE_URL, params=params, timeout=60)

        page_num += 1
        raw = r.content
        all_raw_parts.append(raw)

        C.snapshot(
            SOURCE,
            f"projects_NP_page{page_num:02d}_os{offset}",
            raw,
            url=url,
            params=str(params),
            http_status=r.status_code,
            ext="json",
        )

        if r.status_code != 200:
            print(f"  WARNING: page {page_num} (os={offset}) returned HTTP {r.status_code}")
            break

        payload = r.json()
        total = int(payload.get("total", 0))
        page_projects = payload.get("projects", {})

        if not isinstance(page_projects, dict):
            print(f"  WARNING: 'projects' is not a dict on page {page_num}")
            break

        projects.update(page_projects)
        print(f"  page {page_num}: os={offset}, got {len(page_projects)} projects "
              f"(cumulative {len(projects)}/{total})")

        offset += len(page_projects)
        if offset >= total or len(page_projects) == 0:
            break

    # Concatenate all raw pages into one bytes blob for a master snapshot
    separator = b"\n---PAGE_BREAK---\n"
    combined = separator.join(all_raw_parts)
    return list(projects.values()), combined


def parse_amount(val) -> float | None:
    """Parse an amount field (string or number or None) to float, None if unparseable/zero."""
    if val is None:
        return None
    try:
        f = float(str(val).strip())
        return f if f != 0.0 else None
    except (ValueError, TypeError):
        return None


def extract_year(project: dict) -> int | None:
    """Extract approval year from boardapprovaldate or approvalfy."""
    bad = project.get("boardapprovaldate", "")
    if bad and len(str(bad)) >= 4:
        try:
            return int(str(bad)[:4])
        except ValueError:
            pass
    afy = project.get("approvalfy", "")
    if afy:
        try:
            return int(str(afy).strip())
        except ValueError:
            pass
    return None


def extract_sector(project: dict) -> str:
    """Pull a human-readable sector string from major_sector_name or sectorcode."""
    msn = project.get("major_sector_name", "")
    if msn:
        # Take the first named sector (can be a comma-separated list)
        return str(msn).split(",")[0].strip()
    sc = project.get("sectorcode", "")
    if sc:
        return str(sc).split(",")[0].strip()
    return ""


def classify_instrument(totalamt: float | None, idacommamt: float | None,
                         grantamt: float | None) -> str:
    """Determine instrument type from amount fields."""
    if grantamt and grantamt > 0:
        return "grant"
    if idacommamt and idacommamt > 0:
        return "concessional_loan"
    return "other"


def build_rows(projects: list[dict], retrieved: str) -> list[dict]:
    rows = []
    skipped_no_id = 0

    for p in projects:
        pid = p.get("id") or p.get("proj_id", "")
        if not pid:
            skipped_no_id += 1
            continue

        project_url = f"https://projects.worldbank.org/en/projects-operations/project-detail/{pid}"

        # Parse amounts — all already absolute USD per WB API docs
        totalamt = parse_amount(p.get("totalamt"))
        idacommamt = parse_amount(p.get("idacommamt"))
        grantamt = parse_amount(p.get("grantamt"))

        # Determine the canonical commitment amount
        if totalamt is not None and totalamt > 0:
            amount_usd = totalamt
            amount_note = "totalamt"
        elif idacommamt is not None and grantamt is not None:
            # Fallback: sum IDA commitment + grant
            amount_usd = (idacommamt or 0.0) + (grantamt or 0.0)
            amount_note = "idacommamt+grantamt"
        elif idacommamt is not None:
            amount_usd = idacommamt
            amount_note = "idacommamt"
        elif grantamt is not None:
            amount_usd = grantamt
            amount_note = "grantamt"
        else:
            # No usable amount — record the project but mark MISSING
            amount_usd = ""
            amount_note = "no_amount"

        instrument = classify_instrument(totalamt, idacommamt, grantamt)
        year = extract_year(p)
        sector_str = extract_sector(p)
        project_name = p.get("project_name", "")

        # Status: REPORTED if we have both year and amount, MISSING otherwise
        if amount_usd == "":
            row_status = "MISSING"
            row_confidence = "low"
        elif year is None:
            row_status = "MISSING"
            row_confidence = "low"
        else:
            row_status = "REPORTED"
            row_confidence = "high"

        # Year fallback for MISSING rows — use 0 as sentinel (non-empty required)
        row_year = year if year is not None else 0

        notes_parts = [
            f"project: {project_name}" if project_name else "",
            f"amount_from={amount_note}",
        ]
        lpc = p.get("lendprojectcost")
        if lpc:
            notes_parts.append(f"lendprojectcost={lpc}")
        notes = "; ".join(x for x in notes_parts if x)

        rows.append(C.new_row(
            side="donor",
            source=SOURCE,
            source_record_id=pid,
            donor_name=DONOR_NAME,
            donor_iati_id=DONOR_IATI_ID,
            sector=sector_str,
            sector_raw=project_name,
            flow_stage="commitment",
            instrument=instrument,
            amount_usd=amount_usd,
            amount_original=amount_usd,
            currency_original="USD",
            price_base="current",
            year=row_year,
            fiscal_basis="calendar",
            status=row_status,
            confidence=row_confidence,
            is_multilateral_outflow=True,
            counts_in_headline=False,
            source_url=project_url,
            retrieved_at=retrieved,
            notes=notes,
        ))

    if skipped_no_id:
        print(f"  WARNING: {skipped_no_id} projects skipped (no id)")

    return rows


def self_check(rows: list[dict]) -> None:
    """Print project count and total commitment by year (for REPORTED rows only)."""
    from collections import defaultdict

    by_year: dict[int, list[float]] = defaultdict(list)
    missing_amt = 0
    missing_year = 0

    for r in rows:
        if r["status"] == "MISSING":
            if r["amount_usd"] == "":
                missing_amt += 1
            else:
                missing_year += 1
            continue
        y = int(r["year"])
        amt = float(r["amount_usd"])
        by_year[y].append(amt)

    print(f"\n{SOURCE}: {len(rows)} total project rows")
    print(f"  REPORTED={sum(1 for r in rows if r['status'] == 'REPORTED')}, "
          f"MISSING_amt={missing_amt}, MISSING_year={missing_year}")
    print(f"  {'Year':>6}  {'Projects':>9}  {'Total commitment (USD)':>22}")
    for y in sorted(by_year):
        n = len(by_year[y])
        total = sum(by_year[y])
        print(f"  {y:>6}  {n:>9}  {total:>22,.0f}")
    grand_total = sum(v for amts in by_year.values() for v in amts)
    print(f"  {'ALL':>6}  {sum(len(v) for v in by_year.values()):>9}  {grand_total:>22,.0f}")


def main() -> None:
    session = C.make_session()
    retrieved = C.utc_now()

    print(f"Fetching WB projects for Nepal from {BASE_URL} ...")
    projects, combined_raw = fetch_all_projects(session)
    print(f"  Total projects retrieved: {len(projects)}")

    # Save a combined master snapshot for easy inspection
    C.snapshot(
        SOURCE,
        "projects_NP_ALL",
        combined_raw,
        url=BASE_URL + "?format=json&countrycode_exact=NP&rows=500",
        params="all pages combined",
        http_status=200,
        ext="json",
    )

    rows = build_rows(projects, retrieved)
    C.write_interim(SOURCE, rows)
    self_check(rows)


if __name__ == "__main__":
    main()
