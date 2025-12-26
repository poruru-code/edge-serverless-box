"""
Tests for Manager Provision API

TDD: RED phase - write tests first, then implement.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport


class TestProvisionEndpoint:
    """Tests for POST /containers/provision endpoint"""

    @pytest.fixture
    def mock_manager(self):
        """Mock ContainerManager with provision_containers method"""
        from services.common.models.internal import WorkerInfo

        manager = MagicMock()
        manager.provision_containers = AsyncMock(
            return_value=[
                WorkerInfo(
                    id="container123",
                    name="lambda-hello-world-abc12345",
                    ip_address="172.18.0.5",
                    port=8080,
                )
            ]
        )
        return manager

    @pytest.mark.asyncio
    async def test_provision_single_container(self, mock_manager):
        """POST /containers/provision should return provisioned worker"""
        from services.manager.main import app

        transport = ASGITransport(app=app)  # type: ignore
        with patch("services.manager.main.manager", mock_manager):
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/containers/provision",
                    json={"function_name": "hello-world"},
                )

        assert response.status_code == 200
        data = response.json()
        assert "workers" in data
        assert len(data["workers"]) == 1
        assert data["workers"][0]["id"] == "container123"
        assert data["workers"][0]["name"] == "lambda-hello-world-abc12345"

    @pytest.mark.asyncio
    async def test_provision_multiple_containers(self, mock_manager):
        """POST /containers/provision should support count parameter"""
        from services.common.models.internal import WorkerInfo
        from services.manager.main import app

        mock_manager.provision_containers = AsyncMock(
            return_value=[
                WorkerInfo(id=f"c{i}", name=f"w{i}", ip_address=f"10.0.0.{i}")
                for i in range(3)
            ]
        )

        transport = ASGITransport(app=app)  # type: ignore
        with patch("services.manager.main.manager", mock_manager):
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/containers/provision",
                    json={"function_name": "hello-world", "count": 3},
                )

        assert response.status_code == 200
        assert len(response.json()["workers"]) == 3
        mock_manager.provision_containers.assert_called_once()
        call_args = mock_manager.provision_containers.call_args
        assert call_args.kwargs["count"] == 3

    @pytest.mark.asyncio
    async def test_provision_with_custom_image(self, mock_manager):
        """POST /containers/provision should pass custom image"""
        from services.manager.main import app

        transport = ASGITransport(app=app)  # type: ignore
        with patch("services.manager.main.manager", mock_manager):
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/containers/provision",
                    json={
                        "function_name": "hello-world",
                        "image": "my-custom:v2",
                        "env": {"DEBUG": "true"},
                    },
                )

        assert response.status_code == 200
        call_args = mock_manager.provision_containers.call_args
        assert call_args.kwargs["image"] == "my-custom:v2"
        assert call_args.kwargs["env"] == {"DEBUG": "true"}

    @pytest.mark.asyncio
    async def test_provision_image_not_found(self, mock_manager):
        """POST /containers/provision should return 404 for missing image"""
        import docker.errors
        from services.manager.main import app

        mock_manager.provision_containers = AsyncMock(
            side_effect=docker.errors.ImageNotFound("Image not found")
        )

        transport = ASGITransport(app=app)  # type: ignore
        with patch("services.manager.main.manager", mock_manager):
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/containers/provision",
                    json={"function_name": "nonexistent"},
                )

        assert response.status_code == 404


class TestHeartbeatEndpoint:
    """Tests for POST /containers/heartbeat endpoint"""

    @pytest.fixture
    def mock_manager(self):
        """Mock ContainerManager with update_heartbeat method"""
        manager = MagicMock()
        manager.update_heartbeat = AsyncMock()
        return manager

    @pytest.mark.asyncio
    async def test_heartbeat_success(self, mock_manager):
        """POST /containers/heartbeat should return 200 OK"""
        from services.manager.main import app

        transport = ASGITransport(app=app)  # type: ignore
        with patch("services.manager.main.manager", mock_manager):
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/containers/heartbeat",
                    json={
                        "function_name": "hello-world",
                        "container_names": ["c1", "c2", "c3"],
                    },
                )

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        mock_manager.update_heartbeat.assert_called_once_with(
            "hello-world", ["c1", "c2", "c3"]
        )

    @pytest.mark.asyncio
    async def test_heartbeat_empty_names(self, mock_manager):
        """POST /containers/heartbeat should accept empty container_names"""
        from services.manager.main import app

        transport = ASGITransport(app=app)  # type: ignore
        with patch("services.manager.main.manager", mock_manager):
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/containers/heartbeat",
                    json={
                        "function_name": "hello-world",
                        "container_names": [],
                    },
                )

        assert response.status_code == 200
