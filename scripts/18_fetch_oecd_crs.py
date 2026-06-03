#!/usr/bin/env python3
"""
18_fetch_oecd_crs.py — OECD CRS activity-level flows to Nepal (NPL), 2015-2024.

This is the INSTRUMENT + SECTOR authority for the donor side. side=donor,
counts_in_headline=False on EVERY row (the donor-side headline is already fully
captured by OECD DAC2A, which reconciles to the World Bank net-ODA anchor). Our
contribution here is detail: sector splits (5-digit DAC purpose codes), the
grant/loan/OOF instrument split, and the commitment-vs-disbursement distinction.

ENDPOINT QUIRK (load-bearing): the standard SDMX host
  https://sdmx.oecd.org/public/rest/data/OECD.DCD.FSD,DSD_CRS@DF_CRS,/...
returns HTTP 500 "Object reference not set to an instance of an object" for EVERY
CRS data query (the DAC2A flow on the same host works fine — verified). The
working host for CRS is the DCD-public node:
  https://sdmx.oecd.org/dcd-public/rest/data/...
which returns proper SDMX responses (200 / clean 404 / 422). We use it here.

DIMENSION ORDER (from DSD_CRS, 11 keyed dims + TIME):
  1 DONOR  2 RECIPIENT  3 SECTOR  4 MEASURE  5 CHANNEL  6 MODALITY
  7 FLOW_TYPE  8 PRICE_BASE  9 MD_DIM  10 MD_ID  11 UNIT_MEASURE  (then TIME_PERIOD)
Key = ".NPL...{CH=_T}{MO=_T}..{MD=_T}.." with RECIPIENT pinned to NPL.

We pin CHANNEL=_T, MODALITY=_T, MD_DIM=_T to collapse the channel/modality/microdata
explosion (full NPL pull for ONE year is 114 MB / 318k rows; pinning the totals
drops it to ~9 MB / 28k rows). One HTTP request per year, snapshotted separately.

DEDUP (mirrors 10_fetch_oecd.py):
  - DONOR codelist mixes leaf donors with aggregate/parent rollups (ALLD, ALLM, DAC,
    G7, 5WB0/5WBG0 parents of 5WB002=IDA, 5RDB0, 1UN0, 9OTH0 ...) and a duplicate
    ADB code (5ASDB01 == 5ASDB0). Summing leaves+aggregates multi-counts. We keep
    LEAF donors for the (non-summed) detail and emit ALLD/ALLM/DAC as benchmark rows
    flagged counts_in_headline=False + a 'benchmark' note.
  - SECTOR codelist mixes 5-digit leaf purpose codes with group rollups (100, 110,
    450, 1000=All). Sum of 5-digit leaves == SECTOR=1000 total exactly (verified
    ratio 1.000). We emit 5-digit leaf-sector rows for the sector split, plus the
    per-donor SECTOR=1000 'all-sectors' row (flagged, not summed with the leaves).
  - MEASURE 100 (ODA total) == 11 (grants) + 13 (loans) (verified). We emit the
    instrument legs 11/13 (+14 OOF) and SKIP 100 to avoid double-counting; 30
    (private dev finance), 19 (equity), 91-99 (PSI etc.) are not ODA -> skipped,
    except 14 (OOF) kept as instrument='oof'.

amount_usd = OBS_VALUE * 10^UNIT_MULT  (UNIT_MULT is uniformly 6 -> millions -> abs USD).
PRICE_BASE V (current) -> amount_usd ; Q (constant, base 2024) -> amount_usd_constant.
All amounts are already USD as reported by OECD (no FX conversion needed).
"""
import csv
import io
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C

SOURCE = "oecd_crs"

# DCD-public host — the /public/ host 500s on CRS data (see module docstring).
HOST = "https://sdmx.oecd.org/dcd-public/rest/data"
FLOW = "OECD.DCD.FSD,DSD_CRS@DF_CRS,"
# 11-segment key, RECIPIENT(pos2)=NPL, CHANNEL/MODALITY/MD_DIM totals pinned.
KEY = ".".join(["", "NPL", "", "", "_T", "_T", "", "", "_T", "", ""])
YEARS = range(2015, 2025)


def year_url(year: int) -> str:
    return (f"{HOST}/{FLOW}/{KEY}"
            f"?startPeriod={year}&endPeriod={year}&dimensionAtObservation=AllDimensions")


# --- DONOR aggregate / duplicate-parent codes excluded from the leaf detail -----
# (alpha aggregates + numeric rollups + verified duplicates). ALLD/ALLM/DAC kept
# separately below as benchmark rows.
DONOR_AGG = {
    # NB: ALLD/ALLM/DAC are deliberately NOT here — they are kept as benchmark
    # rows (see DONOR_BENCHMARK) flagged counts_in_headline=False and never summed.
    "DAC_EC", "DACEU", "DACEU_EC", "G7", "WXDAC", "EU00",
    "5RDB0", "5WB0", "5WBG0", "1UN0", "9OTH0",
    "5ASDB01",   # duplicate of 5ASDB0 (Asian Development Bank)
}
# benchmark totals we DO emit (flagged, never summed into anything)
DONOR_BENCHMARK = {"ALLD": "Official donors total",
                   "ALLM": "Multilateral organisations total",
                   "DAC": "DAC countries total"}

# MEASURE -> (instrument, keep_as_instrument_leg). 100 skipped (==11+13).
MEASURE_MAP = {
    "11": "grant",              # ODA Grants
    "13": "concessional_loan",  # ODA Loans
    "14": "oof",                # Other Official Flows (non Export Credit)
}
FLOW_MAP = {"D": "disbursement", "C": "commitment"}
# multilateral-agency leaf-donor code prefixes (own outflows)
MULTI_PREFIX = ("5", "1UN", "4EU", "9OTH")


def split_cell(v):
    """'CODE: Label' -> ('CODE','Label'); plain -> (v, v)."""
    if v is None:
        return "", ""
    p = v.split(": ", 1)
    return (p[0].strip(), p[1].strip()) if len(p) == 2 else (v.strip(), v.strip())


def col(headers, prefix):
    for h in headers:
        if h.split(":")[0].strip() == prefix:
            return h
    raise KeyError(prefix)


def _valid_cached_snapshot(year: int) -> bytes | None:
    """Return the bytes of the most recent VALID snapshot for `year`, else None.

    A snapshot is valid if it is a substantial SDMX-CSV file (begins with the
    DATAFLOW header and is well over the size of an error stub). This makes the
    fetch loop idempotent and resilient to OECD's 429 download throttle: a year
    already captured cleanly is not re-downloaded.
    """
    snaps = sorted((C.RAW / SOURCE).glob(f"crs_NPL_{year}_*.csv"))
    for path in reversed(snaps):  # newest first
        try:
            b = path.read_bytes()
        except OSError:
            continue
        if len(b) > 100_000 and b[:8] == b"DATAFLOW":
            return b
    return None


def is_leaf_sector(code: str) -> bool:
    return len(code) == 5 and code.isdigit()


def map_sector(code5: str) -> str:
    """Map a 5-digit DAC purpose code to a crosswalk 'sector'.

    The crosswalk is keyed by DAC broad 3-digit groups (110, 120, 230, 700, ...).
    A 5-digit purpose code's parent group is its first two digits + '0'
    (e.g. 15110 -> 151 -> group 150; 23230 -> 232 -> group 230). The 7xx
    humanitarian sub-codes (720xx/730xx/740xx) roll up one level further to the
    700 broad bucket, so fall back to first-digit + '00'. Verified to cover
    100% of the 199 purpose codes present in the NPL extract.
    """
    g3 = code5[:2] + "0"
    if g3 in SECTOR_XWALK:
        return SECTOR_XWALK[g3]
    g_broad = code5[:1] + "00"
    if g_broad in SECTOR_XWALK:
        return SECTOR_XWALK[g_broad]
    return SECTOR_XWALK.get(code5[:3], "")


def main():
    s = C.make_session()
    retrieved = C.utc_now()

    # accumulate V/Q into one record per (donor, sector, measure, flow, year)
    g = defaultdict(lambda: {"cur": None, "con": None, "base": "",
                             "dlabel": "", "slabel": "", "obs_status": ""})
    years_ok, years_failed = [], []

    for year in YEARS:
        url = year_url(year)
        # Idempotent + rate-limit resilient: reuse an existing VALID snapshot for this
        # year if one is on disk; otherwise fetch and snapshot. (OECD throttles bulk
        # data downloads with HTTP 429 on a tight sliding window — see module note.)
        cached = _valid_cached_snapshot(year)
        if cached is not None:
            content = cached
            print(f"  {year}: reusing cached snapshot ({len(content):,} bytes)")
        else:
            r = C.get(s, url, accept=C.SDMX_CSV_ACCEPT, timeout=300)
            ok = (r.status_code == 200 and r.content
                  and r.content[:30] != b"Object reference not set to an"
                  and not r.content.startswith(b"You have exceeded"))
            C.snapshot(SOURCE, f"crs_NPL_{year}", r.content, url=url,
                       params=("recipient=NPL; CHANNEL=_T; MODALITY=_T; MD_DIM=_T; "
                               "measures=all; flow=C,D; price=V,Q"),
                       http_status=r.status_code)
            if not ok:
                years_failed.append(year)
                print(f"  {year}: FAILED HTTP {r.status_code} "
                      f"({r.content[:60]!r})")
                continue
            content = r.content
        years_ok.append(year)

        reader = csv.DictReader(io.StringIO(content.decode("utf-8")))
        H = reader.fieldnames
        c_don = col(H, "DONOR"); c_sec = col(H, "SECTOR"); c_meas = col(H, "MEASURE")
        c_flow = col(H, "FLOW_TYPE"); c_pb = col(H, "PRICE_BASE")
        c_mult = col(H, "UNIT_MULT"); c_base = col(H, "BASE_PER")
        c_status = col(H, "OBS_STATUS")

        for row in reader:
            raw = (row.get("OBS_VALUE") or "").strip()
            if raw in ("", "NaN"):
                continue
            mcode, _ = split_cell(row[c_meas])
            # keep instrument legs (11/13/14); ODA-total 100 skipped (==11+13)
            if mcode not in MEASURE_MAP:
                continue
            fcode, _ = split_cell(row[c_flow])
            if fcode not in FLOW_MAP:
                continue
            dcode, dlabel = split_cell(row[c_don])
            scode, slabel = split_cell(row[c_sec])
            # sector: keep 5-digit leaf purpose codes + the per-donor all-sectors total
            if not (is_leaf_sector(scode) or scode == "1000"):
                continue
            # donor: drop aggregate/duplicate parents EXCEPT explicit benchmark codes
            if dcode in DONOR_AGG:
                continue
            is_benchmark = dcode in DONOR_BENCHMARK
            # benchmark rows only as the all-sectors total (avoid huge sector x benchmark)
            if is_benchmark and scode != "1000":
                continue

            pcode, _ = split_cell(row[c_pb])
            mult = int((split_cell(row[c_mult])[0]) or 0)
            amt = float(raw) * (10 ** mult)
            key = (dcode, scode, mcode, fcode, year)
            rec = g[key]
            rec["dlabel"] = dlabel
            rec["slabel"] = slabel
            if pcode == "V":
                rec["cur"] = amt
                rec["obs_status"] = split_cell(row[c_status])[0]
            elif pcode == "Q":
                rec["con"] = amt
                rec["base"] = split_cell(row[c_base])[0]

    if not years_ok:
        # nothing retrieved — emit nothing, report failed honestly
        C.write_interim(SOURCE, [])
        print(f"{SOURCE}: FAILED — no years retrieved (failed: {years_failed})")
        return "failed", 0

    # --- build canonical rows -------------------------------------------------
    rows = []
    for (dcode, scode, mcode, fcode, year), v in g.items():
        instrument = MEASURE_MAP[mcode]
        flow_stage = FLOW_MAP[fcode]
        is_benchmark = dcode in DONOR_BENCHMARK
        is_alltot = (scode == "1000")
        is_multi = (not is_benchmark) and dcode.startswith(MULTI_PREFIX)

        if is_benchmark:
            sector = "all_sectors"
            sector_raw = f"1000: All sectors [{DONOR_BENCHMARK[dcode]}]"
            note = (f"benchmark donor aggregate ({DONOR_BENCHMARK[dcode]}); "
                    f"all-sectors; not summed; measure {mcode}")
        elif is_alltot:
            sector = "all_sectors"
            sector_raw = "1000: All sectors"
            note = (f"per-donor all-sectors total; not summed with leaf sectors; "
                    f"measure {mcode}")
        else:
            sector = map_sector(scode)
            sector_raw = f"{scode}: {v['slabel']}"
            note = f"measure {mcode} ({instrument}); DAC purpose {scode}"

        rid = f"CRS|{dcode}|{scode}|{mcode}|{fcode}|{year}"
        rows.append(C.new_row(
            side="donor", source=SOURCE, source_record_id=rid,
            donor_name=v["dlabel"], donor_dac_code=dcode,
            sector=sector, sector_raw=sector_raw,
            flow_stage=flow_stage, instrument=instrument,
            amount_usd=v["cur"] if v["cur"] is not None else "",
            amount_usd_constant=v["con"] if v["con"] is not None else "",
            price_base_year=v["base"],
            amount_original=v["cur"] if v["cur"] is not None else "",
            currency_original="USD", price_base="current",
            year=year, fiscal_basis="calendar",
            status="REPORTED", confidence="high",
            is_multilateral_outflow=is_multi,
            counts_in_headline=False,   # donor-side detail; headline owned by DAC2A
            source_url=year_url(year), retrieved_at=retrieved,
            notes=note + (f"; OBS_STATUS={v['obs_status']}" if v["obs_status"] else ""),
        ))

    C.write_interim(SOURCE, rows)

    # --- self-check -----------------------------------------------------------
    # total CRS disbursement by year = leaf-donor 5-digit-sector grant+loan (V),
    # i.e. gross ODA disbursement. Compare loosely to ~1.2-1.8 bn net ODA anchor.
    BENCH = set(DONOR_BENCHMARK)
    disb_by_year = defaultdict(float)
    sector_disb = defaultdict(float)
    for r_ in rows:
        if r_["flow_stage"] != "disbursement":
            continue
        if r_["donor_dac_code"] in BENCH:
            continue
        if r_["sector"] == "all_sectors":
            continue
        if r_["instrument"] not in ("grant", "concessional_loan"):
            continue  # ODA only for the anchor comparison (exclude OOF)
        if r_["amount_usd"] == "":
            continue
        amt = float(r_["amount_usd"])
        disb_by_year[r_["year"]] += amt
        sector_disb[r_["sector"]] += amt

    print(f"{SOURCE}: {len(rows)} rows from years {years_ok}"
          + (f" (FAILED: {years_failed})" if years_failed else ""))
    print("  CRS gross ODA disbursement (grant+loan, leaf donors, 5-digit sectors) by year:")
    for y in sorted(disb_by_year):
        print(f"    {y}: ${disb_by_year[y]:,.0f}")
    print("  Top 5 sectors by total disbursement (2015-2024):")
    for sec, amt in sorted(sector_disb.items(), key=lambda x: -x[1])[:5]:
        print(f"    {sec:16s} ${amt:,.0f}")

    status = "partial" if years_failed else "ok"
    return status, len(rows)


# load sector crosswalk once at import (3-digit DAC purpose prefix -> sector)
def _load_sector_xwalk():
    out = {}
    p = C.CONFIG / "sector_crosswalk.csv"
    if p.exists():
        with p.open() as fh:
            for r in csv.DictReader(fh):
                out[r["dac_purpose_prefix"].strip()] = r["sector"].strip()
    return out


SECTOR_XWALK = _load_sector_xwalk()


if __name__ == "__main__":
    main()
