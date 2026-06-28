set shell := ["zsh", "-lc"]

research:
  uv run python -m super_crypto.cli pipeline --config configs/pipeline_v4a.yaml --split train_validation

holdout:
  uv run python -m super_crypto.cli pipeline --config configs/pipeline_v4a.yaml --split holdout --final

resume:
  uv run python -m super_crypto.cli pipeline --config configs/pipeline_v4a.yaml --resume

scan:
  uv run python -m super_crypto.cli scanner --config configs/scanner.yaml --once

dashboard:
  uv run python -m super_crypto.cli report serve --host 127.0.0.1 --port 8000

test:
  uv run pytest

