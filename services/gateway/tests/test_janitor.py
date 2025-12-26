"""
Tests for HeartbeatJanitor

TDD: RED phase - write tests first, then implement.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


class TestHeartbeatJanitor:
    """Tests for HeartbeatJanitor class"""

    @pytest.fixture
    def mock_pool_manager(self):
        """Mock PoolManager"""
        pm = MagicMock()
        pm.get_all_worker_names = MagicMock(
            return_value={
                "function-a": ["w1", "w2"],
                "function-b": ["w3"],
            }
        )
        return pm

    @pytest.fixture
    def mock_manager_client(self):
        """Mock ManagerClient with heartbeat method"""
        client = MagicMock()
        client.heartbeat = AsyncMock()
        return client

    @pytest.fixture
    def janitor(self, mock_pool_manager, mock_manager_client):
        """Create a HeartbeatJanitor for testing"""
        from services.gateway.services.janitor import HeartbeatJanitor

        return HeartbeatJanitor(
            pool_manager=mock_pool_manager,
            manager_client=mock_manager_client,
            interval=1,  # Fast interval for testing
        )

    def test_janitor_creation(self, janitor, mock_pool_manager, mock_manager_client):
        """HeartbeatJanitor should be created with correct settings"""
        assert janitor.pool_manager is mock_pool_manager
        assert janitor.manager_client is mock_manager_client
        assert janitor.interval == 1
        assert janitor._task is None

    @pytest.mark.asyncio
    async def test_janitor_start_stop(self, janitor):
        """HeartbeatJanitor should start and stop the loop task"""
        await janitor.start()
        assert janitor._task is not None
        assert not janitor._task.done()

        await janitor.stop()
        assert janitor._task.done()

    @pytest.mark.asyncio
    async def test_send_heartbeat(self, janitor, mock_manager_client):
        """_send_heartbeat should call manager_client.heartbeat for each function"""
        await janitor._send_heartbeat()

        # Should be called twice (once per function)
        assert mock_manager_client.heartbeat.call_count == 2

    @pytest.mark.asyncio
    async def test_send_heartbeat_with_empty_pool(
        self, mock_pool_manager, mock_manager_client
    ):
        """_send_heartbeat should not call heartbeat for empty functions"""
        from services.gateway.services.janitor import HeartbeatJanitor

        # Empty pool
        mock_pool_manager.get_all_worker_names = MagicMock(
            return_value={"function-a": []}  # Empty list
        )

        janitor = HeartbeatJanitor(
            pool_manager=mock_pool_manager,
            manager_client=mock_manager_client,
            interval=1,
        )

        await janitor._send_heartbeat()

        # Should not be called for empty function
        mock_manager_client.heartbeat.assert_not_called()

    @pytest.mark.asyncio
    async def test_loop_sends_heartbeat_periodically(self, janitor, mock_manager_client):
        """The loop should send heartbeat after interval"""
        await janitor.start()

        # Wait for at least one heartbeat (interval=1 second + buffer)
        await asyncio.sleep(1.5)

        await janitor.stop()

        # Should have sent at least one heartbeat
        assert mock_manager_client.heartbeat.call_count >= 1
