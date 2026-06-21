# Nepal development-finance dataset — reproducible build.
# Each fetch target writes an immutable dated snapshot to data/raw/ and a manifest fragment.
PY := python3

.PHONY: all anchor fetch build report validate clean smoke

smoke:
	$(PY) scripts/common.py

# Phase 1 — verified headline core
anchor:
	$(PY) scripts/12_fetch_wb_indicators.py
	$(PY) scripts/10_fetch_oecd.py

# Phase 2 — breadth (also driven by the multi-agent workflow)
fetch:
	$(PY) scripts/11_fetch_wb_projects.py
	$(PY) scripts/13_fetch_iati_dportal.py
	$(PY) scripts/14_fetch_adb_iati.py
	$(PY) scripts/15_fetch_us.py
	$(PY) scripts/19_fetch_us_agency.py
	$(PY) scripts/16_fetch_nepal_dcr.py
	$(PY) scripts/17_fetch_aiddata.py
	$(PY) scripts/18_fetch_oecd_crs.py
	$(PY) scripts/89_us_projects_data.py
	$(PY) scripts/90_us_project_detail.py
	$(PY) scripts/88_fetch_docs.py
	$(PY) scripts/92_fetch_audits.py
	$(PY) scripts/94_org_audits.py   # org -> FAC Single Audit + OIG (set FAC_API_KEY for a full pull)
	$(PY) scripts/95_org_locations.py   # org -> registered country/address (USAspending)

# primary supporting documents (strategies, compact agreements) -> data/raw/docs + registry
docs:
	$(PY) scripts/88_fetch_docs.py

# Phase 3 — synthesis
build:
	$(PY) scripts/40_dedupe_iati.py
	$(PY) scripts/50_reconcile.py
	$(PY) scripts/60_build_core.py

validate:
	$(PY) scripts/90_validate.py

figures:
	$(PY) scripts/80_figures.py

dashboard-data:
	$(PY) scripts/85_dashboard_data.py
	$(PY) scripts/86_us_dashboard_data.py
	$(PY) scripts/87_us_partners_data.py
	$(PY) scripts/91_us_localization.py
	$(PY) scripts/89_us_projects_data.py
	$(PY) scripts/93_search_index.py   # cross-dataset entity search index (run last; reads the others)

# serve the self-contained dashboard at http://127.0.0.1:8848
serve: dashboard-data
	cd report/dashboard && $(PY) -m http.server 8848 --bind 127.0.0.1

all: anchor fetch build validate figures dashboard-data

clean:
	rm -rf data/interim/* data/processed/* data/manifest_*.csv
