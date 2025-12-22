import pytest
from unittest.mock import AsyncMock, Mock, patch
import httpx

# Assuming the class will be created in this module
from services.gateway.services.lambda_invoker import LambdaInvoker


@pytest.fixture
def mock_client():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.post.return_value = httpx.Response(200, json={"message": "ok"})
    return client


@pytest.fixture
def mock_registry():
    registry = Mock()
    registry.get_function_config.return_value = {"image": "test-image", "environment": {}}
    return registry


@pytest.mark.asyncio
async def test_invoke_function(mock_client, mock_registry):
    # Patching get_lambda_host where it is imported in lambda_invoker.py
    with patch(
        "services.gateway.services.lambda_invoker.get_lambda_host", new_callable=AsyncMock
    ) as mock_get_host:
        mock_get_host.return_value = "1.2.3.4"

        invoker = LambdaInvoker(mock_client, mock_registry)
        response = await invoker.invoke_function("test-func", b"{}")

        assert response.status_code == 200
        mock_client.post.assert_called_once()
        # Verify URL construction
        args, kwargs = mock_client.post.call_args
        assert "http://1.2.3.4:8080" in args[0]


@pytest.mark.asyncio
async def test_invoke_function_logs_error_on_request_failure(mock_client, mock_registry):
    """
    TDD Red: Lambda呼び出し失敗時に詳細なエラーログを出力する
    """
    from services.gateway.core.exceptions import LambdaExecutionError

    mock_client.post.side_effect = httpx.ConnectError("Connection refused")

    with patch(
        "services.gateway.services.lambda_invoker.get_lambda_host", new_callable=AsyncMock
    ) as mock_get_host:
        mock_get_host.return_value = "1.2.3.4"

        with patch("services.gateway.services.lambda_invoker.logger") as mock_logger:
            invoker = LambdaInvoker(mock_client, mock_registry)

            with pytest.raises(LambdaExecutionError):
                await invoker.invoke_function("test-func", b"{}")

            # エラーログが出力されることを確認
            mock_logger.error.assert_called_once()
            call_args = mock_logger.error.call_args

            # extra に詳細情報が含まれることを確認
            assert "extra" in call_args.kwargs
            extra = call_args.kwargs["extra"]
            assert "function_name" in extra
            assert "target_url" in extra
            assert "error_type" in extra
            assert extra["function_name"] == "test-func"
