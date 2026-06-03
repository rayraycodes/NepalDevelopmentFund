#!/usr/bin/env python3
"""
85_dashboard_data.py — distill the processed series into report/dashboard/data.js
(a compact `window.NEPAL_DATA = {...}` so the dashboard opens directly from file://).
Reads only the small aggregate CSVs, not the 76k-row core table.
"""
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C

OUT = C.ROOT / "report" / "dashboard" / "data.js"


def num(s):
    return pd.to_numeric(s, errors="coerce")


def main():
    recon = pd.read_csv(C.PROCESSED / "reconciliation_donor_vs_recipient.csv")
    don = pd.read_csv(C.PROCESSED / "agg_by_donor_year.csv")
    sec = pd.read_csv(C.PROCESSED / "agg_by_sector_year.csv")
    core = pd.read_csv(C.PROCESSED / "core_long.csv", dtype=str, keep_default_na=False)
    core["usd"] = num(core["amount_usd"]).fillna(0.0)
    core["yr"] = num(core["year"])

    # reconciliation series
    reconciliation = []
    for _, r in recon.iterrows():
        reconciliation.append({
            "year": int(r["year"]),
            "donor": round(num(r["donor_side_usd"]) / 1e6, 1) if pd.notna(num(r["donor_side_usd"])) else None,
            "recipient": round(num(r["recipient_side_usd"]) / 1e6, 1) if pd.notna(num(r["recipient_side_usd"])) else None,
            "anchor": round(num(r["anchor_usd"]) / 1e6, 1) if pd.notna(num(r["anchor_usd"])) else None,
            "gap_pct": round(num(r["gap_pct"]), 1) if pd.notna(num(r["gap_pct"])) else None,
            "verdict": r.get("donor_vs_anchor", ""),
        })

    # top donors by side and year (top 12)
    def top(side, year, n=12):
        d = don[(don["side"] == side) & (don["year"] == year) &
                (don["flow_stage"] == "disbursement")].copy()
        d["amount_usd"] = num(d["amount_usd"])
        d = d.nlargest(n, "amount_usd")
        return [{"name": row["donor_name"], "usd": round(row["amount_usd"] / 1e6, 1)}
                for _, row in d.iterrows()]
    topDonors = {"donor": {}, "recipient": {}}
    for y in (2018, 2019, 2020, 2021, 2022):
        topDonors["donor"][str(y)] = top("donor", y)
        topDonors["recipient"][str(y)] = top("recipient", y)

    # China commitments (AidData) vs disbursements (DCR)
    ch = core[core["donor_name"] == "China"]
    years = list(range(2015, 2023))
    com = ch[(ch["source"] == "aiddata_gcdf") & (ch["flow_stage"] == "commitment")].groupby("yr")["usd"].sum()
    dis = ch[(ch["source"] == "nepal_dcr") & (ch["flow_stage"] == "disbursement") &
             (ch["counts_in_headline"].str.lower() == "true")].groupby("yr")["usd"].sum()
    china = {"years": years,
             "commitments": [round(com.get(y, 0) / 1e6, 1) for y in years],
             "disbursements": [round(dis.get(y, 0) / 1e6, 1) for y in years]}

    # sectors (CRS) by year
    sectors = {}
    for y in (2020, 2021, 2022, 2023):
        s = sec[(sec["year"] == y) & (sec["flow_stage"] == "disbursement") &
                (sec["source"] == "oecd_crs")].copy()
        s["amount_usd"] = num(s["amount_usd"])
        s = s.nlargest(10, "amount_usd")
        sectors[str(y)] = [{"name": row["sector"], "usd": round(row["amount_usd"] / 1e6, 1)}
                           for _, row in s.iterrows()]

    # KPIs
    anchor_2023 = next((x["anchor"] for x in reconciliation if x["year"] == 2023), None)
    peak = max((x for x in reconciliation if x["anchor"]), key=lambda x: x["anchor"])
    kpis = {
        "net_oda_2023": anchor_2023,
        "peak_year": peak["year"], "peak_value": peak["anchor"],
        "largest_partner": "World Bank (IDA)",
        "largest_nondac": "India", "largest_nondac_value": 99.8,
        "n_rows": len(core), "n_sources": core["source"].nunique(),
        "n_headline": int((core["counts_in_headline"].str.lower() == "true").sum()),
    }

    # curated (the coverage matrix has cross-source naming noise; state the real finding)
    nondac_missing = ["India", "China", "Saudi Fund", "Kuwait Fund (KFAED)",
                      "OPEC Fund (OFID)", "SAARC Development Fund"]

    discrepancies = [
        {"id": "D1", "comparison": "OECD DAC2A vs World Bank net ODA, 2023",
         "magnitude": "+3.5%", "verdict": "CONSISTENT",
         "cause": "Data vintage: the World Bank series is an earlier OECD snapshot."},
        {"id": "D3", "comparison": "Donor side (OECD net) vs recipient side (Nepal DCR)",
         "magnitude": "-33% to +15% by year", "verdict": "EXPLAINED",
         "cause": "DCR is gross and includes China/India/Gulf that OECD omits; Nepal fiscal year vs calendar; on/off-budget classification."},
        {"id": "D4", "comparison": "OECD CRS gross vs OECD DAC2A net",
         "magnitude": "1.12-1.30x", "verdict": "EXPECTED",
         "cause": "CRS is gross by activity; DAC2A net deducts loan principal repayments."},
        {"id": "D5", "comparison": "ADB: OECD net / ADB IATI gross / DCR, 2022",
         "magnitude": "$156m / $196m / $334m", "verdict": "EXPLAINED",
         "cause": "Net vs gross; ADB IATI excludes the TA Special Fund; DCR records gross loan disbursement."},
        {"id": "D6", "comparison": "US official ForeignAssistance.gov (FY) vs OECD ODA (CY), 2022",
         "magnitude": "$206m vs ~$130m", "verdict": "EXPLAINED",
         "cause": "ForeignAssistance.gov counts all US assistance (incl. non-ODA) by fiscal year; OECD counts ODA only by calendar year. New US obligations fell ~74% in FY2025 while disbursements held near $210m."},
        {"id": "D7", "comparison": "China: Nepal DCR disbursement vs AidData commitments",
         "magnitude": "DCR $14m (2022) vs AidData commitments up to $660m", "verdict": "KEY FINDING",
         "cause": "China's headline numbers are commitments/pledges; recorded disbursements are modest and fell after 2018."},
        {"id": "D8", "comparison": "India",
         "magnitude": "$99.8m recipient side; absent donor side", "verdict": "KEY FINDING",
         "cause": "India is a non-DAC donor and does not report to OECD CRS; only recipient-side reporting captures it."},
    ]

    sources = [
        {"name": "OECD DAC2A (ODA by recipient)", "side": "donor", "status": "high",
         "url": "https://sdmx.oecd.org/public/rest/data/OECD.DCD.FSD,DSD_DAC2@DF_DAC2A,/.NPL...?startPeriod=2015&endPeriod=2024&dimensionAtObservation=AllDimensions"},
        {"name": "World Bank net ODA received (DT.ODA.ODAT.CD)", "side": "donor", "status": "high",
         "url": "https://api.worldbank.org/v2/country/NPL/indicator/DT.ODA.ODAT.CD?format=json&date=2015:2024&per_page=100"},
        {"name": "OECD CRS (activity level)", "side": "donor", "status": "med",
         "url": "https://sdmx.oecd.org/dcd-public/rest/data/OECD.DCD.FSD,DSD_CRS@DF_CRS,/.NPL..."},
        {"name": "World Bank Projects", "side": "donor", "status": "med",
         "url": "https://search.worldbank.org/api/v3/projects?format=json&countrycode_exact=NP&rows=500"},
        {"name": "ADB IATI (XM-DAC-46004)", "side": "donor", "status": "med",
         "url": "https://www.adb.org/iati/iati-activities-np.xml"},
        {"name": "US ForeignAssistance.gov (official)", "side": "donor", "status": "med",
         "url": "https://foreignassistance.gov/cd/nepal"},
        {"name": "IATI via d-portal", "side": "donor", "status": "low",
         "url": "http://d-portal.org/q?from=act&country_code=NP&form=json"},
        {"name": "Nepal MoF Development Cooperation Report", "side": "recipient", "status": "low",
         "url": "https://giwmscdntwo.gov.np/media/pdf_upload/DCR%20Report%202022_23_pt2fped.pdf"},
        {"name": "AidData Global Chinese Development Finance v3.0", "side": "donor", "status": "low",
         "url": "https://www.aiddata.org/data/aiddatas-geospatial-global-chinese-development-finance-dataset-version-3-0"},
    ]

    data = {
        "meta": {"retrieved_at": "2026-06-03", "version": C.DATASET_VERSION,
                 "n_rows": kpis["n_rows"], "n_sources": kpis["n_sources"],
                 "n_headline": kpis["n_headline"]},
        "kpis": kpis, "reconciliation": reconciliation, "topDonors": topDonors,
        "china": china, "sectors": sectors, "nondac_missing": nondac_missing,
        "discrepancies": discrepancies, "sources": sources,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("window.NEPAL_DATA = " + json.dumps(data, indent=1) + ";\n")
    print(f"wrote {OUT} ({OUT.stat().st_size:,} bytes)")
    print(f"  reconciliation years: {[x['year'] for x in reconciliation]}")
    print(f"  KPIs: net ODA 2023 = ${kpis['net_oda_2023']}m, peak {kpis['peak_year']} ${kpis['peak_value']}m")


if __name__ == "__main__":
    main()
