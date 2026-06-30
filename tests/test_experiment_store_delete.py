from __future__ import annotations

from super_crypto.experiments.experiment_store import ExperimentStore


def test_delete_experiment_bundle_removes_trades_and_orphan_signals(tmp_path):
    store = ExperimentStore(tmp_path / "experiments.db")
    store.upsert(
        "experiments",
        "experiment_id",
        {"experiment_id": "exp-a", "created_at": "2026-01-01T00:00:00Z"},
    )
    store.upsert(
        "experiments",
        "experiment_id",
        {"experiment_id": "exp-b", "created_at": "2026-01-01T00:00:00Z"},
    )
    store.bulk_upsert(
        "trades",
        "trade_id",
        [
            {"trade_id": "trade-a", "experiment_id": "exp-a", "signal_id": "signal-shared"},
            {"trade_id": "trade-b", "experiment_id": "exp-a", "signal_id": "signal-a"},
            {"trade_id": "trade-c", "experiment_id": "exp-b", "signal_id": "signal-shared"},
        ],
    )
    store.bulk_upsert(
        "signals",
        "signal_id",
        [
            {"signal_id": "signal-shared"},
            {"signal_id": "signal-a"},
        ],
    )

    deleted = store.delete_experiment_bundle(["exp-a"])

    assert deleted == {"experiments": 1, "trades": 2, "signals": 1}
    assert store.get_payload("experiments", "experiment_id", "exp-a") is None
    assert store.get_payload("experiments", "experiment_id", "exp-b") is not None
    assert store.get_payload("trades", "trade_id", "trade-a") is None
    assert store.get_payload("trades", "trade_id", "trade-b") is None
    assert store.get_payload("trades", "trade_id", "trade-c") is not None
    assert store.get_payload("signals", "signal_id", "signal-a") is None
    assert store.get_payload("signals", "signal_id", "signal-shared") is not None
