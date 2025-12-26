import pytest
from unittest.mock import MagicMock, AsyncMock
from services.orchestrator.service import ContainerOrchestrator
from services.orchestrator.docker_adaptor import DockerAdaptor


@pytest.mark.asyncio
class TestContainerOrchestratorStopBug:
    """
    ContainerOrchestrator.stop_container のバグ(ID文字列を直接stopに渡す)を検証・修正するためのテスト
    """

    async def test_stop_container_uses_object_not_id(self):
        """
        stop_container が DockerAdaptor.stop_container に ID(str) ではなく
        Container Object を渡しているかを検証する。
        現状の実装では str を渡してしまっているため、AttributeError になるはず。
        """
        # Mock DockerAdaptor
        mock_docker = MagicMock(spec=DockerAdaptor)
        mock_docker.get_container = AsyncMock()
        mock_docker.stop_container = AsyncMock()

        # Mock container object
        mock_container_obj = MagicMock()
        mock_container_obj.stop = MagicMock()  # Docker objects have .stop()

        # Setup get_container to return the mock object
        mock_docker.get_container.return_value = mock_container_obj

        # Initialize Orchestrator with mock
        orchestrator = ContainerOrchestrator()
        orchestrator.docker = mock_docker

        # Add to last_accessed to verify cleanup
        container_id = "test-container-id"
        orchestrator.last_accessed[container_id] = 12345.0

        # Run stop_container
        await orchestrator.stop_container(container_id)

        # Assertions

        # 1. get_container MUST be called to resolve ID -> Object
        # If this is NOT called, it means we are passing str directly -> BUG
        mock_docker.get_container.assert_awaited_with(container_id)

        # 2. stop_container MUST receive the object, not the ID
        # If the bug exists, this will likely fail or the mock call will rely on implementation details
        mock_docker.stop_container.assert_awaited_with(mock_container_obj)

        # 3. Cleanup verification
        assert container_id not in orchestrator.last_accessed
