from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

QualityState = Literal["healthy", "partial", "stale", "failed", "blocked"]
SplitName = Literal["train", "validation", "holdout", "train_validation"]
StrategyName = Literal["V3", "V4A", "V4B"]


class DataQuality(BaseModel):
    generated_at: datetime
    source: str
    freshness_sec: int
    data_quality: QualityState
    missing_fields: list[str] = Field(default_factory=list)
    stale_fields: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


class MarketSnapshot(BaseModel):
    symbol: str
    price: float
    price_change_percent: float
    quote_volume: float
    trade_count: int
    funding_rate: float | None = None
    oi_usd: float | None = None
    oi_change_1h: float | None = None
    oi_change_6h: float | None = None
    oi_change_24h: float | None = None
    oi_acceleration: float | None = None
    snapshot_time: datetime
    data_quality: DataQuality


class CycleRecord(BaseModel):
    cycle_id: str
    symbol: str
    timeframe: str | None = None
    pump_start: datetime
    peak_time: datetime
    dump_end: datetime
    pump_return: float
    dump_return: float
    pump_duration_hours: float = 0.0
    dump_duration_hours: float = 0.0
    duration_hours: float
    rule_id: str = ""
    quality_score: float = 0.0
    detection_rule: str = ""
    score_context: dict[str, Any] = Field(default_factory=dict)


class ScoreRecord(BaseModel):
    symbol: str
    score: float
    bucket: Literal["ultra_high", "high", "medium", "low"]
    cycle_count: int
    avg_pump_return: float
    avg_dump_return: float
    point_in_time_cutoff: datetime
    data_completeness: float
    components: dict[str, float] = Field(default_factory=dict)


class OrderbookEstimate(BaseModel):
    symbol: str
    snapshot_time: datetime
    spread_bps: float
    imbalance: float
    max_size_under_50bps: float
    slippage_bps_by_notional: dict[str, float]
    data_quality: DataQuality


class SignalRecord(BaseModel):
    signal_id: str
    symbol: str
    strategy: StrategyName
    side: Literal["SHORT"]
    signal_time: datetime
    decision_time: datetime
    data_cutoff_time: datetime
    entry_reference: str
    stop_loss: float
    trailing_stop: float
    confidence: float
    manipulation_score_bucket: Literal["ultra_high", "high", "medium", "low"]
    reason: list[str]
    data_quality: QualityState
    missing_fields: list[str] = Field(default_factory=list)
    stale_fields: list[str] = Field(default_factory=list)
    orderbook_slippage_bps: float | None = None
    status: Literal["open", "closed", "expired"] = "open"


class TradeRecord(BaseModel):
    trade_id: str
    signal_id: str
    experiment_id: str | None = None
    symbol: str
    strategy: StrategyName
    split: SplitName
    source: Literal["backtest", "paper"]
    side: Literal["SHORT"]
    entry_time: datetime
    entry_price: float
    exit_time: datetime
    exit_price: float
    gross_return: float
    fee_cost: float
    slippage_cost: float
    funding_cost: float
    net_return: float
    exit_reason: str
    holding_minutes: float
    mae: float
    mfe: float
    orderbook_snapshot_status: QualityState


class ExperimentMetrics(BaseModel):
    net_return: float
    sharpe: float
    sortino: float
    max_drawdown: float
    profit_factor: float
    win_rate: float
    avg_win: float
    avg_loss: float
    trade_count: int
    median_holding_minutes: float
    fee_cost: float
    slippage_cost: float
    funding_cost: float
    top5_removed_net_return: float


class ExperimentRecord(BaseModel):
    experiment_id: str
    name: str
    strategy: StrategyName
    engine: str
    split: SplitName
    status: Literal["running", "accepted", "rejected", "failed", "completed"]
    config_hash: str
    split_hash: str
    data_snapshot_hash: str
    git_commit_hash: str
    report_path: str
    trade_log_path: str
    metrics: ExperimentMetrics
    created_at: datetime
    failure_reason: str | None = None


class PipelineStageRecord(BaseModel):
    run_id: str
    stage: str
    status: Literal["pending", "running", "completed", "failed", "skipped"]
    started_at: datetime | None = None
    completed_at: datetime | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class PipelineRunRecord(BaseModel):
    run_id: str
    name: str
    split: SplitName
    status: Literal["running", "completed", "failed"]
    config_hash: str
    split_hash: str
    data_snapshot_hash: str
    git_commit_hash: str
    report_path: str | None = None
    created_at: datetime
    updated_at: datetime


class ApiEnvelope(BaseModel):
    generated_at: datetime
    source: str
    freshness_sec: int
    data_quality: QualityState
    missing_fields: list[str] = Field(default_factory=list)
    stale_fields: list[str] = Field(default_factory=list)
    payload: Any
