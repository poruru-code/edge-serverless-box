import pytest
from unittest.mock import AsyncMock, MagicMock
from services.orchestrator.service import ContainerOrchestrator
from services.common.models.internal import WorkerInfo


@pytest.mark.asyncio
async def test_orchestrator_stop_container():
    """Test stop_container method (Phase 2)"""
    orchestrator = ContainerOrchestrator()
    orchestrator.docker = MagicMock()
    # Mock container info
    orchestrator.docker.params = {"c1": {"name": "lambda-func-1", "id": "c1"}}

    # Mock stop_container (docker adaptor)
    orchestrator.docker.stop_container = AsyncMock()

    # Execute
    await orchestrator.stop_container("c1")

    # Verify
    orchestrator.docker.stop_container.assert_called_once_with("c1")
    # Verify cleanup from internal state if any (though Orchestrator mainly relies on Docker state?)
    # The specification implies Orchestrator might track managed containers.


@pytest.mark.asyncio
async def test_orchestrator_list_managed_containers():
    """Test list_managed_containers method (Phase 2)"""
    orchestrator = ContainerOrchestrator()
    orchestrator.docker = MagicMock()

    # Mock list_containers return
    mock_workers = [
        WorkerInfo(id="c1", name="lambda-func-1", ip_address="1.1.1.1"),
        WorkerInfo(id="c2", name="lambda-func-2", ip_address="1.1.1.2"),
    ]
    orchestrator.docker.list_containers = AsyncMock(return_value=mock_workers)

    # Execute
    workers = await orchestrator.list_managed_containers()

    # Verify
    assert len(workers) == 2
    assert workers[0].id == "c1"
    orchestrator.docker.list_containers.assert_called_once()
