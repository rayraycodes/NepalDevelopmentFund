#!/usr/bin/env python3
"""
91_us_localization.py — build the "where the money landed" summary (us_detail.js) from the
sub-award CSVs produced by 90_us_project_detail.py. Reads local CSVs only (no network).

Applies the official list of Nepal's 77 districts so the geography is real, not regex noise.
Leads with the ONWARD-FLOW story (money sub-granted to other organisations), which is solid.
Does NOT publish a USASpending spend rate — its outlay field is under-reported (a completed
award, SUAAHARA II, shows only 48%); the authoritative delivery figure is FA.gov's 81.6%.
"""
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C

NEPAL_DISTRICTS = {  # 77 districts
 "Achham","Arghakhanchi","Baglung","Baitadi","Bajhang","Bajura","Banke","Bara","Bardiya",
 "Bhaktapur","Bhojpur","Chitwan","Dadeldhura","Dailekh","Dang","Darchula","Dhading","Dhankuta",
 "Dhanusha","Dolakha","Dolpa","Doti","Gorkha","Gulmi","Humla","Ilam","Jajarkot","Jhapa","Jumla",
 "Kailali","Kalikot","Kanchanpur","Kapilvastu","Kaski","Kathmandu","Kavrepalanchok","Khotang",
 "Lalitpur","Lamjung","Mahottari","Makwanpur","Manang","Morang","Mugu","Mustang","Myagdi",
 "Nawalparasi","Nuwakot","Okhaldhunga","Palpa","Panchthar","Parbat","Parsa","Pyuthan","Ramechhap",
 "Rasuwa","Rautahat","Rolpa","Rukum","Rupandehi","Salyan","Sankhuwasabha","Saptari","Sarlahi",
 "Sindhuli","Sindhupalchok","Siraha","Solukhumbu","Sunsari","Surkhet","Syangja","Tanahun",
 "Taplejung","Terhathum","Udayapur","Parasi","Nawalpur"}
M = lambda v: round(v / 1e6, 2)


def main():
    subs = list(csv.DictReader(open(C.PROCESSED / "us_subawards.csv")))
    det = list(csv.DictReader(open(C.PROCESSED / "us_project_detail.csv")))

    by_sub, by_dist = defaultdict(float), defaultdict(float)
    n_dist_aware = 0
    for x in subs:
        amt = float(x["amount_usd"] or 0)
        by_sub[x["sub_recipient"]] += amt
        d = (x["district"] or "").strip().title()
        if d in NEPAL_DISTRICTS:
            by_dist[d] += amt
            n_dist_aware += 1

    tot_sub = sum(float(x["amount_usd"] or 0) for x in subs)
    tot_obl = sum(float(d["obligated_usd"] or 0) for d in det)
    top_sub = sorted(by_sub.items(), key=lambda kv: -kv[1])[:16]
    top_dist = sorted(by_dist.items(), key=lambda kv: -kv[1])[:12]

    data = {
        "meta": {"retrieved_at": C.utc_now(), "n_awards": len(det), "n_subawards": len(subs)},
        "headline": {"obligated_m": M(tot_obl), "subawarded_m": M(tot_sub),
                     "n_sub_orgs": len(by_sub),
                     "onward_pct": round(100 * tot_sub / tot_obl, 1) if tot_obl else None,
                     "n_districts": len(by_dist)},
        "top_sub": [{"name": n, "m": M(v)} for n, v in top_sub],
        "top_districts": [{"name": n, "m": M(v)} for n, v in top_dist],
    }
    out = C.ROOT / "report/dashboard/usforeignaiddata/us_detail.js"
    out.write_text("window.US_DETAIL = " + json.dumps(data) + ";\n")

    # full sub-award records for client-side drill-down (click a bar/row -> breakdown).
    # compact keys: s=sub-recipient, a=amount $, d=district, p=prime, j=project desc, w=prime award id
    desc_by_award = {d["award_id"]: d["desc"] for d in det}
    recs = []
    for x in subs:
        amt = float(x["amount_usd"] or 0)
        if amt <= 0:
            continue
        d = (x["district"] or "").strip().title()
        recs.append({"s": x["sub_recipient"], "a": round(amt),
                     "d": d if d in NEPAL_DISTRICTS else "",
                     "p": x["prime"], "w": x["prime_award"],
                     "j": desc_by_award.get(x["prime_award"], "")[:60]})
    sj = C.ROOT / "report/dashboard/usforeignaiddata/us_subawards.js"
    sj.write_text("window.US_SUBS = " + json.dumps(recs, separators=(",", ":")) + ";\n")
    print(f"  + us_subawards.js ({len(recs)} records, {sj.stat().st_size//1024} KB) for drill-down")
    print(f"onward-flow ${tot_sub/1e6:,.0f}m to {len(by_sub)} orgs "
          f"({100*tot_sub/tot_obl:.0f}% of the ${tot_obl/1e6:,.0f}m obligated) | "
          f"{len(by_dist)} Nepal districts named in {n_dist_aware} sub-awards")
    print("top districts:", [(n, M(v)) for n, v in top_dist[:6]])
    print(f"wrote {out.name}")


if __name__ == "__main__":
    main()
