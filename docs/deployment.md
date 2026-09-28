# Running and deploying

## Requirements

- Python 3.12 and [uv](https://docs.astral.sh/uv/)
- Node.js 20.9+ (CI and the Docker image use Node 24)
- Docker with Compose, for the Postgres stack (optional)
- About 1 GB of disk for the data, models and local database

## Local development

`make start` is the one-command version: it installs and builds whatever is
missing, serves the API and a production build of the web app, opens the
browser, and stops both on Ctrl+C. For development with live reload:

```bash
make install     # uv sync --all-extras; npm ci in apps/web
make pipeline    # download → build + validate → features → train → explain → load ./barca.db
make api         # FastAPI on http://localhost:8000 (docs at /docs)
make web         # Next.js on http://localhost:3000
```

`make pipeline` is the chain of `make data build features train explain db`;
each step can be rerun on its own. Without a `DATABASE_URL`, the loader and
the API use a SQLite file at `./barca.db`.

The notebooks read the same files: `uv run jupyter lab`, or re-execute all of
them with `make notebooks`.

MLflow runs are stored in `./mlflow.db`:

```bash
uv run mlflow ui --backend-store-uri sqlite:///mlflow.db
```

## Docker Compose (PostgreSQL + API + web)

```bash
make pipeline    # the data and models are built on the host
make up          # Postgres → load it → build and start api + web
```

`make up` does three things:

1. starts `postgres:17-alpine` and waits for it to be healthy;
2. runs `barca db` on the host against
   `postgresql://barca:barca@localhost:5432/barca`: Alembic migrations, then a
   bulk load with `COPY` (about 45 seconds);
3. builds and starts the `api` and `web` images and waits for their health
   checks.

The web app is then on http://localhost:3000 and the API on
http://localhost:8000. `make down` stops the stack; the database lives in the
`pgdata` volume.

Loading happens on the host because it needs the pipeline's Parquet files
and model artefacts, and the ML stack. The images stay small and only serve.

### Images

| Image | Base | Contents |
|---|---|---|
| `apps/api/Dockerfile` (build context: repo root) | `python:3.12-slim` + uv | core package + FastAPI, Uvicorn, Alembic. No LightGBM, SHAP or MLflow. Non-root user, health check on `/health`. |
| `apps/web/Dockerfile` | `node:24-alpine`, multi-stage | Next.js standalone server only. Non-root user. |

## Configuration

| Variable | Used by | Default | Notes |
|---|---|---|---|
| `DATABASE_URL` | API, `barca db` | `sqlite:///./barca.db` | `postgresql://...` URLs are switched to the psycopg 3 driver automatically |
| `CORS_ORIGINS` | API | `http://localhost:3000,http://127.0.0.1:3000` | comma-separated |
| `NEXT_PUBLIC_API_URL` | web, **at build time** | `http://localhost:8000` | the URL the *browser* uses to reach the API; baked into the client bundle, so rebuild the web image when it changes |
| `BARCA_ROOT` | pipeline | repository root | where `data/`, `models/` and `reports/` live |
| `MLFLOW_TRACKING_URI` | training | `sqlite:///./mlflow.db` | |
| `TEST_DATABASE_URL` | integration tests | unset (SQLite) | a Postgres database for the integration tests; **its public schema is dropped** |

`.env.example` lists them.

## Hosting publicly

Any container host works: the API image plus a managed Postgres, and the web
image (or the Next.js app on a static-friendly host) with
`NEXT_PUBLIC_API_URL` set to the public API URL at build time. Load the
database once from a machine that has run the pipeline, with `DATABASE_URL`
pointing at the managed instance.

Before hosting, read the StatsBomb user agreement: the app publishes
analysis (allowed with attribution and the logo, which every page shows),
but the API also serves event-level records such as shot locations. Keeping
the deployment private, or limiting the API to aggregated outputs, avoids
any question of redistributing the data.

## Continuous integration

`.github/workflows/ci.yml` runs on every push and pull request:

| Job | Steps |
|---|---|
| Python | ruff (lint + format check), mypy, unit and integration tests on SQLite, integration tests again on a Postgres 17 service, and a check that the browser-test fixtures still match the API |
| Data (manual only) | downloads the 40 latest Barcelona matches plus all football-data seasons, runs the full build with its validation gate, builds the feature store and runs the data-quality and leakage tests; uploads the data-quality report |
| Web | ESLint, route type generation + `tsc`, and the Playwright suite (desktop and mobile) against the production build, with the API served from fixtures |
| Docker | builds both images |

The data job never runs automatically: football-data.co.uk offers its files
to private individuals, not to automated downloads (D-039). Start it by hand
from the Actions tab ("Run workflow") when you want to check the upstream
data.

## Tests locally

```bash
make test        # unit + integration (no data needed)
make test-data   # data-quality and leakage tests on the built data
make test-e2e    # Playwright against the production web build
make check       # lint + types + tests
```

To run the integration tests against Postgres (for example the Compose
database):

```bash
docker compose exec db createdb -U barca barca_test
TEST_DATABASE_URL=postgresql://barca:barca@localhost:5432/barca_test uv run pytest tests/integration
```
