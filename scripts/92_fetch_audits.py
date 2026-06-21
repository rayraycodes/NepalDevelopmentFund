#!/usr/bin/env python3
"""
92_fetch_audits.py — the accountability layer: USAID Office of Inspector General financial
and performance audits of US assistance to Nepal.

For each audit: record the citable metadata (report number, what was audited, period, questioned
costs from the OIG's own report page), then ARCHIVE the PDF where the OIG still serves it
(oig.usaid.gov), snapshot it with SHA-256, extract its text, and VERIFY the questioned-cost
figure actually appears in the document. Audits whose PDF now lives only on the dead pdf.usaid.gov
are recorded with their OIG node link and marked not-archived — honestly.

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

# Metadata from the OIG report pages (oig.usaid.gov node URLs are the citation).
AUDITS = [
 {"report": "5-367-23-024-R", "node": "https://oig.usaid.gov/node/6194",
  "title": "Financial Audit: Dept. of Health Services, AA 367-013, IL 150 (FY2021/22)",
  "what": "Health funds managed by the Government of Nepal", "period": "Jul 2021-Jul 2022",
  "questioned": 0, "verdict": "clean"},
 {"report": "5-367-22-024-R", "node": "https://oig.usaid.gov/node/5507",
  "title": "Financial Audit: Health, Dept. of Health Services & Karnali Province (FY2020/21)",
  "what": "Health funds managed by the Government of Nepal", "period": "Jul 2020-Jul 2021",
  "questioned": 27809, "verdict": "questioned costs"},
 {"report": "5-367-20-060-R", "node": "https://oig.usaid.gov/node/4218",
  "title": "Financial Audit: Dept. of Health Services, MoHP (FY2018/19)",
  "what": "Health funds managed by the Government of Nepal", "period": "Jul 2018-Jul 2019",
  "questioned": 49030, "verdict": "questioned costs"},
 {"report": "5-367-18-017-R", "node": "https://oig.usaid.gov/node/1626",
  "title": "Financial Audit: Dept. of Health Services (FY2016/17)",
  "what": "Health funds managed by the Government of Nepal", "period": "Jul 2016-Jul 2017",
  "questioned": 90732, "verdict": "questioned costs",
  "pdf": "https://oig.usaid.gov/sites/default/files/2018-06/5-367-18-017-r.pdf"},
 {"report": "NSET-2022", "node": "https://oig.usaid.gov/node/6121",
  "title": "Financial Audit: National Society for Earthquake Technology-Nepal (FY2021/22)",
  "what": "NSET-Nepal, multiple USAID agreements", "period": "Jul 2021-Jul 2022",
  "questioned": 110564, "verdict": "questioned costs"},
 {"report": "367-014-DFP", "node": "https://oig.usaid.gov/node/7144",
  "title": "Financial Audit: Health Direct Financing Project, DOAG 367-014",
  "what": "Health funds managed by the Government of Nepal", "period": "to Jul 2022",
  "questioned": 45026, "verdict": "questioned costs"},
 {"report": "Hariyo-Ban", "node": "https://oig.usaid.gov/node/3097",
  "title": "Audit of USAID/Nepal's Hariyo Ban Program (performance)",
  "what": "Environment/biodiversity program (implemented by WWF)", "period": "performance audit",
  "questioned": 0, "verdict": "performance findings"},
]
PDF_RX = re.compile(r'https?://[^"\']+\.pdf|/sites/default/files/[^"\']+\.pdf', re.I)


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
        pdf_url = find_pdf(s, a)
        archived, sha, verified, pages = False, "", "", ""
        content = fetch_pdf(s, pdf_url) if pdf_url else None
        if content:
            path = C.snapshot(SOURCE, a["report"], content, url=pdf_url, http_status=200, ext="pdf")
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
                     "node_url": a["node"], "pdf_url": pdf_url or "",
                     "archived": archived, "pages": pages, "verified_in_pdf": verified, "sha256": sha})
        print(f"  {a['report']:16s} archived={archived!s:5s} verified={verified or '-':14s} ${a['questioned']:,}")

    with (C.PROCESSED / "audits.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

    tot = sum(r["questioned"] for r in rows)
    n_arch = sum(1 for r in rows if r["archived"])
    data = {"meta": {"retrieved_at": C.utc_now(), "n": len(rows), "n_archived": n_arch,
                     "total_questioned": tot, "source": "USAID Office of Inspector General"},
            "list": [{"report": r["report"], "title": r["title"], "what": r["what"],
                      "period": r["period"], "questioned": r["questioned"], "verdict": r["verdict"],
                      "node_url": r["node_url"], "pdf_url": r["pdf_url"],
                      "archived": r["archived"], "verified": r["verified_in_pdf"]}
                     for r in sorted(rows, key=lambda r: -r["questioned"])]}
    out = C.ROOT / "report/dashboard/usforeignaiddata/audits.js"
    out.write_text("window.US_AUDITS = " + json.dumps(data) + ";\n")
    print(f"\n{len(rows)} audits, {n_arch} archived, total questioned costs ${tot:,} "
          f"({tot/2.01e9*100:.3f}% of $2.0bn delivered) -> audits.csv, audits.js")


if __name__ == "__main__":
    main()
