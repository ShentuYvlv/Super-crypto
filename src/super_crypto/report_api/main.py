from __future__ import annotations

from fastapi import FastAPI

from super_crypto.report_api import data_quality, experiments, overview, pipeline, reports, signals, symbols, trades


def create_app() -> FastAPI:
    app = FastAPI(title="Super Crypto Report API")
    app.include_router(overview.router)
    app.include_router(pipeline.router)
    app.include_router(experiments.router)
    app.include_router(signals.router)
    app.include_router(trades.router)
    app.include_router(symbols.router)
    app.include_router(data_quality.router)
    app.include_router(reports.router)
    return app

