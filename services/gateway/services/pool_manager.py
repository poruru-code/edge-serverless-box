"""
PoolManager - Manages ContainerPools for all functions

Provides a unified interface for acquiring/releasing workers across multiple
Lambda functions. Each function gets its own ContainerPool with independent
capacity management.
"""

import asyncio
import logging
from typing import Callable, Dict, List, Any

from .container_pool import ContainerPool
from services.common.models.internal import WorkerInfo

logger = logging.getLogger("gateway.pool_manager")


class PoolManager:
    """
    全関数のプールを統括管理

    - プール作成は遅延初期化 (get_pool で初めて作成)
    - 関数ごとに独立した max_capacity を設定可能
    """

    def __init__(
        self,
        provision_client: Any,
        config_loader: Callable[[str], Dict[str, Any]],
    ):
        """
        Args:
            provision_client: Manager への provision リクエストを送信するクライアント
            config_loader: 関数名から設定を取得するコールバック (function_name -> config dict)
        """
        self._pools: Dict[str, ContainerPool] = {}
        self._lock = asyncio.Lock()
        self.provision_client = provision_client
        self.config_loader = config_loader

    async def get_pool(self, function_name: str) -> ContainerPool:
        """関数名からプールを取得（なければ作成）"""
        if function_name not in self._pools:
            async with self._lock:
                if function_name not in self._pools:
                    config = self.config_loader(function_name)
                    scaling = config.get("scaling", {})
                    self._pools[function_name] = ContainerPool(
                        function_name=function_name,
                        max_capacity=scaling.get("max_capacity", 1),
                        min_capacity=scaling.get("min_capacity", 0),
                        acquire_timeout=scaling.get("acquire_timeout", 5.0),
                    )
                    logger.info(
                        f"Created pool for {function_name}: "
                        f"max_capacity={self._pools[function_name].max_capacity}"
                    )
        return self._pools[function_name]

    async def _provision_wrapper(self, function_name: str) -> List[WorkerInfo]:
        """Provision API ラッパー (List[WorkerInfo] を返す)"""
        return await self.provision_client.provision(function_name)

    async def acquire_worker(self, function_name: str) -> WorkerInfo:
        """ワーカーを取得"""
        pool = await self.get_pool(function_name)
        return await pool.acquire(self._provision_wrapper)

    def release_worker(self, function_name: str, worker: WorkerInfo) -> None:
        """ワーカーを返却"""
        if function_name in self._pools:
            self._pools[function_name].release(worker)

    def evict_worker(self, function_name: str, worker: WorkerInfo) -> None:
        """死んだワーカーを除外 (sync - Semaphore.release は sync)"""
        if function_name in self._pools:
            self._pools[function_name].evict(worker)

    def get_all_worker_names(self) -> Dict[str, List[str]]:
        """Heartbeat用: 全プールの全Worker Nameを収集 (Busy + Idle)"""
        result = {}
        for fname, pool in self._pools.items():
            result[fname] = pool.get_all_names()
        return result
