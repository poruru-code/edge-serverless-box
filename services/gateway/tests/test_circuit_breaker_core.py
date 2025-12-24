import asyncio
import pytest
from services.gateway.core.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError


class TestCircuitBreaker:
    @pytest.mark.asyncio
    async def test_closed_state_success(self):
        """通常状態(CLOSED)で成功する場合、正常に結果が返ること"""
        breaker = CircuitBreaker(failure_threshold=2)

        async def mock_func():
            return "success"

        result = await breaker.call(mock_func)
        assert result == "success"
        assert breaker.state == "CLOSED"
        assert breaker.failures == 0

    @pytest.mark.asyncio
    async def test_to_open_state_on_failures(self):
        """失敗がしきい値を超えると OPEN 状態になること"""
        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)

        async def failing_func():
            raise ValueError("boom")

        # 1回目失敗
        with pytest.raises(ValueError):
            await breaker.call(failing_func)
        assert breaker.state == "CLOSED"
        assert breaker.failures == 1

        # 2回目失敗 -> OPEN へ
        with pytest.raises(ValueError):
            await breaker.call(failing_func)
        assert breaker.state == "OPEN"
        assert breaker.failures == 2

        # OPEN 状態では関数は呼ばれず、即座に CircuitBreakerOpenError が投じられること
        with pytest.raises(CircuitBreakerOpenError):
            await breaker.call(failing_func)

    @pytest.mark.asyncio
    async def test_recovery_to_half_open_and_closed(self):
        """リカバリタイムアウト後に成功すると CLOSED に戻ること"""
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)

        async def failing_func():
            raise ValueError("boom")

        async def success_func():
            return "ok"

        # OPEN にする
        with pytest.raises(ValueError):
            await breaker.call(failing_func)
        assert breaker.state == "OPEN"

        # タイムアウトを待つ
        await asyncio.sleep(0.15)

        # 次の呼び出しで HALF_OPEN になり、成功すれば CLOSED に戻る
        result = await breaker.call(success_func)
        assert result == "ok"
        assert breaker.state == "CLOSED"
        assert breaker.failures == 0

    @pytest.mark.asyncio
    async def test_half_open_to_open_on_failure(self):
        """HALF_OPEN 状態で失敗すると再び OPEN に戻ること"""
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)

        async def failing_func():
            raise ValueError("boom")

        # OPEN にする
        with pytest.raises(ValueError):
            await breaker.call(failing_func)
        assert breaker.state == "OPEN"

        # タイムアウトを待つ
        await asyncio.sleep(0.15)

        # HALF_OPEN での再試行が失敗
        with pytest.raises(ValueError):
            await breaker.call(failing_func)

        assert breaker.state == "OPEN"
        # HALF_OPEN で失敗した場合は即座に OPEN に戻るべき
