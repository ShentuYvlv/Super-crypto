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
        query = (
            f"insert into {table} values (?, ?) "
            f"on conflict({key}) do update set payload=excluded.payload"
        )
        with self._connect() as conn:
            conn.execute(
                query,
                (identifier, canonical_json(payload)),
            )

    def bulk_upsert(self, table: str, key: str, payloads: list[dict[str, Any]]) -> None:
        query = (
            f"insert into {table} values (?, ?) "
            f"on conflict({key}) do update set payload=excluded.payload"
        )
        with self._connect() as conn:
            conn.executemany(
                query,
                [(item[key], canonical_json(item)) for item in payloads],
            )

    def list_payloads(self, table: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(f"select payload from {table}").fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def get_payload(self, table: str, key: str, value: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(f"select payload from {table} where {key} = ?", (value,)).fetchone()
        return json.loads(row["payload"]) if row else None

    def delete_payloads(self, table: str, key: str, values: list[str]) -> int:
        if not values:
            return 0
        placeholders = ",".join("?" for _ in values)
        with self._connect() as conn:
            cursor = conn.execute(
                f"delete from {table} where {key} in ({placeholders})",
                values,
            )
        return int(cursor.rowcount)

    def delete_experiment_bundle(self, experiment_ids: list[str]) -> dict[str, int]:
        unique_ids = sorted(set(experiment_ids))
        if not unique_ids:
            return {"experiments": 0, "trades": 0, "signals": 0}
        experiments = [
            item
            for item in self.list_payloads("experiments")
            if item.get("experiment_id") in unique_ids
        ]
        trades = self.list_payloads("trades")
        deleted_trades = [
            trade for trade in trades if trade.get("experiment_id") in unique_ids
        ]
        deleted_trade_ids = [trade["trade_id"] for trade in deleted_trades]
        deleted_signal_ids = {
            trade["signal_id"] for trade in deleted_trades if trade.get("signal_id")
        }
        remaining_signal_ids = {
            trade["signal_id"]
            for trade in trades
            if trade.get("experiment_id") not in unique_ids and trade.get("signal_id")
        }
        orphan_signal_ids = sorted(deleted_signal_ids - remaining_signal_ids)
        return {
            "experiments": self.delete_payloads(
                "experiments",
                "experiment_id",
                [experiment["experiment_id"] for experiment in experiments],
            ),
            "trades": self.delete_payloads("trades", "trade_id", deleted_trade_ids),
            "signals": self.delete_payloads("signals", "signal_id", orphan_signal_ids),
        }

    def clear_autoresearch_runs(self, run_ids: list[str]) -> int:
        unique_ids = set(run_ids)
        if not unique_ids:
            return 0
        cleared = 0
        autoresearch_keys = [
            "autoresearch_run_id",
            "autoresearch_iteration",
            "autoresearch_started_at",
            "autoresearch_completed_at",
            "autoresearch_parent_config",
            "autoresearch_generated_config",
            "autoresearch_hypothesis",
            "autoresearch_decision",
            "autoresearch_recommendation",
        ]
        for experiment in self.list_payloads("experiments"):
            if experiment.get("autoresearch_run_id") not in unique_ids:
                continue
            for key in autoresearch_keys:
                experiment.pop(key, None)
            self.upsert("experiments", "experiment_id", experiment)
            cleared += 1
        return cleared

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
