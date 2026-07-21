#!/usr/bin/env python3
"""
92_fetch_audits.py — the accountability layer: USAID Office of Inspector General financial
and performance audits of US assistance to Nepal.

For each audit: record the citable metadata (report number, what was audited, period, questioned
costs from the OIG's own report page), then ARCHIVE the PDF, snapshot it with SHA-256, extract
its text, and VERIFY the questioned-cost figure actually appears in the document.

Resilience (USAID was folded into the State Department in 2025; oig.usaid.gov has been
intermittent since): an audit already archived under data/raw/audits/ is REUSED, never
re-downloaded — a rerun with the server dark keeps every archived=True fact. For fresh
downloads the order is: verified live PDF url -> node-page scrape -> verified Wayback
snapshot (fetched via its id_ raw-bytes form and labelled as such in the outputs). Every
row also carries the Wayback node/PDF snapshot URLs (link-checked LINK_CHECKED) so the
dashboard can state exactly where a reader can still verify each report.

Outputs:
  data/raw/audits/<report>_<ts>.pdf            archived audit PDFs (+ manifest_audits.csv)
  data/interim/audits/<report>.txt             extracted text
  data/processed/audits.csv                    registry
  report/dashboard/usforeignaiddata/audits.js  for the dashboard Accountability section
"""
import csv
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C

SOURCE = "audits"
TXT = C.INTERIM / "audits"
TXT.mkdir(parents=True, exist_ok=True)

# Every node/pdf/wb_* URL below was actually fetched with HTTP 200 on that date (pdf/wb_pdf
# verified by download: %PDF header, expected size). wb_* are Internet Archive snapshots — the
# whole OIG site was crawled 2026-06-30, so they are the insurance if it goes dark again.
LINK_CHECKED = "2026-07-20"

# Metadata from the OIG report pages (oig.usaid.gov node URLs are the citation).
#   pdf     verified live PDF on oig.usaid.gov ("" fields absent = no live copy exists)
#   wb_node verified Wayback snapshot of the report page
#   wb_pdf  verified Wayback snapshot of the PDF (display URL; fetched via its id_ form)
AUDITS = [
 {"report": "5-367-23-024-R", "node": "https://oig.usaid.gov/node/6194",
  "title": "Financial Audit: Dept. of Health Services, AA 367-013, IL 150 (FY2021/22)",
  "what": "Health funds managed by the Government of Nepal", "period": "Jul 2021-Jul 2022",
  "questioned": 0, "verdict": "clean",
  "pdf": "https://oig.usaid.gov/sites/default/files/2023-08/5-367-23-024-R.pdf",
  "wb_node": "http://web.archive.org/web/20260630021949/https://oig.usaid.gov/node/6194",
  "wb_pdf": "http://web.archive.org/web/20260630021949/https://oig.usaid.gov/sites/default/files/2023-08/5-367-23-024-R.pdf"},
 {"report": "5-367-22-024-R", "node": "https://oig.usaid.gov/node/5507",
  "title": "Financial Audit: Health, Dept. of Health Services & Karnali Province (FY2020/21)",
  "what": "Health funds managed by the Government of Nepal", "period": "Jul 2020-Jul 2021",
  "questioned": 27809, "verdict": "questioned costs",
  "pdf": "https://oig.usaid.gov/sites/default/files/2022-09/5-367-22-024-R_0.pdf",
  "wb_node": "http://web.archive.org/web/20260630023556/https://oig.usaid.gov/node/5507",
  "wb_pdf": "http://web.archive.org/web/20260630023556/https://oig.usaid.gov/sites/default/files/2022-09/5-367-22-024-R_0.pdf"},
 {"report": "5-367-20-060-R", "node": "https://oig.usaid.gov/node/4218",
  "title": "Financial Audit: Dept. of Health Services, MoHP (FY2018/19)",
  "what": "Health funds managed by the Government of Nepal", "period": "Jul 2018-Jul 2019",
  "questioned": 49030, "verdict": "questioned costs",
  "pdf": "https://oig.usaid.gov/sites/default/files/2020-08/5-367-20-060-R.pdf",
  "wb_node": "http://web.archive.org/web/20260630024533/https://oig.usaid.gov/node/4218",
  "wb_pdf": "http://web.archive.org/web/20260630024532/https://oig.usaid.gov/sites/default/files/2020-08/5-367-20-060-R.pdf"},
 {"report": "5-367-18-017-R", "node": "https://oig.usaid.gov/node/1626",
  "title": "Financial Audit: Dept. of Health Services (FY2016/17)",
  "what": "Health funds managed by the Government of Nepal", "period": "Jul 2016-Jul 2017",
  "questioned": 90732, "verdict": "questioned costs",
  "pdf": "https://oig.usaid.gov/sites/default/files/2018-06/5-367-18-017-r.pdf",
  "wb_node": "http://web.archive.org/web/20260630024227/https://oig.usaid.gov/node/1626",
  "wb_pdf": "http://web.archive.org/web/20260630022646/https://oig.usaid.gov/sites/default/files/2018-06/5-367-18-017-r.pdf"},
 # OIG report no. 5-367-23-023-R (identified via oversight.gov). The PDF is still LIVE on
 # oig.usaid.gov but no longer linked from the node page — recovered 2026-07-20, transmittal
 # text contains the $110,564 questioned figure.
 {"report": "NSET-2022", "node": "https://oig.usaid.gov/node/6121",
  "title": "Financial Audit: National Society for Earthquake Technology-Nepal (FY2021/22)",
  "what": "NSET-Nepal, multiple USAID agreements", "period": "Jul 2021-Jul 2022",
  "questioned": 110564, "verdict": "questioned costs",
  "pdf": "https://oig.usaid.gov/sites/default/files/2023-08/5-367-23-023-R.pdf",
  "wb_node": "http://web.archive.org/web/20260630020131/https://oig.usaid.gov/node/6121",
  "wb_pdf": "https://web.archive.org/web/20260630022803/https://oig.usaid.gov/sites/default/files/2023-08/5-367-23-023-R.pdf"},
 # OIG report no. 5-367-24-050-R (identified via oversight.gov). Live but unlinked, same story:
 # recovered 2026-07-20, text contains the $45,026 questioned figure.
 {"report": "367-014-DFP", "node": "https://oig.usaid.gov/node/7144",
  "title": "Financial Audit: Health Direct Financing Project, DOAG 367-014",
  "what": "Health funds managed by the Government of Nepal", "period": "to Jul 2022",
  "questioned": 45026, "verdict": "questioned costs",
  "pdf": "https://oig.usaid.gov/sites/default/files/2024-09/5-367-24-050-R_0.pdf",
  "wb_node": "http://web.archive.org/web/20260630020929/https://oig.usaid.gov/node/7144",
  "wb_pdf": "https://web.archive.org/web/20260630015011/https://oig.usaid.gov/sites/default/files/2024-09/5-367-24-050-R_0.pdf"},
 # OIG report no. 5-367-15-003-P. The ONLY audit with no live copy anywhere: the pre-2016
 # /sites/default/files/audit-reports/ layout is retired (404). The full 20-page report
 # survives in the Wayback Machine's 2015 crawl — so no "pdf", wb_pdf is the real artifact.
 {"report": "Hariyo-Ban", "node": "https://oig.usaid.gov/node/3097",
  "title": "Audit of USAID/Nepal's Hariyo Ban Program (performance)",
  "what": "Environment/biodiversity program (implemented by WWF)", "period": "performance audit",
  "questioned": 0, "verdict": "performance findings",
  "wb_node": "http://web.archive.org/web/20260630025430/https://oig.usaid.gov/node/3097",
  "wb_pdf": "https://web.archive.org/web/20150315043615/http://oig.usaid.gov/sites/default/files/audit-reports/5-367-15-003-p.pdf"},
]
PDF_RX = re.compile(r'https?://[^"\']+\.pdf|/sites/default/files/[^"\']+\.pdf', re.I)


def wb_raw(wb_url):
    """Wayback id_ form: /web/<ts>id_/ serves the ORIGINAL archived bytes (no toolbar wrapper),
    so the snapshot we checksum is the document itself, not archive.org chrome."""
    return re.sub(r"(/web/\d{14})/", r"\1id_/", wb_url)


def find_pdf(session, a):
    if a.get("pdf"):
        return a["pdf"]
    try:
        html = C.get(session, a["node"], timeout=40).text
    except Exception:
        return None
    for m in PDF_RX.findall(html):
        if "logo" not in m.lower() and "icon" not in m.lower():
            return m if m.startswith("http") else "https://oig.usaid.gov" + m
    return None


def fetch_pdf(session, url):
    try:
        r = C.get(session, url, timeout=90)
        if r.status_code == 200 and r.content[:4] == b"%PDF":
            return r.content
    except Exception:
        pass
    c = subprocess.run(["curl", "-sL", "--fail", "-A", C.BROWSER_UA, "--max-time", "90", url],
                       capture_output=True)
    return c.stdout if c.returncode == 0 and c.stdout[:4] == b"%PDF" else None


def main():
    s = C.make_session()
    rows = []
    for a in AUDITS:
        pdf_url, wb_pdf = a.get("pdf", ""), a.get("wb_pdf", "")
        # 1) RERUN SAFETY: reuse the newest immutable local snapshot if we already hold one —
        #    never re-download, never lose archived=True when oig.usaid.gov is dark again.
        existing = sorted((C.RAW / SOURCE).glob(f"{a['report']}_*.pdf"))
        path = existing[-1] if existing else None
        content, fetched_from = (path.read_bytes(), "local archive") if path else (None, "")
        if content is None:
            # 2) fresh download: verified live URL (or node-page scrape) first, then the
            #    Wayback snapshot's raw-bytes id_ form. Each candidate tolerates failure.
            for url in filter(None, (pdf_url or find_pdf(s, a), wb_raw(wb_pdf) if wb_pdf else None)):
                content = fetch_pdf(s, url)
                if content:
                    path = C.snapshot(SOURCE, a["report"], content, url=url, http_status=200, ext="pdf")
                    fetched_from = url
                    break
        archived, sha, verified, pages = False, "", "", ""
        if content:
            txt = TXT / f"{a['report']}.txt"
            subprocess.run(["pdftotext", "-layout", str(path), str(txt)], check=False)
            body = txt.read_text(errors="ignore") if txt.exists() else ""
            sha, archived = C.sha256_bytes(content), True
            info = subprocess.run(["pdfinfo", str(path)], capture_output=True, text=True).stdout
            pages = next((l.split(":")[1].strip() for l in info.splitlines() if l.startswith("Pages")), "")
            # verify the questioned-cost figure is really in the document
            if a["questioned"]:
                q = a["questioned"]
                verified = "yes" if (f"{q:,}" in body or str(q) in body.replace(",", "")) else "not found in text"
        rows.append({**{k: a[k] for k in ("report", "title", "what", "period", "questioned", "verdict")},
                     "node_url": a["node"], "pdf_url": pdf_url,
                     "wayback_node": a.get("wb_node", ""), "wayback_pdf": wb_pdf,
                     "archived": archived, "pages": pages, "verified_in_pdf": verified, "sha256": sha})
        print(f"  {a['report']:16s} archived={archived!s:5s} verified={verified or '-':14s} "
              f"${a['questioned']:,}  [{fetched_from or 'NOT ARCHIVED'}]")

    with (C.PROCESSED / "audits.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

    tot = sum(r["questioned"] for r in rows)
    n_arch = sum(1 for r in rows if r["archived"])
    data = {"meta": {"retrieved_at": C.utc_now(), "n": len(rows), "n_archived": n_arch,
                     "total_questioned": tot, "link_checked": LINK_CHECKED,
                     "source": "USAID Office of Inspector General"},
            "list": [{"report": r["report"], "title": r["title"], "what": r["what"],
                      "period": r["period"], "questioned": r["questioned"], "verdict": r["verdict"],
                      "node_url": r["node_url"], "pdf_url": r["pdf_url"],
                      "wayback_node": r["wayback_node"], "wayback_pdf": r["wayback_pdf"],
                      "archived": r["archived"], "verified": r["verified_in_pdf"]}
                     for r in sorted(rows, key=lambda r: -r["questioned"])]}
    out = C.ROOT / "report/dashboard/usforeignaiddata/audits.js"
    out.write_text("window.US_AUDITS = " + json.dumps(data) + ";\n")
    print(f"\n{len(rows)} audits, {n_arch} archived, total questioned costs ${tot:,} "
          f"({tot/2.01e9*100:.3f}% of $2.0bn delivered) -> audits.csv, audits.js")


if __name__ == "__main__":
    main()
