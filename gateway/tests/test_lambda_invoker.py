"""
lambda_invoker のテスト
"""

import pytest
from unittest.mock import patch, MagicMock
import requests

from gateway.app.core.exceptions import (
    FunctionNotFoundError,
    ContainerStartError,
    LambdaExecutionError,
)


class TestLambdaInvoker:
    """lambda_invoker モジュールのテスト"""

    @pytest.fixture
    def mock_function_config(self):
        """テスト用の関数設定"""
        return {
            "environment": {
                "LAMBDA_ENDPOINT": "https://onpre-gateway:443",
                "S3_ENDPOINT": "http://onpre-storage:9000",
            }
        }

    @pytest.fixture
    def mock_container_manager(self):
        """コンテナマネージャーのモック"""
        manager = MagicMock()
        manager.ensure_container_running.return_value = "lambda-hello"
        return manager

    def test_invoke_function_calls_rie(self, mock_function_config, mock_container_manager):
        """Lambda RIE に POST リクエストを送信する"""
        from gateway.app.services.lambda_invoker import invoke_function

        with patch(
            "gateway.app.services.lambda_invoker.get_function_config",
            return_value=mock_function_config,
        ):
            with patch(
                "gateway.app.services.lambda_invoker.get_manager",
                return_value=mock_container_manager,
            ):
                with patch("gateway.app.services.lambda_invoker.requests.post") as mock_post:
                    mock_response = MagicMock()
                    mock_response.content = b'{"result": "success"}'
                    mock_response.status_code = 200
                    mock_post.return_value = mock_response

                    result = invoke_function("lambda-hello", b'{"key": "value"}')

                    mock_post.assert_called_once()
                    call_args = mock_post.call_args
                    assert "8080/2015-03-31/functions/function/invocations" in call_args[0][0]
                    assert result.status_code == 200

    def test_invoke_function_raises_for_unknown_function(self):
        """存在しない関数の場合は FunctionNotFoundError を送出"""
        from gateway.app.services.lambda_invoker import invoke_function

        with patch(
            "gateway.app.services.lambda_invoker.get_function_config",
            return_value=None,
        ):
            with pytest.raises(FunctionNotFoundError) as exc_info:
                invoke_function("non-existent", b"{}")

            assert "non-existent" in str(exc_info.value)

    def test_invoke_function_starts_container(self, mock_function_config, mock_container_manager):
        """呼び出し時にコンテナを起動する"""
        from gateway.app.services.lambda_invoker import invoke_function

        with patch(
            "gateway.app.services.lambda_invoker.get_function_config",
            return_value=mock_function_config,
        ):
            with patch(
                "gateway.app.services.lambda_invoker.get_manager",
                return_value=mock_container_manager,
            ):
                with patch("gateway.app.services.lambda_invoker.requests.post"):
                    invoke_function("lambda-hello", b"{}")

                    mock_container_manager.ensure_container_running.assert_called_once_with(
                        name="lambda-hello",
                        image=None,
                        env=mock_function_config["environment"],
                    )

    def test_invoke_function_raises_container_start_error(self, mock_function_config):
        """コンテナ起動失敗時は ContainerStartError を送出"""
        from gateway.app.services.lambda_invoker import invoke_function

        with patch(
            "gateway.app.services.lambda_invoker.get_function_config",
            return_value=mock_function_config,
        ):
            with patch("gateway.app.services.lambda_invoker.get_manager") as mock_manager:
                mock_manager.return_value.ensure_container_running.side_effect = Exception(
                    "Container failed"
                )

                with pytest.raises(ContainerStartError):
                    invoke_function("lambda-hello", b"{}")

    def test_invoke_function_raises_execution_error(
        self, mock_function_config, mock_container_manager
    ):
        """リクエスト例外時は LambdaExecutionError を送出"""
        from gateway.app.services.lambda_invoker import invoke_function

        with patch(
            "gateway.app.services.lambda_invoker.get_function_config",
            return_value=mock_function_config,
        ):
            with patch(
                "gateway.app.services.lambda_invoker.get_manager",
                return_value=mock_container_manager,
            ):
                with patch(
                    "gateway.app.services.lambda_invoker.requests.post",
                    side_effect=requests.exceptions.ConnectionError("Connection failed"),
                ):
                    with pytest.raises(LambdaExecutionError):
                        invoke_function("lambda-hello", b"{}")
