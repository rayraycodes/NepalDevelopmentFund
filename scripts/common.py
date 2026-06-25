"""
common.py — shared foundation for the Nepal development-finance dataset.

Every fetch/normalize script imports this. It defines:
  - the canonical long-format schema (CORE_COLUMNS) and allowed enum values
  - a browser-User-Agent HTTP session (OECD blocks the default agent)
  - immutable raw-snapshot writing with SHA-256 + per-source manifest fragments
  - deterministic obs_id hashing and a validated row builder
  - interim CSV writing in canonical column order

Repo layout assumed:  <root>/scripts/common.py , <root>/data/{raw,interim,processed} , <root>/config
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import time
from datetime import date, datetime, timezone
from pathlib import Path

# NOTE: `requests` is imported lazily inside the HTTP helpers below, so the synthesis and
# dashboard scripts (which only use the schema/paths) do not require it to be installed.

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config"
DATA = ROOT / "data"
RAW = DATA / "raw"
INTERIM = DATA / "interim"
PROCESSED = DATA / "processed"
LOGS = ROOT / "logs"
for _p in (RAW, INTERIM, PROCESSED, LOGS):
    _p.mkdir(parents=True, exist_ok=True)

# Build tag stamped onto every row so a row ties back to one pipeline run.
DATASET_VERSION = os.environ.get("DATASET_VERSION", f"{date.today():%Y-%m-%d}.1")

# As-of date for the US award data (when USAspending / ForeignAssistance.gov were pulled). The
# project-ledger triage (completed / active / ended) and the report cite this. Tie it to the data
# VINTAGE, not the wall clock, so rebuilds stay deterministic; bump it when the US data is refetched.
# (Per-project "deadline passed" labels in the browser use the live date instead — see search.js.)
US_DATA_ASOF = os.environ.get("US_DATA_ASOF", "2026-06-21")

# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------
BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
# OECD SDMX CSV with both code and label columns
SDMX_CSV_ACCEPT = "application/vnd.sdmx.data+csv;labels=both"


def make_session() -> "requests.Session":
    import requests
    s = requests.Session()
    s.headers.update({"User-Agent": BROWSER_UA, "Accept-Language": "en"})
    return s


def get(session, url: str, *, accept: str | None = None,
        params: dict | None = None, timeout: int = 120, retries: int = 4):
    """GET with simple exponential backoff. Raises on final failure."""
    import requests
    headers = {"Accept": accept} if accept else {}
    last = None
    for attempt in range(retries):
        try:
            r = session.get(url, params=params, headers=headers, timeout=timeout)
            if r.status_code < 500 and r.status_code != 429:
                return r
            last = r
        except requests.RequestException as e:  # network blip
            last = e
        time.sleep(2 ** attempt)
    if isinstance(last, requests.Response):
        return last
    raise RuntimeError(f"GET failed after {retries} tries: {url} ({last})")


# ---------------------------------------------------------------------------
# Time / hashing
# ---------------------------------------------------------------------------
def utc_now() -> str:
    """ISO-8601 UTC, second precision, e.g. 2026-06-03T11:42:07Z."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def obs_id(source: str, source_record_id: str, flow_stage: str, year) -> str:
    """Deterministic primary key, stable across rebuilds."""
    key = f"{source}|{source_record_id}|{flow_stage}|{year}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Organisation-name normalisation + Nepal geography
# Single source of truth for scripts 91/93/94/95 (and kept in sync with the JS in
# report/dashboard/dash-utils.js). norm_org() builds the key used to merge an org's prime and
# sub-recipient roles and to join FAC audits / locations to org ids, so every script MUST use
# this exact function or the keys silently stop lining up.
# ---------------------------------------------------------------------------
NAME_STOP = {"INC", "INCORPORATED", "LLC", "LTD", "LIMITED", "CORP", "CORPORATION",
             "CO", "PVT", "PRIVATE", "THE", "AND", "OF", "A"}


def norm_org(name: str) -> str:
    """Canonical org key: uppercase, punctuation->space, drop legal/stopword tokens."""
    toks = re.sub(r"[^A-Z0-9 ]", " ", (name or "").upper()).split()
    return " ".join(t for t in toks if t not in NAME_STOP)


# Nepal's 77 districts — whitelist that turns regex-extracted place names into real geography.
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

# English -> Nepali district names. SEARCH ALIASES ONLY (never a figure), so a transcription slip
# can at worst miss a match, never corrupt a number.
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


# ---------------------------------------------------------------------------
# Raw snapshots + manifest
# ---------------------------------------------------------------------------
def snapshot(source: str, name: str, content: bytes, *, url: str,
             params: str = "", http_status: int = 200, ext: str = "csv") -> Path:
    """
    Write an IMMUTABLE raw snapshot to data/raw/<source>/<name>_<ts>.<ext> and append a
    row to data/manifest_<source>.csv (the fragment merged later into data/manifest.csv).
    """
    ts = utc_now().replace(":", "").replace("-", "")
    out_dir = RAW / source
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{name}_{ts}.{ext}"
    path.write_bytes(content)

    frag = DATA / f"manifest_{source}.csv"
    new = not frag.exists()
    with frag.open("a", newline="") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["source", "snapshot_path", "url", "params", "sha256",
                        "bytes", "http_status", "retrieved_at"])
        w.writerow([source, str(path.relative_to(ROOT)), url, params,
                    sha256_bytes(content), len(content), http_status, utc_now()])
    return path


# ---------------------------------------------------------------------------
# Canonical schema
# ---------------------------------------------------------------------------
CORE_COLUMNS = [
    "obs_id", "side", "source", "source_record_id",
    "donor_name", "donor_dac_code", "donor_iati_id", "recipient",
    "sector", "sector_raw",
    "flow_stage", "instrument",
    "amount_usd", "amount_usd_constant", "price_base_year",
    "amount_original", "currency_original", "price_base",
    "year", "fiscal_basis", "period_start", "period_end",
    "status", "confidence", "dataset_version", "dedup_key",
    "is_multilateral_outflow", "counts_in_headline",
    "source_url", "retrieved_at", "notes",
]

ENUMS = {
    "side": {"donor", "recipient"},
    "flow_stage": {"commitment", "disbursement"},
    "instrument": {"grant", "concessional_loan", "oof", "other", ""},
    "price_base": {"current", "constant", ""},
    "fiscal_basis": {"nepal_fy", "donor_fy", "calendar"},
    "status": {"REPORTED", "ESTIMATED", "MISSING"},
    "confidence": {"high", "med", "low"},
}
# enum fields that must always be explicitly declared (empty not allowed)
REQUIRED_ENUMS = {"side", "flow_stage", "status", "confidence", "fiscal_basis"}

# default value for every column when a builder kwarg is omitted
_DEFAULTS = {c: "" for c in CORE_COLUMNS}
_DEFAULTS.update({
    "recipient": "NPL",
    "is_multilateral_outflow": False,
    "counts_in_headline": True,
    "dataset_version": DATASET_VERSION,
    "status": "REPORTED",
})


def new_row(**kw) -> dict:
    """
    Build one validated canonical row. Required: side, source, source_record_id,
    flow_stage, year, source_url, retrieved_at. obs_id and dedup_key auto-filled.
    Enum fields are validated; unknown columns raise.
    """
    unknown = set(kw) - set(CORE_COLUMNS)
    if unknown:
        raise ValueError(f"unknown columns: {sorted(unknown)}")
    row = dict(_DEFAULTS)
    row.update(kw)

    for field, allowed in ENUMS.items():
        v = row.get(field, "")
        if field in REQUIRED_ENUMS and v in ("", None):
            raise ValueError(f"{field} must be declared "
                             f"(record {row.get('source')}/{row.get('source_record_id')})")
        if v not in allowed:
            raise ValueError(f"{field}={v!r} not in {sorted(allowed)} "
                             f"(record {row.get('source')}/{row.get('source_record_id')})")
    for req in ("source", "source_record_id", "year", "source_url", "retrieved_at"):
        if row.get(req) in ("", None):
            raise ValueError(f"missing required field {req}")

    if not row.get("obs_id"):
        row["obs_id"] = obs_id(row["source"], row["source_record_id"],
                               row["flow_stage"], row["year"])
    if not row.get("dedup_key"):
        row["dedup_key"] = row["source_record_id"]
    return row


def write_interim(source: str, rows: list[dict]) -> Path:
    """Write data/interim/<source>_long.csv in canonical column order."""
    path = INTERIM / f"{source}_long.csv"
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CORE_COLUMNS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return path


def load_fx() -> dict:
    """config/fx_rates.csv -> {(year, currency): usd_per_unit}. Optional."""
    path = CONFIG / "fx_rates.csv"
    out: dict = {}
    if not path.exists():
        return out
    with path.open() as fh:
        for r in csv.DictReader(fh):
            try:
                out[(int(r["year"]), r["currency"].upper())] = float(r["usd_per_unit"])
            except (KeyError, ValueError):
                continue
    return out


if __name__ == "__main__":
    # smoke test
    r = new_row(side="donor", source="selftest", source_record_id="X1",
                flow_stage="disbursement", year=2022, amount_usd=1.0,
                status="REPORTED", confidence="high", fiscal_basis="calendar",
                source_url="https://example.org", retrieved_at=utc_now())
    assert r["obs_id"] and r["recipient"] == "NPL"
    print("common.py OK — schema cols:", len(CORE_COLUMNS), "| version:", DATASET_VERSION)
