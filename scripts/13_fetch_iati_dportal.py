#!/usr/bin/env python3
"""
13_fetch_iati_dportal.py — IATI activity inventory for Nepal via d-portal.org.

SOURCE = iati_dportal.  side=donor.  counts_in_headline=False.
dedup_key = the IATI identifier (field "aid").

This script fetches all IATI activities tagged with country_code=NP from the
d-portal public API (no API key required) and emits two row types per activity:
  - 'commitment'  from the activity-level commitment total
  - 'disbursement' from the activity-level spend total
Rows with zero values are skipped.

NOTE — select=stats IS BROKEN on d-portal; we use from=act.

AMOUNT: d-portal provides commitment/spend in native currency and EUR conversions
(*_eur).  There is no native USD field.  We convert from *_eur to USD using annual
average ECB EUR/USD rates stored in config/fx_rates.csv.  status='ESTIMATED' is set
on every row because this is a converted value.

YEAR: Activity-level totals aggregate across the whole project life cycle; there is
no clean single year.  We use the activity start year derived from day_start (days
since 1970-01-01) when available.  If day_start is absent, year is set to '' and
confidence='low'.  This limitation is clearly noted.

MULTILATERAL: is_multilateral_outflow=True when reporting_ref starts with a known
multilateral prefix (XM-DAC, XI-IATI, 47 for UN/WFP/UNICEF, 44 for EU, 21 for
global funds).

SELF-CHECK: distinct publisher refs and distinct IATI identifiers are printed at end.
"""
import datetime
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C

SOURCE = "iati_dportal"
BASE_URL = "http://d-portal.org/q"
PAGE_SIZE = 500

# Annual EUR->USD rates loaded from config/fx_rates.csv
# Fallback used when a year has no matching rate (uses most recent available)
_FALLBACK_EUR_USD = 1.08  # approximate 2023-2024 rate

# Known IATI reporting-org prefix patterns for multilateral agencies
# XM-DAC  = OECD DAC multilateral donors
# XI-IATI = IATI registered intergovernmental bodies
# 47-     = UN agencies (WFP=WFP, UNICEF=UNICEF, etc.)
# 44-     = EU institutions
# 21-     = Global funds (e.g. GFATM, GAVI)
_MULTI_PREFIXES = ("XM-DAC", "XI-IATI", "47-", "44-", "21-")


def is_multilateral(reporting_ref: str) -> bool:
    if not reporting_ref:
        return False
    return any(reporting_ref.upper().startswith(p.upper()) for p in _MULTI_PREFIXES)


def day_start_to_year(day_start) -> int | None:
    """Convert d-portal day_start (days since 1970-01-01) to calendar year."""
    if day_start is None:
        return None
    try:
        dt = datetime.date(1970, 1, 1) + datetime.timedelta(days=int(day_start))
        return dt.year
    except (ValueError, OverflowError):
        return None


def get_eur_usd(fx: dict, year: int | None) -> tuple[float, str]:
    """
    Return (rate, note).  Uses ECB annual average for the given year if available,
    else falls back to the closest available year.
    """
    if year is not None and (year, "EUR") in fx:
        rate = fx[(year, "EUR")]
        return rate, f"ECB EUR/USD annual avg {year} from config/fx_rates.csv"
    # Try a range of nearby years as fallback
    if year is not None:
        for delta in range(1, 5):
            for candidate in (year - delta, year + delta):
                if (candidate, "EUR") in fx:
                    r = fx[(candidate, "EUR")]
                    return r, f"ECB EUR/USD annual avg {candidate} (fallback for missing {year})"
    return _FALLBACK_EUR_USD, f"EUR/USD fallback rate {_FALLBACK_EUR_USD} (year unknown)"


def fetch_all_pages(session: C.requests.Session) -> list[dict]:
    """Paginate d-portal /q?from=act&country_code=NP until an empty page."""
    all_rows: list[dict] = []
    offset = 0
    page_num = 0
    while True:
        params = {
            "from": "act",
            "country_code": "NP",
            "form": "json",
            "limit": str(PAGE_SIZE),
            "offset": str(offset),
        }
        url = BASE_URL + "?" + "&".join(f"{k}={v}" for k, v in params.items())
        r = C.get(session, BASE_URL, params=params, timeout=120)
        http_status = r.status_code
        # Snapshot every page
        C.snapshot(
            SOURCE,
            f"page_{page_num:04d}_offset{offset}",
            r.content,
            url=url,
            params=str(params),
            http_status=http_status,
            ext="json",
        )
        if http_status != 200:
            print(f"  WARNING: HTTP {http_status} at offset={offset}; stopping pagination")
            break
        try:
            data = r.json()
        except Exception as e:
            print(f"  WARNING: JSON parse error at offset={offset}: {e}; stopping")
            break
        page_rows = data.get("rows", [])
        if not page_rows:
            # Empty page — we're done
            break
        all_rows.extend(page_rows)
        print(f"  page {page_num}: offset={offset}, fetched {len(page_rows)} rows "
              f"(cumulative {len(all_rows)})")
        if len(page_rows) < PAGE_SIZE:
            # Last partial page
            break
        offset += PAGE_SIZE
        page_num += 1
        # Be polite to d-portal
        time.sleep(0.3)
    return all_rows


def main():
    session = C.make_session()
    fx = C.load_fx()
    if not fx:
        print("WARNING: config/fx_rates.csv not found or empty; using fallback EUR/USD rates")

    print(f"Fetching IATI activities for Nepal from {BASE_URL} ...")
    raw_activities = fetch_all_pages(session)
    print(f"Total raw activities fetched: {len(raw_activities)}")

    if not raw_activities:
        print("ERROR: no activities returned; exiting with status=failed")
        C.write_interim(SOURCE, [])
        return

    # Snapshot the full merged payload as a summary JSON
    summary_bytes = json.dumps(
        {"total_activities": len(raw_activities), "activities": raw_activities},
        ensure_ascii=False,
    ).encode("utf-8")
    C.snapshot(
        SOURCE,
        "all_activities_merged",
        summary_bytes,
        url=BASE_URL + "?from=act&country_code=NP",
        params=f"total={len(raw_activities)}",
        http_status=200,
        ext="json",
    )

    retrieved = C.utc_now()
    rows: list[dict] = []
    skipped_zero = 0
    skipped_no_aid = 0
    seen_aids: set = set()
    seen_publishers: set = set()

    for act in raw_activities:
        aid = (act.get("aid") or "").strip()
        if not aid:
            skipped_no_aid += 1
            continue

        reporting_ref = (act.get("reporting_ref") or "").strip()
        reporting = (act.get("reporting") or "").strip()
        title = (act.get("title") or "").strip()

        seen_aids.add(aid)
        seen_publishers.add(reporting_ref or reporting)

        # Derive year from day_start
        # year is required by common.new_row; use 0 as sentinel for "unknown"
        # (0 is a non-empty value that passes validation while clearly flagging missing data)
        year_val = day_start_to_year(act.get("day_start"))
        if year_val is not None and 1990 <= year_val <= 2030:
            year = year_val
            yr_confidence = "low"  # activity totals span many years; start year is a proxy
        else:
            year = 0   # sentinel: year unknown or out-of-range
            yr_confidence = "low"

        is_multi = is_multilateral(reporting_ref)

        source_url = f"http://d-portal.org/ctrack.html#view=act&aid={aid}"

        # ---------- Build commitment row ----------
        commitment_orig = act.get("commitment")
        commitment_eur = act.get("commitment_eur")
        if commitment_orig is not None and float(commitment_orig) != 0 and commitment_eur is not None:
            fx_rate, fx_note = get_eur_usd(fx, year if year != 0 else None)
            amount_usd = float(commitment_eur) * fx_rate
            rows.append(C.new_row(
                side="donor",
                source=SOURCE,
                source_record_id=f"{aid}|commitment",
                donor_name=reporting,
                donor_iati_id=reporting_ref,
                flow_stage="commitment",
                instrument="",
                amount_usd=round(amount_usd, 2),
                amount_original=float(commitment_orig),
                currency_original="native",  # d-portal native; EUR conversion used
                price_base="current",
                year=year,
                fiscal_basis="calendar",
                status="ESTIMATED",
                confidence=yr_confidence,
                is_multilateral_outflow=is_multi,
                counts_in_headline=False,
                dedup_key=aid,
                source_url=source_url,
                retrieved_at=retrieved,
                notes=(
                    f"IATI activity commitment. EUR={commitment_eur}; "
                    f"fx: {fx_note}. "
                    f"Year=activity start (day_start={act.get('day_start')}); "
                    "activity-level totals span full project life, not a single year."
                ),
            ))
        else:
            skipped_zero += 1

        # ---------- Build disbursement row ----------
        spend_orig = act.get("spend")
        spend_eur = act.get("spend_eur")
        if spend_orig is not None and float(spend_orig) != 0 and spend_eur is not None:
            fx_rate, fx_note = get_eur_usd(fx, year if year != 0 else None)
            amount_usd = float(spend_eur) * fx_rate
            rows.append(C.new_row(
                side="donor",
                source=SOURCE,
                source_record_id=f"{aid}|disbursement",
                donor_name=reporting,
                donor_iati_id=reporting_ref,
                flow_stage="disbursement",
                instrument="",
                amount_usd=round(amount_usd, 2),
                amount_original=float(spend_orig),
                currency_original="native",
                price_base="current",
                year=year,
                fiscal_basis="calendar",
                status="ESTIMATED",
                confidence=yr_confidence,
                is_multilateral_outflow=is_multi,
                counts_in_headline=False,
                dedup_key=aid,
                source_url=source_url,
                retrieved_at=retrieved,
                notes=(
                    f"IATI activity spend/disbursement. EUR={spend_eur}; "
                    f"fx: {fx_note}. "
                    f"Year=activity start (day_start={act.get('day_start')}); "
                    "activity-level totals span full project life, not a single year."
                ),
            ))
        else:
            skipped_zero += 1

    C.write_interim(SOURCE, rows)

    # Self-check summary
    n_commitment = sum(1 for r in rows if r["flow_stage"] == "commitment")
    n_disbursement = sum(1 for r in rows if r["flow_stage"] == "disbursement")
    n_multi = sum(1 for r in rows if r["is_multilateral_outflow"])

    print(f"\n{SOURCE}: {len(rows)} rows total "
          f"({n_commitment} commitment, {n_disbursement} disbursement)")
    print(f"  skipped_zero_or_no_eur: {skipped_zero}")
    print(f"  skipped_no_aid: {skipped_no_aid}")
    print(f"  distinct IATI identifiers: {len(seen_aids)}")
    print(f"  distinct publishers (reporting_ref): {len(seen_publishers)}")
    print(f"  multilateral rows: {n_multi}")

    print("\nSample commitment rows (top 5 by amount_usd):")
    commit_rows = [r for r in rows if r["flow_stage"] == "commitment" and r["amount_usd"]]
    for r in sorted(commit_rows, key=lambda x: float(x["amount_usd"]), reverse=True)[:5]:
        print(f"  {r['donor_name'][:40]:<40} year={r['year']} "
              f"${float(r['amount_usd']):>16,.0f}  [{r['dedup_key'][:40]}]")

    print("\nSample disbursement rows (top 5 by amount_usd):")
    disb_rows = [r for r in rows if r["flow_stage"] == "disbursement" and r["amount_usd"]]
    for r in sorted(disb_rows, key=lambda x: float(x["amount_usd"]), reverse=True)[:5]:
        print(f"  {r['donor_name'][:40]:<40} year={r['year']} "
              f"${float(r['amount_usd']):>16,.0f}  [{r['dedup_key'][:40]}]")


if __name__ == "__main__":
    main()
