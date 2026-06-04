#!/usr/bin/env python3
"""
80_figures.py — generate report figures from the processed series into report/figures/.
Read-only on data; writes PNGs only. Uses the non-interactive Agg backend.
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C

FIG = C.ROOT / "report" / "figures"
FIG.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"figure.dpi": 130, "font.size": 10, "axes.grid": True,
                     "grid.alpha": 0.3, "axes.axisbelow": True})

core = pd.read_csv(C.PROCESSED / "core_long.csv", dtype=str, keep_default_na=False)
core["usd"] = pd.to_numeric(core["amount_usd"].replace("", "0"), errors="coerce").fillna(0.0)
core["yr"] = pd.to_numeric(core["year"], errors="coerce")
recon = pd.read_csv(C.PROCESSED / "reconciliation_donor_vs_recipient.csv")
donyr = pd.read_csv(C.PROCESSED / "agg_by_donor_year.csv")
secyr = pd.read_csv(C.PROCESSED / "agg_by_sector_year.csv")


def m(x):
    return x / 1e6


# --- Fig 1: donor vs recipient vs anchor, by year ---
def fig1():
    r = recon.copy()
    for c in ("donor_side_usd", "recipient_side_usd", "anchor_usd"):
        r[c] = pd.to_numeric(r[c], errors="coerce")
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(r["year"], m(r["anchor_usd"]), "o-", color="#444", lw=2,
            label="World Bank net ODA received (anchor)")
    ax.plot(r["year"], m(r["donor_side_usd"]), "s-", color="#1f77b4", lw=2,
            label="Donor side: OECD DAC2A (net)")
    ax.plot(r["year"], m(r["recipient_side_usd"]), "^-", color="#d62728", lw=2,
            label="Recipient side: Nepal DCR (gross, incl. China/India)")
    ax.set_title("Development funding to Nepal: donor side vs recipient side vs anchor")
    ax.set_xlabel("Year (calendar; Nepal DCR by FY start year)")
    ax.set_ylabel("US$ millions, current")
    ax.legend(loc="lower right", fontsize=8.5)
    ax.set_ylim(0, None)
    fig.tight_layout(); fig.savefig(FIG / "fig1_donor_vs_recipient.png"); plt.close(fig)


# --- Fig 2: top donors 2022, donor side vs recipient side ---
def fig2():
    d = donyr[(donyr["year"] == 2022) & (donyr["flow_stage"] == "disbursement") &
              (donyr["side"] == "donor")].nlargest(10, "amount_usd")
    r = donyr[(donyr["year"] == 2022) & (donyr["flow_stage"] == "disbursement") &
              (donyr["side"] == "recipient")].nlargest(10, "amount_usd")
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 5.2))
    a1.barh(d["donor_name"][::-1], m(d["amount_usd"])[::-1], color="#1f77b4")
    a1.set_title("Donor side — OECD DAC2A, CY2022 (net)")
    a1.set_xlabel("US$ m")
    a2.barh(r["donor_name"][::-1], m(r["amount_usd"])[::-1], color="#d62728")
    a2.set_title("Recipient side — Nepal DCR, FY2022/23 (gross)")
    a2.set_xlabel("US$ m")
    fig.suptitle("Top donors to Nepal, 2022 (note: ranking agrees; India is recipient-side only)")
    fig.tight_layout(); fig.savefig(FIG / "fig2_top_donors_2022.png"); plt.close(fig)


# --- Fig 3: China commitments (AidData) vs disbursements (DCR) ---
def fig3():
    ch = core[core["donor_name"] == "China"]
    com = (ch[(ch["source"] == "aiddata_gcdf") & (ch["flow_stage"] == "commitment")]
           .groupby("yr")["usd"].sum())
    dis = (ch[(ch["source"] == "nepal_dcr") & (ch["flow_stage"] == "disbursement") &
              (ch["counts_in_headline"].str.lower() == "true")].groupby("yr")["usd"].sum())
    yrs = list(range(2015, 2023))
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar([y - 0.2 for y in yrs], [m(com.get(y, 0)) for y in yrs], width=0.4,
           color="#ff7f0e", label="China commitments (AidData GCDF v3.0)")
    ax.bar([y + 0.2 for y in yrs], [m(dis.get(y, 0)) for y in yrs], width=0.4,
           color="#d62728", label="China disbursements recorded by Nepal (DCR)")
    ax.set_title("China and Nepal: large commitments, modest recorded disbursements")
    ax.set_xlabel("Year"); ax.set_ylabel("US$ millions"); ax.legend()
    fig.tight_layout(); fig.savefig(FIG / "fig3_china.png"); plt.close(fig)


# --- Fig 4: sector composition 2022 (CRS) ---
def fig4():
    s = secyr[(secyr["year"] == 2022) & (secyr["flow_stage"] == "disbursement") &
              (secyr["source"] == "oecd_crs")].nlargest(10, "amount_usd")
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.barh(s["sector"][::-1], m(s["amount_usd"])[::-1], color="#2ca02c")
    ax.set_title("Sector composition of aid to Nepal, 2022 (OECD CRS gross disbursement)")
    ax.set_xlabel("US$ millions")
    fig.tight_layout(); fig.savefig(FIG / "fig4_sectors_2022.png"); plt.close(fig)


# --- Fig 5: donor vs recipient gap % by year ---
def fig5():
    r = recon.dropna(subset=["gap_pct"]).copy()
    r["gap_pct"] = pd.to_numeric(r["gap_pct"], errors="coerce")
    colors = ["#d62728" if v < 0 else "#1f77b4" for v in r["gap_pct"]]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(r["year"], r["gap_pct"], color=colors)
    ax.axhline(0, color="#333", lw=0.8)
    ax.set_title("Donor minus recipient gap (negative = Nepal reports receiving more)")
    ax.set_xlabel("Year"); ax.set_ylabel("Gap, % of recipient-side total")
    fig.tight_layout(); fig.savefig(FIG / "fig5_gap.png"); plt.close(fig)


# --- Fig 6: US assistance by agency (stacked), the USAID -> MCC shift ---
def fig6():
    path = C.PROCESSED / "us_by_agency.csv"
    if not path.exists():
        return
    a = pd.read_csv(path)
    a = a[a["flow_stage"] == "disbursement"].copy()
    a["amount_usd"] = pd.to_numeric(a["amount_usd"], errors="coerce").fillna(0)
    a["year"] = pd.to_numeric(a["year"], errors="coerce")
    years = list(range(2018, 2027))
    totals = a.groupby("agency_acronym")["amount_usd"].sum().sort_values(ascending=False)
    top = list(totals.index[:5])
    disp = {"USAID": "USAID", "STATE": "State", "MCC": "MCC", "AGR": "USDA", "PC": "Peace Corps"}
    colors = ["#2563eb", "#0e7c86", "#f59e0b", "#0f9d58", "#94a3b8", "#cbd5e1"]
    fig, ax = plt.subplots(figsize=(9, 5))
    bottom = [0] * len(years)
    series = [(disp.get(ac, ac), [a[(a.agency_acronym == ac) & (a.year == y)]["amount_usd"].sum() / 1e6 for y in years]) for ac in top]
    oth = [a[(~a.agency_acronym.isin(top)) & (a.year == y)]["amount_usd"].sum() / 1e6 for y in years]
    series.append(("Other", oth))
    for (name, vals), col in zip(series, colors):
        ax.bar(years, vals, bottom=bottom, label=name, color=col)
        bottom = [b + v for b, v in zip(bottom, vals)]
    ax.set_title("US assistance to Nepal by agency: the shift to MCC (disbursements)")
    ax.set_xlabel("US fiscal year (FY2026 partial)"); ax.set_ylabel("US$ millions")
    ax.legend(fontsize=8, ncol=3)
    fig.tight_layout(); fig.savefig(FIG / "fig6_us_agency.png"); plt.close(fig)


if __name__ == "__main__":
    for f in (fig1, fig2, fig3, fig4, fig5, fig6):
        f(); print(f"  wrote {f.__name__}")
    print("figures ->", FIG)
