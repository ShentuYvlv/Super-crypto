from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from super_crypto.common.config import canonical_json
from super_crypto.common.paths import DB_PATH, ensure_parent


class ExperimentStore:
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
                create table if not exists experiments (
                  experiment_id text primary key,
                  payload text not null
                );
                create table if not exists signals (
                  signal_id text primary key,
                  payload text not null
                );
                create table if not exists trades (
                  trade_id text primary key,
                  payload text not null
                );
                create table if not exists paper_trades (
                  trade_id text primary key,
                  payload text not null
                );
                create table if not exists holdout_audits (
                  audit_id integer primary key autoincrement,
                  created_at text not null,
                  payload text not null
                );
                """
            )

    def upsert(self, table: str, key: str, payload: dict[str, Any]) -> None:
        identifier = payload[key]
        with self._connect() as conn:
            conn.execute(
                f"insert into {table} values (?, ?) on conflict({key}) do update set payload=excluded.payload",
                (identifier, canonical_json(payload)),
            )

    def bulk_upsert(self, table: str, key: str, payloads: list[dict[str, Any]]) -> None:
        with self._connect() as conn:
            conn.executemany(
                f"insert into {table} values (?, ?) on conflict({key}) do update set payload=excluded.payload",
                [(item[key], canonical_json(item)) for item in payloads],
            )

    def list_payloads(self, table: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(f"select payload from {table}").fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def get_payload(self, table: str, key: str, value: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                f"select payload from {table} where {key} = ?", (value,)
            ).fetchone()
        return json.loads(row["payload"]) if row else None

    def record_holdout_audit(self, payload: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                "insert into holdout_audits(created_at, payload) values (?, ?)",
                (payload["created_at"], canonical_json(payload)),
            )

    def holdout_run_count(self) -> int:
        with self._connect() as conn:
            row = conn.execute("select count(*) as count from holdout_audits").fetchone()
        return int(row["count"]) if row else 0
