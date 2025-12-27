import pytest
import asyncio
import time
from services.gateway.services.container_pool import ContainerPool
from services.common.models.internal import WorkerInfo


class TestContainerPoolLifecycle:
    """
    ContainerPool のライフサイクルとタイムスタンプ更新を検証するテスト
    ユーザー指示: 試行錯誤ではなく根拠（テスト）に基づいて修正を行うため。
    """

    @pytest.fixture
    def pool(self):
        return ContainerPool(
            function_name="test-func", max_capacity=10, min_capacity=0, acquire_timeout=1.0
        )

    @pytest.mark.asyncio
    async def test_last_used_at_updates_on_release(self, pool):
        """
        release() 呼び出し時に last_used_at が更新されることを確認
        """

        # Mock provision callback
        async def mock_provision(fname):
            return [WorkerInfo(id="w1", name="w1", ip_address="1.1.1.1")]

        # 1. Acquire (New worker)
        worker = await pool.acquire(mock_provision)
        initial_time = worker.last_used_at

        # Simulate usage time
        await asyncio.sleep(0.1)

        # 2. Release (Now a coroutine)
        await pool.release(worker)

        # Verify timestamp updated
        assert worker.last_used_at > initial_time
        assert worker.last_used_at >= time.time() - 0.5  # Rough check

    @pytest.mark.asyncio
    async def test_adopt_sets_timestamp(self, pool):
        """
        adopt() 呼び出し時に last_used_at が現在時刻に設定されることを確認
        """
        worker = WorkerInfo(id="w2", name="w2", ip_address="2.2.2.2", last_used_at=0.0)

        # adopt() is now a coroutine
        await pool.adopt(worker)

        assert worker.last_used_at > 0.0
        assert worker.last_used_at >= time.time() - 0.5

    @pytest.mark.asyncio
    async def test_prune_respects_last_used_at(self, pool):
        """
        prune_idle_workers() が last_used_at を正しく評価することを確認
        """
        # Add a worker that is "old" manually
        old_worker = WorkerInfo(id="w_old", name="w_old", ip_address="1.1.1.1")
        old_worker.last_used_at = time.time() - 100  # 100 seconds ago

        # Add to idle queue directly for testing state
        pool._all_workers.add(old_worker)
        pool._idle_workers.append(old_worker)  # deque uses append, not put_nowait

        # Add a worker that is "new"
        new_worker = WorkerInfo(id="w_new", name="w_new", ip_address="2.2.2.2")
        new_worker.last_used_at = time.time()  # Now

        pool._all_workers.add(new_worker)
        pool._idle_workers.append(new_worker)

        # Prune with 60s timeout (Now a coroutine)
        pruned = await pool.prune_idle_workers(idle_timeout=60.0)

        assert old_worker in pruned
        assert new_worker not in pruned
        assert len(pool._all_workers) == 1
        assert new_worker in pool._all_workers
