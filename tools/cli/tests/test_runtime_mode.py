# Where: tools/cli/tests/test_runtime_mode.py
# What: Tests for runtime mode persistence helpers.
# Why: Ensure mode settings are stored and read predictably.
import pytest

from tools.cli import config as cli_config
from tools.cli import runtime_mode


def test_load_mode_defaults_when_missing(tmp_path):
    """Return default mode when config file is missing."""
    mode_path = tmp_path / "mode.yaml"
    data = runtime_mode.load_mode(mode_path)
    assert data["mode"] == cli_config.DEFAULT_ESB_MODE


def test_save_mode_roundtrip(tmp_path):
    """Persist and reload the selected mode."""
    mode_path = tmp_path / "mode.yaml"
    runtime_mode.save_mode(cli_config.ESB_MODE_FIRECRACKER, mode_path)
    assert runtime_mode.get_mode(mode_path) == cli_config.ESB_MODE_FIRECRACKER


def test_save_mode_invalid_raises(tmp_path):
    """Reject invalid mode values."""
    mode_path = tmp_path / "mode.yaml"
    with pytest.raises(ValueError):
        runtime_mode.save_mode("invalid", mode_path)
