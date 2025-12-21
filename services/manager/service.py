import docker.errors
import time
import logging
import os
import asyncio
from typing import Dict, Optional

import httpx
from .docker_adaptor import DockerAdaptor

logger = logging.getLogger("manager.service")


class ContainerManager:
    """
    Manages lifecycle of Lambda containers.
    """

    def __init__(self, network: Optional[str] = None):
        self.docker = DockerAdaptor()
        self.last_accessed: Dict[str, float] = {}
        # Per-container lock management
        self.locks: Dict[str, asyncio.Lock] = {}
        self._locks_lock = asyncio.Lock()

        # Use env var or default to 'bridge' if not specified.
        self.network = network or os.environ.get("CONTAINERS_NETWORK") or "bridge"
        logger.info(f"ContainerManager initialized with network: {self.network}")

    async def ensure_container_running(
        self, name: str, image: Optional[str] = None, env: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Ensures the container is running. Returns the hostname (container name) or IP.
        """
        self.last_accessed[name] = time.time()

        if image is None:
            image = f"{name}:latest"

        # Thread-safe acquisition of the per-container lock
        async with self._locks_lock:
            if name not in self.locks:
                self.locks[name] = asyncio.Lock()
            lock = self.locks[name]

        # Use name-based lock to prevent race conditions (TOCTOU)
        async with lock:
            try:
                container = await self.docker.get_container(name)

                if container.status == "running":
                    pass  # Already running

                elif container.status == "exited":
                    logger.info(f"Warm-up: Restarting container {name}...")
                    # container.start() is blocking? DockerAdaptor doesn't have start() yet?
                    # Adaptor should have start helpers or we use generic run_in_executor
                    # Let's assume container object methods are blocking.
                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(None, container.start)
                else:
                    logger.info(f"Container {name} in state {container.status}, removing...")
                    await self.docker.remove_container(container, force=True)
                    raise docker.errors.NotFound(f"Removed {name}")

            except docker.errors.NotFound:
                logger.info(f"Cold Start: Creating and starting container {name}...")

                # Configure Fluentd logging driver
                from docker.types import LogConfig

                log_config = LogConfig(
                    type=LogConfig.types.FLUENTD,
                    config={
                        "fluentd-address": "localhost:24224",
                        "tag": f"lambda.{name}",
                        "fluentd-async": "true",
                    },
                )

                container = await self.docker.run_container(
                    image,
                    name=name,
                    detach=True,
                    environment=env or {},
                    network=self.network,
                    restart_policy={"Name": "no"},
                    labels={"created_by": "sample-dind"},
                    log_config=log_config,
                )

            # Reload container to get latest attributes (IP) and check readiness
            await self.docker.reload_container(container)
            try:
                ip = container.attrs["NetworkSettings"]["Networks"][self.network]["IPAddress"]
                if not ip:
                    # Fallback to name if IP is not yet assigned (rare in bridge network)
                    logger.warning(f"IP address not found for {name}. Falling back to hostname.")
                    ip = name
            except KeyError:
                logger.warning(
                    f"Network {self.network} not found for {name}. Falling back to host."
                )
                ip = name

            # Use IP address for readiness check to avoid DNS lag
            await self._wait_for_readiness(ip)
            return name

    async def _wait_for_readiness(self, host: str, port: int = 8080, timeout: int = 30) -> None:
        """POST /invocations でRIEの起動を確認（AWS RIE標準方式）"""
        url = f"http://{host}:{port}/2015-03-31/functions/function/invocations"
        start = time.time()

        async with httpx.AsyncClient() as client:
            while time.time() - start < timeout:
                try:
                    response = await client.post(url, json={"ping": True}, timeout=1.0)
                    if response.status_code == 200:
                        return
                except (httpx.RequestError, httpx.TimeoutException):
                    await asyncio.sleep(0.5)

        logger.warning(f"Container {host} did not become ready in {timeout}s")

    async def stop_idle_containers(self, timeout_seconds: int = 900) -> None:
        now = time.time()
        to_remove = []

        for name, last_access in list(self.last_accessed.items()):  # Iterate copy
            if now - last_access > timeout_seconds:
                try:
                    logger.info(f"Scale-down: Stopping idle container {name}")
                    try:
                        container = await self.docker.get_container(name)
                        if container.status == "running":
                            await self.docker.stop_container(container)
                    except docker.errors.NotFound:
                        pass

                    to_remove.append(name)
                except Exception as e:
                    logger.error(f"Error stopping/checking {name}: {e}", exc_info=True)

        async with self._locks_lock:
            for name in to_remove:
                if name in self.locks:
                    del self.locks[name]
                self.last_accessed.pop(name, None)

        if to_remove:
            logger.info(f"Cleanup completed. Removed: {to_remove}")

    def prune_managed_containers(self):
        """
        Kills and removes containers managed by this service (zombies).
        WARNING: This is synchronous as currently written, but usually called at startup.
        Should be updated to async if possible, but startup might be sync.
        Original code was running in threadpool.
        Let's keep it sync or make it async?
        The plan said "convert ContainerManager methods to async".
        But prune is called from lifecycle.

        If we make it async, we need to update main.py to await it.
        """
        # For now, let's leave it sync or use the sync client?
        # But we replaced self.client with self.docker (Adaptor).
        # Adaptor has `_client` which is sync.

        logger.info("Pruning zombie containers...")
        try:
            # Direct access to sync client for pruning (used at startup)
            containers = self.docker._client.containers.list(
                all=True,  # Include stopped ones
                filters={"label": "created_by=sample-dind"},
            )
            for container in containers:
                logger.info(f"Removing zombie container: {container.name}")
                try:
                    if container.status == "running":
                        container.kill()
                    container.remove(force=True)
                except Exception as e:
                    logger.error(f"Error removing {container.name}: {e}")
        except Exception as e:
            logger.error(f"Failed to prune containers: {e}")
