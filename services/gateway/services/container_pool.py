"""
ContainerPool - Worker Pool Management for Auto-Scaling

Manages a pool of Lambda containers for a single function using Semaphore-based
capacity control. Supports concurrent acquire/release with proper cleanup on eviction.
"""

import asyncio
import logging
from typing import Callable, Awaitable, List, Set

from services.common.models.internal import WorkerInfo

logger = logging.getLogger("gateway.container_pool")


class ContainerPool:
    """
    関数ごとのコンテナプール管理 (Semaphore方式)

    - acquire(): セマフォ取得 → アイドルチェック → なければ作成
    - release(): アイドルに戻す + セマフォ解放
    - evict(): ワーカー破棄 + セマフォ解放 (待機者が即起動)

    重要: _all_workers で Busy/Idle 両方を追跡し、Heartbeat 漏れを防止
    """

    def __init__(
        self,
        function_name: str,
        max_capacity: int = 1,
        min_capacity: int = 0,
        acquire_timeout: float = 5.0,
    ):
        self.function_name = function_name
        self.max_capacity = max_capacity
        self.min_capacity = min_capacity
        self.acquire_timeout = acquire_timeout

        # セマフォで容量管理 (max_capacity が初期値)
        self._sem = asyncio.Semaphore(max_capacity)
        self._idle_workers: asyncio.Queue[WorkerInfo] = asyncio.Queue()

        # 全ワーカーの台帳 (Busy + Idle)
        # Heartbeat でこのセットから ID を収集
        self._all_workers: Set[WorkerInfo] = set()

    async def acquire(
        self, provision_callback: Callable[[str], Awaitable[List[WorkerInfo]]]
    ) -> WorkerInfo:
        """
        利用可能なワーカーを取得。なければプロビジョニング。

        Args:
            provision_callback: async def (function_name) -> List[WorkerInfo]

        Returns:
            WorkerInfo

        Raises:
            asyncio.TimeoutError: 取得タイムアウト
        """
        # 1. セマフォ取得 (容量が空くまで待つ)
        try:
            await asyncio.wait_for(self._sem.acquire(), timeout=self.acquire_timeout)
        except asyncio.TimeoutError:
            raise asyncio.TimeoutError(f"Pool acquire timeout for {self.function_name}")

        try:
            # 2. アイドルプールにあれば使う
            try:
                worker = self._idle_workers.get_nowait()
                return worker
            except asyncio.QueueEmpty:
                pass

            # 3. なければ作る (容量は確保済み)
            try:
                workers: List[WorkerInfo] = await provision_callback(self.function_name)
                worker = workers[0]
                # 台帳に登録 (Heartbeat で追跡対象になる)
                self._all_workers.add(worker)
                return worker
            except Exception:
                # 作成失敗したら枠を返す
                self._sem.release()
                raise

        except Exception:
            # 想定外エラーでも枠を解放
            self._sem.release()
            raise

    def release(self, worker: WorkerInfo) -> None:
        """ワーカーをプールに返却"""
        self._idle_workers.put_nowait(worker)
        self._sem.release()  # 枠解放 → 待機者が起きる

    def evict(self, worker: WorkerInfo) -> None:
        """
        死んだワーカーをプールから除外 (Self-Healing)
        ワーカーは捨てるが、枠は解放 → 待機者が起きて新規作成へ
        """
        # 台帳から削除 (Heartbeat から外れる)
        self._all_workers.discard(worker)
        self._sem.release()  # 枠解放 → Queue空なので新規作成へ

    def get_all_names(self) -> List[str]:
        """Heartbeat用: Busy も Idle もすべて含む Name リスト"""
        return [w.name for w in self._all_workers]

    @property
    def stats(self) -> dict:
        """プール統計情報"""
        available = getattr(self._sem, "_value", "N/A")
        return {
            "function_name": self.function_name,
            "available_slots": available,
            "total_workers": len(self._all_workers),
            "idle": self._idle_workers.qsize(),
            "max_capacity": self.max_capacity,
        }
