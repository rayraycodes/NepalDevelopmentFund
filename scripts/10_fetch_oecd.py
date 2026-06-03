#!/usr/bin/env python3
"""
10_fetch_oecd.py — OECD DAC2A: ODA disbursements to Nepal (NPL) by donor, 2015-2024.

Donor-dimension is a FLAT codelist that mixes leaf donors with aggregate totals
(ALLD=Official donors, ALLM=Multilaterals, DAC, G7, 5RDB0=Regional Dev Banks ...) and
DUPLICATE agency codes (ADB 5ASDB0/5ASDB01; World Bank 5WB0/5WBG0/5WB002=IDA;
IMF 5IMF0/5IMF02). Summing leaves+aggregates triple-counts. We therefore:
  - keep LEAF donors only for the headline (explicit AGG_CODES blocklist below);
  - retain ALLD (Official donors) as a NON-summed donor-side benchmark — it reconciles
    almost exactly to the World Bank net-ODA anchor (validated 2015-2022);
  - merge current (V) and constant (Q, base 2024) prices into one row;
  - measure 206 (ODA disbursements, net) = headline; 201 (grants) and 218 (loans, net)
    kept for instrument detail but NOT summed (206 already nets them).
OBS_VALUE is in millions (UNIT_MULT=6) -> converted to absolute USD.
"""
import csv
import io
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C

SOURCE = "oecd_dac2a"
URL = ("https://sdmx.oecd.org/public/rest/data/OECD.DCD.FSD,DSD_DAC2@DF_DAC2A,/"
       ".NPL...?startPeriod=2015&endPeriod=2024&dimensionAtObservation=AllDimensions")

# aggregate totals + duplicate parent codes -> excluded from the headline breakdown
AGG_CODES = {
    "ALLD", "ALLM", "DAC", "DAC_EC", "DACEU", "DACEU_EC", "G7", "WXDAC",
    "5RDB0", "5WB0", "5WBG0", "1UN0", "9OTH0", "9PRIV0", "9PLG0",
    "5ASDB01",  # duplicate of 5ASDB0 (ADB)
    "5IMF0",    # parent of 5IMF02 (IMF Concessional Trust Funds)
}
KEEP_MEASURES = {
    "206": ("disbursement", "", True),                 # net ODA disbursements -> HEADLINE
    "201": ("disbursement", "grant", False),           # ODA grants (instrument detail)
    "218": ("disbursement", "concessional_loan", False),  # ODA loans net (instrument detail)
}
MULTI_PREFIX = ("5", "1UN", "4EU", "9OTH")  # multilateral-agency leaf donors


def split_cell(v: str):
    if v is None:
        return "", ""
    p = v.split(": ", 1)
    return (p[0], p[1]) if len(p) == 2 else (v, v)


def col(headers, prefix):
    for h in headers:
        if h.split(":")[0].strip() == prefix:
            return h
    raise KeyError(prefix)


def main():
    s = C.make_session()
    r = C.get(s, URL, accept=C.SDMX_CSV_ACCEPT, timeout=180)
    if r.status_code != 200 or not r.content:
        raise SystemExit(f"OECD DAC2A fetch failed: HTTP {r.status_code}")
    C.snapshot(SOURCE, "dac2a_NPL_2015-2024", r.content, url=URL,
               params="recipient=NPL; measures=all; price=V,Q", http_status=r.status_code)

    reader = csv.DictReader(io.StringIO(r.content.decode("utf-8")))
    H = reader.fieldnames
    c_don, c_meas, c_pb = col(H, "DONOR"), col(H, "MEASURE"), col(H, "PRICE_BASE")
    c_year, c_mult, c_base = col(H, "TIME_PERIOD"), col(H, "UNIT_MULT"), col(H, "BASE_PER")

    g = defaultdict(lambda: {"cur": None, "con": None, "base": ""})
    for row in reader:
        val = row.get("OBS_VALUE", "").strip()
        if val == "":
            continue
        dcode, dlabel = split_cell(row[c_don])
        mcode, _ = split_cell(row[c_meas])
        if mcode not in KEEP_MEASURES:
            continue
        # keep only leaf donors, plus ALLD as the benchmark total
        if dcode in AGG_CODES and dcode != "ALLD":
            continue
        if dcode == "ALLD" and mcode != "206":
            continue
        pcode, _ = split_cell(row[c_pb])
        year = int(row[c_year])
        mult = int(split_cell(row[c_mult])[0] or 0)
        amt = float(val) * (10 ** mult)
        key = (dcode, dlabel, mcode, year)
        if pcode == "V":
            g[key]["cur"] = amt
        elif pcode == "Q":
            g[key]["con"] = amt
            g[key]["base"] = split_cell(row[c_base])[0]

    rows, retrieved = [], C.utc_now()
    for (dcode, dlabel, mcode, year), v in g.items():
        flow_stage, instrument, is_headline_meas = KEEP_MEASURES[mcode]
        is_benchmark = (dcode == "ALLD")
        is_multi = (not is_benchmark) and dcode.startswith(MULTI_PREFIX)
        if is_benchmark:
            note = "OECD all-donor total (Official donors); donor-side benchmark, not summed"
        else:
            note = f"measure {mcode}" + ("" if is_headline_meas else " [instrument detail, not summed]")
        rows.append(C.new_row(
            side="donor", source=SOURCE,
            source_record_id=f"DAC2A|{dcode}|{mcode}|{year}",
            donor_name=dlabel, donor_dac_code=dcode,
            flow_stage=flow_stage, instrument=instrument,
            amount_usd=v["cur"] if v["cur"] is not None else "",
            amount_usd_constant=v["con"] if v["con"] is not None else "",
            price_base_year=v["base"],
            amount_original=v["cur"] if v["cur"] is not None else "",
            currency_original="USD", price_base="current",
            year=year, fiscal_basis="calendar",
            status="REPORTED", confidence="high",
            is_multilateral_outflow=is_multi,
            counts_in_headline=(is_headline_meas and not is_benchmark),
            source_url=URL, retrieved_at=retrieved, notes=note,
        ))
    C.write_interim(SOURCE, rows)

    # self-check: leaf-206 headline sum vs ALLD benchmark, by year
    leaf = defaultdict(float)
    alld = {}
    for r_ in rows:
        if r_["amount_usd"] == "":
            continue
        if r_["counts_in_headline"]:
            leaf[r_["year"]] += float(r_["amount_usd"])
        if r_["donor_dac_code"] == "ALLD":
            alld[r_["year"]] = float(r_["amount_usd"])
    print(f"{SOURCE}: {len(rows)} rows "
          f"({sum(1 for x in rows if x['counts_in_headline'])} headline)")
    print("  year | leaf-206 headline sum | ALLD benchmark | ratio")
    for y in sorted(leaf):
        a = alld.get(y, float("nan"))
        print(f"  {y}: {leaf[y]:14,.0f}  {a:14,.0f}  {leaf[y]/a:.3f}")


if __name__ == "__main__":
    main()
