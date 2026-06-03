#!/usr/bin/env python3
"""
15_fetch_us.py — US foreign assistance to Nepal from ForeignAssistance.gov.

Source: andrewheiss/foreign-assistance-data community mirror of the ForeignAssistance.gov
"complete" dataset, snapshot as of 2025-02-03 (Dropbox ZIP).
ZIP URL: https://www.dropbox.com/scl/fi/btzeaaq84wdpahb7c033g/data-raw_2025-02-03.zip?rlkey=atqpr633ayy4ya9p428vi6lon&dl=1

The complete CSV has ~3.5 GB uncompressed; we stream it and keep only NPL rows.
Amounts are in current USD (absolute, not millions). Fiscal year = US FY (Oct-Sep).

Transaction type 2 = Obligations -> flow_stage=commitment
Transaction type 3 = Disbursements -> flow_stage=disbursement

Instrument mapping (Aid Type Group Name):
  Budget support        -> grant (budget/GBS; US does not give loans)
  Core contributions    -> grant (contributions to multilateral funds)
  Project-Type          -> grant
  Technical Assistance  -> grant
  Administrative Costs  -> other (admin overhead; excluded from headline amounts)

counts_in_headline=False: this is donor-side detail; OECD DAC2A already captures the headline.
is_multilateral_outflow=False: US bilateral flows (pass-throughs to multilaterals kept as grant).

Self-check: disbursements 2024 ~$151M, 2023 ~$147M; 2015/2016 spike = earthquake reconstruction.
"""
import csv
import io
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C

SOURCE = "us_fa"
ZIP_URL = (
    "https://www.dropbox.com/scl/fi/btzeaaq84wdpahb7c033g/"
    "data-raw_2025-02-03.zip?rlkey=atqpr633ayy4ya9p428vi6lon&dl=1"
)
RAW_CSV_NAME = "data-raw/us_foreign_aid_complete.csv"
SOURCE_URL = "https://foreignassistance.gov/data"
MIRROR_URL = "https://github.com/andrewheiss/foreign-assistance-data"

# flow_stage mapping
FLOW_STAGE_MAP = {
    "2": "commitment",    # Obligations
    "3": "disbursement",  # Disbursements
}

# Instrument mapping from Aid Type Group
AID_TYPE_TO_INSTRUMENT = {
    "Budget support":      "grant",
    "Core contributions":  "grant",
    "Project-Type":        "grant",
    "Technical Assistance": "grant",
    "Administrative Costs": "other",
}


def load_or_download_zip() -> Path:
    """Return path to the raw zip, downloading if necessary."""
    zip_path = C.RAW / SOURCE / "data-raw_2025-02-03.zip"
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    if zip_path.exists() and zip_path.stat().st_size > 100_000_000:
        print(f"  Using cached zip: {zip_path}")
        return zip_path

    print(f"  Downloading ~110 MB zip from Dropbox …")
    s = C.make_session()
    r = C.get(s, ZIP_URL, timeout=600, retries=3)
    if r.status_code != 200:
        raise SystemExit(
            f"Failed to download zip: HTTP {r.status_code} from {ZIP_URL}"
        )
    zip_path.write_bytes(r.content)
    print(f"  Saved {len(r.content):,} bytes to {zip_path}")
    return zip_path


def stream_nepal_rows(zip_path: Path) -> tuple[list[dict], bytes]:
    """
    Stream the large complete CSV from the zip, filter to NPL,
    return (rows_as_dicts, nepal_csv_bytes_for_snapshot).
    We keep ALL fiscal years (1952+) for completeness but flag older years.
    """
    nepal_rows_raw = []
    header_line = None

    with zipfile.ZipFile(zip_path) as zf:
        with zf.open(RAW_CSV_NAME) as fh:
            for raw_line in fh:
                line = raw_line.decode("utf-8", errors="replace")
                if header_line is None:
                    header_line = line
                    continue
                # Fast pre-filter: country code column (col 1) = NPL
                if ",NPL," not in line:
                    continue
                nepal_rows_raw.append(line)

    # Build a clean Nepal-only CSV bytes for snapshot
    nepal_csv_bytes = (header_line + "".join(nepal_rows_raw)).encode("utf-8")

    # Parse into dicts
    reader = csv.DictReader(io.StringIO(header_line + "".join(nepal_rows_raw)))
    dicts = list(reader)
    print(f"  Nepal rows extracted: {len(dicts):,}")
    return dicts, nepal_csv_bytes


def parse_amount(s: str) -> float | None:
    """Parse Current Dollar Amount; return None if blank or non-numeric."""
    s = s.strip()
    if s in ("", ".", "NULL"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def parse_fy(s: str) -> int | None:
    """Parse Fiscal Year — handle '1976tq' transition-quarter artifact."""
    s = s.strip()
    if s.isdigit():
        return int(s)
    # '1976tq' = transition quarter between FY1976 and FY1977; treat as FY1976
    if s.startswith("1976"):
        return 1976
    return None


def make_source_record_id(row: dict, row_idx: int) -> str:
    """
    Unique key per transaction row.
    The raw data has many line items per activity/FY/txtype (sector × partner
    breakdowns), so we include a zero-padded row index as a tiebreaker to
    guarantee uniqueness within each source rebuild.
    """
    return (
        f"{row['Submission ID']}|{row['Activity ID']}|"
        f"{row['Transaction Type ID']}|{row['Fiscal Year']}|{row_idx:06d}"
    )


def build_notes(row: dict) -> str:
    parts = [
        f"agency={row['Managing Agency Acronym']}",
        f"intl_sector={row['International Sector Name']}",
        f"us_sector={row['US Sector Name']}",
        f"aid_type={row['Aid Type Group Name']}",
        f"funding_account={row['Funding Account Name'][:60]}",
    ]
    if row.get("Activity Name", "").strip() not in ("", "NULL"):
        parts.append(f"activity={row['Activity Name'][:80]}")
    return "; ".join(parts)


def main():
    zip_path = load_or_download_zip()

    # Snapshot the zip itself (by reference; too large to re-snapshot bytes, record manifest)
    C.snapshot(
        SOURCE,
        "data-raw_2025-02-03_zip_metadata",
        f"zip_path={zip_path}\nsize={zip_path.stat().st_size}\nurl={ZIP_URL}".encode(),
        url=ZIP_URL,
        params="complete; all countries; snapshot 2025-02-03",
        http_status=200,
        ext="txt",
    )

    raw_dicts, nepal_csv_bytes = stream_nepal_rows(zip_path)

    # Snapshot the Nepal-filtered CSV
    C.snapshot(
        SOURCE,
        "nepal_filtered",
        nepal_csv_bytes,
        url=SOURCE_URL,
        params="country=Nepal(NPL); from data-raw_2025-02-03.zip",
        http_status=200,
        ext="csv",
    )

    retrieved = C.utc_now()
    rows = []
    skipped_fy = 0
    skipped_amt = 0
    skipped_txtype = 0

    for row_idx, raw in enumerate(raw_dicts):
        fy = parse_fy(raw["Fiscal Year"])
        if fy is None:
            skipped_fy += 1
            continue

        tx_id = raw["Transaction Type ID"].strip()
        flow_stage = FLOW_STAGE_MAP.get(tx_id)
        if flow_stage is None:
            skipped_txtype += 1
            continue

        amt = parse_amount(raw["Current Dollar Amount"])
        if amt is None:
            skipped_amt += 1
            continue

        aid_type = raw["Aid Type Group Name"].strip()
        instrument = AID_TYPE_TO_INSTRUMENT.get(aid_type, "other")

        record_id = make_source_record_id(raw, row_idx)

        rows.append(C.new_row(
            side="donor",
            source=SOURCE,
            source_record_id=record_id,
            donor_name="United States",
            donor_iati_id="US-GOV",
            recipient="NPL",
            sector=raw["International Category Name"].strip(),
            sector_raw=(
                f"{raw['International Category Name']} / "
                f"{raw['International Sector Name']} / "
                f"{raw['US Sector Name']}"
            ),
            flow_stage=flow_stage,
            instrument=instrument,
            amount_usd=amt,
            amount_original=amt,
            currency_original="USD",
            price_base="current",
            year=fy,
            fiscal_basis="donor_fy",
            status="REPORTED",
            confidence="med",
            is_multilateral_outflow=False,
            counts_in_headline=False,
            source_url=SOURCE_URL,
            retrieved_at=retrieved,
            notes=build_notes(raw),
        ))

    C.write_interim(SOURCE, rows)

    print(f"\n{SOURCE}: {len(rows):,} rows written")
    print(f"  Skipped: {skipped_fy} bad-FY, {skipped_amt} null-amount, {skipped_txtype} unknown-txtype")

    # Self-check: disbursements by year (2015+)
    disb_by_year: dict[int, float] = defaultdict(float)
    oblig_by_year: dict[int, float] = defaultdict(float)
    for r in rows:
        y = int(r["year"])
        if y < 2015:
            continue
        if r["flow_stage"] == "disbursement":
            disb_by_year[y] += float(r["amount_usd"])
        elif r["flow_stage"] == "commitment":
            oblig_by_year[y] += float(r["amount_usd"])

    print("\n  Self-check: US disbursements to Nepal (FY2015+, current USD)")
    print(f"  {'FY':<6} {'Disbursements':>16} {'Obligations':>16}")
    print(f"  {'-'*6} {'-'*16} {'-'*16}")
    for y in sorted(disb_by_year):
        d = disb_by_year[y]
        o = oblig_by_year.get(y, 0.0)
        flag = "  <- 2024->2025 drop expected" if y == 2024 else ""
        print(f"  FY{y}  {d:>16,.0f}  {o:>16,.0f}{flag}")

    print(
        "\n  NOTE: Data through FY2024 (Feb 2025 snapshot). USAID restructured into State"
        " in 2025; FY2025 flows will be under State Department. No FY2025 data in snapshot."
    )


if __name__ == "__main__":
    main()
