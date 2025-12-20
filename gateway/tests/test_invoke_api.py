"""
Invoke API エンドポイントのテスト
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


class TestInvokeAPI:
    """Invoke API エンドポイントのテスト"""

    @pytest.fixture
    def client(self):
        """FastAPI テストクライアント"""
        from gateway.app.main import app

        return TestClient(app)

    @pytest.fixture
    def mock_response(self):
        """テスト用のモックレスポンス"""
        resp = MagicMock()
        resp.content = b'{"result": "success"}'
        resp.status_code = 200
        return resp

    def test_invoke_request_response_returns_lambda_result(self, client, mock_response):
        """同期呼び出し（RequestResponse）で Lambda の結果を返す"""
        with patch(
            "gateway.app.services.lambda_invoker.get_function_config",
            return_value={"environment": {}},
        ):
            with patch("gateway.app.services.lambda_invoker.get_manager") as mock_manager:
                mock_manager.return_value.ensure_container_running.return_value = "lambda-hello"
                with patch(
                    "gateway.app.services.lambda_invoker.requests.post",
                    return_value=mock_response,
                ):
                    response = client.post(
                        "/2015-03-31/functions/lambda-hello/invocations",
                        content=b'{"key": "value"}',
                    )

                    assert response.status_code == 200
                    assert response.json() == {"result": "success"}

    def test_invoke_event_returns_202(self, client, mock_response):
        """非同期呼び出し（Event）で 202 を即座に返す"""
        with patch(
            "gateway.app.services.lambda_invoker.get_function_config",
            return_value={"environment": {}},
        ):
            with patch("gateway.app.services.lambda_invoker.get_manager") as mock_manager:
                mock_manager.return_value.ensure_container_running.return_value = "lambda-hello"
                with patch(
                    "gateway.app.services.lambda_invoker.requests.post",
                    return_value=mock_response,
                ):
                    response = client.post(
                        "/2015-03-31/functions/lambda-hello/invocations",
                        content=b'{"key": "value"}',
                        headers={"X-Amz-Invocation-Type": "Event"},
                    )

                    assert response.status_code == 202

    def test_invoke_unknown_function_returns_404(self, client):
        """存在しない関数には 404 を返す"""
        with patch(
            "gateway.app.services.lambda_invoker.get_function_config",
            return_value=None,
        ):
            response = client.post(
                "/2015-03-31/functions/non-existent/invocations",
                content=b"{}",
            )

            assert response.status_code == 404
            assert "not found" in response.json()["message"].lower()

    def test_invoke_container_error_returns_503(self, client):
        """コンテナ起動失敗時は 503 を返す"""
        with patch(
            "gateway.app.services.lambda_invoker.get_function_config",
            return_value={"environment": {}},
        ):
            with patch("gateway.app.services.lambda_invoker.get_manager") as mock_manager:
                mock_manager.return_value.ensure_container_running.side_effect = Exception(
                    "Container failed"
                )

                response = client.post(
                    "/2015-03-31/functions/lambda-hello/invocations",
                    content=b"{}",
                )

                assert response.status_code == 503
