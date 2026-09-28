PY := uv run
WEB := apps/web
.DEFAULT_GOAL := help

.PHONY: help start install data data-360 interim build features train explain db pipeline \
	api web fixtures api-types test test-data test-e2e test-all lint format typecheck \
	check notebooks up down clean

help:  ## list targets
	@grep -E '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-12s %s\n", $$1, $$2}'

start:  ## one command: install and build whatever is missing, run the app, open the browser
	@bash scripts/start.sh

install:  ## install Python deps (all extras + dev) and web deps
	uv sync --all-extras
	cd $(WEB) && npm ci

# --- data and models -------------------------------------------------------

data:  ## download raw data (StatsBomb pinned commit + football-data)
	$(PY) barca fetch

data-360:  ## download raw data including 2020/21 360 freeze frames
	$(PY) barca fetch --with-360

interim:  ## raw JSON/CSV -> interim Parquet
	$(PY) barca interim

build:  ## interim -> processed -> validated (fails on a data-quality error)
	$(PY) barca build

features:  ## validated data -> feature store
	$(PY) barca features

train:  ## walk-forward training of the outcome and lineup models
	$(PY) barca train

explain:  ## SHAP explanations, permutation importance, PDP/ICE
	$(PY) barca explain

db:  ## create the app database schema and load it (DATABASE_URL or ./barca.db)
	$(PY) barca db

pipeline: data build features train explain db  ## everything from download to a loaded database

# --- app -------------------------------------------------------------------

api:  ## run the API on :8000 with reload
	$(PY) uvicorn app.main:app --app-dir apps/api --reload --port 8000

web:  ## run the web app on :3000 (expects the API on :8000)
	cd $(WEB) && npm run dev

fixtures:  ## regenerate the synthetic API fixtures used by the browser tests
	$(PY) python scripts/export_e2e_fixtures.py

api-types:  ## regenerate TypeScript types from the running API's OpenAPI schema
	cd $(WEB) && npm run api:types

PG_URL := postgresql://barca:barca@localhost:5432/barca

up:  ## Postgres + API + web in Docker, loading Postgres from the local data and models
	docker compose up -d --wait db
	DATABASE_URL=$(PG_URL) $(PY) barca db
	docker compose up -d --build --wait api web
	@echo "web: http://localhost:3000  api: http://localhost:8000/docs"

down:  ## stop the Docker Compose stack
	docker compose down

# --- quality ---------------------------------------------------------------

test:  ## unit and API integration tests (no data needed)
	$(PY) pytest -m "not data"

test-data:  ## data-quality and leakage tests against the built data
	$(PY) pytest tests/data_quality

test-e2e:  ## browser tests against the production web build
	cd $(WEB) && npm run test:e2e

test-all: test test-data test-e2e  ## every test suite

lint:  ## ruff + eslint
	$(PY) ruff check src apps/api tests scripts
	$(PY) ruff format --check src apps/api tests scripts
	cd $(WEB) && npm run lint

format:  ## apply ruff formatting and autofixes
	$(PY) ruff format src apps/api tests scripts
	$(PY) ruff check --fix src apps/api tests scripts

typecheck:  ## mypy + tsc
	$(PY) mypy
	cd $(WEB) && npm run typecheck

check: lint typecheck test  ## what CI runs before the data and browser jobs

notebooks:  ## re-execute every notebook in place
	$(PY) jupyter nbconvert --to notebook --execute --inplace \
		--ExecutePreprocessor.timeout=1800 --ExecutePreprocessor.record_timing=False \
		notebooks/*.ipynb

clean:  ## remove caches and build output (keeps data and models)
	rm -rf .pytest_cache .mypy_cache .ruff_cache $(WEB)/.next $(WEB)/test-results $(WEB)/playwright-report
	find . -name __pycache__ -type d -prune -not -path "./.venv/*" -exec rm -rf {} +
