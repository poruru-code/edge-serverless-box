"""
function_registry のテスト
"""

import pytest
from unittest.mock import patch, mock_open


class TestFunctionRegistry:
    """function_registry モジュールのテスト"""

    @pytest.fixture
    def sample_functions_yaml(self):
        """テスト用の functions.yml 内容"""
        return """
defaults:
  environment:
    LAMBDA_ENDPOINT: "https://onpre-gateway:443"

functions:
  lambda-hello: {}

  lambda-s3-test:
    environment:
      S3_ENDPOINT: "http://onpre-storage:9000"
      RUSTFS_ROOT_USER: "testuser"

  lambda-scylla-test:
    image: "custom-scylla:v1"
    environment:
      DYNAMODB_ENDPOINT: "http://onpre-database:8000"
"""

    def test_load_functions_config_parses_yaml(self, sample_functions_yaml):
        """functions.yml を正しくパースできる"""
        from gateway.app.services.function_registry import load_functions_config

        with patch("builtins.open", mock_open(read_data=sample_functions_yaml)):
            with patch(
                "gateway.app.services.function_registry.config.FUNCTIONS_CONFIG_PATH",
                "/fake/path/functions.yml",
            ):
                result = load_functions_config()

        assert "lambda-hello" in result
        assert "lambda-s3-test" in result
        assert "lambda-scylla-test" in result

    def test_get_function_config_returns_merged_config(self, sample_functions_yaml):
        """get_function_config はデフォルト環境変数をマージして返す"""
        from gateway.app.services.function_registry import (
            load_functions_config,
            get_function_config,
        )

        with patch("builtins.open", mock_open(read_data=sample_functions_yaml)):
            with patch(
                "gateway.app.services.function_registry.config.FUNCTIONS_CONFIG_PATH",
                "/fake/path/functions.yml",
            ):
                load_functions_config()

        config = get_function_config("lambda-s3-test")

        assert config is not None
        assert config["environment"]["LAMBDA_ENDPOINT"] == "https://onpre-gateway:443"
        assert config["environment"]["S3_ENDPOINT"] == "http://onpre-storage:9000"

    def test_get_function_config_returns_none_for_unknown(self, sample_functions_yaml):
        """存在しない関数名には None を返す"""
        from gateway.app.services.function_registry import (
            load_functions_config,
            get_function_config,
        )

        with patch("builtins.open", mock_open(read_data=sample_functions_yaml)):
            with patch(
                "gateway.app.services.function_registry.config.FUNCTIONS_CONFIG_PATH",
                "/fake/path/functions.yml",
            ):
                load_functions_config()

        result = get_function_config("non-existent-function")
        assert result is None

    def test_get_function_config_includes_custom_image(self, sample_functions_yaml):
        """カスタムイメージが指定されている場合はそれを返す"""
        from gateway.app.services.function_registry import (
            load_functions_config,
            get_function_config,
        )

        with patch("builtins.open", mock_open(read_data=sample_functions_yaml)):
            with patch(
                "gateway.app.services.function_registry.config.FUNCTIONS_CONFIG_PATH",
                "/fake/path/functions.yml",
            ):
                load_functions_config()

        config = get_function_config("lambda-scylla-test")
        assert config["image"] == "custom-scylla:v1"

    def test_get_function_config_empty_function_uses_defaults(self, sample_functions_yaml):
        """空の関数定義でもデフォルト環境変数が適用される"""
        from gateway.app.services.function_registry import (
            load_functions_config,
            get_function_config,
        )

        with patch("builtins.open", mock_open(read_data=sample_functions_yaml)):
            with patch(
                "gateway.app.services.function_registry.config.FUNCTIONS_CONFIG_PATH",
                "/fake/path/functions.yml",
            ):
                load_functions_config()

        config = get_function_config("lambda-hello")
        assert config is not None
        assert config["environment"]["LAMBDA_ENDPOINT"] == "https://onpre-gateway:443"

    def test_load_functions_config_file_not_found(self):
        """ファイルが見つからない場合は空の辞書を返す"""
        from gateway.app.services.function_registry import load_functions_config

        with patch("builtins.open", side_effect=FileNotFoundError()):
            with patch(
                "gateway.app.services.function_registry.config.FUNCTIONS_CONFIG_PATH",
                "/nonexistent/functions.yml",
            ):
                result = load_functions_config()

        assert result == {}
