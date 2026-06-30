from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from super_crypto.common.config import canonical_json
from super_crypto.common.paths import DB_PATH, ensure_parent


class PipelineStore:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = ensure_parent(db_path or DB_PATH)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                create table if not exists pipeline_runs (
                  run_id text primary key,
                  payload text not null
                );
                create table if not exists pipeline_stages (
                  stage_id text primary key,
                  payload text not null
                );
                """
            )

    def upsert_run(self, payload: dict[str, Any]) -> None:
        query = (
            "insert into pipeline_runs values (?, ?) "
            "on conflict(run_id) do update set payload=excluded.payload"
        )
        with self._connect() as conn:
            conn.execute(
                query,
                (payload["run_id"], canonical_json(payload)),
            )

    def upsert_stage(self, payload: dict[str, Any]) -> None:
        stage_id = f"{payload['run_id']}:{payload['stage']}"
        query = (
            "insert into pipeline_stages values (?, ?) "
            "on conflict(stage_id) do update set payload=excluded.payload"
        )
        with self._connect() as conn:
            conn.execute(
                query,
                (stage_id, canonical_json(payload)),
            )

    def list_runs(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("select payload from pipeline_runs").fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def list_stages(self, run_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "select payload from pipeline_stages where stage_id like ?", (f"{run_id}:%",)
            ).fetchall()
        return [json.loads(row["payload"]) for row in rows]
