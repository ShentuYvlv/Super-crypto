from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import uvicorn
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response

from super_crypto.common.paths import DASHBOARD_OUT, DASHBOARD_ROOT, REPORT_ROOT
from super_crypto.report_api.main import create_app


class NoStoreStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope) -> Response:
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-store"
        return response


def _latest_mtime(root: Path, patterns: tuple[str, ...]) -> float:
    latest = 0.0
    for pattern in patterns:
        for path in root.glob(pattern):
            if path.is_file():
                latest = max(latest, path.stat().st_mtime)
    return latest


def _dashboard_source_mtime() -> float:
    return _latest_mtime(
        DASHBOARD_ROOT,
        (
            "app/**/*.tsx",
            "app/**/*.ts",
            "components/**/*.tsx",
            "components/**/*.ts",
            "lib/**/*.ts",
            "types/**/*.ts",
            "*.mjs",
            "*.json",
        ),
    )


def _dashboard_out_mtime() -> float:
    return _latest_mtime(DASHBOARD_OUT, ("**/*",))


def _build_dashboard() -> None:
    shutil.rmtree(DASHBOARD_OUT, ignore_errors=True)
    shutil.rmtree(DASHBOARD_ROOT / ".next", ignore_errors=True)
    if not (DASHBOARD_ROOT / "node_modules").exists():
        subprocess.run(["npm", "install"], cwd=DASHBOARD_ROOT, check=True)
    subprocess.run(["npm", "run", "build"], cwd=DASHBOARD_ROOT, check=True)


def ensure_dashboard_built() -> None:
    if DASHBOARD_OUT.exists() and _dashboard_out_mtime() >= _dashboard_source_mtime():
        return
    _build_dashboard()


def serve(host: str, port: int) -> None:
    app = create_app()
    ensure_dashboard_built()
    app.mount("/artifacts", StaticFiles(directory=REPORT_ROOT, html=True), name="artifacts")
    app.mount("/", NoStoreStaticFiles(directory=DASHBOARD_OUT, html=True), name="dashboard")
    uvicorn.run(app, host=host, port=port)
