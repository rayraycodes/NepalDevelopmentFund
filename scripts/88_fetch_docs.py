#!/usr/bin/env python3
"""
88_fetch_docs.py — download and archive the PRIMARY SUPPORTING DOCUMENTS behind the
funding data (strategies, compact agreements, country frameworks), then extract their
text for analysis.

Each PDF is snapshotted immutably (SHA-256 in the manifest, like every data source) so the
analysis remains verifiable even when the original site dies — which already happened to
USAID's website (the CDCS survives only as a grants.gov attachment).

Outputs:
  data/raw/docs/<slug>_<ts>.pdf        archived originals + manifest_docs.csv
  data/interim/docs/<slug>.txt         extracted text (pdftotext -layout)
  data/processed/documents.csv         registry: title, publisher, date, pages, urls, sha
"""
import csv
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C

SOURCE = "docs"
DOCS = [
    {"slug": "us_ics_nepal_2022",
     "title": "Integrated Country Strategy: Nepal (US Department of State)",
     "publisher": "US Department of State", "date": "2022 (2024 update)",
     "url": "https://2021-2025.state.gov/wp-content/uploads/2022/06/ICS_SCA_Nepal_Public.pdf"},
    {"slug": "usaid_cdcs_nepal_2020_2025",
     "title": "USAID Nepal Country Development Cooperation Strategy, Dec 2020 - Dec 2025",
     "publisher": "USAID (site offline; recovered from a grants.gov attachment)",
     "date": "2020-12",
     "url": "https://apply07.grants.gov/grantsws/rest/opportunity/att/download/331087"},
    {"slug": "mcc_nepal_compact_2017",
     "title": "Millennium Challenge Compact between the USA and Nepal (signed agreement)",
     "publisher": "Millennium Challenge Corporation", "date": "2017-09-14",
     "url": "https://assets.mcc.gov/content/uploads/compact-nepal.pdf"},
    {"slug": "adb_cps_nepal_2025_2029",
     "title": "ADB Country Partnership Strategy: Nepal 2025-2029",
     "publisher": "Asian Development Bank", "date": "2025-05",
     "url": "https://www.adb.org/sites/default/files/institutional-document/1058276/cps-nep-2025-2029.pdf"},
    {"slug": "wb_cpf_nepal_fy2025_31",
     "title": "World Bank Group Country Partnership Framework: Nepal FY2025-FY2031",
     "publisher": "World Bank Group", "date": "2025-05-06",
     "url": "https://documents.worldbank.org/curated/en/099050625143524020/pdf/BOSIB-16a89439-c3ef-4002-9acb-ca6b2c267585.pdf"},
]

TXT_DIR = C.INTERIM / "docs"
TXT_DIR.mkdir(parents=True, exist_ok=True)


def fetch(session, url) -> bytes | None:
    """requests first; fall back to system curl (Apple trust store) for hosts whose
    cert chain is missing an intermediate in Python's bundled CA file (e.g. assets.mcc.gov).
    Both paths are fully TLS-verified; no verification is ever disabled."""
    try:
        r = C.get(session, url, timeout=120)
        if r.status_code == 200 and r.content.startswith(b"%PDF"):
            return r.content
    except RuntimeError:
        pass
    c = subprocess.run(["curl", "-sL", "--fail", "-A", C.BROWSER_UA, "--max-time", "120", url],
                       capture_output=True)
    if c.returncode == 0 and c.stdout.startswith(b"%PDF"):
        return c.stdout
    return None


def main():
    s = C.make_session()
    reg = []
    existing = {p.name.rsplit("_", 1)[0] for p in (C.RAW / SOURCE).glob("*.pdf")} \
        if (C.RAW / SOURCE).exists() else set()
    for d in DOCS:
        if d["slug"] in existing:
            path = sorted((C.RAW / SOURCE).glob(f"{d['slug']}_*.pdf"))[-1]
            content = path.read_bytes()
            print(f"  SKIP (already archived) {d['slug']}")
        else:
            content = fetch(s, d["url"])
            if content is None:
                print(f"  FAILED {d['slug']}")
                reg.append({**d, "status": "FAILED", "pages": "", "sha256": ""})
                continue
            path = C.snapshot(SOURCE, d["slug"], content, url=d["url"],
                              http_status=200, ext="pdf")
        txt = TXT_DIR / f"{d['slug']}.txt"
        subprocess.run(["pdftotext", "-layout", str(path), str(txt)], check=True)
        pages = subprocess.run(["pdfinfo", str(path)], capture_output=True, text=True
                               ).stdout
        npages = next((l.split(":")[1].strip() for l in pages.splitlines()
                       if l.startswith("Pages")), "?")
        reg.append({**d, "status": "ARCHIVED", "pages": npages,
                    "sha256": C.sha256_bytes(content), "archived_path": str(path.relative_to(C.ROOT))})
        print(f"  OK {d['slug']}: {len(content):,}B, {npages} pages")

    with (C.PROCESSED / "documents.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["slug", "title", "publisher", "date", "pages",
                                           "status", "url", "archived_path", "sha256"],
                           extrasaction="ignore")
        w.writeheader()
        w.writerows(reg)
    print(f"\nregistry -> data/processed/documents.csv ({len(reg)} documents)")


if __name__ == "__main__":
    main()
