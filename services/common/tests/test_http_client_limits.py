import httpx
from unittest.mock import patch
from services.common.core.config import BaseAppConfig
from services.common.core.http_client import HttpClientFactory


class TestHttpClientLimits:
    @patch("httpx.AsyncClient")
    def test_create_async_client_defaults_limits(self, mock_client):
        """AsyncClient 作成時にデフォルトで拡張された Limits が適用されること"""
        config = BaseAppConfig(VERIFY_SSL=True)
        factory = HttpClientFactory(config)

        factory.create_async_client()

        # 呼び出し時の引数を確認
        args, kwargs = mock_client.call_args
        limits = kwargs.get("limits")

        assert isinstance(limits, httpx.Limits)
        assert limits.max_keepalive_connections == 20
        assert limits.max_connections == 100

    @patch("httpx.AsyncClient")
    def test_create_async_client_override_limits(self, mock_client):
        """引数で Limits を指定した場合、それが優先されること"""
        config = BaseAppConfig(VERIFY_SSL=True)
        factory = HttpClientFactory(config)

        custom_limits = httpx.Limits(max_connections=500)
        factory.create_async_client(limits=custom_limits)

        args, kwargs = mock_client.call_args
        limits = kwargs.get("limits")

        assert limits == custom_limits
        assert limits.max_connections == 500
