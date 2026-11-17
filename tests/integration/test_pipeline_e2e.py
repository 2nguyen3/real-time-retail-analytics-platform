"""Opt-in pytest integration checks; normal unit-test runs never touch Docker."""

from __future__ import annotations

import os
import subprocess
import uuid
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "tests/integration/run_stage07.py"
ENABLED = os.getenv("RUN_STAGE07_INTEGRATION") == "1"
pytestmark = pytest.mark.skipif(not ENABLED, reason="set RUN_STAGE07_INTEGRATION=1 to use Docker")


def run_cases(*cases: str) -> None:
    batch = "pytest_" + uuid.uuid4().hex[:10]
    result = subprocess.run([str(ROOT / (".venv/Scripts/python.exe" if (ROOT / ".venv/Scripts/python.exe").exists() else ".venv/bin/python")), str(RUNNER),
                             "--cases", *cases, "--batch", batch],
                            cwd=ROOT, capture_output=True, text=True, timeout=360)
    assert result.returncode == 0, (result.stdout + result.stderr)[-3000:]


def test_normal_quality_and_reconciliation() -> None:
    run_cases("TC01", "TC02", "TC03", "TC04", "TC10")


def test_flink_savepoint_restore() -> None:
    run_cases("TC07")
