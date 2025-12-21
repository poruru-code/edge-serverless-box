from services.common.core.logging_config import setup_logging as common_setup_logging
import os


def setup_logging():
    """
    YAML設定ファイルを読み込み、ロギングを初期化します。
    """
    config_path = os.getenv("LOG_CONFIG_PATH", "/app/config/manager_log.yaml")
    common_setup_logging(config_path)
