#!/usr/bin/env python3
"""
93_search_index.py — build ONE cross-dataset search index for the whole site.

Reads only local, already-verified artifacts (no network):
  data/processed/us_project_detail.csv   primes + projects (four amounts, deadlines, sub-stats)
  data/processed/us_subawards.csv         sub-recipients, districts, prime<->sub<->project edges
  report/dashboard/usforeignaiddata/us_projects.js   full award ledger (links, agency, status)
  report/dashboard/usforeignaiddata/us_data.js       budget accounts (obligated vs delivered)
  report/dashboard/usforeignaiddata/audits.js        OIG audits
  report/dashboard/data.js                            donors, sectors, sources, China (main board)

Writes report/dashboard/search_index.js  ->  window.SEARCH_INDEX = [...]

Every figure is AGGREGATED from the same data the dashboards already display; nothing is
invented. Organisations are merged across the prime and sub-recipient roles only when their
normalised names match (conservative: we would rather show two honest entries than merge two
different organisations into one). Each entry carries everything its profile card needs, so the
search works identically on both pages without loading the page-specific drill data.
"""
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C

DASH = C.ROOT / "report/dashboard"
US = DASH / "usforeignaiddata"

# --- helpers --------------------------------------------------------------
def load_js_global(path):
    """report/dashboard/*.js files are `window.NAME = <pure JSON>;`."""
    txt = Path(path).read_text()
    return json.loads(txt.split("=", 1)[1].rstrip().rstrip("\n").rstrip(";"))

REDACT = re.compile(r"redact", re.I)
STOP = {"INC", "INCORPORATED", "LLC", "LTD", "LIMITED", "CORP", "CORPORATION",
        "CO", "PVT", "PRIVATE", "THE", "AND", "OF", "A"}

def norm(name):
    """Conservative normaliser for merging an org's prime and sub-recipient roles."""
    toks = re.sub(r"[^A-Z0-9 ]", " ", (name or "").upper()).split()
    return " ".join(t for t in toks if t not in STOP)

def topn(d, n=10):
    return [{"n": k, "a": round(v)} for k, v in sorted(d.items(), key=lambda kv: -kv[1])[:n] if k]

# The official 77 districts (same whitelist 91_us_localization.py applies) so the search
# surfaces REAL geography, not regex noise from the sub-award descriptions.
NEPAL_DISTRICTS = {
 "Achham", "Arghakhanchi", "Baglung", "Baitadi", "Bajhang", "Bajura", "Banke", "Bara", "Bardiya",
 "Bhaktapur", "Bhojpur", "Chitwan", "Dadeldhura", "Dailekh", "Dang", "Darchula", "Dhading", "Dhankuta",
 "Dhanusha", "Dolakha", "Dolpa", "Doti", "Gorkha", "Gulmi", "Humla", "Ilam", "Jajarkot", "Jhapa", "Jumla",
 "Kailali", "Kalikot", "Kanchanpur", "Kapilvastu", "Kaski", "Kathmandu", "Kavrepalanchok", "Khotang",
 "Lalitpur", "Lamjung", "Mahottari", "Makwanpur", "Manang", "Morang", "Mugu", "Mustang", "Myagdi",
 "Nawalparasi", "Nuwakot", "Okhaldhunga", "Palpa", "Panchthar", "Parbat", "Parsa", "Pyuthan", "Ramechhap",
 "Rasuwa", "Rautahat", "Rolpa", "Rukum", "Rupandehi", "Salyan", "Sankhuwasabha", "Saptari", "Sarlahi",
 "Sindhuli", "Sindhupalchok", "Siraha", "Solukhumbu", "Sunsari", "Surkhet", "Syangja", "Tanahun",
 "Taplejung", "Terhathum", "Udayapur", "Parasi", "Nawalpur"}

# Official Nepali names for districts, used only as SEARCH ALIASES (never as a figure),
# so a transcription slip can at worst miss a match — it can never corrupt a number.
DISTRICT_NE = {
    "Kathmandu": "काठमाडौं", "Lalitpur": "ललितपुर", "Bhaktapur": "भक्तपुर",
    "Kavrepalanchok": "काभ्रेपलाञ्चोक", "Sindhupalchok": "सिन्धुपाल्चोक", "Dolakha": "दोलखा",
    "Ramechhap": "रामेछाप", "Sindhuli": "सिन्धुली", "Makwanpur": "मकवानपुर", "Chitwan": "चितवन",
    "Dhading": "धादिङ", "Nuwakot": "नुवाकोट", "Rasuwa": "रसुवा", "Gorkha": "गोरखा",
    "Lamjung": "लमजुङ", "Tanahun": "तनहुँ", "Kaski": "कास्की", "Manang": "मनाङ",
    "Mustang": "मुस्ताङ", "Myagdi": "म्याग्दी", "Parbat": "पर्वत", "Baglung": "बागलुङ",
    "Gulmi": "गुल्मी", "Palpa": "पाल्पा", "Syangja": "स्याङ्जा", "Arghakhanchi": "अर्घाखाँची",
    "Nawalparasi": "नवलपरासी", "Rupandehi": "रुपन्देही", "Kapilvastu": "कपिलवस्तु",
    "Dang": "दाङ", "Pyuthan": "प्युठान", "Rolpa": "रोल्पा", "Rukum": "रुकुम",
    "Salyan": "सल्यान", "Banke": "बाँके", "Bardiya": "बर्दिया", "Surkhet": "सुर्खेत",
    "Dailekh": "दैलेख", "Jajarkot": "जाजरकोट", "Jumla": "जुम्ला", "Kalikot": "कालिकोट",
    "Mugu": "मुगु", "Humla": "हुम्ला", "Dolpa": "डोल्पा", "Kailali": "कैलाली",
    "Kanchanpur": "कञ्चनपुर", "Achham": "अछाम", "Doti": "डोटी", "Bajura": "बाजुरा",
    "Bajhang": "बझाङ", "Darchula": "दार्चुला", "Baitadi": "बैतडी", "Dadeldhura": "डडेल्धुरा",
    "Morang": "मोरङ", "Sunsari": "सुनसरी", "Jhapa": "झापा", "Ilam": "इलाम",
    "Udayapur": "उदयपुर", "Saptari": "सप्तरी", "Siraha": "सिराहा", "Dhanusha": "धनुषा",
    "Mahottari": "महोत्तरी", "Sarlahi": "सर्लाही", "Rautahat": "रौतहट", "Bara": "बारा",
    "Parsa": "पर्सा", "Sankhuwasabha": "संखुवासभा", "Bhojpur": "भोजपुर", "Khotang": "खोटाङ",
    "Okhaldhunga": "ओखलढुंगा", "Solukhumbu": "सोलुखुम्बु", "Taplejung": "ताप्लेजुङ",
    "Panchthar": "पाँचथर", "Terhathum": "तेह्रथुम", "Dhankuta": "धनकुटा", "Dolpo": "डोल्पा",
}


def main():
    detail = list(csv.DictReader(open(C.PROCESSED / "us_project_detail.csv")))
    subs = list(csv.DictReader(open(C.PROCESSED / "us_subawards.csv")))
    projects_js = load_js_global(US / "us_projects.js")
    us_data = load_js_global(US / "us_data.js")
    audits = load_js_global(US / "audits.js")
    main_data = load_js_global(DASH / "data.js")
    # org -> financial-accountability records (FAC Single Audits + OIG), keyed by the same norm
    org_audits_path = C.PROCESSED / "org_audits.json"
    ORG_AUDITS = json.loads(org_audits_path.read_text()) if org_audits_path.exists() else {}

    # award_id -> ledger metadata (link, agency, status, $m) for every named award
    award_meta = {}
    for a in projects_js["list"]:
        aid = a["link"].split("/award/")[1] if a.get("link") else None
        if aid:
            award_meta[aid] = a

    # ---- aggregate the sub-award graph -----------------------------------
    sub_recv = defaultdict(float)                 # sub-recipient -> $ received
    sub_from = defaultdict(lambda: defaultdict(float))   # sub -> {prime: $}
    sub_dist = defaultdict(lambda: defaultdict(float))   # sub -> {district: $}
    sub_proj = defaultdict(lambda: defaultdict(float))   # sub -> {project: $}
    sub_n = defaultdict(int)
    dist_total = defaultdict(float)               # district -> $
    dist_orgs = defaultdict(lambda: defaultdict(float))  # district -> {org: $}
    dist_primes = defaultdict(lambda: defaultdict(float))
    dist_n = defaultdict(int)
    proj_subs = defaultdict(lambda: defaultdict(float))  # award_id -> {sub: $}
    proj_dist = defaultdict(lambda: defaultdict(float))  # award_id -> {district: $}
    desc_by_award = {d["award_id"]: d["desc"] for d in detail}

    for x in subs:
        amt = float(x["amount_usd"] or 0)
        if amt <= 0:
            continue
        s, p, w = x["sub_recipient"], x["prime"], x["prime_award"]
        d = (x["district"] or "").strip().title()
        if d not in NEPAL_DISTRICTS:           # drop regex noise; keep only real districts
            d = ""
        proj = desc_by_award.get(w, "")
        sub_recv[s] += amt; sub_n[s] += 1
        sub_from[s][p] += amt
        if proj:
            sub_proj[s][proj] += amt
        proj_subs[w][s] += amt
        if d:
            sub_dist[s][d] += amt
            dist_total[d] += amt; dist_n[d] += 1
            dist_orgs[d][s] += amt; dist_primes[d][p] += amt
            proj_dist[w][d] += amt

    # ---- primes (from the project detail) --------------------------------
    prime_obl = defaultdict(float); prime_out = defaultdict(float)
    prime_onward = defaultdict(float)
    prime_awards = defaultdict(list)
    for d in detail:
        rec = d["recipient"]
        if not rec or REDACT.search(rec):
            continue
        obl = float(d["obligated_usd"] or 0); out = float(d["outlayed_usd"] or 0)
        prime_obl[rec] += obl; prime_out[rec] += out
        prime_onward[rec] += float(d["subawarded_usd"] or 0)
        prime_awards[rec].append({
            "j": d["desc"], "o": round(out), "b": round(obl),
            "s": d["start"], "e": d["deadline"], "st": d["status"], "w": d["award_id"]})

    # ---- merge prime + sub roles into one organisation entity ------------
    orgs = {}   # norm_key -> entity dict
    def org(key, display):
        if key not in orgs:
            orgs[key] = {"name": display, "alias": set(), "prime": None, "sub": None}
        orgs[key]["alias"].add(display)
        return orgs[key]

    for rec in sorted(set(list(prime_obl) + list(prime_onward))):   # sorted -> deterministic merge
        o = org(norm(rec), rec)
        aw = sorted(prime_awards[rec], key=lambda a: -a["b"])[:8]
        o["prime"] = {"obl": round(prime_obl[rec]), "out": round(prime_out[rec]),
                      "onward": round(prime_onward[rec]), "n": len(prime_awards[rec]), "aw": aw}
        if not REDACT.search(o["name"]) and rec[0].isupper() and rec.lower() != rec:
            o["name"] = rec  # prefer the nicely-cased prime name as the display name

    for s in sub_recv:
        o = org(norm(s), s)
        # keep the largest existing sub role if two names merge to one org
        if not o["sub"] or sub_recv[s] > o["sub"]["recv"]:
            o["sub"] = {"recv": round(sub_recv[s]), "n": sub_n[s], "sname": s,
                        "from": topn(sub_from[s]), "dist": topn(sub_dist[s]),
                        "proj": topn(sub_proj[s])}

    index = []
    for key, o in orgs.items():
        amt = max((o["prime"] or {}).get("obl", 0), (o["sub"] or {}).get("recv", 0))
        roles = []
        if o["prime"]:
            roles.append("prime")
        if o["sub"]:
            roles.append("sub")
        entry = {"i": "org:" + key, "t": "org", "n": o["name"],
                 "k": sorted(o["alias"]), "a": amt, "g": "us",
                 "p": {"prime": o["prime"], "sub": o["sub"], "roles": roles}}
        aud = ORG_AUDITS.get(key)        # small -> kept at top level so it loads on BOTH pages
        if aud and (aud.get("fac") or aud.get("oig")):
            entry["audit"] = {k2: aud[k2] for k2 in ("fac", "oig") if aud.get(k2)}
        index.append(entry)

    # ---- districts -------------------------------------------------------
    for d, tot in dist_total.items():
        ne = DISTRICT_NE.get(d, "")
        index.append({"i": "dist:" + d, "t": "district", "n": d, "ne": ne,
                      "k": [d] + ([ne] if ne else []), "a": round(tot), "g": "us", "h": "#landed",
                      "p": {"landed": round(tot), "n": dist_n[d],
                            "orgs": topn(dist_orgs[d]), "primes": topn(dist_primes[d])}})

    # ---- projects (detailed first, then any other named ledger award) ----
    seen_aw = set()
    for d in detail:
        aid = d["award_id"]; seen_aw.add(aid)
        meta = award_meta.get(aid, {})
        name = d["desc"] if d["desc"] and not REDACT.search(d["desc"]) else (
            (d["recipient"] + " award") if d["recipient"] and not REDACT.search(d["recipient"])
            else (meta.get("agency", "US") + " award"))
        index.append({"i": "proj:" + aid, "t": "project", "n": name,
                      "k": [name, d["recipient"], meta.get("agency", "")],
                      "a": round(float(d["obligated_usd"] or 0)), "g": "us", "h": "#projects", "d": aid,
                      "p": {"o": round(float(d["outlayed_usd"] or 0)),
                            "b": round(float(d["obligated_usd"] or 0)),
                            "c": round(float(d["current_award_usd"] or 0)),
                            "pt": round(float(d["potential_award_usd"] or 0)),
                            "e": d["deadline"], "s": d["start"], "st": d["status"],
                            "rec": d["recipient"], "ag": meta.get("agency", ""),
                            "link": meta.get("link", ""),
                            "subs": topn(proj_subs[aid]), "dist": topn(proj_dist[aid]),
                            "onward": round(float(d["subawarded_usd"] or 0)),
                            "nsub": int(d["n_subawards"] or 0)}})
    for aid, a in award_meta.items():
        if aid in seen_aw:
            continue
        desc = a.get("desc", "")
        if not desc or REDACT.search(desc):
            if REDACT.search(a.get("recipient", "")):
                continue
        name = desc if desc and not REDACT.search(desc) else a.get("recipient") or (a.get("agency", "US") + " award")
        index.append({"i": "proj:" + aid, "t": "project", "n": name,
                      "k": [name, a.get("recipient", ""), a.get("agency", "")],
                      "a": round(float(a.get("usd", 0)) * 1e6), "g": "us", "h": "#projects", "d": aid,
                      "p": {"b": round(float(a.get("usd", 0)) * 1e6), "rec": a.get("recipient", ""),
                            "ag": a.get("agency", ""), "st": a.get("status", ""),
                            "s": a.get("start", ""), "e": a.get("end", ""), "link": a.get("link", ""),
                            "light": 1}})

    # ---- donors (main board, donor side) ---------------------------------
    donor_years = main_data["topDonors"]["donor"]
    donor_series = defaultdict(dict)
    for yr, rows in donor_years.items():
        for r in rows:
            donor_series[r["name"]][yr] = r["usd"]
    for name, ser in donor_series.items():
        yrs = sorted(ser)
        latest = yrs[-1]
        alias = [name]
        m = re.search(r"\[([^\]]+)\]", name)          # e.g. "... [IDA]"
        if m:
            alias.append(m.group(1)); alias.append(re.sub(r"\s*\[[^\]]+\]", "", name))
        index.append({"i": "donor:" + name, "t": "donor", "n": re.sub(r"\s*\[[^\]]+\]", "", name),
                      "k": alias, "a": round(ser[latest] * 1e6), "g": "main", "h": "#donors",
                      "p": {"latest_usd": round(ser[latest] * 1e6), "year": latest,
                            "series": [{"y": y, "m": ser[y]} for y in yrs]}})

    # China & India appear only on the recipient side; surface them explicitly.
    ch = main_data.get("china", {})
    if ch.get("years"):
        index.append({"i": "donor:China", "t": "donor", "n": "China", "k": ["China", "चीन"],
                      "a": round((ch["disbursements"][-1] if ch.get("disbursements") else 0) * 1e6),
                      "g": "main", "h": "#china",
                      "p": {"nondac": 1, "series": [{"y": y, "m": v} for y, v in
                            zip(ch["years"], ch.get("disbursements", []))],
                            "note": "Non-DAC partner; recipient-reported (Nepal DCR)."}})
    k = main_data["kpis"]
    if k.get("largest_nondac") == "India":
        index.append({"i": "donor:India", "t": "donor", "n": "India", "k": ["India", "भारत"],
                      "a": round(k["largest_nondac_value"] * 1e6), "g": "main", "h": "#china",
                      "p": {"nondac": 1, "latest_usd": round(k["largest_nondac_value"] * 1e6),
                            "note": "Largest funder the OECD donor system misses; recipient-reported."}})

    # ---- US budget accounts (the funnel: obligated vs delivered) ---------
    for a in us_data.get("funnel", {}).get("accounts", []):
        index.append({"i": "acct:" + a["acct"], "t": "account", "n": a["acct"],
                      "k": [a["acct"], a.get("agency", "")], "a": round(a["ob"] * 1e6),
                      "g": "us", "h": "#funnel",
                      "p": {"ob": a["ob"], "di": a["di"], "rate": a["rate"], "ag": a.get("agency", "")}})

    # ---- sectors (donor side, latest OECD year) --------------------------
    oecd = main_data["sectors"]["oecd"]
    yr = sorted(oecd)[-1]
    for r in oecd[yr]:
        index.append({"i": "sector:" + r["name"], "t": "sector", "n": r["name"].replace("_", " "),
                      "k": [r["name"].replace("_", " ")], "a": round(r["usd"] * 1e6),
                      "g": "main", "h": "#sectors",
                      "p": {"usd": round(r["usd"] * 1e6), "year": yr, "side": "donor (OECD)"}})

    # ---- sources & audits ------------------------------------------------
    for sname_url in main_data.get("sources", []):
        index.append({"i": "src:" + sname_url["name"], "t": "source", "n": sname_url["name"],
                      "k": [sname_url["name"]], "a": 0, "g": "main", "h": "#sources",
                      "p": {"side": sname_url.get("side", ""), "status": sname_url.get("status", ""),
                            "url": sname_url.get("url", "")}})
    for a in audits.get("list", []):
        index.append({"i": "audit:" + a["report"], "t": "audit",
                      "n": a["report"] + " - " + a.get("what", ""),
                      "k": [a["report"], a.get("title", ""), a.get("what", "")],
                      "a": round(a.get("questioned", 0)), "g": "us", "h": "#audits",
                      "p": {"q": a.get("questioned", 0), "verdict": a.get("verdict", ""),
                            "period": a.get("period", ""), "url": a.get("node_url", "")}})

    # Well-established acronyms so people can search the way they actually refer to these
    # organisations. Factual abbreviations only; added as ALIASES (never alter a figure).
    ACRONYM = {
        "research triangle institute": "RTI",
        "international foundation for electoral systems": "IFES",
        "development alternatives": "DAI",
        "family health international": "FHI 360",
        "world food programme": "WFP UN",
        "catholic relief services": "CRS",
        "cooperative for assistance and relief everywhere": "CARE",
        "world wildlife fund": "WWF",
        "abt associates": "Abt",
        "center for environmental and agricultural policy research": "CEAPRED",
        "nepali technical assistance group": "NTAG",
        "international development association": "World Bank IDA",
        "international bank for reconstruction": "World Bank IBRD",
        "asian development bank": "ADB",
        "united nations children": "UNICEF",
        "united states agency for international development": "USAID",
    }
    # clean keyword lists (dedupe, drop empties/redacted), add acronyms, sort by importance
    for e in index:
        kws = {(w or "").strip() for w in e["k"] if w and not REDACT.search(w)} | {e["n"]}
        hay = " ".join(kws).lower()
        for sub, acr in ACRONYM.items():
            if sub in hay:
                kws.add(acr)
        e["k"] = sorted(kws)
    index.sort(key=lambda e: (-e["a"], e["i"]))    # stable, fully deterministic order

    # --- split: keep every entity SEARCHABLE everywhere (name + headline scalars), but ship
    # the heavy counterparty LISTS (sub-recipients, awards, districts) only to the deep-dive
    # page. The main board stays light; the full profile is one click (deep-link) away.
    ARRAY_FIELDS = {"aw", "from", "dist", "proj", "subs", "orgs", "primes"}  # NOT donor "series" (core, tiny)
    HEAVY = {"org", "project", "district"}

    def slim(p):
        out = {}
        for k, v in (p or {}).items():
            if k in ARRAY_FIELDS:
                continue
            out[k] = {kk: vv for kk, vv in v.items() if kk not in ARRAY_FIELDS} if isinstance(v, dict) else v
        return out

    us_profiles = {}
    for e in index:
        if e["t"] in HEAVY and e.get("p"):
            us_profiles[e["i"]] = e["p"]      # full profile (with the big lists) -> deep-dive only
            e["p"] = slim(e["p"])             # headline scalars stay in the core index

    out = DASH / "search_index.js"
    out.write_text("window.SEARCH_INDEX = " + json.dumps(index, separators=(",", ":"),
                                                          ensure_ascii=False) + ";\n")
    usf = DASH / "search_index_us.js"
    usf.write_text("window.SEARCH_US = " + json.dumps(us_profiles, separators=(",", ":"),
                                                      ensure_ascii=False) + ";\n")
    by_t = defaultdict(int)
    for e in index:
        by_t[e["t"]] += 1
    print(f"wrote {out.relative_to(C.ROOT)}  (core, both pages: {len(index)} entities, {out.stat().st_size//1024} KB)")
    print(f"wrote {usf.relative_to(C.ROOT)}  (deep-dive only: {len(us_profiles)} full profiles, {usf.stat().st_size//1024} KB)")
    print("  by type:", dict(sorted(by_t.items(), key=lambda kv: -kv[1])))


if __name__ == "__main__":
    main()
