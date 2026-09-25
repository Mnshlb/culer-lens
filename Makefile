PY := uv run
.DEFAULT_GOAL := help

help:  ## list targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-16s %s\n", $$1, $$2}'

install:  ## install Python deps (all extras + dev) and web deps
	uv sync --all-extras
	cd apps/web && npm ci

data:  ## download raw data (StatsBomb pinned commit + football-data)
	$(PY) barca fetch

data-360:  ## download raw data including 2020/21 360 freeze frames
	$(PY) barca fetch --with-360

interim:  ## raw JSON/CSV -> interim Parquet
	$(PY) barca interim
