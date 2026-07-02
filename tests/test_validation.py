from __future__ import annotations

import pytest

from super_crypto.common.config import load_yaml
from super_crypto.common.config_validation import validate_pipeline_config, validate_split_config
from super_crypto.validation.leakage_checks import scan_for_negative_shift
from super_crypto.validation.splits import holdout_guard


def test_holdout_requires_final_flag():
    with pytest.raises(ValueError):
        holdout_guard("configs/pipeline_v4a.yaml", "holdout", False)


def test_no_negative_shift_in_signal_files():
    assert scan_for_negative_shift() == []


def test_primary_configs_parse_and_validate():
    pipeline = load_yaml("configs/pipeline_v4a.yaml")
    experiment = load_yaml("configs/experiment_v4a_full.yaml")

    validate_pipeline_config(pipeline)
    validate_split_config(experiment["splits"])
