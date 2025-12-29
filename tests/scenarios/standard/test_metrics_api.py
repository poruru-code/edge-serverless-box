"""
Gateway metrics API tests.

- Metrics are exposed via Gateway.
- Resource limits are reflected in reported metrics.
"""

import time
import requests
from tests.conftest import (
    GATEWAY_URL,
    VERIFY_SSL,
    call_api,
)


class TestMetricsAPI:
    """Verify Gateway metrics endpoint behavior."""

    def test_metrics_api(self, gateway_health, auth_token):
        """E2E: metrics endpoint returns container metrics."""
        response = call_api("/api/echo", auth_token, {"message": "metrics"})
        assert response.status_code == 200

        headers = {"Authorization": f"Bearer {auth_token}"}
        expected_memory_max = 128 * 1024 * 1024

        metrics_entry = None
        for _ in range(10):
            metrics_resp = requests.get(
                f"{GATEWAY_URL}/metrics/containers",
                headers=headers,
                verify=VERIFY_SSL,
            )
            assert metrics_resp.status_code == 200
            data = metrics_resp.json()
            metrics_entry = next(
                (item for item in data.get("containers", []) if item.get("function_name") == "lambda-echo"),
                None,
            )
            if metrics_entry and metrics_entry.get("memory_max", 0) > 0:
                break
            time.sleep(1)

        assert metrics_entry is not None
        assert metrics_entry["state"] in {"RUNNING", "PAUSED"}
        assert metrics_entry["memory_max"] == expected_memory_max
        assert metrics_entry["memory_current"] >= 0
        assert metrics_entry["cpu_usage_ns"] >= 0
