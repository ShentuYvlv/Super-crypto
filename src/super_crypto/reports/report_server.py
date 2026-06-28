from __future__ import annotations

import subprocess

import uvicorn
from fastapi.staticfiles import StaticFiles

from super_crypto.common.paths import DASHBOARD_OUT, DASHBOARD_ROOT, REPORT_ROOT
from super_crypto.report_api.main import create_app


def ensure_dashboard_built() -> None:
    if DASHBOARD_OUT.exists():
        return
    if not (DASHBOARD_ROOT / "node_modules").exists():
        subprocess.run(["npm", "install"], cwd=DASHBOARD_ROOT, check=True)
    subprocess.run(["npm", "run", "build"], cwd=DASHBOARD_ROOT, check=True)


def serve(host: str, port: int) -> None:
    app = create_app()
    ensure_dashboard_built()
    app.mount("/artifacts", StaticFiles(directory=REPORT_ROOT, html=True), name="artifacts")
    app.mount("/", StaticFiles(directory=DASHBOARD_OUT, html=True), name="dashboard")
    uvicorn.run(app, host=host, port=port)
