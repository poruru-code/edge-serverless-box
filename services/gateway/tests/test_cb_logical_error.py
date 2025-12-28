import pytest
import respx
import httpx
import re
from unittest.mock import AsyncMock, MagicMock
from services.gateway.services.lambda_invoker import LambdaInvoker
from services.gateway.config import GatewayConfig


@pytest.mark.asyncio
async def test_circuit_breaker_on_rie_200_error_FINAL():
    config = GatewayConfig(
        JWT_SECRET_KEY="test-secret-key-32-chars-long-!!!",
        X_API_KEY="test",
        AUTH_USER="test",
        AUTH_PASS="test",
        CONTAINERS_NETWORK="test",
        GATEWAY_INTERNAL_URL="http://test",
        CIRCUIT_BREAKER_THRESHOLD=2,
        CIRCUIT_BREAKER_RECOVERY_TIMEOUT=10.0,
    )

    mock_client = httpx.AsyncClient()
    registry = MagicMock()  # It's used synchronously in LambdaInvoker
    registry.get_function_config.return_value = {"image": "test", "environment": {}}

    from services.common.models.internal import WorkerInfo

    backend = AsyncMock()
    mock_worker = WorkerInfo(id="w1", name="w1", ip_address="localhost")
    backend.acquire_worker.return_value = mock_worker
    backend.release_worker = AsyncMock()
    backend.evict_worker = AsyncMock()

    invoker = LambdaInvoker(mock_client, registry, config, backend)

    # RIE がよく返す「200 だけどエラー」のレスポンス
    error_body = {
        "errorType": "Runtime.ExitError",
        "errorMessage": "RequestId: xxx Error: Runtime exited with error: exit status 1",
    }

    with respx.mock:
        respx.post(url=re.compile(r".*/invocations")).mock(
            return_value=httpx.Response(200, json=error_body)
        )

        # 1回目リクエスト (200 Error) -> 失敗としてカウントされるべき
        with pytest.raises(Exception):
            await invoker.invoke_function("test-func", b"{}")

        # 2回目リクエスト -> 失敗としてカウントされ、回路が開くはず
        with pytest.raises(Exception):
            await invoker.invoke_function("test-func", b"{}")

        # 3回目リクエスト -> 回路が開いているので CircuitBreakerOpenError が投げられるはず
        # それが LambdaInvoker でラップされて LambdaExecutionError になる
        from services.gateway.core.exceptions import LambdaExecutionError

        with pytest.raises(LambdaExecutionError) as excinfo:
            await invoker.invoke_function("test-func", b"{}")

        assert "Circuit Breaker Open" in str(excinfo.value)
        print("\n✅ Circuit Breaker validated with logical 200 errors!")


if __name__ == "__main__":
    import asyncio

    asyncio.run(test_circuit_breaker_on_rie_200_error_FINAL())
