#!/usr/bin/env python3
"""
86_us_dashboard_data.py — deep-granularity pull of OFFICIAL US foreign-assistance data for
Nepal and the data file for the /usforeignaiddata dashboard page.

Three country-filtered cuts of the same money from the ForeignAssistance.gov data-api (all
verified to reconcile to the dollar on FY2022 disbursements = 206,004,730):
  by-usg-sector.json        category + sector x transaction type x FY (current + constant USD)
  by-funding-agency.json    funding agency + BUDGET ACCOUNT x type x FY
  by-managing-agency.json   implementing (managing) agency x type x FY

Outputs:
  data/processed/us_by_account.csv            (agency, account, year, flow, current, constant)
  data/processed/us_by_usg_sector_detail.csv  (category, sector, year, flow, current, constant)
  data/processed/us_by_managing_agency.csv    (implementing agency, year, flow, current, constant)
  report/dashboard/usforeignaiddata/us_data.js
Only transaction types Obligations / Disbursements are kept (budget request and appropriation
types are plans, not flows). US fiscal year basis. FY2026 is partial.
"""
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C

SOURCE = "us_fa_deep"
BASE = "https://foreignassistance.gov/data-api/"
PAGE_URL = "https://foreignassistance.gov/cd/nepal"
FLOW = {"Obligations": "commitment", "Disbursements": "disbursement"}
OUT_JS = C.ROOT / "report" / "dashboard" / "usforeignaiddata" / "us_data.js"
Y0, Y1 = 2001, 2026          # full span the API carries
SY0 = 2015                   # series start for account/sector charts

# short display names for the big budget accounts (official names are long)
ACCT_SHORT = {
    "Economic Support Fund and Development Fund": "Economic Support Fund",
    "Agency for International Development, Development Assistance": "Development Assistance",
    "Agency for International Development, Global Health Programs": "Global Health (USAID)",
    "Department of State, Global Health Programs": "Global Health (State)",
    "Global Health Programs": "Global Health",
    "Agency for International Development, International Disaster Assistance": "Disaster Assistance",
    "Millennium Challenge Corporation": "MCC compact",
    "Department of Agriculture, Food for Peace Title II": "Food for Peace",
    "Food for Education": "Food for Education",
    "Department of State, International Narcotics Control and Law Enforcement": "Narcotics & Law Enf.",
    "Department of State, Nonproliferation, Antiterrorism, Demining and Related Programs": "Demining & Antiterror",
}


def short_acct(name: str) -> str:
    if name in ACCT_SHORT:
        return ACCT_SHORT[name]
    for k, v in ACCT_SHORT.items():
        if k in name:
            return v
    # generic shortening: drop the agency prefix before the first comma
    return (name.split(", ", 1)[1] if ", " in name and len(name) > 46 else name)[:46]


def pull(session, ep):
    rows, page = [], 1
    while True:
        r = C.get(session, BASE + ep, params={"country_code": "NPL", "per_page": 1000,
                                              "page": page}, accept="application/json", timeout=90)
        j = r.json()
        rows += j["data"]
        if page == 1:
            C.snapshot(SOURCE, ep.replace(".json", "_NPL_p1"), r.content, url=r.url,
                       params="country_code=NPL;per_page=1000", http_status=r.status_code, ext="json")
        if page >= j["page_info"]["total_pages"]:
            return rows
        page += 1


def keep(rows):
    out = []
    for x in rows:
        tt = x.get("transaction_type_name")
        if tt not in FLOW:
            continue
        try:
            y = int(x["fiscal_year"])
        except (TypeError, ValueError):
            continue
        if not (Y0 <= y <= Y1):
            continue
        cur = float(x["current_amount"] or 0)
        con = float(x["constant_amount"] or 0)
        out.append((FLOW[tt], y, cur, con, x))
    return out


def main():
    s = C.make_session()
    sec_rows = keep(pull(s, "by-usg-sector.json"))
    acc_rows = keep(pull(s, "by-funding-agency.json"))
    man_rows = keep(pull(s, "by-managing-agency.json"))
    retrieved = C.US_DATA_ASOF   # data vintage (deterministic), not wall-clock
    print(f"kept flow rows: sector={len(sec_rows)} account={len(acc_rows)} managing={len(man_rows)}")

    # ---- reconciliation across the three cuts (disbursements, by FY) ----
    def tot(rows, flow):
        d = defaultdict(float)
        for f, y, cur, _c, _x in rows:
            if f == flow:
                d[y] += cur
        return d
    ts, ta, tm = tot(sec_rows, "disbursement"), tot(acc_rows, "disbursement"), tot(man_rows, "disbursement")
    bad = [y for y in sorted(set(ts) | set(ta) | set(tm))
           if max(ts.get(y, 0), ta.get(y, 0), tm.get(y, 0)) - min(ts.get(y, 0), ta.get(y, 0), tm.get(y, 0)) > 1.0]
    print("cuts reconcile on disbursements:", "ALL YEARS OK" if not bad else f"MISMATCH {bad}")

    # ---- derive the constant-dollar base year (current == constant there) ----
    base_votes = defaultdict(int)
    for f, y, cur, con, _x in sec_rows:
        if cur and con and abs(cur - con) < 0.5:
            base_votes[y] += 1
    constant_base = max(base_votes, key=base_votes.get) if base_votes else None
    print("derived constant-USD base year:", constant_base)

    # ---- granular CSVs ----
    def wcsv(path, header, rows):
        with path.open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(header + ["source", "source_url", "retrieved_at"])
            for r in rows:
                w.writerow(list(r) + [SOURCE, PAGE_URL, retrieved])
        print(f"  wrote {path.name} ({len(rows)} rows)")

    wcsv(C.PROCESSED / "us_by_account.csv",
         ["funding_agency", "funding_account", "year", "flow_stage", "amount_usd", "amount_usd_constant"],
         sorted((x.get("funding_agency_acronym", ""), x.get("funding_account_name", ""), y, f,
                 round(cur, 2), round(con, 2)) for f, y, cur, con, x in acc_rows))
    wcsv(C.PROCESSED / "us_by_usg_sector_detail.csv",
         ["usg_category", "usg_sector", "year", "flow_stage", "amount_usd", "amount_usd_constant"],
         sorted((x.get("usg_category_name", ""), x.get("usg_sector_name", ""), y, f,
                 round(cur, 2), round(con, 2)) for f, y, cur, con, x in sec_rows))
    wcsv(C.PROCESSED / "us_by_managing_agency.csv",
         ["implementing_agency_acronym", "implementing_agency_name", "year", "flow_stage",
          "amount_usd", "amount_usd_constant"],
         sorted((x.get("implementing_agency_acronym", ""), x.get("implementing_agency_name", ""), y, f,
                 round(cur, 2), round(con, 2)) for f, y, cur, con, x in man_rows))

    years_all = list(range(Y0, Y1 + 1))
    years_s = list(range(SY0, Y1 + 1))
    M = lambda v: round(v / 1e6, 2)

    # ---- flows: obligations vs disbursements (current) + constant disbursements ----
    ob, di, dic = tot(acc_rows, "commitment"), ta, defaultdict(float)
    for f, y, _cur, con, _x in acc_rows:
        if f == "disbursement":
            dic[y] += con
    flows = [{"y": y, "ob": M(ob.get(y, 0)), "di": M(di.get(y, 0)), "dic": M(dic.get(y, 0))}
             for y in years_all]

    # ---- accounts: series (top by total disb 2015+), sankey links, FY24->26 cuts ----
    acct_tot = defaultdict(float)
    acct_agency = {}
    per = defaultdict(lambda: defaultdict(float))           # (acct)(year) -> disb
    per_ob = defaultdict(lambda: defaultdict(float))        # (acct)(year) -> obligations
    links = defaultdict(lambda: defaultdict(float))         # (year)(agency, acct) -> disb
    for f, y, cur, _c, x in acc_rows:
        acct = short_acct(x.get("funding_account_name", ""))
        ag = x.get("funding_agency_acronym", "")
        acct_agency.setdefault(acct, ag)
        if f == "disbursement":
            if y >= SY0:
                per[acct][y] += cur
                links[y][(ag, acct)] += cur
            acct_tot[acct] += cur if y >= SY0 else 0
        else:
            per_ob[acct][y] += cur
    top_accts = sorted(acct_tot, key=acct_tot.get, reverse=True)[:9]
    series = [{"name": a, "agency": acct_agency.get(a, ""),
               "data": [M(per[a].get(y, 0)) for y in years_s]} for a in top_accts]
    other = [M(sum(per[a].get(y, 0) for a in per if a not in top_accts)) for y in years_s]
    series.append({"name": "Other", "agency": "", "data": other})

    sankey = {}
    for y in years_s:
        ls = [{"ag": ag, "acct": acct, "v": M(v)} for (ag, acct), v in links[y].items() if v >= 100000]
        sankey[str(y)] = sorted(ls, key=lambda l: -l["v"])[:18]

    cuts = []
    for a in sorted(per_ob, key=lambda a: -per_ob[a].get(2024, 0)):
        ob24, ob25, ob26 = (per_ob[a].get(y, 0) for y in (2024, 2025, 2026))
        if max(ob24, ob25, ob26) < 1e6:
            continue
        cuts.append({"acct": a, "agency": acct_agency.get(a, ""),
                     "ob24": M(ob24), "ob25": M(ob25), "ob26": M(ob26)})

    # ---- sectors: category -> sector treemap per year (disbursements) ----
    sectors = {}
    for y in years_s:
        tree = defaultdict(lambda: defaultdict(float))
        for f, yy, cur, _c, x in sec_rows:
            if f == "disbursement" and yy == y and cur > 0:
                tree[x.get("usg_category_name", "")][x.get("usg_sector_name", "")] += cur
        sectors[str(y)] = [{"cat": c, "sec": sec, "v": M(v)}
                           for c, secs in tree.items() for sec, v in secs.items() if v >= 50000]

    # ---- managing (implementing) agency series ----
    man = defaultdict(lambda: defaultdict(float))
    for f, y, cur, _c, x in man_rows:
        if f == "disbursement" and y >= SY0:
            man[x.get("implementing_agency_acronym", "")][y] += cur
    man_top = sorted(man, key=lambda a: -sum(man[a].values()))[:6]
    managing = [{"name": a, "data": [M(man[a].get(y, 0)) for y in years_s]} for a in man_top]
    mo = [M(sum(man[a].get(y, 0) for a in man if a not in man_top)) for y in years_s]
    managing.append({"name": "Other", "data": mo})

    # ---- the funnel: promise -> delivery -> purpose (cumulative FY2015-26) ----
    ob_tot = {a: sum(per_ob[a].get(y, 0) for y in years_s) for a in per_ob}
    di_tot = {a: sum(per[a].get(y, 0) for y in years_s) for a in per}
    fun_accts = []
    for a in sorted(ob_tot, key=ob_tot.get, reverse=True)[:10]:
        ob_a, di_a = ob_tot.get(a, 0), di_tot.get(a, 0)
        if ob_a < 5e6:
            continue
        fun_accts.append({"acct": a, "agency": acct_agency.get(a, ""),
                          "ob": M(ob_a), "di": M(di_a),
                          "rate": round(100 * di_a / ob_a, 1) if ob_a else None})
    overall_ob = sum(ob.get(y, 0) for y in years_s)
    overall_di = sum(di.get(y, 0) for y in years_s)
    # purpose split: USG categories of DELIVERED money; "Program Support" = explicit admin lines
    cat_di = defaultdict(float)
    for f, y, cur, _c, x in sec_rows:
        if f == "disbursement" and y >= SY0:
            cat_di[x.get("usg_category_name", "")] += cur
    purpose = [{"cat": c, "di": M(v)} for c, v in sorted(cat_di.items(), key=lambda kv: -kv[1])]
    support_di = cat_di.get("Program Support", 0)
    mcc_di_tot = di_tot.get("MCC compact", 0)
    funnel = {"overall": {"ob": M(overall_ob), "di": M(overall_di),
                          "rate": round(100 * overall_di / overall_ob, 1)},
              "accounts": fun_accts, "purpose": purpose,
              "support_share": round(100 * support_di / sum(cat_di.values()), 1),
              "mcc": {"ob": M(per_ob["MCC compact"].get(2023, 0) + per_ob["MCC compact"].get(2024, 0)),
                      "di": M(mcc_di_tot)}}

    # ---- people vs system vs machine: a TRANSPARENT 3-way classification of every
    # USG sector (published in full on the page; contestable by design) ----
    # people  = the immediate object of spending is a person (care, food, classroom, cash, water)
    # system  = building institutions/assets AROUND people (governance, infrastructure,
    #           policies, security, markets, environment, surveillance, preparedness)
    # machine = running the aid operation itself (admin, oversight, M&E)
    PEOPLE = {"Nutrition", "Maternal and Child Health", "Family Planning and Reproductive Health",
              "HIV/AIDS", "Malaria", "Water Supply and Sanitation", "Basic Education",
              "Higher Education", "Social Assistance", "Social Services",
              "Protection, Assistance and Solutions", "Agriculture",
              "Health - General", "Education and Social Services - General",
              "Humanitarian Assistance - General", "Economic Opportunity"}
    MACHINE_CATS = {"Program Support"}
    def cls(cat, sec):
        if cat in MACHINE_CATS:
            return "machine"
        return "people" if sec in PEOPLE else "system"

    ppl_year = defaultdict(lambda: defaultdict(float))   # year -> class -> usd
    ppl_cat = defaultdict(lambda: defaultdict(float))    # category -> class -> usd
    classmap = defaultdict(float)                        # (cat, sec, class) -> usd
    for f, y, cur, _c, x in sec_rows:
        if f != "disbursement" or y < SY0:
            continue
        cat, sec = x.get("usg_category_name", ""), x.get("usg_sector_name", "")
        k = cls(cat, sec)
        ppl_year[y][k] += cur
        ppl_cat[cat][k] += cur
        classmap[(cat, sec, k)] += cur
    tot_all = sum(sum(v.values()) for v in ppl_year.values())
    split = {k: round(100 * sum(ppl_year[y][k] for y in ppl_year) / tot_all, 1)
             for k in ("people", "system", "machine")}
    people = {
        "split": split,
        "byYear": [{"y": y, "people": M(ppl_year[y]["people"]), "system": M(ppl_year[y]["system"]),
                    "machine": M(ppl_year[y]["machine"])} for y in sorted(ppl_year)],
        "byCat": [{"cat": c, "people": M(v["people"]), "system": M(v["system"]),
                   "machine": M(v["machine"])}
                  for c, v in sorted(ppl_cat.items(), key=lambda kv: -sum(kv[1].values()))
                  if sum(v.values()) >= 1e6],
        "classmap": [{"cat": c, "sec": s, "cls": k, "di": M(v)}
                     for (c, s, k), v in sorted(classmap.items(), key=lambda kv: -kv[1])
                     if v >= 50000],
    }

    # ---- KPIs + analysis prints ----
    total15 = sum(di.get(y, 0) for y in range(SY0, Y1 + 1))
    peak_y = max((y for y in years_all if y <= 2025), key=lambda y: di.get(y, 0))
    mcc_ob23 = per_ob.get("MCC compact", {}).get(2023, 0)
    ida15_16 = per["Disaster Assistance"].get(2015, 0) + per["Disaster Assistance"].get(2016, 0)
    n_act24 = sum(1 for a in per if per[a].get(2024, 0) > 1e5)
    n_act26 = sum(1 for a in per if per[a].get(2026, 0) > 1e5)
    kpis = {"total_2015_2026": M(total15), "peak_year": peak_y, "peak": M(di.get(peak_y, 0)),
            "mcc_ob_2023": M(mcc_ob23), "quake_disaster_15_16": M(ida15_16),
            "accounts_2024": n_act24, "accounts_2026": n_act26, "constant_base": constant_base}
    print("\nANALYSIS:")
    print(f"  total disbursed FY2015-26: ${total15/1e6:,.0f}m | peak FY{peak_y} ${di.get(peak_y,0)/1e6:,.1f}m")
    print(f"  MCC obligation FY2023: ${mcc_ob23/1e6:,.1f}m | earthquake Disaster Assistance FY15+16: ${ida15_16/1e6:,.1f}m")
    print(f"  accounts active (> $0.1m disb): FY2024 = {n_act24} -> FY2026 = {n_act26}")
    print("  top accounts by FY2015-26 disb:", [(a, round(acct_tot[a]/1e6,1)) for a in top_accts[:6]])

    data = {"meta": {"retrieved_at": retrieved, "page": PAGE_URL,
                     "endpoints": ["by-usg-sector.json", "by-funding-agency.json", "by-managing-agency.json"],
                     "years_all": years_all, "years": years_s, "fy26_partial": True,
                     "constant_base": constant_base},
            "kpis": kpis, "flows": flows, "accounts": {"series": series, "sankey": sankey, "cuts": cuts},
            "sectors": sectors, "managing": managing, "funnel": funnel, "people": people}
    OUT_JS.parent.mkdir(parents=True, exist_ok=True)
    OUT_JS.write_text("window.US_DATA = " + json.dumps(data) + ";\n")
    print(f"\nwrote {OUT_JS} ({OUT_JS.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
