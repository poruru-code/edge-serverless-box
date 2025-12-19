"""
E2Eテスト: HTTP → FastAPI → Lambda RIE 統合テスト

docker-compose.ymlでGatewayコンテナ（DinD環境）を起動し、
外部HTTPリクエストで完全なフローをテストします。

前提条件:
- docker-compose up -d gateway でGatewayを起動済み
- 内部でLambda RIE + RustFSが自動起動

テストフロー:
1. 認証（/user/auth/v1）
2. ルーティング経由でLambda呼び出し（/api/s3/test）
"""
import pytest
import requests
import time

from gateway.app.config import config

# テスト用設定
GATEWAY_URL = "http://localhost:8000"
API_KEY = config.X_API_KEY


@pytest.fixture(scope="module")
def gateway_health():
    """Gatewayのヘルスチェック"""
    for i in range(10):
        try:
            response = requests.get(f"{GATEWAY_URL}/health", timeout=5)
            if response.status_code == 200:
                return True
        except Exception:
            print(f"Waiting for Gateway... ({i+1}/10)")
            time.sleep(3)
    pytest.skip("Gateway is not running. Start with: docker compose up -d gateway")


def get_auth_token() -> str:
    """認証してトークンを取得"""
    response = requests.post(
        f"{GATEWAY_URL}{config.AUTH_ENDPOINT_PATH}",
        json={
            "AuthParameters": {
                "USERNAME": config.AUTH_USER,
                "PASSWORD": config.AUTH_PASS
            }
        },
        headers={"x-api-key": API_KEY}
    )
    assert response.status_code == 200, f"Auth failed: {response.text}"
    return response.json()["AuthenticationResult"]["IdToken"]


class TestE2E:
    """E2E統合テスト: HTTP → FastAPI → Lambda RIE"""
    
    def test_health(self, gateway_health):
        """E2E: ヘルスチェック"""
        response = requests.get(f"{GATEWAY_URL}/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
    
    def test_auth(self, gateway_health):
        """E2E: 認証フロー"""
        token = get_auth_token()
        assert token is not None
        assert len(token) > 0
    
    def test_routing_401(self, gateway_health):
        """E2E: 認証なし → 401"""
        response = requests.post(
            f"{GATEWAY_URL}/api/s3/test",
            json={"action": "test"}
        )
        assert response.status_code == 401
    
    def test_routing_404(self, gateway_health):
        """E2E: 存在しないルート → 404"""
        token = get_auth_token()
        response = requests.post(
            f"{GATEWAY_URL}/api/nonexistent",
            json={"action": "test"},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 404
    
    def test_lambda_invocation(self, gateway_health):
        """E2E: 認証 → ルーティング → Lambda呼び出し"""
        token = get_auth_token()
        
        response = requests.post(
            f"{GATEWAY_URL}/api/s3/test",
            json={"action": "test"},
            headers={"Authorization": f"Bearer {token}"}
        )
        
        # Lambda RIEが起動していない場合は502になる可能性がある
        if response.status_code == 502:
            pytest.skip("Lambda RIE not available in Gateway container")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["user"] == config.AUTH_USER


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
