from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_cli_help_runs():
    project_root = Path(__file__).resolve().parents[1]
    env = {
        **os.environ,
        "PYTHONPATH": str(project_root / "src"),
    }
    result = subprocess.run(
        [sys.executable, "-m", "super_crypto.cli", "--help"],
        capture_output=True,
        text=True,
        check=False,
        cwd=project_root,
        env=env,
    )
    assert result.returncode == 0
    assert "Super Crypto research CLI" in result.stdout
