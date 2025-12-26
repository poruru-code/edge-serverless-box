import pytest
import time
from services.gateway.services.container_pool import ContainerPool
from services.common.models.internal import WorkerInfo


@pytest.mark.asyncio
async def test_pool_prune_idle_workers():
    """Test prune_idle_workers method (Phase 4)"""
    pool = ContainerPool("test-func")

    # Create workers
    w1 = WorkerInfo(id="c1", name="n1", ip_address="1.1.1.1", last_used_at=time.time() - 100)
    w2 = WorkerInfo(
        id="c2", name="n2", ip_address="1.1.1.2", last_used_at=time.time() - 10
    )  # Active

    # Manually populate pool (simulating state)
    pool.adopt(w1)
    pool.adopt(w2)

    # Overwrite timestamp for testing (since adopt resets it)
    w1.last_used_at = time.time() - 100
    w2.last_used_at = time.time() - 10

    # Prune (timeout=50s) -> w1 should be pruned
    pruned = pool.prune_idle_workers(idle_timeout=50.0)

    assert len(pruned) == 1
    assert pruned[0].id == "c1"

    # Check remaining
    assert pool.size == 1
    assert w2 in pool._all_workers


@pytest.mark.asyncio
async def test_pool_adopt():
    """Test adopt method (Phase 4)"""
    pool = ContainerPool("test-func")
    w1 = WorkerInfo(id="c1", name="n1", ip_address="1.1.1.1")

    pool.adopt(w1)

    assert pool.size == 1
    assert w1 in pool._all_workers
    # Check semaphore logic (adopt should decrease available slots? No, adopt adds existing resource)
    # Actually adopt adds to _all_workers and _idle_workers (makes it available)
    # But usually pool starts with capacity 0?

    # Verify it can be acquired
    # acquire requires a callback, but since we adopted, it should be in idle queue
    # so callback won't be called.
    async def mock_provision(fname):
        return []

    worker = await pool.acquire(mock_provision)
    assert worker == w1


@pytest.mark.asyncio
async def test_pool_drain():
    """Test drain method (Phase 4)"""
    pool = ContainerPool("test-func")
    w1 = WorkerInfo(id="c1", name="n1", ip_address="1.1.1.1")
    pool.adopt(w1)

    drained = pool.drain()

    assert len(drained) == 1
    assert drained[0] == w1
    assert pool.size == 0
