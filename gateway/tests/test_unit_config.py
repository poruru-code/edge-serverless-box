import os
import pytest
from gateway.app.config import GatewayConfig

class TestConfig:
    def test_default_values(self):
        """デフォルト値の検証"""
        config = GatewayConfig()
        assert config.UVICORN_WORKERS == 4
        assert config.UVICORN_BIND_ADDR == "0.0.0.0:8000"
        assert config.AUTH_USER == "onpremise-user"
        # bool値の検証
        assert config.RUSTFS_DEDUPLICATION is True

    def test_custom_values(self):
        """環境変数から値を設定できるか検証"""
        # Pydanticモデルに直接値を渡して検証
        config = GatewayConfig(
            UVICORN_WORKERS=8,
            AUTH_USER="admin",
            RUSTFS_DEDUPLICATION=False,
            # 文字列で渡した場合の型変換 (Pydanticの機能)
            JWT_EXPIRES_DELTA="7200"
        )
        
        assert config.UVICORN_WORKERS == 8
        assert config.AUTH_USER == "admin"
        assert config.RUSTFS_DEDUPLICATION is False
        assert config.JWT_EXPIRES_DELTA == 7200

    def test_env_loading(self, monkeypatch):
        """load_config関数が環境変数を読み込むか検証"""
        from gateway.app.config import load_config
        
        monkeypatch.setenv("UVICORN_WORKERS", "10")
        monkeypatch.setenv("AUTH_USER", "env_user")
        monkeypatch.setenv("RUSTFS_DEDUPLICATION", "0") # 0 -> False
        
        config = load_config()
        
        assert config.UVICORN_WORKERS == 10
        assert config.AUTH_USER == "env_user"
        assert config.RUSTFS_DEDUPLICATION is False
