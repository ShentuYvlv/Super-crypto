from __future__ import annotations

from typing import Annotated

import pandas as pd
import typer
import yaml

from super_crypto.autoresearch.agent_loop import run_loop
from super_crypto.common.config import load_yaml
from super_crypto.common.logging import configure_logging
from super_crypto.common.paths import DATA_ROOT, resolve_project_path
from super_crypto.common.time import utc_now
from super_crypto.cycles.label_cycles import run as label_cycles
from super_crypto.cycles.seed_events import build_event_set
from super_crypto.data.ingest_coinglass import run as ingest_coinglass
from super_crypto.data.ingest_funding import run as ingest_funding
from super_crypto.data.ingest_klines import run as ingest_klines
from super_crypto.data.ingest_market_snapshots import run as ingest_market_snapshots
from super_crypto.data.ingest_open_interest import run as ingest_open_interest
from super_crypto.data.ingest_orderbook import run as ingest_orderbook
from super_crypto.experiments.experiment_store import ExperimentStore
from super_crypto.experiments.pipeline_runner import run_pipeline
from super_crypto.experiments.run_experiment import build_expanded_experiment_config
from super_crypto.experiments.run_experiment import latest_frozen_config_path
from super_crypto.experiments.run_experiment import run as run_experiment
from super_crypto.realtime.scanner import run as run_scanner
from super_crypto.reports.report_server import serve
from super_crypto.universe.manipulation_score import score_symbols, write_scores
from super_crypto.validation.leakage_checks import scan_for_negative_shift
from super_crypto.validation.splits import build_split_manifest, holdout_guard

app = typer.Typer(help="Super Crypto research CLI")
report_app = typer.Typer(help="Report server and dashboard")
app.add_typer(report_app, name="report")


def _config_section(config_path: str, key: str) -> dict:
    payload = load_yaml(config_path)
    return payload.get(key, payload)


def _echo_research_result(result: dict) -> None:
    typer.echo(f"AutoResearch run_id: {result['run_id']}")
    typer.echo(f"status: {result['status']}")
    typer.echo(f"created_at: {result['created_at']}")
    typer.echo(f"config: {result['config_path']}")
    typer.echo(f"model_mode: {result['model_status']['mode']}")
    typer.echo(f"model_reason: {result['model_status']['reason']}")
    typer.echo(f"recommendation: {result['recommendation']}")
    typer.echo(f"manifest: {result['manifest_path']}")
    typer.echo("iterations:")
    for iteration in result["iterations"]:
        experiment = iteration["validation_result"]["experiment"]
        acceptance = iteration["validation_acceptance"]
        metrics = experiment["metrics"]
        typer.echo(
            "  "
            f"#{iteration['iteration']} "
            f"{experiment['experiment_id']} "
            f"{experiment['created_at']} "
            f"{acceptance['reason']} "
            f"trades={metrics['trade_count']} "
            f"net={metrics['net_return']:.2%}"
        )
        typer.echo(f"     started={iteration['started_at']} completed={iteration['completed_at']}")


def _run_research(
    config: str,
    autoresearch_config: str,
    max_runs: int | None,
    no_llm: bool,
) -> dict:
    return run_loop(
        config,
        autoresearch_config_path=autoresearch_config,
        max_runs=max_runs,
        use_llm=not no_llm,
    )


def _holdout_splits_config(config: str) -> dict:
    expanded = build_expanded_experiment_config(config)
    return expanded["splits"]


def _holdout_frozen_config_path(config: str) -> str:
    expanded = build_expanded_experiment_config(config)
    configured_path = expanded.get("frozen_config_path")
    if configured_path:
        return str(resolve_project_path(configured_path))
    return str(latest_frozen_config_path(expanded["strategy"]["strategy"]))


@app.callback()
def main_callback(verbose: bool = typer.Option(False, "--verbose")) -> None:
    configure_logging(verbose=verbose)


@app.command()
def ingest(config: str = typer.Option(..., "--config")) -> None:
    data_config = _config_section(config, "data")
    typer.echo(
        {
            "market_snapshots": ingest_market_snapshots(data_config),
            "klines": ingest_klines(data_config),
            "funding": ingest_funding(data_config),
            "open_interest": ingest_open_interest(data_config),
        }
    )


@app.command("build-splits")
def build_splits_command(config: str = typer.Option(..., "--config")) -> None:
    typer.echo(build_split_manifest(_config_section(config, "splits")))


@app.command("detect-cycles")
def detect_cycles_command(
    config: str = typer.Option(..., "--config"),
    symbols: Annotated[list[str] | None, typer.Option()] = None,
) -> None:
    payload = load_yaml(config)
    data_config = payload.get("data") or load_yaml("configs/pipeline_v4a.yaml")["data"]
    typer.echo(label_cycles(payload.get("cycle", payload), symbols or data_config["symbols"]))


@app.command("score-symbols")
def score_symbols_command(config: str = typer.Option(..., "--config")) -> None:
    score_config = _config_section(config, "scores")
    cycles_dir = DATA_ROOT / "processed" / "cycles"
    derivatives_dir = DATA_ROOT / "processed" / "derivatives"
    cycle_frames = []
    derivatives = {}
    for cycle_path in cycles_dir.glob("*.parquet"):
        frame = pd.read_parquet(cycle_path)
        frame["pump_start"] = pd.to_datetime(frame["pump_start"], utc=True)
        cycle_frames.append(frame)
        symbol = cycle_path.stem
        oi_path = derivatives_dir / f"open_interest_{symbol}.parquet"
        if oi_path.exists():
            derivatives[symbol] = pd.read_parquet(oi_path)
    cycles = pd.concat(cycle_frames, ignore_index=True) if cycle_frames else pd.DataFrame()
    scores = score_symbols(
        cycles, cutoff_time=utc_now(), config=score_config, derivatives_by_symbol=derivatives
    )
    path = write_scores(str(DATA_ROOT / "processed" / "scores" / "latest.parquet"), scores)
    typer.echo({"score_count": len(scores), "path": str(path)})


@app.command("build-event-set")
def build_event_set_command(
    seed_events_config: str = typer.Option(..., "--seed-events-config"),
    cycle_config: str = typer.Option(..., "--cycle-config"),
) -> None:
    typer.echo(build_event_set(seed_events_config, cycle_config))


@app.command()
def enrich(
    config: str = typer.Option(..., "--config"),
    symbols: Annotated[list[str] | None, typer.Option()] = None,
) -> None:
    enrichment_config = _config_section(config, "enrichment")
    typer.echo(
        {
            "coinglass": ingest_coinglass(enrichment_config, symbols=symbols),
            "orderbook": ingest_orderbook(enrichment_config, symbols=symbols),
        }
    )


@app.command()
def run(
    config: str = typer.Option(..., "--config"),
    split: str = typer.Option(..., "--split"),
    final: bool = typer.Option(False, "--final"),
) -> None:
    """Debug a single experiment without running the full research loop."""
    experiment_config = load_yaml(config)
    splits_guard_config = experiment_config.get("splits") or experiment_config.get(
        "splits_config",
        load_yaml("configs/pipeline_v4a.yaml")["splits"],
    )
    holdout_guard(splits_guard_config, split, final, ExperimentStore().holdout_run_count())
    typer.echo(run_experiment(config, split, final_flag=final))


@app.command()
def research(
    config: str = typer.Option("configs/experiment_v4a_full.yaml", "--config"),
    autoresearch_config: str = typer.Option("configs/autoresearch.yaml", "--autoresearch-config"),
    max_runs: int | None = typer.Option(None, "--max-runs", min=1),
    no_llm: bool = typer.Option(False, "--no-llm"),
) -> None:
    """Run the main AutoResearch loop."""
    _echo_research_result(_run_research(config, autoresearch_config, max_runs, no_llm))


@app.command()
def holdout(config: str = typer.Option("configs/experiment_v4a_full.yaml", "--config")) -> None:
    """Run the protected final holdout on the latest frozen strategy config."""
    frozen_config_path = _holdout_frozen_config_path(config)
    if not resolve_project_path(frozen_config_path).exists():
        typer.echo(
            (
                "No frozen config found. Run `just research` until a validation experiment is "
                f"accepted first. Expected frozen config: {frozen_config_path}"
            ),
            err=True,
        )
        raise typer.Exit(code=1)
    store = ExperimentStore()
    holdout_guard(
        _holdout_splits_config(config),
        "holdout",
        final=True,
        existing_holdout_runs=store.holdout_run_count(),
    )
    typer.echo(run_experiment(config, "holdout", final_flag=True))


@app.command("expand-experiment-config")
def expand_experiment_config_command(
    config: str = typer.Option(..., "--config"),
    output: str = typer.Option(..., "--output"),
) -> None:
    expanded = build_expanded_experiment_config(config)
    output_path = resolve_project_path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(expanded, handle, sort_keys=False, allow_unicode=True)
    typer.echo({"output": str(output_path)})


@app.command()
def pipeline(
    config: str = typer.Option(..., "--config"),
    split: str = typer.Option("train_validation", "--split"),
    from_stage: str | None = typer.Option(None, "--from"),
    only: str | None = typer.Option(None, "--only"),
    resume: bool = False,
    final: bool = False,
) -> None:
    """Debug the internal execution pipeline used by research."""
    typer.echo(
        run_pipeline(
            config,
            split,
            from_stage=from_stage,
            only_stage=only,
            resume=resume,
            final_flag=final,
        )
    )


@app.command()
def scanner(
    config: str = typer.Option(..., "--config"),
    once: bool = typer.Option(False, "--once"),
) -> None:
    """Run a forward-test scanner pass after research has selected a strategy."""
    typer.echo(run_scanner(config, once=once))


@app.command()
def autoresearch(
    config: str = typer.Option("configs/experiment_v4a_full.yaml", "--config"),
    autoresearch_config: str = typer.Option("configs/autoresearch.yaml", "--autoresearch-config"),
    max_runs: int | None = typer.Option(None, "--max-runs", min=1),
    no_llm: bool = typer.Option(False, "--no-llm"),
) -> None:
    """Compatibility alias for `research`."""
    _echo_research_result(_run_research(config, autoresearch_config, max_runs, no_llm))


@app.command("leakage-check")
def leakage_check() -> None:
    offenders = scan_for_negative_shift()
    if offenders:
        raise typer.Exit(code=1)
    typer.echo({"status": "ok"})


@report_app.command("serve")
def serve_command(host: str = "127.0.0.1", port: int = 8000) -> None:
    serve(host, port)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
