"""Project paths and runtime settings."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(os.environ.get("BARCA_ROOT", Path(__file__).resolve().parents[2]))

DATA = ROOT / "data"
RAW = DATA / "raw"
INTERIM = DATA / "interim"
PROCESSED = DATA / "processed"
FEATURES = DATA / "features"

MODELS = ROOT / "models"
REPORTS = ROOT / "reports"
FIGURES = REPORTS / "figures"
REFERENCE = Path(__file__).resolve().parent / "data" / "reference"

RAW_STATSBOMB = RAW / "statsbomb"
RAW_FOOTBALL_DATA = RAW / "football_data"

MLFLOW_URI = os.environ.get("MLFLOW_TRACKING_URI", f"sqlite:///{ROOT / 'mlflow.db'}")

RANDOM_SEED = 42


def ensure_dirs() -> None:
    for path in (RAW_STATSBOMB, RAW_FOOTBALL_DATA, INTERIM, PROCESSED, FEATURES, MODELS, FIGURES):
        path.mkdir(parents=True, exist_ok=True)
