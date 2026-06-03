#!/usr/bin/env python3
"""
14_fetch_adb_iati.py — ADB IATI publication: development finance to Nepal.

Reporting-org: XM-DAC-46004 (Asian Development Bank).
Source XML: https://www.adb.org/iati/iati-activities-np.xml (~7 MB)

Rows:
  side=donor, is_multilateral_outflow=True, counts_in_headline=False.
  flow_stage: transaction-type 2 = commitment, 3 = disbursement.
  instrument: inferred from default-finance-type or aid-type when available.
  Only transactions from 2015 onward are emitted.

NOTE on every row: "ADB IATI excludes Technical Assistance Special Fund (undercount)".

Self-check: activity count + commitment/disbursement totals by year printed at end.
"""
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C

SOURCE = "adb_iati"
XML_URL = "https://www.adb.org/iati/iati-activities-np.xml"

# IATI transaction-type codes we care about
TX_COMMITMENT = "2"    # Outgoing Commitment
TX_DISBURSEMENT = "3"  # Disbursement

# IATI finance-type codes -> instrument
# https://iatistandard.org/en/iati-standard/203/codelists/financetype/
LOAN_CODES = {
    "410",  # Aid Loan excl. debt reorganisation
    "411",  # Investment-related loan to developing countries
    "412",  # Loan in a joint venture with the recipient
    "413",  # Loan to national private investor
    "414",  # Loan to foreign private investor
    "421",  # Standard loan
    "422",  # Reimbursable grant
    "423",  # Bonds
    "424",  # Asset-backed securities
    "425",  # Other debt securities
    "431",  # Subordinated loan
    "432",  # Preferred equity
    "433",  # Other hybrid instruments
    "451",  # Non-banks guaranteed export credits
    "452",  # Non-banks non-guaranteed portions of guaranteed export credits
    "453",  # Bank export credits
    "510",  # Common equity
    "610",  # Debt forgiveness
    "620",  # Debt conversion
    "630",  # Debt rescheduling
    "710",  # Foreign direct investment, new capital outflow
    "711",  # Other foreign direct investment, including reinvested earnings
    "712",  # Foreign direct investment, new capital acquisition
    "810",  # Bank bonds
    "910",  # Other securities/claims
}
GRANT_CODES = {
    "110",  # Standard grant
    "111",  # Subsidies to national private investors
    "210",  # Interest subsidy
    "211",  # Interest subsidy to national private exporters
    "310",  # Capital subscription on deposit basis
    "311",  # Capital subscription on encashment basis
}


def infer_instrument(finance_type_code: str, aid_type_code: str) -> str:
    """Map IATI finance-type (preferred) or aid-type to instrument enum."""
    ft = (finance_type_code or "").strip()
    if ft in LOAN_CODES:
        return "concessional_loan"
    if ft in GRANT_CODES:
        return "grant"
    # Fallback: aid-type B = Budget support loans, C = project-type interventions
    # ADB mostly uses C01 (project) and B = loans; use finance-type primarily
    return ""


def elem_text(el, tag: str) -> str:
    """Return stripped text of first child with given tag, or ''."""
    child = el.find(tag)
    if child is not None and child.text:
        return child.text.strip()
    return ""


def year_from_date(date_str: str) -> int | None:
    """Extract 4-digit year from YYYY-MM-DD or YYYY/MM/DD or partial strings."""
    if not date_str:
        return None
    # take first 4 chars
    part = date_str.strip()[:4]
    try:
        y = int(part)
        if 2000 <= y <= 2035:
            return y
    except ValueError:
        pass
    return None


def main():
    s = C.make_session()
    print(f"Fetching {XML_URL} ...")
    r = C.get(s, XML_URL, timeout=300)

    # Snapshot raw bytes regardless of status
    C.snapshot(SOURCE, "iati-activities-np", r.content,
               url=XML_URL, http_status=r.status_code, ext="xml")

    if r.status_code != 200 or not r.content:
        print(f"ERROR: HTTP {r.status_code} — status=failed, 0 rows emitted")
        C.write_interim(SOURCE, [])
        return

    print(f"Downloaded {len(r.content):,} bytes (HTTP {r.status_code})")

    # Parse XML
    try:
        root = ET.fromstring(r.content)
    except ET.ParseError as e:
        print(f"XML parse error: {e} — status=failed")
        C.write_interim(SOURCE, [])
        return

    # Normalise namespace prefix if present
    # Some IATI files use xmlns="http://..." which prefixes every tag
    ns = ""
    tag = root.tag
    if tag.startswith("{"):
        ns = tag.split("}")[0] + "}"

    def t(name: str) -> str:
        return f"{ns}{name}"

    retrieved = C.utc_now()
    rows = []
    activity_count = 0
    skipped_no_np = 0
    skipped_before_2015 = 0

    # Accumulators for self-check
    check: dict = defaultdict(lambda: defaultdict(float))  # year -> flow_stage -> amount

    activities = root.findall(t("iati-activity"))
    print(f"Total <iati-activity> elements found: {len(activities)}")

    for activity in activities:
        # --- iati-identifier ---
        iati_id = elem_text(activity, t("iati-identifier"))
        if not iati_id:
            continue

        # --- recipient-country: keep only NP ---
        rc_el = activity.find(t("recipient-country"))
        if rc_el is None:
            # Try multiple recipient-country elements (some activities have several)
            # If any is NP, accept; if none found at all, skip
            rcs = activity.findall(t("recipient-country"))
            if not rcs:
                skipped_no_np += 1
                continue
            np_found = any((rc.get("code", "").upper() == "NP") for rc in rcs)
            if not np_found:
                skipped_no_np += 1
                continue
        else:
            if rc_el.get("code", "").upper() != "NP":
                skipped_no_np += 1
                continue

        # --- title ---
        title_el = activity.find(t("title"))
        if title_el is not None:
            # may contain <narrative> child
            narr = title_el.find(t("narrative"))
            if narr is not None and narr.text:
                title = narr.text.strip()
            elif title_el.text:
                title = title_el.text.strip()
            else:
                title = ""
        else:
            title = ""

        # --- sector (first one) ---
        sector_el = activity.find(t("sector"))
        sector_code = sector_el.get("code", "") if sector_el is not None else ""
        sector_vocab = sector_el.get("vocabulary", "") if sector_el is not None else ""
        sector_raw = f"{sector_vocab}:{sector_code}" if sector_code else ""

        # --- default-finance-type (activity level) ---
        dft_el = activity.find(t("default-finance-type"))
        default_finance_code = dft_el.get("code", "") if dft_el is not None else ""

        # --- default-aid-type (activity level) ---
        dat_el = activity.find(t("default-aid-type"))
        default_aid_code = dat_el.get("code", "") if dat_el is not None else ""

        # --- transactions ---
        for tx in activity.findall(t("transaction")):
            tx_type_el = tx.find(t("transaction-type"))
            if tx_type_el is None:
                continue
            tx_code = tx_type_el.get("code", "").strip()
            if tx_code not in (TX_COMMITMENT, TX_DISBURSEMENT):
                continue

            flow_stage = "commitment" if tx_code == TX_COMMITMENT else "disbursement"

            # --- value ---
            val_el = tx.find(t("value"))
            if val_el is None or val_el.text is None:
                continue
            try:
                amount_raw = float(val_el.text.strip().replace(",", ""))
            except ValueError:
                continue
            if amount_raw == 0:
                continue

            currency = val_el.get("currency", "USD").upper().strip()
            val_date = val_el.get("value-date", "")

            # --- transaction-date ---
            td_el = tx.find(t("transaction-date"))
            tx_date = td_el.get("iso-date", "") if td_el is not None else ""

            # Year: prefer transaction-date, fall back to value-date
            year = year_from_date(tx_date) or year_from_date(val_date)
            if year is None or year < 2015:
                skipped_before_2015 += 1
                continue

            # --- transaction-level finance-type overrides activity default ---
            tx_ft_el = tx.find(t("finance-type"))
            tx_finance_code = tx_ft_el.get("code", "") if tx_ft_el is not None else ""

            tx_at_el = tx.find(t("aid-type"))
            tx_aid_code = tx_at_el.get("code", "") if tx_at_el is not None else ""

            finance_code = tx_finance_code or default_finance_code
            aid_code = tx_aid_code or default_aid_code
            instrument = infer_instrument(finance_code, aid_code)

            # --- amount in USD (ADB predominantly reports in USD) ---
            if currency == "USD":
                amount_usd = amount_raw
                status = "REPORTED"
                price_base = "current"
            else:
                # ADB IATI is almost always USD; if not, flag as ESTIMATED
                # We do not have a general FX lookup here; mark MISSING for non-USD
                # so we don't fabricate
                amount_usd = ""
                status = "MISSING"
                price_base = ""
                # Still emit the row with original amount for transparency

            # Build unique source_record_id: iati-id + tx-type + date + amount
            # (IATI doesn't have stable transaction IDs in all versions)
            period_start = tx_date or val_date
            record_id = f"{iati_id}|{tx_code}|{period_start}|{amount_raw:.2f}"

            row = C.new_row(
                side="donor",
                source=SOURCE,
                source_record_id=record_id,
                dedup_key=record_id,
                donor_name="Asian Development Bank",
                donor_dac_code="5ASDB0",
                donor_iati_id="XM-DAC-46004",
                recipient="NPL",
                sector=sector_code,
                sector_raw=sector_raw,
                flow_stage=flow_stage,
                instrument=instrument,
                amount_usd=amount_usd,
                amount_original=amount_raw,
                currency_original=currency,
                price_base=price_base if amount_usd != "" else "",
                year=year,
                fiscal_basis="calendar",
                period_start=period_start,
                status=status,
                confidence="high" if status == "REPORTED" else "med",
                is_multilateral_outflow=True,
                counts_in_headline=False,
                source_url=XML_URL,
                retrieved_at=retrieved,
                notes=(
                    f"ADB IATI excludes Technical Assistance Special Fund (undercount). "
                    f"Activity: {iati_id}. Title: {title[:120]}."
                    + (f" finance-type={finance_code}" if finance_code else "")
                ),
            )
            rows.append(row)
            activity_count_key = iati_id  # for distinct count

            if isinstance(amount_usd, float):
                check[year][flow_stage] += amount_usd

    # Distinct activity count
    seen_activities = set()
    for row in rows:
        # extract iati_id from source_record_id (before first |)
        seen_activities.add(row["source_record_id"].split("|")[0])

    C.write_interim(SOURCE, rows)

    # --- Self-check printout ---
    print(f"\n{SOURCE}: {len(rows)} transaction rows from {len(seen_activities)} activities")
    print(f"  Skipped (non-NP recipient): {skipped_no_np}")
    print(f"  Skipped (before 2015 or no date): {skipped_before_2015}")
    print("\n  Year | Commitment (USD) | Disbursement (USD)")
    print("  " + "-" * 55)
    for year in sorted(check):
        c = check[year].get("commitment", 0)
        d = check[year].get("disbursement", 0)
        print(f"  {year}: {c:20,.0f} | {d:20,.0f}")
    total_c = sum(v.get("commitment", 0) for v in check.values())
    total_d = sum(v.get("disbursement", 0) for v in check.values())
    print(f"  {'TOTAL':5}: {total_c:20,.0f} | {total_d:20,.0f}")
    print(f"\nInterim CSV: data/interim/{SOURCE}_long.csv")


if __name__ == "__main__":
    main()
