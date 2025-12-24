"""
Logging Configuration
Custom JSON Logger implementation optimized for VictoriaLogs.
"""

import logging
import logging.config
import json
import os
import string
from datetime import datetime, timezone

import yaml


class CustomJsonFormatter(logging.Formatter):
    """
    VictoriaLogs optimized JSON Formatter.

    Fields:
      - _time: ISO8601 timestamp (millisecond precision)
      - level: Log level
      - logger: Logger name (e.g. uvicorn.access, gateway.main)
      - message: Log message
      - trace_id: Trace ID for distributed tracing (X-Amzn-Trace-Id root)
    """

    def format(self, record: logging.LogRecord) -> str:
        # Trace ID resolution (trace_id > request_id for backward compat)
        trace_id = getattr(record, "trace_id", None) or getattr(record, "request_id", None)
        if not trace_id:
            try:
                from .request_context import get_trace_id

                trace_id = get_trace_id()
            except ImportError:
                pass

        log_data = {
            "_time": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(
                timespec="milliseconds"
            ),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if trace_id:
            log_data["trace_id"] = trace_id

        # Include extra fields
        standard_attrs = {
            "args",
            "asctime",
            "created",
            "exc_info",
            "exc_text",
            "filename",
            "funcName",
            "levelname",
            "levelno",
            "lineno",
            "module",
            "msecs",
            "message",
            "msg",
            "name",
            "pathname",
            "process",
            "processName",
            "relativeCreated",
            "stack_info",
            "thread",
            "threadName",
        }

        for key, value in record.__dict__.items():
            if key not in standard_attrs and not key.startswith("_"):
                log_data[key] = value

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, ensure_ascii=False)


def setup_logging(config_path: str = "logging.yml"):
    """
    YAML設定ファイルを読み込み、環境変数を置換した上でロギングを初期化します。
    """
    if not os.path.exists(config_path):
        logging.basicConfig(level=logging.INFO)
        return

    with open(config_path, "r", encoding="utf-8") as f:
        # string.Templateを使用して環境変数を置換
        # ${LOG_LEVEL} などの形式に対応
        template = string.Template(f.read())

        # デフォルト値の設定
        mapping = os.environ.copy()
        if "LOG_LEVEL" not in mapping:
            mapping["LOG_LEVEL"] = "INFO"

        content = template.safe_substitute(mapping)
        config = yaml.safe_load(content)
        logging.config.dictConfig(config)
