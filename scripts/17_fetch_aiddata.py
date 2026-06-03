#!/usr/bin/env python3
"""
17_fetch_aiddata.py — AidData Global Chinese Development Finance Dataset v3.0
                      (the China non-DAC fill for Nepal).

Source: https://www.aiddata.org/data/aiddatas-global-chinese-development-finance-dataset-version-3-0
Bulk download (ZIP, ~28 MB): https://docs.aiddata.org/ad4/datasets/AidDatas_Global_Chinese_Development_Finance_Dataset_Version_3_0.zip

Dataset covers 20,985 projects globally, commitment years 2000-2021.
We filter to Nepal (Recipient ISO-3 == 'NPL') only.

Mapping decisions:
  - flow_stage = 'commitment' (AidData tracks commitments)
  - donor_name = 'China'  (all entries are Chinese official-sector finance)
  - year = Commitment Year
  - amount_usd = Amount (Nominal USD)   [current USD, preferred]
  - amount_usd_constant = Amount (Constant USD 2021) if nominal is missing
  - price_base_year = 2021 if only constant available
  - instrument mapping:
      Grant / Free-standing technical assistance / Scholarships -> 'grant'
      Loan, Flow Class ODA-like -> 'concessional_loan'
      Loan, Flow Class OOF-like -> 'oof'
      Debt rescheduling / Vague TBD / other -> 'other'
  - counts_in_headline = False  (China is not a DAC donor; non-DAC fill only)
  - confidence = 'med'
  - Rows with 'Recommended For Aggregates' == 'No' are emitted with a note
    (they are child/linked records or otherwise flagged; still project texture)
  - Rows with no amount (null nominal + null constant) get status='MISSING'

Coverage note: dataset ends at commitment year 2021.
"""
import io
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C

SOURCE = "aiddata_gcdf"
ZIP_URL = (
    "https://docs.aiddata.org/ad4/datasets/AidDatas_Global_Chinese_Development_Finance_Dataset_Version_3_0.zip"
)
DATASET_PAGE = (
    "https://www.aiddata.org/data/aiddatas-global-chinese-development-finance-dataset-version-3-0"
)
XLSX_MEMBER = (
    "AidDatas_Global_Chinese_Development_Finance_Dataset_Version_3_0/"
    "AidDatasGlobalChineseDevelopmentFinanceDataset_v3.0.xlsx"
)


def _map_instrument(flow_type: str, flow_class: str) -> str:
    """Map AidData flow type + class to canonical instrument enum value."""
    ft = (flow_type or "").strip()
    fc = (flow_class or "").strip()
    if ft in (
        "Grant",
        "Free-standing technical assistance",
        "Scholarships/training in the donor country",
    ):
        return "grant"
    if ft == "Loan":
        if "OOF" in fc:
            return "oof"
        return "concessional_loan"  # ODA-like loans + vague
    return "other"  # Debt rescheduling, Vague TBD, etc.


def main():
    s = C.make_session()

    # -----------------------------------------------------------------------
    # Download bulk ZIP
    # -----------------------------------------------------------------------
    print(f"{SOURCE}: downloading bulk ZIP (~28 MB)…")
    r = C.get(s, ZIP_URL, timeout=300)
    print(f"  HTTP {r.status_code}, {len(r.content):,} bytes")

    C.snapshot(
        SOURCE,
        "AidDatas_GCDF_v3.0",
        r.content,
        url=ZIP_URL,
        params="all_recipients; will filter to NPL",
        http_status=r.status_code,
        ext="zip",
    )

    if r.status_code != 200 or not r.content:
        print(f"ERROR: download failed (HTTP {r.status_code})")
        C.write_interim(SOURCE, [])
        return

    # -----------------------------------------------------------------------
    # Open ZIP and extract Excel
    # -----------------------------------------------------------------------
    try:
        z = zipfile.ZipFile(io.BytesIO(r.content))
    except zipfile.BadZipFile as e:
        print(f"ERROR: bad ZIP: {e}")
        C.write_interim(SOURCE, [])
        return

    if XLSX_MEMBER not in z.namelist():
        print(f"ERROR: expected member not found: {XLSX_MEMBER}")
        print("Available:", z.namelist())
        C.write_interim(SOURCE, [])
        return

    xlsx_bytes = z.read(XLSX_MEMBER)
    # Also snapshot the extracted Excel so it can be re-read without re-downloading
    C.snapshot(
        SOURCE,
        "AidDatasGlobalChineseDevelopmentFinanceDataset_v3.0",
        xlsx_bytes,
        url=ZIP_URL,
        params="extracted from ZIP",
        http_status=200,
        ext="xlsx",
    )

    # -----------------------------------------------------------------------
    # Parse Excel — GCDF_3.0 sheet
    # -----------------------------------------------------------------------
    import openpyxl  # local import so failure is clear

    print(f"{SOURCE}: opening Excel workbook…")
    wb = openpyxl.load_workbook(
        io.BytesIO(xlsx_bytes), read_only=True, data_only=True
    )
    ws = wb["GCDF_3.0"]
    rows_iter = ws.iter_rows(values_only=True)
    header = next(rows_iter)
    col_idx = {h: i for i, h in enumerate(header) if h is not None}

    # Column index helpers
    def _get(row, col_name, default=None):
        idx = col_idx.get(col_name)
        if idx is None:
            return default
        v = row[idx]
        return default if v is None else v

    retrieved = C.utc_now()
    rows_out = []
    n_total = 0
    n_nepal = 0

    for row in rows_iter:
        n_total += 1
        if _get(row, "Recipient ISO-3") != "NPL":
            continue
        n_nepal += 1

        record_id = str(_get(row, "AidData Record ID", ""))
        commit_year = _get(row, "Commitment Year")
        if commit_year is None:
            # Cannot assign a year — still emit with MISSING status
            commit_year = 0  # placeholder; note will document

        title = _get(row, "Title", "")
        flow_type = _get(row, "Flow Type", "")
        flow_class = _get(row, "Flow Class", "")
        sector_name = _get(row, "Sector Name", "")
        rec_for_agg = _get(row, "Recommended For Aggregates", "")
        proj_status = _get(row, "Status", "")
        source_urls = _get(row, "Source URLs", "")
        orig_amt = _get(row, "Amount (Original Currency)")
        orig_curr = _get(row, "Original Currency", "")
        nom_usd = _get(row, "Amount (Nominal USD)")
        const_usd = _get(row, "Amount (Constant USD 2021)")

        instrument = _map_instrument(flow_type, flow_class)

        # Amount logic: prefer nominal (current) USD; fall back to constant 2021
        if nom_usd is not None:
            amount_usd = float(nom_usd)
            amount_usd_constant = float(const_usd) if const_usd is not None else ""
            price_base = "current"
            price_base_year = ""
            row_status = "REPORTED"
        elif const_usd is not None:
            # Only constant amount available — flag as ESTIMATED (price base 2021)
            amount_usd = float(const_usd)
            amount_usd_constant = float(const_usd)
            price_base = "constant"
            price_base_year = "2021"
            row_status = "ESTIMATED"
        else:
            # No amount at all — emit row so project count is correct
            amount_usd = ""
            amount_usd_constant = ""
            price_base = ""
            price_base_year = ""
            row_status = "MISSING"

        notes_parts = []
        if rec_for_agg == "No":
            notes_parts.append("Recommended For Aggregates=No (child/linked record)")
        if proj_status:
            notes_parts.append(f"project_status={proj_status}")
        if flow_class:
            notes_parts.append(f"flow_class={flow_class}")
        if flow_type and flow_type != instrument:
            notes_parts.append(f"flow_type_raw={flow_type!r}")
        notes_parts.append("coverage_end=2021")
        note = "; ".join(notes_parts)

        # Use dataset page as source_url (stable); individual source URLs go in notes
        src_url = DATASET_PAGE

        rows_out.append(
            C.new_row(
                side="donor",
                source=SOURCE,
                source_record_id=f"GCDF3|{record_id}",
                donor_name="China",
                flow_stage="commitment",
                instrument=instrument,
                amount_usd=amount_usd,
                amount_usd_constant=amount_usd_constant,
                price_base_year=price_base_year,
                amount_original=float(orig_amt) if orig_amt is not None else "",
                currency_original=orig_curr if orig_curr else "",
                price_base=price_base if price_base else "",
                year=int(commit_year),
                fiscal_basis="calendar",
                status=row_status,
                confidence="med",
                is_multilateral_outflow=False,
                counts_in_headline=False,
                sector_raw=sector_name,
                source_url=src_url,
                retrieved_at=retrieved,
                notes=note + (f"; title={title[:120]}" if title else ""),
            )
        )

    wb.close()

    C.write_interim(SOURCE, rows_out)

    # -----------------------------------------------------------------------
    # Self-check: Nepal project count and committed totals by year
    # -----------------------------------------------------------------------
    from collections import defaultdict

    year_nominal = defaultdict(float)
    year_count = defaultdict(int)
    for rr in rows_out:
        y = rr["year"]
        year_count[y] += 1
        if rr["amount_usd"] not in ("", None):
            year_nominal[y] += float(rr["amount_usd"])

    print(
        f"\n{SOURCE}: {n_total:,} global rows scanned; "
        f"{n_nepal} Nepal rows; {len(rows_out)} emitted"
    )
    print(
        f"  Rows with amount (nominal USD): "
        f"{sum(1 for r in rows_out if r['status'] == 'REPORTED')}"
    )
    print(
        f"  Rows with constant-only amount (ESTIMATED): "
        f"{sum(1 for r in rows_out if r['status'] == 'ESTIMATED')}"
    )
    print(
        f"  Rows with no amount (MISSING):  "
        f"{sum(1 for r in rows_out if r['status'] == 'MISSING')}"
    )
    print()
    print("  Year | Projects | Committed (nominal USD)")
    for y in sorted(year_count):
        total = year_nominal.get(y, 0.0)
        print(f"  {y}: {year_count[y]:4d} projects  ${total:>18,.0f}")

    grand_total = sum(year_nominal.values())
    print(f"\n  Grand total nominal USD committed to Nepal: ${grand_total:,.0f}")
    print(f"\n{SOURCE}: interim CSV written.")


if __name__ == "__main__":
    main()
