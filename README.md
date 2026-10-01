# Culer Lens

An end-to-end football analytics platform about FC Barcelona, built with
StatsBomb's free open event data: a validated data pipeline, team and player
analytics, a calibrated match-outcome model, starting-XI prediction,
explainable AI, a FastAPI service and an interactive Next.js app.

> **A personal, non-commercial project.** It uses StatsBomb's free open data
> and is **not affiliated with, endorsed by or connected to FC Barcelona or
> StatsBomb**.

The data ends in 2021, so the app **replays history**: pick any Barcelona
fixture from 2008/09 to 2020/21 and it shows exactly what the platform would
have said on the morning of that match (prediction, predicted XI, workload,
form), with the result hidden until you reveal it.

![Overview: the Clásico of 21 November 2015, as seen before kick-off](docs/images/overview.png)

## Highlights

- **3.1 million events** from 869 matches (17 Barcelona seasons, the complete
  2015/16 La Liga, three Champions League finals), joined to **10,044 La Liga
  results** since 1995/96.
- **38 football-aware data-quality rules** with a hard gate: the feature
  stage will not run on data that failed. Events reproduce all 869 official
  scores, and the two sources agree on every league match.
- **Leakage is tested, not assumed**: a future-scrambling test on the real
  data rebuilds every feature after randomising all later results and
  requires nothing earlier to change.
- **Match-outcome ensemble** (Elo ordered logit + Poisson goals model +
  LightGBM), selected on 2008-2014 and scored once on the 2014-2021 holdout:
  log loss **0.968** against the betting market's **0.953**, closing **87%** of
  the gap between base rates and the market, from results alone. Calibration
  error 0.017, level with the market.
- **Starting-XI model**: **8.99 of 11** starters right on the holdout seasons,
  with a formation-aware assignment and plain-language reasons for each pick.
- **Explanations for every prediction**: permutation SHAP of the shipped
  ensemble (not a proxy model), grouped permutation importance, PDP/ICE, and an
  automated audit that catches a deliberately leaky model.
- **Player analytics**: expected threat, a transparent position-aware player
  rating (BIPR), match ratings, interactive action heatmaps, and a workload
  index that is explicitly *not* a fatigue measure.
- **Production shape**: Postgres or SQLite behind FastAPI (every endpoint
  under 15 ms), Docker Compose, GitHub Actions running unit, integration
  (on both databases), data-quality and browser tests.

## Screenshots

| Match centre: prediction, predicted XI and SHAP explanation | After the reveal: shot map |
|---|---|
| ![Match centre](docs/images/match-centre.png) | ![Shot map](docs/images/match-analysis.png) |

| Player profile: rating pillars, trends, action heatmap, workload | Model intelligence: holdout metrics, calibration, explanations |
|---|---|
| ![Player profile](docs/images/player-profile.png) | ![Model intelligence](docs/images/model.png) |

Every page also works on a phone:

<img src="docs/images/mobile.png" alt="Overview on a phone" width="260">

## How it works

```mermaid
flowchart LR
    SB[StatsBomb Open Data] --> RAW
    FD[football-data.co.uk] --> RAW
    RAW[raw] --> PROC[processed<br/>cleaned]
    PROC --> GATE{{38 validation rules}}
    GATE --> FEAT[features<br/>Elo, form, xT,<br/>ratings, workload]
    FEAT --> MOD[models<br/>walk-forward]
    MOD --> XAI[explanations]
    FEAT --> DB[(Postgres / SQLite)]
    MOD --> DB
    XAI --> DB
    DB --> API[FastAPI] --> WEB[Next.js app]
```

| Stage | Notebooks | Documentation |
|---|---|---|
| Data discovery and EDA | 01-06 | [EDA findings](docs/eda-findings.md), [data sources](docs/data-sources.md) |
| Profiling, quality, cleaning | 07-08 | [Data quality](docs/data-quality.md), [data dictionary](docs/data-dictionary.md) |
| Features | 09 | [Feature engineering](docs/feature-engineering.md) |
| Ratings and workload | 10-11 | [Model methodology § Ratings](docs/model-methodology.md#ratings), [workload](docs/workload-methodology.md) |
| Outcome models and evaluation | 12-14 | [Model methodology](docs/model-methodology.md) |
| Explainability | 15 | [XAI methodology](docs/xai-methodology.md) |
| Starting XI | 16 | [Model methodology § Starting XI](docs/model-methodology.md#starting-xi) |
| API, app, deployment | | [Architecture](docs/architecture.md), [deployment](docs/deployment.md) |

What the platform cannot do is set out in [limitations](docs/limitations.md).

## Results

Walk-forward: each season is predicted by a model trained only on earlier
seasons. Holdout = 2014/15-2020/21, never used for any decision.

| Holdout, all La Liga (2,660 matches) | Log loss | RPS | Accuracy |
|---|---|---|---|
| Betting market (average odds) | 0.953 | 0.190 | 54.1% |
| **Ensemble (production)** | **0.968** | **0.194** | **52.9%** |
| Elo alone | 0.970 | 0.195 | 53.0% |
| LightGBM alone | 0.974 | 0.195 | 52.7% |
| Base rates | 1.066 | 0.227 | 45.6% |

On Barcelona's 266 holdout matches: log loss 0.758 (market 0.749),
accuracy 71.8%. The market stays ahead because it prices team news; where
the two disagree most, the market is usually right, so the model is not a
betting tool.

## Quickstart

**You need:** [uv](https://docs.astral.sh/uv/) (it installs Python 3.12 by
itself if your system has another version), Node.js 20.9+, `make`, git, an
internet connection for the download, and about 1 GB of disk. Docker is
optional.

**Before downloading**, StatsBomb asks every user of its open data to
register their name and email at
[statsbomb.com/resource-centre](https://statsbomb.com/resource-centre)
(clause 2.2 of its user agreement).

```bash
git clone https://github.com/Mnshlb/culer-lens.git && cd culer-lens
make start
```

`make start` does everything: it installs the dependencies, builds the data,
models and database on the first run, builds the web app, starts the API and
the app, and opens http://localhost:3000. Press Ctrl+C to stop. Later runs
skip what is already built and start in a few seconds. Other ports:
`API_PORT=8001 WEB_PORT=3001 make start`.

To start it from any folder by typing `culer-lens`, run
`make install-command` once (`make uninstall-command` removes it).

Step by step, the same thing is:

```bash
make install      # Python and web dependencies (a few minutes the first time)
make pipeline     # download, validate, build features, train, explain, load ./barca.db
make api          # terminal 1: http://localhost:8000/docs (development mode)
make web          # terminal 2: http://localhost:3000 (development mode)
```

The first build (`make pipeline`) takes about 4 minutes on a recent laptop:

| Step | Time | What it does |
|---|---|---|
| `make data` | ~1 min | downloads 1,778 StatsBomb files at the pinned version and 26 football-data files |
| `make build` | ~15 s | cleans the data and runs the 38 validation rules; stops if an error rule fails |
| `make features` | ~15 s | builds the feature store |
| `make train` | ~1 min | walk-forward training of the outcome and starting-XI models |
| `make explain` | ~1 min | SHAP explanations for 494 fixtures, plus global explanations |
| `make db` | ~30 s | creates the database and loads it |

Every step is deterministic: a rebuild on another machine produces the same
data and checksums, and the same model results to many decimal places.

Or with PostgreSQL in Docker, after `make pipeline`:

```bash
make up           # Postgres + API + web
```

`make help` lists every target. The tests that need no data run with
`make test`; see [deployment](docs/deployment.md) for the rest.

## Repository layout

```
src/barca/       the Python package: data, analytics, features, models, xai, db, cli
apps/api/        FastAPI service and Alembic migrations
apps/web/        Next.js app and Playwright tests
notebooks/       16 executed analysis notebooks, in milestone order
reports/         generated reports (coverage, profile, data quality, feature catalogue) and figures
docs/            methodology, architecture, limitations, screenshots
tests/           unit, integration and data-quality suites
```

## Tech stack

Python 3.12 · Polars · pandas · Parquet · scikit-learn · LightGBM ·
XGBoost · SHAP · Optuna · MLflow · SQLAlchemy · Alembic · PostgreSQL ·
FastAPI · Next.js 16 · TypeScript · Tailwind · shadcn/ui · SVG · Recharts ·
TanStack Query · pytest · Playwright · Docker · GitHub Actions

## Data and licence

Event data: [StatsBomb Open Data](https://github.com/statsbomb/open-data).
Results and odds: [football-data.co.uk](https://www.football-data.co.uk).
The data is **not included** in this repository. The StatsBomb user
agreement does not allow redistribution, so `make data` downloads it from
the original sources at a pinned version.

Data by <a href="https://statsbomb.com"><img src="apps/web/public/statsbomb-logo.png" alt="StatsBomb" width="140" align="middle"></a>

**The source code is not open source.** It is © 2026 Manshul Budholiya, all
rights reserved: it is public so it can be read and evaluated, and you may
run it on your own computer to try it out, but you may not copy, reuse or
redistribute it. See [LICENSE](LICENSE). This is a personal, non-commercial
project. It is not
affiliated with, endorsed by or connected to FC Barcelona or StatsBomb; the
StatsBomb logo is the data credit that StatsBomb's user agreement asks for.
Club and competition names are used only to identify teams and matches.
