import pytest
from unittest.mock import MagicMock, AsyncMock, Mock, patch
import docker.errors
from services.manager.service import ContainerManager


@pytest.fixture
def mock_docker_adaptor():
    # Patch the class in the service module
    with patch("services.manager.service.DockerAdaptor") as mock_cls:
        adaptor = Mock()  # The instance
        mock_cls.return_value = adaptor
        yield adaptor


@pytest.mark.asyncio
async def test_ensure_container_running_cold_start(mock_docker_adaptor):
    # Mock methods of adaptor to be async
    mock_docker_adaptor.get_container = AsyncMock()
    mock_docker_adaptor.run_container = AsyncMock()
    mock_docker_adaptor.reload_container = AsyncMock()
    mock_docker_adaptor.remove_container = AsyncMock()

    manager = ContainerManager(network="test-net")

    # Mock get_container to raise NotFound
    mock_docker_adaptor.get_container.side_effect = docker.errors.NotFound("Not found")

    # Mock run_container
    mock_container = MagicMock()
    mock_container.attrs = {"NetworkSettings": {"Networks": {"test-net": {"IPAddress": "1.2.3.4"}}}}
    mock_docker_adaptor.run_container.return_value = mock_container

    # Mock internal readiness wait
    with patch.object(manager, "_wait_for_readiness", new_callable=AsyncMock) as mock_wait:
        result = await manager.ensure_container_running("test-func", "test-image")

        assert result == "test-func"
        mock_docker_adaptor.run_container.assert_awaited_once()
        mock_wait.assert_awaited_once_with("1.2.3.4")


@pytest.mark.asyncio
async def test_ensure_container_running_warm_start(mock_docker_adaptor):
    mock_docker_adaptor.get_container = AsyncMock()
    mock_docker_adaptor.run_container = AsyncMock()
    mock_docker_adaptor.reload_container = AsyncMock()

    manager = ContainerManager(network="test-net")

    mock_container = MagicMock()
    mock_container.status = "running"
    mock_container.attrs = {"NetworkSettings": {"Networks": {"test-net": {"IPAddress": "1.2.3.4"}}}}

    # Warm start: get returns running container
    mock_docker_adaptor.get_container.side_effect = None
    mock_docker_adaptor.get_container.return_value = mock_container

    with patch.object(manager, "_wait_for_readiness", new_callable=AsyncMock) as mock_wait:
        result = await manager.ensure_container_running("test-func")

        assert result == "test-func"
        mock_docker_adaptor.run_container.assert_not_awaited()
        mock_wait.assert_awaited_once_with("1.2.3.4")


@pytest.mark.asyncio
async def test_wait_for_readiness_post_success():
    """TDD: _wait_for_readiness が POST /invocations を使用してRIE起動を確認"""
    with patch("services.manager.service.DockerAdaptor"):
        manager = ContainerManager(network="test-net")

    with patch("services.manager.service.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        # POST成功レスポンス
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.post.return_value = mock_response

        await manager._wait_for_readiness("1.2.3.4")

        # POST が正しいURLとペイロードで呼ばれたことを確認
        mock_client.post.assert_called()
        call_args = mock_client.post.call_args
        assert "/2015-03-31/functions/function/invocations" in call_args[0][0]
        assert call_args[1]["json"] == {"ping": True}


@pytest.mark.asyncio
async def test_wait_for_readiness_post_retry_then_success():
    """TDD: POST失敗時にリトライし、最終的に成功"""
    with patch("services.manager.service.DockerAdaptor"):
        manager = ContainerManager(network="test-net")

    with patch("services.manager.service.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        # 最初の2回は例外、3回目は成功
        import httpx

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.post.side_effect = [
            httpx.ConnectError("Connection refused"),
            httpx.TimeoutException("Timeout"),
            mock_response,
        ]

        with patch("services.manager.service.asyncio.sleep", new_callable=AsyncMock):
            await manager._wait_for_readiness("1.2.3.4", timeout=30)

        # 3回呼ばれたことを確認
        assert mock_client.post.call_count == 3
