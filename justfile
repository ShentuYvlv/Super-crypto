set windows-shell := ["powershell.exe", "-NoLogo", "-NoProfile", "-Command"]
set shell := ["sh", "-cu"]

research config="configs/pipeline_v4a.yaml" split="train_validation":
  @echo "research: pipeline_config={{config}} split={{split}}"
  uv run python -m super_crypto.cli pipeline --config {{config}} --split {{split}}

experiment config="configs/experiment_v4a_full.yaml" split="validation":
  @echo "experiment: experiment_config={{config}} split={{split}}"
  uv run python -m super_crypto.cli run --config {{config}} --split {{split}}

expand-experiment config="configs/experiment_v4a_full.yaml" output="configs/experiment_v4a_full.yaml":
  @echo "expand-experiment: input={{config}} output={{output}}"
  uv run python -m super_crypto.cli expand-experiment-config --config {{config}} --output {{output}}

loopresearch config="configs/experiment_v4a_full.yaml" max_runs="3":
  @echo "loopresearch: experiment_config={{config}} llm=auto max_runs={{max_runs}}"
  uv run python -m super_crypto.cli autoresearch --config {{config}} --max-runs {{max_runs}}

loopresearch-local config="configs/experiment_v4a_full.yaml" max_runs="3":
  @echo "loopresearch-local: experiment_config={{config}} llm=off max_runs={{max_runs}}"
  uv run python -m super_crypto.cli autoresearch --config {{config}} --max-runs {{max_runs}} --no-llm

holdout config="configs/pipeline_v4a.yaml":
  @echo "holdout: pipeline_config={{config}} split=holdout final=true"
  uv run python -m super_crypto.cli pipeline --config {{config}} --split holdout --final

resume config="configs/pipeline_v4a.yaml":
  @echo "resume: pipeline_config={{config}}"
  uv run python -m super_crypto.cli pipeline --config {{config}} --resume

scan config="configs/scanner.yaml":
  @echo "scan: scanner_config={{config}}"
  uv run python -m super_crypto.cli scanner --config {{config}} --once

dashboard:
  uv run python -m super_crypto.cli report serve --host 127.0.0.1 --port 8000

test:
  uv run pytest
