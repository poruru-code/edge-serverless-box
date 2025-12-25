"""
Gateway 基本機能テスト

- ヘルスチェック
- 認証フロー
- 基本的なルーティング (401, 404)
"""

import requests
from tests.conftest import (
    GATEWAY_URL,
    VERIFY_SSL,
    call_api,
)


class TestGatewayBasics:
    """Gateway 基本機能の検証"""

    def test_health(self, gateway_health):
        """E2E: ヘルスチェック"""
        response = requests.get(f"{GATEWAY_URL}/health", verify=VERIFY_SSL)
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_auth(self, auth_token):
        """E2E: 認証フロー"""
        assert auth_token is not None
        assert len(auth_token) > 0

    def test_routing_401(self, gateway_health):
        """E2E: 認証なし → 401"""
        response = call_api("/api/echo", payload={"message": "test"})
        if response.status_code != 401:
            print(f"Debug 401 Error: {response.status_code} - {response.text}")
        assert response.status_code == 401

    def test_routing_404(self, auth_token):
        """E2E: 存在しないルート → 404"""
        response = call_api("/api/nonexistent", auth_token, {"action": "test"})
        assert response.status_code == 404
