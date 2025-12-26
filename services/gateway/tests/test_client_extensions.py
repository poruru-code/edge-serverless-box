import pytest
from unittest.mock import AsyncMock, MagicMock
from services.gateway.client import OrchestratorClient
from services.common.models.internal import WorkerInfo


@pytest.mark.asyncio
async def test_client_delete_container():
    """Test delete_container method (Phase 3)"""
    mock_http = AsyncMock()
    mock_http.delete.return_value.status_code = 200

    client = OrchestratorClient(mock_http)

    # Execute
    await client.delete_container("c1")

    # Verify
    mock_http.delete.assert_called_once()
    args, kwargs = mock_http.delete.call_args
    assert "containers/c1" in args[0]


@pytest.mark.asyncio
async def test_client_list_containers():
    """Test list_containers method (Phase 3)"""
    mock_http = AsyncMock()

    # Mock response
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "containers": [
            {
                "id": "c1",
                "name": "n1",
                "ip_address": "1.1.1.1",
                "port": 8080,
                "created_at": 100.0,
                "last_used_at": 200.0,
            }
        ]
    }
    mock_http.get.return_value = mock_resp

    client = OrchestratorClient(mock_http)

    # Execute
    workers = await client.list_containers()

    # Verify
    assert len(workers) == 1
    assert isinstance(workers[0], WorkerInfo)
    assert workers[0].id == "c1"
    assert workers[0].last_used_at == 200.0
    mock_http.get.assert_called_once()
    args, kwargs = mock_http.get.call_args
    assert "containers/sync" in args[0]
