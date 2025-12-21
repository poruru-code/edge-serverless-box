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


@pytest.mark.asyncio
async def test_sync_with_docker_adopts_running_containers(mock_docker_adaptor):
    """TDD Red: 実行中コンテナをlast_accessedに登録"""
    mock_docker_adaptor.list_containers = AsyncMock()
    mock_docker_adaptor.remove_container = AsyncMock()

    manager = ContainerManager(network="test-net")

    # 実行中コンテナをモック
    mock_container1 = MagicMock()
    mock_container1.name = "lambda-test1"
    mock_container1.status = "running"

    mock_container2 = MagicMock()
    mock_container2.name = "lambda-test2"
    mock_container2.status = "running"

    mock_docker_adaptor.list_containers.return_value = [mock_container1, mock_container2]

    await manager.sync_with_docker()

    # 実行中コンテナがlast_accessedに登録されることを確認
    assert "lambda-test1" in manager.last_accessed
    assert "lambda-test2" in manager.last_accessed
    # 削除は呼ばれない
    mock_docker_adaptor.remove_container.assert_not_awaited()


@pytest.mark.asyncio
async def test_sync_with_docker_removes_exited_containers(mock_docker_adaptor):
    """TDD Red: 停止中コンテナを削除"""
    mock_docker_adaptor.list_containers = AsyncMock()
    mock_docker_adaptor.remove_container = AsyncMock()

    manager = ContainerManager(network="test-net")

    # 停止中コンテナをモック
    mock_container1 = MagicMock()
    mock_container1.name = "lambda-stopped"
    mock_container1.status = "exited"

    mock_docker_adaptor.list_containers.return_value = [mock_container1]

    await manager.sync_with_docker()

    # 停止中コンテナはlast_accessedに登録されない
    assert "lambda-stopped" not in manager.last_accessed
    # 削除が呼ばれる
    mock_docker_adaptor.remove_container.assert_awaited_once_with(mock_container1, force=True)


@pytest.mark.asyncio
async def test_sync_with_docker_handles_mixed_containers(mock_docker_adaptor):
    """TDD Red: 実行中と停止中が混在するケース"""
    mock_docker_adaptor.list_containers = AsyncMock()
    mock_docker_adaptor.remove_container = AsyncMock()

    manager = ContainerManager(network="test-net")

    # 混在状態をモック
    running = MagicMock()
    running.name = "lambda-running"
    running.status = "running"

    exited = MagicMock()
    exited.name = "lambda-exited"
    exited.status = "exited"

    paused = MagicMock()
    paused.name = "lambda-paused"
    paused.status = "paused"

    mock_docker_adaptor.list_containers.return_value = [running, exited, paused]

    await manager.sync_with_docker()

    # 実行中だけがlast_accessedに登録
    assert "lambda-running" in manager.last_accessed
    assert "lambda-exited" not in manager.last_accessed
    assert "lambda-paused" not in manager.last_accessed

    # 停止中とpausedは削除される
    assert mock_docker_adaptor.remove_container.await_count == 2


@pytest.mark.asyncio
async def test_ensure_container_running_handles_409_conflict(mock_docker_adaptor):
    """TDD Red: 409 Conflict時に既存コンテナを取得して続行"""
    mock_docker_adaptor.get_container = AsyncMock()
    mock_docker_adaptor.run_container = AsyncMock()
    mock_docker_adaptor.reload_container = AsyncMock()

    manager = ContainerManager(network="test-net")

    # 最初のget_containerはNotFound
    mock_docker_adaptor.get_container.side_effect = [
        docker.errors.NotFound("Not found"),  # 1st call
        MagicMock(  # 2nd call (Conflict後の再取得)
            status="running",
            attrs={"NetworkSettings": {"Networks": {"test-net": {"IPAddress": "1.2.3.4"}}}},
        ),
    ]

    # run_containerが409 Conflictを返す
    api_error = docker.errors.APIError("Conflict", response=MagicMock(status_code=409))
    mock_docker_adaptor.run_container.side_effect = api_error

    with patch.object(manager, "_wait_for_readiness", new_callable=AsyncMock):
        result = await manager.ensure_container_running("test-func", "test-image")

        # 正常に完了
        assert result == "test-func"
        # run_containerが呼ばれた
        mock_docker_adaptor.run_container.assert_awaited_once()
        # 409後にget_containerが再度呼ばれた
        assert mock_docker_adaptor.get_container.await_count == 2
