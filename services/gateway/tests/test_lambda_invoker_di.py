import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from services.gateway.services.lambda_invoker import LambdaInvoker
from services.gateway.services.function_registry import FunctionRegistry
from services.gateway.config import GatewayConfig


@pytest.mark.asyncio
async def test_lambda_invoker_di_initialization():
    """Test LambdaInvoker can be initialized with dependencies"""
    client = AsyncMock()
    registry = MagicMock(spec=FunctionRegistry)
    container_manager = AsyncMock()  # Protocol mock
    config = GatewayConfig()

    invoker = LambdaInvoker(
        client=client, registry=registry, container_manager=container_manager, config=config
    )

    assert invoker.client == client
    assert invoker.registry == registry
    assert invoker.container_manager == container_manager
    assert invoker.config == config


@pytest.mark.asyncio
async def test_lambda_invoker_invoke_flow():
    """Test invoke_function uses injected dependencies"""
    # Arrange
    client = AsyncMock()
    registry = MagicMock(spec=FunctionRegistry)
    container_manager = AsyncMock()
    config = GatewayConfig()
    config.GATEWAY_INTERNAL_URL = "http://gateway-internal"

    invoker = LambdaInvoker(client, registry, container_manager, config)

    function_name = "test-func"
    payload = b"{}"

    # Mock Registry
    registry.get_function_config.return_value = {
        "image": "test-image",
        "environment": {"VAR": "VAL"},
    }

    # Mock Container Manager
    container_manager.get_lambda_host.return_value = "10.0.0.5"

    # Mock HTTP Client - return valid JSON response (not an error)
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = b'{"statusCode": 200, "body": "OK"}'
    mock_response.json.return_value = {"statusCode": 200, "body": "OK"}
    mock_response.headers = {}
    client.post.return_value = mock_response

    # Act
    await invoker.invoke_function(function_name, payload)

    # Assert
    # 1. Registry called
    registry.get_function_config.assert_called_with(function_name)

    # 2. Container Manager called with correct args
    container_manager.get_lambda_host.assert_called_once()
    args, kwargs = container_manager.get_lambda_host.call_args
    # get_lambda_host(function_name, image, env)
    assert kwargs.get("function_name") == function_name or args[0] == function_name

    # Verify environment extension
    called_env = kwargs.get("env") or args[2]
    assert called_env["VAR"] == "VAL"
    assert called_env["GATEWAY_INTERNAL_URL"] == "http://gateway-internal"

    # 3. HTTP Client called
    expected_url = f"http://10.0.0.5:{config.LAMBDA_PORT}/2015-03-31/functions/function/invocations"
    client.post.assert_called_once()
    assert client.post.call_args[0][0] == expected_url


@pytest.mark.asyncio
async def test_lambda_invoker_logging_on_error():
    """Test LambdaInvoker logs errors with extra context"""
    from services.gateway.core.exceptions import LambdaExecutionError
    import httpx

    client = AsyncMock()
    registry = MagicMock(spec=FunctionRegistry)
    container_manager = AsyncMock()
    config = GatewayConfig()

    invoker = LambdaInvoker(client, registry, container_manager, config)

    # Setup mocks
    registry.get_function_config.return_value = {"image": "img", "environment": {}}
    container_manager.get_lambda_host.return_value = "host"
    client.post.side_effect = httpx.RequestError("Connection failed")

    with patch("services.gateway.services.lambda_invoker.logger") as mock_logger:
        with pytest.raises(LambdaExecutionError):
            await invoker.invoke_function("error-func", b"{}")

        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args
        assert "function_name" in call_args.kwargs["extra"]
        assert call_args.kwargs["extra"]["function_name"] == "error-func"
