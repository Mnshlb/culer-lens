"""Barcelona Intelligence API."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.routers import analytics, matches, models, overview, players, predictions, teams
from app.settings import get_settings

DESCRIPTION = """
Football analytics and predictions for FC Barcelona, 2004/05-2020/21.

Every prediction is the one the model would have made **before** the match,
trained only on earlier seasons. Event data: StatsBomb Open Data.
"""


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Barcelona Intelligence API", version="1.0.0", description=DESCRIPTION)
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(
        CORSMiddleware, allow_origins=settings.origins, allow_methods=["GET"], allow_headers=["*"]
    )
    for router in (
        overview.router,
        matches.router,
        players.router,
        teams.router,
        predictions.router,
        analytics.router,
        models.router,
    ):
        app.include_router(router)

    @app.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
