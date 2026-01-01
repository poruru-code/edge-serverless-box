# Where: services/runtime-node/tests/test_entrypoint.py
# What: Tests for runtime-node entrypoint safeguards.
# Why: Prevent devmapper pool reinitialization regressions.
from pathlib import Path


def test_entrypoint_requires_existing_devmapper_pool():
    script = Path("services/runtime-node/entrypoint.sh").read_text()
    assert "ensure_devmapper_ready" in script
    assert "dmsetup status" in script
    assert "Run esb node provision." in script
    assert "dmsetup create" not in script


def test_entrypoint_applies_hv_network_guard():
    script = Path("services/runtime-node/entrypoint.sh").read_text()
    assert "ensure_hv_network" in script
    assert "tx-checksumming off" in script
