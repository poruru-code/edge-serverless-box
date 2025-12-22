import pytest
from unittest.mock import Mock, patch, AsyncMock
from services.manager.docker_adaptor import DockerAdaptor


@pytest.mark.asyncio
async def test_prune_containers_method_exists():
    """
    TDD: DockerAdaptor should have an async prune_containers method.
    """
    adaptor = DockerAdaptor()
    assert hasattr(adaptor, "prune_containers")
    assert callable(getattr(adaptor, "prune_containers"))


@pytest.mark.asyncio
async def test_prune_containers_uses_executor():
    """
    TDD: prune_containers should use run_in_executor to avoid blocking event loop.
    """
    with patch("services.manager.docker_adaptor.docker.from_env") as mock_docker:
        mock_client = Mock()
        mock_docker.return_value = mock_client
        mock_client.containers.list.return_value = []

        adaptor = DockerAdaptor()

        # Mock the event loop to verify run_in_executor is called
        with patch("asyncio.get_running_loop") as mock_loop:
            mock_loop_instance = AsyncMock()
            mock_loop.return_value = mock_loop_instance
            mock_loop_instance.run_in_executor = AsyncMock(return_value=None)

            await adaptor.prune_containers()

            # Verify run_in_executor was called
            mock_loop_instance.run_in_executor.assert_awaited_once()


def test_docker_adaptor_has_dedicated_executor():
    """TDD Red: DockerAdaptor が専用 ThreadPoolExecutor を持つ"""
    with patch("services.manager.docker_adaptor.docker.from_env"):
        adaptor = DockerAdaptor()
        assert hasattr(adaptor, "executor")
        from concurrent.futures import ThreadPoolExecutor

        assert isinstance(adaptor.executor, ThreadPoolExecutor)


def test_docker_adaptor_uses_config_max_workers():
    """TDD Red: DockerAdaptor が config.DOCKER_MAX_WORKERS を使用する"""
    with patch("services.manager.docker_adaptor.docker.from_env"):
        with patch("services.manager.docker_adaptor.config") as mock_config:
            mock_config.DOCKER_MAX_WORKERS = 10
            mock_config.DOCKER_CLIENT_TIMEOUT = 30
            adaptor = DockerAdaptor()
            assert adaptor.executor._max_workers == 10


def test_docker_adaptor_uses_config_timeout():
    """TDD Red: DockerAdaptor が config.DOCKER_CLIENT_TIMEOUT を使用する"""
    with patch("services.manager.docker_adaptor.docker.from_env") as mock_from_env:
        with patch("services.manager.docker_adaptor.config") as mock_config:
            mock_config.DOCKER_MAX_WORKERS = 20
            mock_config.DOCKER_CLIENT_TIMEOUT = 45
            DockerAdaptor()
            mock_from_env.assert_called_once_with(timeout=45)


@pytest.mark.asyncio
async def test_docker_adaptor_uses_dedicated_executor_in_run():
    """TDD Red: run_in_executor で専用 executor を使用する"""
    with patch("services.manager.docker_adaptor.docker.from_env") as mock_docker:
        mock_client = Mock()
        mock_docker.return_value = mock_client
        mock_client.containers.run.return_value = Mock()

        with patch("services.manager.docker_adaptor.config") as mock_config:
            mock_config.DOCKER_MAX_WORKERS = 5
            mock_config.DOCKER_CLIENT_TIMEOUT = 30
            adaptor = DockerAdaptor()

            with patch("asyncio.get_running_loop") as mock_get_loop:
                mock_loop_instance = AsyncMock()
                mock_get_loop.return_value = mock_loop_instance
                mock_loop_instance.run_in_executor = AsyncMock(return_value=Mock())

                await adaptor.run_container("test-image")

                # 第一引数が adaptor.executor であることを確認
                call_args = mock_loop_instance.run_in_executor.call_args
                assert call_args[0][0] is adaptor.executor


def test_docker_adaptor_has_shutdown_method():
    """TDD Red: DockerAdaptor に shutdown() メソッドが存在する"""
    with patch("services.manager.docker_adaptor.docker.from_env"):
        with patch("services.manager.docker_adaptor.config") as mock_config:
            mock_config.DOCKER_MAX_WORKERS = 5
            mock_config.DOCKER_CLIENT_TIMEOUT = 30
            adaptor = DockerAdaptor()
            assert hasattr(adaptor, "shutdown")
            assert callable(adaptor.shutdown)
