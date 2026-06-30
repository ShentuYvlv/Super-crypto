from __future__ import annotations

from typing import Annotated

import pandas as pd
import typer

from super_crypto.autoresearch.agent_loop import run_loop
from super_crypto.common.config import load_yaml
from super_crypto.common.logging import configure_logging
from super_crypto.common.paths import DATA_ROOT
from super_crypto.common.time import utc_now
from super_crypto.cycles.label_cycles import run as label_cycles
from super_crypto.data.ingest_coinglass import run as ingest_coinglass
from super_crypto.data.ingest_funding import run as ingest_funding
from super_crypto.data.ingest_klines import run as ingest_klines
from super_crypto.data.ingest_market_snapshots import run as ingest_market_snapshots
from super_crypto.data.ingest_open_interest import run as ingest_open_interest
from super_crypto.data.ingest_orderbook import run as ingest_orderbook
from super_crypto.experiments.experiment_store import ExperimentStore
from super_crypto.experiments.pipeline_runner import run_pipeline
from super_crypto.experiments.run_experiment import run as run_experiment
from super_crypto.realtime.scanner import run as run_scanner
from super_crypto.reports.report_server import serve
from super_crypto.universe.manipulation_score import score_symbols, write_scores
from super_crypto.validation.leakage_checks import scan_for_negative_shift
from super_crypto.validation.splits import build_split_manifest, holdout_guard

app = typer.Typer(help="Super Crypto research CLI")
report_app = typer.Typer(help="Report server and dashboard")
app.add_typer(report_app, name="report")


@app.callback()
def main_callback(verbose: bool = typer.Option(False, "--verbose")) -> None:
    configure_logging(verbose=verbose)


@app.command()
def ingest(config: str = typer.Option(..., "--config")) -> None:
    typer.echo(
        {
            "market_snapshots": ingest_market_snapshots(config),
            "klines": ingest_klines(config),
            "funding": ingest_funding(config),
            "open_interest": ingest_open_interest(config),
        }
    )


@app.command("build-splits")
def build_splits_command(config: str = typer.Option(..., "--config")) -> None:
    typer.echo(build_split_manifest(config))


@app.command("detect-cycles")
def detect_cycles_command(
    config: str = typer.Option(..., "--config"),
    symbols: Annotated[list[str] | None, typer.Option()] = None,
) -> None:
    data_config = load_yaml("configs/data.yaml")
    typer.echo(label_cycles(config, symbols or data_config["symbols"]))


@app.command("score-symbols")
def score_symbols_command(config: str = typer.Option(..., "--config")) -> None:
    score_config = load_yaml(config)
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


@app.command()
def enrich(
    config: str = typer.Option(..., "--config"),
    symbols: Annotated[list[str] | None, typer.Option()] = None,
) -> None:
    typer.echo(
        {
            "coinglass": ingest_coinglass(config, symbols=symbols),
            "orderbook": ingest_orderbook(config, symbols=symbols),
        }
    )


@app.command()
def run(
    config: str = typer.Option(..., "--config"),
    split: str = typer.Option(..., "--split"),
    final: bool = typer.Option(False, "--final"),
) -> None:
    holdout_guard("configs/splits.yaml", split, final, ExperimentStore().holdout_run_count())
    typer.echo(run_experiment(config, split, final_flag=final))


@app.command()
def pipeline(
    config: str = typer.Option(..., "--config"),
    split: str = typer.Option("train_validation", "--split"),
    from_stage: str | None = typer.Option(None, "--from"),
    only: str | None = typer.Option(None, "--only"),
    resume: bool = False,
    final: bool = False,
) -> None:
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
    typer.echo(run_scanner(config, once=once))


@app.command()
def autoresearch(
    config: str = typer.Option("configs/experiment_v4a.yaml", "--config"),
    autoresearch_config: str = typer.Option("configs/autoresearch.yaml", "--autoresearch-config"),
) -> None:
    typer.echo(run_loop(config, autoresearch_config_path=autoresearch_config))


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
