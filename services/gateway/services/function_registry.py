"""
Lambda関数レジストリ

functions.yml を読み込み、関数名→設定のマッピングを提供します。
デフォルト環境変数を関数固有の設定にマージします。
"""

from typing import Dict, Any, Optional
import yaml
import logging
import os
import string

from ..config import config

logger = logging.getLogger("gateway.function_registry")


class FunctionRegistry:
    def __init__(self):
        self._registry: Dict[str, Dict[str, Any]] = {}
        self._defaults: Dict[str, Any] = {}
        self.config_path = config.FUNCTIONS_CONFIG_PATH

    def load_functions_config(self) -> Dict[str, Dict[str, Any]]:
        """
        functions.yml を読み込んでキャッシュ

        Returns:
            関数名→設定の辞書
        """
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                # string.Templateを使用して環境変数を置換
                template = string.Template(f.read())

                # デフォルト値のマッピング作成
                mapping = os.environ.copy()
                if "LOG_LEVEL" not in mapping:
                    mapping["LOG_LEVEL"] = "INFO"

                content = template.safe_substitute(mapping)
                cfg = yaml.safe_load(content) or {}

            self._defaults = cfg.get("defaults", {})
            self._registry = cfg.get("functions", {})

            logger.info(f"Loaded {len(self._registry)} functions from {self.config_path}")

        except FileNotFoundError:
            logger.warning(f"Functions config not found at {self.config_path}")
            self._registry = {}
            self._defaults = {}

        except yaml.YAMLError as e:
            logger.error(f"Error parsing functions config: {e}")
            self._registry = {}
            self._defaults = {}

        return self._registry

    def get_function_config(self, function_name: str) -> Optional[Dict[str, Any]]:
        """
        関数名から設定を取得

        デフォルト環境変数を関数固有の設定にマージして返します。

        Args:
            function_name: 関数名（コンテナ名）

        Returns:
            関数設定（デフォルトマージ済み）。存在しない場合は None
        """
        if function_name not in self._registry:
            return None

        func_config = self._registry[function_name] or {}

        # デフォルト環境変数と関数固有の環境変数をマージ
        merged_env = {}
        default_env = self._defaults.get("environment", {})
        func_env = func_config.get("environment", {})

        # デフォルト → 関数固有の順でマージ（関数固有が優先）
        merged_env.update(default_env)
        merged_env.update(func_env)

        # 結果を構築
        result = dict(func_config)
        result["environment"] = merged_env

        return result
