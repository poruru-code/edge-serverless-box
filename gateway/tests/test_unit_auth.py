import pytest
import jwt
from fastapi.testclient import TestClient
from gateway.app.main import app
from gateway.app.core.security import create_access_token, verify_token
from gateway.app.config import config

client = TestClient(app)

class TestAuthUnit:
    def test_auth_success_default(self):
        """デフォルト設定での認証成功"""
        headers = {
            "x-api-key": "dev-api-key-change-in-production",
            "Content-Type": "application/json"
        }
        payload = {
            "AuthParameters": {
                "USERNAME": "onpremise-user",
                "PASSWORD": "onpremise-pass"
            }
        }
        
        response = client.post(config.AUTH_ENDPOINT_PATH, json=payload, headers=headers)
        assert response.status_code == 200
        assert "AuthenticationResult" in response.json()
        assert "IdToken" in response.json()["AuthenticationResult"]

    def test_auth_custom_config(self, monkeypatch):
        """設定変更後の認証成功・失敗"""
        # Configの値を変更
        monkeypatch.setattr(config, "AUTH_USER", "admin")
        monkeypatch.setattr(config, "AUTH_PASS", "adminpass")
        monkeypatch.setattr(config, "X_API_KEY", "new-api-key")
        
        # 1. 新しい認証情報で成功するか
        headers = {
            "x-api-key": "new-api-key",
            "Content-Type": "application/json"
        }
        payload = {
            "AuthParameters": {
                "USERNAME": "admin",
                "PASSWORD": "adminpass"
            }
        }
        response = client.post(config.AUTH_ENDPOINT_PATH, json=payload, headers=headers)
        assert response.status_code == 200
        
        # 2. 古い認証情報で失敗するか
        payload_old = {
            "AuthParameters": {
                "USERNAME": "onpremise-user",
                "PASSWORD": "onpremise-pass"
            }
        }
        response = client.post(config.AUTH_ENDPOINT_PATH, json=payload_old, headers=headers)
        assert response.status_code == 401
        
        # 3. 古いAPIキーで失敗するか
        headers_old = {
            "x-api-key": "dev-api-key-change-in-production",
            "Content-Type": "application/json"
        }
        response = client.post(config.AUTH_ENDPOINT_PATH, json=payload, headers=headers_old)
        assert response.status_code == 401
        
    def test_token_verify_custom_secret(self, monkeypatch):
        """シークレットキー変更時のトークン検証"""
        new_secret = "new-secret"
        monkeypatch.setattr(config, "JWT_SECRET_KEY", new_secret)
        
        # 新しいシークレットでトークン生成
        token = create_access_token("custom-user", secret_key=new_secret)
        
        # 1. 新しいキーでデコードできるか (create側の検証)
        decoded = jwt.decode(token, new_secret, algorithms=["HS256"])
        assert decoded["sub"] == "custom-user"
        
        # 2. 古いキーではデコードできないか (署名エラーになるはず)
        with pytest.raises(jwt.InvalidSignatureError):
            jwt.decode(token, "dev-secret-key-change-in-production", algorithms=["HS256"])

        # 3. verify_token関数が新しいキーを使って検証できるか
        username = verify_token(f"Bearer {token}", secret_key=new_secret)
        assert username == "custom-user"
