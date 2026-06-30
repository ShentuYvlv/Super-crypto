from __future__ import annotations

import subprocess
from itertools import product
from pathlib import Path

import pandas as pd

from super_crypto.autoresearch.accept_reject_policy import accept
from super_crypto.backtest.event_backtester import run_event_backtest
from super_crypto.backtest.metrics import summarize_metrics
from super_crypto.backtest.trade_report import to_frame, write_csv
from super_crypto.backtest.vectorbt_runner import run_vectorbt_benchmark
from super_crypto.common.config import hash_file, hash_payload, load_yaml
from super_crypto.common.paths import DATA_ROOT, REPORT_ROOT, ensure_directory
from super_crypto.common.time import parse_timestamp, to_iso, utc_now
from super_crypto.experiments.experiment_store import ExperimentStore
from super_crypto.features.orderbook_features import latest_orderbook_metrics
from super_crypto.reports.html_report import render_html_report
from super_crypto.reports.markdown_report import render_markdown_report
from super_crypto.signals.v3_abandon_point import generate as generate_v3
from super_crypto.signals.v4a_early_short import generate as generate_v4a
from super_crypto.signals.v4b_confirmed_short import generate as generate_v4b
from super_crypto.universe.manipulation_score import score_symbols
from super_crypto.validation.robustness import by_month, by_symbol
from super_crypto.validation.splits import filter_frame_for_split, split_hash

GENERATOR_MAP = {
    "V3": generate_v3,
    "V4A": generate_v4a,
    "V4B": generate_v4b,
}


def _git_commit_hash() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


def _data_snapshot_hash(paths: list[Path]) -> str:
    payload = [
        {"path": str(path), "mtime": path.stat().st_mtime_ns, "size": path.stat().st_size}
        for path in paths
        if path.exists()
    ]
    return hash_payload(payload)


def _score_cutoff_for_split(split: str) -> pd.Timestamp:
    split_config = load_yaml("configs/splits.yaml")
    if split == "train_validation":
        return parse_timestamp(split_config["validation"]["end"])
    return parse_timestamp(split_config[split]["end"])


def _load_scores(
    config_path: str,
    symbols: list[str],
    cutoff_time,
    derivatives_by_symbol: dict[str, pd.DataFrame],
) -> list:
    cycle_frames = []
    for symbol in symbols:
        path = DATA_ROOT / "processed" / "cycles" / f"{symbol}.parquet"
        if path.exists():
            frame = pd.read_parquet(path)
            frame["pump_start"] = pd.to_datetime(frame["pump_start"], utc=True)
            if "dump_end" in frame.columns:
                frame["dump_end"] = pd.to_datetime(frame["dump_end"], utc=True)
                frame = frame[frame["dump_end"] <= parse_timestamp(cutoff_time)]
            cycle_frames.append(frame)
    cycles = pd.concat(cycle_frames, ignore_index=True) if cycle_frames else pd.DataFrame()
    return score_symbols(
        cycles,
        cutoff_time=cutoff_time,
        config=load_yaml(config_path),
        derivatives_by_symbol=derivatives_by_symbol,
    )


def _run_strategy_for_config(
    *,
    symbols: list[str],
    ohlcv_by_symbol: dict[str, pd.DataFrame],
    funding_by_symbol: dict[str, pd.DataFrame],
    open_interest_by_symbol: dict[str, pd.DataFrame],
    orderbook_slippage_by_symbol: dict[str, float],
    split: str,
    generator,
    strategy_config: dict,
    backtest_config: dict,
    manipulation_bucket_by_symbol: dict[str, str],
) -> tuple[list[dict], list[dict]]:
    signals_payloads = []
    trades_payloads = []
    for symbol in symbols:
        split_frame = ohlcv_by_symbol[symbol]
        signals = generator(
            split_frame,
            symbol,
            strategy_config,
            funding=funding_by_symbol[symbol],
            open_interest=open_interest_by_symbol[symbol],
            manipulation_bucket=manipulation_bucket_by_symbol.get(symbol, "low"),
            orderbook_slippage_bps=orderbook_slippage_by_symbol[symbol],
        )
        signals_payloads.extend([signal.model_dump(mode="json") for signal in signals])
        max_hold_bars = int(
            strategy_config.get(
                "max_hold_bars",
                backtest_config["max_hold_hours"].get(
                    str(strategy_config["strategy"]).lower(),
                    8,
                ),
            )
        )
        trades = run_event_backtest(
            split_frame,
            signals,
            split=split,
            capital_per_trade_usdt=float(backtest_config["capital_per_trade_usdt"]),
            fee_bps=float(backtest_config["fee_bps"]),
            default_slippage_bps=float(backtest_config["slippage_bps_floor"]),
            max_hold_bars=max_hold_bars,
        )
        trades_payloads.extend([trade.model_dump(mode="json") for trade in trades])
    return signals_payloads, trades_payloads


def _select_parameters(
    parameter_scan: list[dict],
    base_metrics: dict,
    *,
    minimum_trade_count: int,
    allow_selection: bool,
) -> tuple[dict, str, str]:
    if not allow_selection or not parameter_scan:
        return {}, "base_strategy_config", "parameter_selection_disabled"
    for candidate in parameter_scan:
        accepted, reason = accept(
            {"metrics": candidate["metrics"]},
            baseline={"metrics": base_metrics},
            minimum_trade_count=minimum_trade_count,
        )
        if accepted:
            return candidate["params"], "parameter_grid", reason
    best = parameter_scan[0]
    if best["metrics"]["net_return"] > base_metrics["net_return"] and best["metrics"]["trade_count"] >= base_metrics["trade_count"]:
        return best["params"], "parameter_grid_best_effort", "best_grid_candidate_improved_primary_metric"
    return {}, "base_strategy_config", "no_grid_candidate_accepted"


def _parameter_scan(
    *,
    symbols: list[str],
    ohlcv_by_symbol: dict[str, pd.DataFrame],
    funding_by_symbol: dict[str, pd.DataFrame],
    open_interest_by_symbol: dict[str, pd.DataFrame],
    orderbook_slippage_by_symbol: dict[str, float],
    split: str,
    generator,
    strategy_config: dict,
    backtest_config: dict,
    parameter_grid: dict[str, list],
    manipulation_bucket_by_symbol: dict[str, str],
) -> list[dict]:
    if not parameter_grid:
        return []
    keys = list(parameter_grid.keys())
    combos = [
        dict(zip(keys, values, strict=True))
        for values in product(*(parameter_grid[key] for key in keys))
    ]
    results = []
    for combo in combos:
        combo_config = {**strategy_config, **combo}
        combo_trades = []
        combo_signal_count = 0
        for symbol in symbols:
            split_frame = ohlcv_by_symbol[symbol]
            signals = generator(
                split_frame,
                symbol,
                combo_config,
                funding=funding_by_symbol[symbol],
                open_interest=open_interest_by_symbol[symbol],
                manipulation_bucket=manipulation_bucket_by_symbol.get(symbol, "low"),
                orderbook_slippage_bps=orderbook_slippage_by_symbol[symbol],
            )
            combo_signal_count += len(signals)
            trades = run_event_backtest(
                split_frame,
                signals,
                split=split,
                capital_per_trade_usdt=float(backtest_config["capital_per_trade_usdt"]),
                fee_bps=float(backtest_config["fee_bps"]),
                default_slippage_bps=float(backtest_config["slippage_bps_floor"]),
                max_hold_bars=int(
                    combo_config.get(
                        "max_hold_bars",
                        backtest_config["max_hold_hours"].get(
                            str(strategy_config["strategy"]).lower(),
                            8,
                        ),
                    )
                ),
            )
            combo_trades.extend([trade.model_dump(mode="json") for trade in trades])
        combo_metrics = summarize_metrics(to_frame(combo_trades)).model_dump(mode="json")
        results.append(
            {
                "params": combo,
                "signal_count": combo_signal_count,
                "metrics": combo_metrics,
            }
        )
    return sorted(
        results,
        key=lambda item: (item["metrics"]["net_return"], item["metrics"]["trade_count"]),
        reverse=True,
    )


def run(config_path: str, split: str, final_flag: bool = False) -> dict:
    experiment_config = load_yaml(config_path)
    strategy_config = load_yaml(experiment_config["strategy_config"])
    backtest_config = load_yaml(experiment_config["backtest_config"])
    strategy_name = str(strategy_config["strategy"])
    generator = GENERATOR_MAP[strategy_name]
    ohlcv_paths = sorted(
        (DATA_ROOT / "processed" / "ohlcv" / strategy_config["timeframe"]).glob("*.parquet")
    )
    store = ExperimentStore()
    derivatives_by_symbol: dict[str, pd.DataFrame] = {}
    ohlcv_by_symbol: dict[str, pd.DataFrame] = {}
    funding_by_symbol: dict[str, pd.DataFrame] = {}
    open_interest_by_symbol: dict[str, pd.DataFrame] = {}
    orderbook_slippage_by_symbol: dict[str, float] = {}
    symbols = [path.stem for path in ohlcv_paths]
    for symbol in symbols:
        funding_path = DATA_ROOT / "processed" / "derivatives" / f"funding_{symbol}.parquet"
        oi_path = DATA_ROOT / "processed" / "derivatives" / f"open_interest_{symbol}.parquet"
        funding = pd.read_parquet(funding_path) if funding_path.exists() else pd.DataFrame()
        open_interest = pd.read_parquet(oi_path) if oi_path.exists() else pd.DataFrame()
        funding_by_symbol[symbol] = funding
        open_interest_by_symbol[symbol] = open_interest
        derivatives_by_symbol[symbol] = open_interest.assign(
            funding_rate=float(funding["funding_rate"].iloc[-1]) if not funding.empty else 0.0
        )
    cutoff_time = _score_cutoff_for_split(split)
    score_records = _load_scores(
        experiment_config["scores_config"],
        symbols,
        cutoff_time,
        derivatives_by_symbol,
    )
    score_lookup = {score.symbol: score for score in score_records}
    manipulation_bucket_by_symbol = {symbol: score.bucket for symbol, score in score_lookup.items()}
    for ohlcv_path in ohlcv_paths:
        symbol = ohlcv_path.stem
        ohlcv = pd.read_parquet(ohlcv_path)
        split_frame = filter_frame_for_split(ohlcv, "configs/splits.yaml", split)
        if split_frame.empty:
            continue
        ohlcv_by_symbol[symbol] = split_frame
        funding_path = DATA_ROOT / "processed" / "derivatives" / f"funding_{symbol}.parquet"
        oi_path = DATA_ROOT / "processed" / "derivatives" / f"open_interest_{symbol}.parquet"
        orderbook_path = DATA_ROOT / "processed" / "orderbook_features" / f"{symbol}.parquet"
        funding = pd.read_parquet(funding_path) if funding_path.exists() else pd.DataFrame()
        open_interest = pd.read_parquet(oi_path) if oi_path.exists() else pd.DataFrame()
        orderbook = pd.read_parquet(orderbook_path) if orderbook_path.exists() else pd.DataFrame()
        orderbook_metrics = latest_orderbook_metrics(orderbook)
        orderbook_slippage_by_symbol[symbol] = orderbook_metrics["slippage_500"]
    base_signals_payloads, base_trades_payloads = _run_strategy_for_config(
        symbols=list(ohlcv_by_symbol),
        ohlcv_by_symbol=ohlcv_by_symbol,
        funding_by_symbol=funding_by_symbol,
        open_interest_by_symbol=open_interest_by_symbol,
        orderbook_slippage_by_symbol=orderbook_slippage_by_symbol,
        split=split,
        generator=generator,
        strategy_config=strategy_config,
        backtest_config=backtest_config,
        manipulation_bucket_by_symbol=manipulation_bucket_by_symbol,
    )
    base_metrics = summarize_metrics(to_frame(base_trades_payloads)).model_dump(mode="json")
    parameter_scan = _parameter_scan(
        symbols=list(ohlcv_by_symbol),
        ohlcv_by_symbol=ohlcv_by_symbol,
        funding_by_symbol=funding_by_symbol,
        open_interest_by_symbol=open_interest_by_symbol,
        orderbook_slippage_by_symbol=orderbook_slippage_by_symbol,
        split=split,
        generator=generator,
        strategy_config=strategy_config,
        backtest_config=backtest_config,
        parameter_grid=experiment_config.get("parameter_grid", {}),
        manipulation_bucket_by_symbol=manipulation_bucket_by_symbol,
    )
    minimum_trade_count = int(experiment_config.get("minimum_trade_count", 20))
    selected_parameters, selection_source, selection_reason = _select_parameters(
        parameter_scan,
        base_metrics,
        minimum_trade_count=minimum_trade_count,
        allow_selection=split != "holdout",
    )
    selected_strategy_config = {**strategy_config, **selected_parameters}
    if selected_parameters:
        signals_payloads, trades_payloads = _run_strategy_for_config(
            symbols=list(ohlcv_by_symbol),
            ohlcv_by_symbol=ohlcv_by_symbol,
            funding_by_symbol=funding_by_symbol,
            open_interest_by_symbol=open_interest_by_symbol,
            orderbook_slippage_by_symbol=orderbook_slippage_by_symbol,
            split=split,
            generator=generator,
            strategy_config=selected_strategy_config,
            backtest_config=backtest_config,
            manipulation_bucket_by_symbol=manipulation_bucket_by_symbol,
        )
    else:
        signals_payloads, trades_payloads = base_signals_payloads, base_trades_payloads
    trades_frame = to_frame(trades_payloads)
    metrics = summarize_metrics(trades_frame)
    experiment_id = hash_payload(
        {
            "config": hash_file(config_path),
            "split": split,
            "run_at": to_iso(utc_now()),
            "strategy": strategy_name,
        }
    )[:12]
    trades_payloads = [{**trade, "experiment_id": experiment_id} for trade in trades_payloads]
    report_dir = ensure_directory(REPORT_ROOT / experiment_id)
    trade_log_path = write_csv(trades_frame, report_dir / "trades.csv")
    report_context = {
        "experiment_id": experiment_id,
        "strategy": strategy_name,
        "engine": experiment_config["engine"],
        "split": split,
        "metrics": metrics.model_dump(),
        "trades": trades_payloads,
        "symbol_breakdown": by_symbol(trades_frame).to_dict(orient="records"),
        "month_breakdown": by_month(trades_frame).to_dict(orient="records"),
        "signals": signals_payloads,
    }
    markdown_path = render_markdown_report(report_dir / "report.md", report_context)
    html_path = render_html_report(report_dir / "report.html", report_context)
    vectorbt_benchmark = run_vectorbt_benchmark(
        ohlcv_by_symbol=ohlcv_by_symbol,
        signals=signals_payloads,
        split=split,
        backtest_config=backtest_config,
        strategy_config=selected_strategy_config,
    )
    accepted, decision_reason = accept(
        {"metrics": metrics.model_dump(mode="json")},
        minimum_trade_count=minimum_trade_count,
    )
    experiment_payload = {
        "experiment_id": experiment_id,
        "name": experiment_config["name"],
        "strategy": strategy_name,
        "engine": experiment_config["engine"],
        "split": split,
        "status": "accepted" if accepted else "rejected",
        "config_path": str(config_path),
        "strategy_config_path": str(experiment_config["strategy_config"]),
        "backtest_config_path": str(experiment_config["backtest_config"]),
        "config_hash": hash_file(config_path),
        "split_hash": split_hash("configs/splits.yaml"),
        "data_snapshot_hash": _data_snapshot_hash(ohlcv_paths),
        "git_commit_hash": _git_commit_hash(),
        "markdown_report_path": markdown_path,
        "report_path": html_path,
        "trade_log_path": trade_log_path,
        "metrics": metrics.model_dump(mode="json"),
        "base_metrics": base_metrics,
        "selected_parameters": selected_parameters,
        "parameter_selection_source": selection_source,
        "parameter_selection_reason": selection_reason,
        "parameter_sensitivity": parameter_scan[:20],
        "vectorbt_benchmark": vectorbt_benchmark,
        "created_at": to_iso(utc_now()),
        "failure_reason": None if accepted else decision_reason,
    }
    store.upsert("experiments", "experiment_id", experiment_payload)
    store.bulk_upsert("signals", "signal_id", signals_payloads)
    store.bulk_upsert("trades", "trade_id", trades_payloads)
    if split == "holdout":
        store.record_holdout_audit(
            {
                "created_at": to_iso(utc_now()),
                "experiment_id": experiment_id,
                "config_hash": experiment_payload["config_hash"],
                "split_hash": experiment_payload["split_hash"],
                "final_flag": final_flag,
            }
        )
    return {
        "experiment": experiment_payload,
        "markdown_report": markdown_path,
        "html_report": html_path,
        "trades": trade_log_path,
    }
