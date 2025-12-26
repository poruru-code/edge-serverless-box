"""
HeartbeatJanitor - Periodic heartbeat sender from Gateway to Manager

Keeps Manager informed of active containers to prevent zombie cleanup.
"""

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .pool_manager import PoolManager

logger = logging.getLogger("gateway.janitor")


class HeartbeatJanitor:
    """
    Gateway → Manager への定期的な Heartbeat 送信

    保持しているワーカーIDリストを送信し、
    Manager側でOrphanコンテナを検出・削除させる。
    """

    def __init__(
        self,
        pool_manager: "PoolManager",
        manager_client,  # ManagerClient or mock
        interval: int = 30,
        idle_timeout: float = 300.0,
    ):
        self.pool_manager = pool_manager
        self.manager_client = manager_client
        self.interval = interval
        self.idle_timeout = idle_timeout
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Heartbeat Loop 開始"""
        self._task = asyncio.create_task(self._loop())
        logger.info(
            f"Heartbeat Janitor started (interval: {self.interval}s, idle_timeout: {self.idle_timeout}s)"
        )

    async def stop(self) -> None:
        """Heartbeat Loop 停止"""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Heartbeat Janitor stopped")

    async def _loop(self) -> None:
        """定期実行ループ"""
        while True:
            try:
                await asyncio.sleep(self.interval)
                await self._send_heartbeat()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat failed: {e}")

    async def _send_heartbeat(self) -> None:
        """Pruning 後に Heartbeat 送信"""
        # 1. まず Pruning を実行
        try:
            pruned = await self.pool_manager.prune_all_pools(self.idle_timeout)
            for fname, workers in pruned.items():
                logger.info(f"Pruned {len(workers)} idle workers from {fname}")
        except Exception as e:
            logger.error(f"Pruning failed: {e}")

        # 2. 残っているワーカーの名前リストを送信
        worker_names = self.pool_manager.get_all_worker_names()
        for function_name, names in worker_names.items():
            if names:  # Only send if there are workers
                await self.manager_client.heartbeat(function_name, names)
                logger.debug(f"Heartbeat sent: {function_name} ({len(names)} workers)")
