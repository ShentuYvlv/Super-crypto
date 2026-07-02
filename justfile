set windows-shell := ["powershell.exe", "-NoLogo", "-NoProfile", "-Command"]
set shell := ["sh", "-cu"]

research:
  BINANCE_TRUST_ENV=1 uv run python -m super_crypto.cli research

holdout:
  BINANCE_TRUST_ENV=1 uv run python -m super_crypto.cli holdout

dashboard:
  uv run python -m super_crypto.cli report serve --host 127.0.0.1 --port 8000

dev-test:
  uv run pytest

dev-pipeline config="configs/pipeline_v4a.yaml" split="train_validation":
  BINANCE_TRUST_ENV=1 uv run python -m super_crypto.cli pipeline --config {{config}} --split {{split}}

dev-cycle-research config="configs/cycle_discovery.yaml":
  BINANCE_TRUST_ENV=1 uv run python -m super_crypto.cli cycle-research --config {{config}}

dev-experiment config="configs/experiment_v4a_full.yaml" split="validation":
  BINANCE_TRUST_ENV=1 uv run python -m super_crypto.cli run --config {{config}} --split {{split}}

dev-research-local config="configs/experiment_v4a_full.yaml" max_runs="3":
  uv run python -m super_crypto.cli research --config {{config}} --max-runs {{max_runs}} --no-llm

dev-forward-test config="configs/scanner.yaml":
  BINANCE_TRUST_ENV=1 uv run python -m super_crypto.cli scanner --config {{config}} --once

dev-expand-experiment config="configs/experiment_v4a_full.yaml" output="configs/experiment_v4a_full.yaml":
  uv run python -m super_crypto.cli expand-experiment-config --config {{config}} --output {{output}}
