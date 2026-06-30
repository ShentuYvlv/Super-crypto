from __future__ import annotations

import pytest

from super_crypto.validation.leakage_checks import scan_for_negative_shift
from super_crypto.validation.splits import holdout_guard


def test_holdout_requires_final_flag():
    with pytest.raises(ValueError):
        holdout_guard("configs/splits.yaml", "holdout", False)


def test_no_negative_shift_in_signal_files():
    assert scan_for_negative_shift() == []
