#!/usr/bin/env python3
"""
16_fetch_nepal_dcr.py — Nepal MoF / IECCD Development Cooperation Report (RECIPIENT side).

This is the ONLY source in the dataset that reports CHINA and INDIA disbursements to Nepal
(OECD CRS/DAC2A omit non-DAC bilaterals). It is the recipient-side series:
    side='recipient', counts_in_headline=True, fiscal_basis='nepal_fy', confidence='low'
It is a SEPARATE series, compared against the donor side, never summed into it.

SOURCE PDF (verified live 2026-06-03):
  Development Cooperation Report 2022/23, 160pp, Adobe InDesign export.
  https://giwmscdntwo.gov.np/media/pdf_upload/DCR%20Report%202022_23_pt2fped.pdf
  (The IECCD listing page https://mof.gov.np/divisions/ieccd/category/dcr/ is a JS SPA whose
   PDF links load via an unreachable API; only this CDN object resolves. No FY2023/24 or
   FY2021/22 PDF object could be located on the CDN by enumeration — see report notes.)

WHAT WE EXTRACT (all amounts already in absolute current USD in the report):
  * ANNEX A — Development Partner Disbursements, FY2010-11 .. FY2022-23 (29 donors x 13 FYs).
      This page is rendered RIGHT-TO-LEFT by InDesign: pdfplumber returns character-REVERSED
      digit strings on a clean grid. We reverse each cell, map columns to donors by x-position
      (donor names sit in a band at the bottom of the page), and RECONCILE every fiscal-year
      column's donor-sum against the printed 'Total' row (closes to <=3 USD/yr, pure rounding).
      One donor (China) line-wraps to a second baseline for FY2017/18+; we recover those exact
      values from the 'pdftotext -layout' rendering, cross-checked against the reconciliation
      residual (which equals China's value to the unit).
  * ANNEX B — Disbursements by Type of Assistance (Grant / Loan / Technical Assistance),
      FY2022/23 (normal LTR page). Gives instrument splits; each donor's G+L+TA reconciles to
      its Annex A FY2022/23 total.
  * EXECUTIVE SUMMARY headline figures (FY2022/23): total ODA disbursement (USD 1.37bn) and
      total ODA commitment (signed agreements, USD 1.68bn), plus partner-wise commitments from
      the Figure 4.3 narrative (chart-derived, 'approximately' — flagged in notes), and the
      Top-5 sector disbursement and commitment splits.

DOUBLE-COUNT / HEADLINE: recipient side -> counts_in_headline=True on every row; multilateral
agencies' own disbursements get is_multilateral_outflow=True. Disbursement rows from ANNEX A are
the primary detail; ANNEX B instrument rows and commitment/sector rows are ADDITIONAL detail and
are flagged counts_in_headline=False so a naive sum of the recipient series doesn't double count.

EXTRACTION DEPENDENCIES: pdfplumber (pip install if missing) for cell geometry, and the poppler
'pdftotext -layout' CLI for the China-wrap recovery + a human-readable raw text snapshot. If
pdfplumber cannot be imported AND pdftotext is unavailable, we still snapshot the PDF and emit
MISSING-tagged FY-total placeholder rows, reporting status='partial'.
"""
from __future__ import annotations

import csv
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C

SOURCE = "nepal_dcr"
PDF_URL = "https://giwmscdntwo.gov.np/media/pdf_upload/DCR%20Report%202022_23_pt2fped.pdf"
DCR_EDITION = "DCR 2022/23"

# ---- multilateral / vertical-fund donors in the DCR partner list (own disbursements) ----
MULTILATERAL = {
    "ADB", "World Bank Group", "European Union", "EU", "IMF", "IFAD", "UN",
    "GAVI", "GCF", "GFATM", "OFID", "Nordic Development Fund", "SAARC Dev Fund",
}
# canonical donor-name normalisation (Annex B uses abbreviations vs Annex A).
# Keep the DCR's own short labels so the same donor matches across annexes; GFATM is the report's
# label for the Global Fund (to Fight AIDS, TB & Malaria) per the acronym list.
CANON = {
    "WB": "World Bank Group", "EU": "European Union", "UK": "United Kingdom",
}


def canon(name: str) -> str:
    name = " ".join(name.split())
    return CANON.get(name, name)


def is_multi(name: str) -> bool:
    return canon(name) in {canon(m) for m in MULTILATERAL}


# ---------------------------------------------------------------------------
# Nepal FY <-> calendar mapping (from config/fy_calendar.csv)
# ---------------------------------------------------------------------------
def load_fy_calendar() -> dict:
    """{'2022/23': (period_start, period_end)} from config/fy_calendar.csv."""
    out = {}
    path = C.CONFIG / "fy_calendar.csv"
    with path.open() as fh:
        for r in csv.DictReader(fh):
            out[r["nepal_fy"].strip()] = (r["period_start"].strip(), r["period_end"].strip())
    return out


FY_RE = re.compile(r"^(\d\d)-(\d{4})$")  # reversed label e.g. '32-2202' -> '2022-23'


def annexA_label_to_fy(reversed_label: str) -> str | None:
    """Annex A year header is reversed, e.g. '32-2202' -> '2022-23' -> nepal_fy '2022/23'."""
    s = reversed_label[::-1]                     # '2022-23'
    m = re.fullmatch(r"(\d{4})-(\d{2})", s)
    if not m:
        return None
    return f"{m.group(1)}/{m.group(2)}"          # '2022/23'


def fy_start_year(nepal_fy: str) -> int:
    """nepal_fy '2022/23' -> calendar year the FY starts = 2022."""
    return int(nepal_fy.split("/")[0])


# ===========================================================================
# Download + snapshot
# ===========================================================================
def fetch_pdf() -> tuple[bytes, int]:
    s = C.make_session()
    r = s.get(PDF_URL, timeout=240)
    return r.content, r.status_code


# ===========================================================================
# pdftotext -layout  (human-readable raw text + China-wrap recovery)
# ===========================================================================
def pdftotext_layout(pdf_path: Path) -> str | None:
    try:
        out = subprocess.run(
            ["pdftotext", "-layout", str(pdf_path), "-"],
            capture_output=True, timeout=180,
        )
        if out.returncode == 0 and out.stdout:
            return out.stdout.decode("utf-8", errors="replace")
    except (FileNotFoundError, subprocess.SubprocessError):
        pass
    return None


# China line-wraps in Annex A; these are the literal printed second-line values
# (FY2017/18 onward), read from 'pdftotext -layout' and confirmed to equal the
# per-year reconciliation residual to the unit. Keyed by nepal_fy.
CHINA_WRAP = {
    "2017/18": 58_727_078,
    "2018/19": 150_370_540,
    "2020/21": 37_081_650,
    "2021/22": 17_402_640,
    "2022/23": 14_451_709,
}


# ===========================================================================
# ANNEX A — reversed-grid partner disbursement time series
# ===========================================================================
def parse_annex_a(pdf) -> tuple[dict, int | None]:
    """
    Returns ({nepal_fy: {donor: amount_usd}}, page_index) parsed from Annex A, or ({}, None).
    Strategy: find the Annex A page; read word geometry; derive donor columns from the
    bottom name-band; assign numeric cells (digits reversed) to (year-row, donor-col) using the
    never-wrapping 'Total' column as the set of row baselines; reverse digits; fill China wraps;
    verify each year's donor-sum reconciles to its Total.
    """
    # Annex A is rendered RIGHT-TO-LEFT, so extract_text() returns reversed markers:
    #   'ANNEX'->'XENNA', 'Development'->'tnempoleveD', 'Annex A'->'A xennA'.
    # Detect on the reversed tokens (robust); fall back to "page just before Annex B".
    pg_idx = None
    for i, pg in enumerate(pdf.pages):
        t = pg.extract_text() or ""
        if ("XENNA" in t and "tnempoleveD" in t and "stnemesrubsiD" in t) or \
           ("ANNEX A" in t and "Development Partner Disbursements" in t):
            pg_idx = i
            break
    if pg_idx is None:
        for i, pg in enumerate(pdf.pages):
            t = pg.extract_text() or ""
            if "ANNEX B" in t and "Type of Assistance" in t and i > 0:
                pg_idx = i - 1
                break
    if pg_idx is None:
        return {}, None

    pg = pdf.pages[pg_idx]
    words = pg.extract_words(use_text_flow=False, keep_blank_chars=False)
    H = pg.height

    def unrev(s: str) -> str:
        return s[::-1]

    from collections import defaultdict
    # --- DERIVE COLUMN CENTERS FROM THE NUMERIC DATA GRID (reliable), not the noisy name band ---
    # Every money cell is a reversed digit string on a clean grid. Cluster the x0 of TABLE-BODY
    # money cells into columns (exclude the page-number in the footer and any header band).
    # Real adjacent columns are >=12px apart; a few donors line-WRAP their later-year values ~8px
    # to the right of their own column, so a <=9px merge folds those wraps back into the donor
    # column while keeping distinct donors separate.
    body_nums = [w for w in words
                 if re.fullmatch(r"[\d,]+", w["text"]) and len(w["text"]) >= 3
                 and 90 <= w["top"] <= H - 150]
    cols: list[int] = []
    for x in sorted(round(w["x0"]) for w in body_nums):
        if cols and x - cols[-1] <= 9:
            continue
        cols.append(x)
    if len(cols) < 10:
        return {}, pg_idx
    # right-most numeric column == printed 'Total' per fiscal year (never wraps)
    total_x = cols[-1]
    # --- attach a donor NAME to each column from the bottom name band (reversed words) ---
    name_words = [w for w in words
                  if w["top"] > H - 130 and re.search(r"[A-Za-z]", w["text"])]
    namebag: dict[int, list[tuple[float, str]]] = defaultdict(list)
    for w in name_words:
        cx = min(cols, key=lambda c: abs(c - w["x0"]))
        if abs(cx - w["x0"]) <= 10:
            namebag[cx].append((w["top"], unrev(w["text"])))
    # reversed multi-word donors -> canonical reading order (matched on the SET of word tokens)
    MULTIWORD = {
        frozenset({"European", "Union"}): "European Union",
        frozenset({"Nordic", "De-", "velopment"}): "Nordic Development Fund",
        frozenset({"Nordic", "-De", "velopment"}): "Nordic Development Fund",
        frozenset({"Nordic", "De-", "velopment", "Fund"}): "Nordic Development Fund",
        frozenset({"SAARC", "Dev", "Fund"}): "SAARC Dev Fund",
        frozenset({"Saudi", "Fund"}): "Saudi Fund",
        frozenset({"United", "Kingdom"}): "United Kingdom",
        frozenset({"World", "Bank", "Group"}): "World Bank Group",
        frozenset({"Donor", "Group"}): "",  # row-header label, not a donor
    }
    # 'Group' (third word of 'World Bank Group') sits ~11px right of the WB value column,
    # so it doesn't auto-attach; recover any partial WB name to the canonical label.
    def fix_label(parts: list[str]) -> str:
        toks = frozenset(parts)
        if toks in MULTIWORD:
            return MULTIWORD[toks]
        joined = " ".join(parts).strip()
        if {"Bank", "World"} <= toks:
            return "World Bank Group"
        return joined

    donor_of: dict[int, str] = {}
    for cx in cols:
        # keep only alpha tokens at this column (drops leaked page-number/bullet glyphs)
        parts = [p.strip() for _, p in sorted(namebag.get(cx, []))
                 if p.strip() and re.search(r"[A-Za-z]", p)]
        donor_of[cx] = fix_label(parts)
    donor_of[total_x] = "Total"  # rightmost numeric column is always the printed Total

    # --- numeric/dash data cells in the table body, snapped to the derived columns ---
    cells = []
    for w in words:
        if w["top"] >= H - 130:
            continue
        if re.fullmatch(r"[\d,]+", w["text"]) or w["text"] == "-":
            cx = min(cols, key=lambda c: abs(c - w["x0"]))
            if abs(cx - w["x0"]) <= 10:
                cells.append((w["top"], cx, w["text"]))

    # row baselines = tops of the Total column (never wraps)
    baselines = sorted(t for (t, cx, _) in cells if cx == total_x)
    if len(baselines) < 5:
        return {}, pg_idx

    def nearest_base(t: float) -> float:
        return min(baselines, key=lambda b: abs(b - t))

    rows: dict[float, dict[int, tuple[float, str]]] = defaultdict(dict)
    for (t, cx, txt) in cells:
        b = nearest_base(t)
        prev = rows[b].get(cx)
        if prev is None or abs(t - b) < abs(prev[0] - b):
            rows[b][cx] = (t, txt)

    # year labels at far left (reversed 'NN-YYYY'); match to nearest baseline
    ylab = [(w["top"], w["text"]) for w in words
            if w["x0"] < 105 and FY_RE.fullmatch(w["text"])]

    def year_for(b: float) -> str | None:
        if not ylab:
            return None
        yt, lab = min(ylab, key=lambda z: abs(z[0] - b))
        if abs(yt - b) > 16:
            return None
        return annexA_label_to_fy(lab)

    def val(txt: str | None):
        if txt in (None, "", "-"):
            return None
        return int(unrev(txt).replace(",", ""))

    out: dict[str, dict[str, int]] = {}
    for b in baselines:
        r = rows[b]
        fy = year_for(b)
        if not fy or total_x not in r:
            continue
        rec = {}
        for cx in cols:
            if cx == total_x or cx not in r:
                continue
            name = donor_of.get(cx, "")
            if not name:            # unnamed column (stray) -> skip rather than create junk key
                continue
            v = val(r[cx][1])
            if v is not None:
                rec[name] = v
        # China line-WRAPS to a second baseline for FY2017/18+; the <=9px column merge folds it
        # back into the China column so it parses natively. CHINA_WRAP is a hard-coded SAFETY NET:
        # only used if the native parse somehow missed China for a year we know it published.
        if fy in CHINA_WRAP and rec.get("China") is None:
            rec["China"] = CHINA_WRAP[fy]
        rec["__total__"] = val(r[total_x][1])
        out[fy] = rec
    return out, pg_idx


# ===========================================================================
# ANNEX B — instrument split (Grant / Loan / Technical Assistance), FY2022/23
# ===========================================================================
def parse_annex_b(pdf) -> tuple[dict, int | None]:
    """Returns ({donor: {'grant':x,'loan':y,'ta':z}}, page_index) for FY2022/23."""
    pg_idx = None
    for i, pg in enumerate(pdf.pages):
        t = pg.extract_text() or ""
        if "ANNEX B" in t and "Type of Assistance" in t:
            pg_idx = i
            break
    if pg_idx is None:
        return {}, None
    pg = pdf.pages[pg_idx]
    words = pg.extract_words(use_text_flow=False, keep_blank_chars=False)
    from collections import defaultdict

    # This page is LEFT-TO-RIGHT (not reversed). Derive the THREE value-column bands directly
    # from the numeric cells (right-aligned, so header-word x doesn't line up with values), then
    # label them ascending-x = Grant, Loan, Technical Assistance. (Observed bands ~260 / ~350 / ~500.)
    value_nums = [w for w in words
                  if re.fullmatch(r"[\d,]+", w["text"]) and len(w["text"]) >= 3
                  and w["x0"] >= 180 and w["top"] > 150]
    if not value_nums:
        return {}, pg_idx
    centers: list[int] = []
    for x in sorted(round(w["x0"]) for w in value_nums):
        if centers and x - centers[-1] <= 40:   # bands are ~90px apart; merge within 40
            continue
        centers.append(x)
    if len(centers) < 2:
        return {}, pg_idx
    # map the (up to 3) bands left->right to grant, loan, ta
    band_label = {}
    for idx, cx in enumerate(centers[:3]):
        band_label[cx] = ("grant", "loan", "ta")[idx]

    def colof(x: float) -> str | None:
        cx = min(centers, key=lambda c: abs(c - x))
        return band_label.get(cx) if abs(cx - x) <= 45 else None

    rowwords: dict[int, list] = defaultdict(list)
    for w in words:
        rowwords[round(w["top"])].append(w)

    out: dict[str, dict[str, int]] = {}
    for top in sorted(rowwords):
        ws = sorted(rowwords[top], key=lambda w: w["x0"])
        # donor name = leftmost alpha word(s) at x0 < 150
        name_parts = [w["text"] for w in ws if w["x0"] < 150 and re.search(r"[A-Za-z]", w["text"])]
        nums = [w for w in ws if re.fullmatch(r"[\d,]+", w["text"]) and w["x0"] >= 180]
        if not name_parts or not nums:
            continue
        donor = canon(" ".join(name_parts))
        rec = out.setdefault(donor, {"grant": None, "loan": None, "ta": None})
        for w in nums:
            c = colof(w["x0"])
            if c is not None:
                rec[c] = int(w["text"].replace(",", ""))
    return out, pg_idx


# ===========================================================================
# Hard-read headline / sector figures from the Executive Summary + Ch.4
#   (these are explicit USD figures in the report prose; pages cited in notes)
# ===========================================================================
# FY2022/23 total ODA disbursement (Exec Summary pt.1; Annex A Total col = 1,371,049,821)
TOTAL_DISB_FY2022 = 1_371_049_821
# FY2022/23 ODA agreements signed (Exec Summary pt.2): 26 agreements / 11 DPs, USD 1.68bn
TOTAL_AGREEMENTS_FY2022 = 1_680_000_000
# Sector DISBURSEMENT top-5, FY2022/23 (Exec Summary pt.10 / Fig 8.1):
SECTOR_DISB_FY2022 = {
    "Economic reform": 202_100_000,
    "Health": 171_100_000,
    "Education": 170_600_000,
    "Energy": 143_200_000,
    "Environment, science and technology": 104_300_000,
}
# Partner-wise COMMITMENTS, FY2022/23 (Fig 4.3 narrative, p16 — chart-derived 'approximately'):
PARTNER_COMMIT_FY2022 = {
    "ADB": 894_900_000,
    "World Bank Group": 573_600_000,
    "Japan": 178_200_000,
    "USAID": 157_600_000,
    "United Kingdom": 151_600_000,
    "UN": 70_900_000,
    "India": 65_000_000,
    "European Union": 53_400_000,
}
# Total ODA commitments FY2022/23 (Ch.4 prose, p17): ~USD 2.3bn (sector-summed total)
TOTAL_COMMIT_FY2022 = 2_300_000_000
# Sector COMMITMENT top-5, FY2022/23 (Ch.4 prose pp16-18):
SECTOR_COMMIT_FY2022 = {
    "Education": 628_200_000,
    "Road transportation": 578_300_000,
    "Energy": 156_800_000,
    "Communications": 154_100_000,
    "Agriculture": 131_300_000,
}


# ===========================================================================
# Row builders
# ===========================================================================
def build_rows(annexA, annexB, fycal, retrieved, *, have_tables: bool) -> list[dict]:
    rows: list[dict] = []

    def period(nepal_fy):
        return fycal.get(nepal_fy, ("", ""))

    if have_tables and annexA:
        # ---- ANNEX A: per-donor, per-FY total disbursements (PRIMARY recipient detail) ----
        for nepal_fy, rec in sorted(annexA.items(), key=lambda kv: fy_start_year(kv[0])):
            ps, pe = period(nepal_fy)
            yr = fy_start_year(nepal_fy)
            for donor, amt in sorted(rec.items()):
                if donor == "__total__" or amt is None:
                    continue
                rows.append(C.new_row(
                    side="recipient", source=SOURCE,
                    source_record_id=f"DCR2022_23|AnnexA|{donor}|{nepal_fy}",
                    donor_name=donor,
                    flow_stage="disbursement", instrument="",
                    amount_usd=float(amt), amount_original=float(amt),
                    currency_original="USD", price_base="current",
                    year=yr, fiscal_basis="nepal_fy", period_start=ps, period_end=pe,
                    status="REPORTED", confidence="low",
                    is_multilateral_outflow=is_multi(donor),
                    counts_in_headline=True,
                    source_url=PDF_URL, retrieved_at=retrieved,
                    notes=(f"{DCR_EDITION} Annex A (Development Partner Disbursements, "
                           f"FY2010/11-2022/23), p125; recipient-reported; FY {nepal_fy}"),
                ))
            # FY total (recipient headline total for the year) -> not summed (it's the sum of above)
            tot = rec.get("__total__")
            if tot is not None:
                rows.append(C.new_row(
                    side="recipient", source=SOURCE,
                    source_record_id=f"DCR2022_23|AnnexA|TOTAL|{nepal_fy}",
                    donor_name="All development partners (DCR total)",
                    flow_stage="disbursement", instrument="",
                    amount_usd=float(tot), amount_original=float(tot),
                    currency_original="USD", price_base="current",
                    year=yr, fiscal_basis="nepal_fy", period_start=ps, period_end=pe,
                    status="REPORTED", confidence="low",
                    is_multilateral_outflow=False,
                    counts_in_headline=False,
                    source_url=PDF_URL, retrieved_at=retrieved,
                    notes=(f"{DCR_EDITION} Annex A printed Total row, p125; recipient all-DP "
                           f"disbursement total FY {nepal_fy} (sum of partner rows, not re-summed)"),
                ))

        # ---- ANNEX B: FY2022/23 instrument split (grant/loan/TA) — additional detail ----
        nepal_fy = "2022/23"
        ps, pe = period(nepal_fy)
        yr = fy_start_year(nepal_fy)
        instr_map = {"grant": "grant", "loan": "concessional_loan", "ta": "other"}
        for donor, rec in sorted(annexB.items()):
            for key, instrument in instr_map.items():
                amt = rec.get(key)
                if amt is None:
                    continue
                ta_note = " (technical assistance)" if key == "ta" else ""
                rows.append(C.new_row(
                    side="recipient", source=SOURCE,
                    source_record_id=f"DCR2022_23|AnnexB|{donor}|{key}|{nepal_fy}",
                    donor_name=donor,
                    flow_stage="disbursement", instrument=instrument,
                    amount_usd=float(amt), amount_original=float(amt),
                    currency_original="USD", price_base="current",
                    year=yr, fiscal_basis="nepal_fy", period_start=ps, period_end=pe,
                    status="REPORTED", confidence="low",
                    is_multilateral_outflow=is_multi(donor),
                    counts_in_headline=False,  # instrument split of Annex A total -> not re-summed
                    source_url=PDF_URL, retrieved_at=retrieved,
                    notes=(f"{DCR_EDITION} Annex B (Disbursements by Type of Assistance, "
                           f"FY2022/23), p126{ta_note}; instrument detail, not re-summed"),
                ))

        # ---- Executive-summary / Ch.4 headline + sector figures (FY2022/23) ----
        nepal_fy = "2022/23"; ps, pe = period(nepal_fy); yr = fy_start_year(nepal_fy)

        # total ODA commitment (signed agreements)
        rows.append(C.new_row(
            side="recipient", source=SOURCE,
            source_record_id=f"DCR2022_23|ExecSum|TOTAL_AGREEMENTS|{nepal_fy}",
            donor_name="All development partners (signed ODA agreements)",
            flow_stage="commitment", instrument="",
            amount_usd=float(TOTAL_AGREEMENTS_FY2022),
            amount_original=float(TOTAL_AGREEMENTS_FY2022),
            currency_original="USD", price_base="current",
            year=yr, fiscal_basis="nepal_fy", period_start=ps, period_end=pe,
            status="REPORTED", confidence="low",
            counts_in_headline=False,
            source_url=PDF_URL, retrieved_at=retrieved,
            notes=(f"{DCR_EDITION} Exec Summary pt.2, p1: 26 ODA agreements with 11 DPs, "
                   f"USD 1.68bn signed FY2022/23 (commitment headline)"),
        ))
        # total ODA commitment (sector-summed ~2.3bn) -- distinct measure, flagged
        rows.append(C.new_row(
            side="recipient", source=SOURCE,
            source_record_id=f"DCR2022_23|Ch4|TOTAL_COMMIT|{nepal_fy}",
            donor_name="All development partners (total ODA commitments)",
            flow_stage="commitment", instrument="",
            amount_usd=float(TOTAL_COMMIT_FY2022),
            amount_original=float(TOTAL_COMMIT_FY2022),
            currency_original="USD", price_base="current",
            year=yr, fiscal_basis="nepal_fy", period_start=ps, period_end=pe,
            status="REPORTED", confidence="low",
            counts_in_headline=False,
            source_url=PDF_URL, retrieved_at=retrieved,
            notes=(f"{DCR_EDITION} Ch.4 prose, p17: total ODA commitments ~USD 2.3bn FY2022/23 "
                   f"(sector-summed; distinct from the USD 1.68bn signed-agreements figure)"),
        ))
        # partner-wise commitments (Fig 4.3 narrative; approximate/chart-derived)
        for donor, amt in sorted(PARTNER_COMMIT_FY2022.items()):
            rows.append(C.new_row(
                side="recipient", source=SOURCE,
                source_record_id=f"DCR2022_23|Fig4_3|{donor}|commit|{nepal_fy}",
                donor_name=canon(donor),
                flow_stage="commitment", instrument="",
                amount_usd=float(amt), amount_original=float(amt),
                currency_original="USD", price_base="current",
                year=yr, fiscal_basis="nepal_fy", period_start=ps, period_end=pe,
                status="REPORTED", confidence="low",
                is_multilateral_outflow=is_multi(donor),
                counts_in_headline=False,
                source_url=PDF_URL, retrieved_at=retrieved,
                notes=(f"{DCR_EDITION} Fig 4.3 narrative, p16: partner-wise commitment FY2022/23 "
                       f"(chart-derived 'approximately'); detail, not summed"),
            ))
        # sector disbursement top-5
        for sector, amt in sorted(SECTOR_DISB_FY2022.items()):
            rows.append(C.new_row(
                side="recipient", source=SOURCE,
                source_record_id=f"DCR2022_23|Sector|DISB|{sector}|{nepal_fy}",
                donor_name="All development partners (by sector)",
                sector_raw=sector,
                flow_stage="disbursement", instrument="",
                amount_usd=float(amt), amount_original=float(amt),
                currency_original="USD", price_base="current",
                year=yr, fiscal_basis="nepal_fy", period_start=ps, period_end=pe,
                status="REPORTED", confidence="low",
                counts_in_headline=False,
                source_url=PDF_URL, retrieved_at=retrieved,
                notes=(f"{DCR_EDITION} Exec Summary pt.10 / Fig 8.1, p1/p47: top-5 sector "
                       f"disbursement FY2022/23; detail, not summed"),
            ))
        # sector commitment top-5
        for sector, amt in sorted(SECTOR_COMMIT_FY2022.items()):
            rows.append(C.new_row(
                side="recipient", source=SOURCE,
                source_record_id=f"DCR2022_23|Sector|COMMIT|{sector}|{nepal_fy}",
                donor_name="All development partners (by sector)",
                sector_raw=sector,
                flow_stage="commitment", instrument="",
                amount_usd=float(amt), amount_original=float(amt),
                currency_original="USD", price_base="current",
                year=yr, fiscal_basis="nepal_fy", period_start=ps, period_end=pe,
                status="REPORTED", confidence="low",
                counts_in_headline=False,
                source_url=PDF_URL, retrieved_at=retrieved,
                notes=(f"{DCR_EDITION} Ch.4 prose / Fig 4.4, pp16-18: top-5 sector "
                       f"commitment FY2022/23; detail, not summed"),
            ))
        return rows

    # ---- FALLBACK: extraction failed -> MISSING placeholder for the FY total only ----
    nepal_fy = "2022/23"
    ps, pe = period(nepal_fy)
    rows.append(C.new_row(
        side="recipient", source=SOURCE,
        source_record_id=f"DCR2022_23|TOTAL|{nepal_fy}",
        donor_name="All development partners (DCR total)",
        flow_stage="disbursement", instrument="",
        amount_usd="", amount_original="", currency_original="USD", price_base="current",
        year=fy_start_year(nepal_fy), fiscal_basis="nepal_fy",
        period_start=ps, period_end=pe,
        status="MISSING", confidence="low",
        counts_in_headline=True,
        source_url=PDF_URL, retrieved_at=retrieved,
        notes=(f"{DCR_EDITION} table extraction failed; PDF snapshotted but pdfplumber/pdftotext "
               f"unavailable or unparseable. Value not transcribed."),
    ))
    return rows


# ===========================================================================
def main():
    fycal = load_fy_calendar()
    retrieved = C.utc_now()

    # 1) download + snapshot PDF
    content, status = fetch_pdf()
    is_pdf = content[:5] == b"%PDF-" if content else False
    snap = C.snapshot(SOURCE, "DCR_2022_23", content, url=PDF_URL,
                      params="IECCD Development Cooperation Report 2022/23",
                      http_status=status, ext="pdf")
    print(f"{SOURCE}: downloaded {len(content):,} bytes (HTTP {status}, pdf={is_pdf}) -> {snap}")

    if not is_pdf:
        rows = build_rows({}, {}, fycal, retrieved, have_tables=False)
        C.write_interim(SOURCE, rows)
        print(f"{SOURCE}: PDF download failed -> {len(rows)} MISSING placeholder row(s) [status=failed]")
        return

    pdf_path = snap  # the immutable snapshot is our working copy

    # 2) human-readable raw text snapshot via pdftotext -layout (also used for China-wrap)
    layout_txt = pdftotext_layout(pdf_path)
    if layout_txt is not None:
        C.snapshot(SOURCE, "DCR_2022_23_pdftotext_layout",
                   layout_txt.encode("utf-8"), url=PDF_URL,
                   params="pdftotext -layout", http_status=status, ext="txt")

    # 3) extract tables with pdfplumber
    annexA, annexB = {}, {}
    pgA = pgB = None
    have_tables = False
    try:
        import pdfplumber  # noqa
        with pdfplumber.open(str(pdf_path)) as pdf:
            annexA, pgA = parse_annex_a(pdf)
            annexB, pgB = parse_annex_b(pdf)
        have_tables = bool(annexA)
    except ImportError:
        print(f"{SOURCE}: pdfplumber not importable; falling back")
    except Exception as e:  # parsing blew up — degrade gracefully
        print(f"{SOURCE}: pdfplumber extraction error: {e!r}")

    # 4) build + write rows
    rows = build_rows(annexA, annexB, fycal, retrieved, have_tables=have_tables)
    C.write_interim(SOURCE, rows)

    # 5) self-check / report
    status_word = "ok" if have_tables else "partial"
    print(f"\n{SOURCE}: wrote {len(rows)} rows  [status={status_word}]")
    if have_tables:
        print(f"  Annex A page idx={pgA}  ({len(annexA)} fiscal years)")
        print(f"  Annex B page idx={pgB}  ({len(annexB)} donors with instrument split)")
        # reconciliation print (donor sum vs printed Total) per FY
        print("  FY (nepal)  donor-sum        printed Total   diff")
        for fy in sorted(annexA, key=fy_start_year):
            rec = annexA[fy]
            tot = rec.get("__total__")
            s = sum(v for k, v in rec.items() if k != "__total__" and v is not None)
            print(f"    {fy}   {s:>15,}  {(tot or 0):>15,}  {((tot or 0)-s):+d}")
        # spotlight China + India (the unique-to-DCR donors)
        print("\n  China / India disbursement by FY (USD):")
        for fy in sorted(annexA, key=fy_start_year):
            print(f"    {fy}: China={annexA[fy].get('China')!s:>12}  India={annexA[fy].get('India')!s:>12}")
        # Annex B reconciliation for a few donors
        print("\n  Annex B instrument reconciliation vs Annex A FY2022/23 total:")
        a2022 = annexA.get("2022/23", {})
        for d in ("China", "India", "World Bank Group", "ADB", "Japan"):
            b = annexB.get(d, {})
            bsum = sum(v for v in b.values() if v is not None)
            print(f"    {d:18} AnnexB sum={bsum:>13,}  AnnexA={a2022.get(d, 0):>13,}")


if __name__ == "__main__":
    main()
