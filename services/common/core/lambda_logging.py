"""
Lambda Logging Utilities

Provides robust logging for short-lived Lambda environments.
Ensures logs are flushed before the Lambda execution context freezes.
"""

import functools
import logging
import os
import sys

from .logging_config import CustomJsonFormatter, VictoriaLogsHandler


class StreamToLogger:
    """
    Redirects stdout/stderr to a logger instance.
    Captures print() statements and sends them through the logging system.
    """

    def __init__(self, logger: logging.Logger, level: int):
        self.logger = logger
        self.level = level

    def write(self, buf: str):
        for line in buf.rstrip().splitlines():
            if line.strip():
                self.logger.log(self.level, line.rstrip())

    def flush(self):
        pass


def robust_lambda_logger(service_name: str = "lambda"):
    """
    Decorator for Lambda handlers to ensure logs are flushed and stdout is captured.

    Features:
    - Adds VictoriaLogsHandler if VICTORIALOGS_URL is set
    - Captures stdout/stderr and sends through logging
    - Flushes all handlers in finally block (important for Lambda freeze)

    Usage:
        @robust_lambda_logger(service_name="echo-func")
        def lambda_handler(event, context):
            print("This will be logged!")
            return {"statusCode": 200}
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(event, context):
            vl_url = os.getenv("VICTORIALOGS_URL")
            original_stdout = sys.stdout
            original_stderr = sys.stderr

            logger = logging.getLogger()

            # セットアップ: VictoriaLogsHandlerが存在しなければ追加
            if vl_url:
                # 既存ハンドラーチェック（重複防止）
                if not any(isinstance(h, VictoriaLogsHandler) for h in logger.handlers):
                    handler = VictoriaLogsHandler(
                        url=vl_url,
                        stream_fields={"container_name": service_name, "job": "lambda"},
                    )
                    handler.setFormatter(CustomJsonFormatter())
                    logger.addHandler(handler)

                    # ログレベル調整（必要に応じて）
                    if logger.getEffectiveLevel() > logging.INFO:
                        logger.setLevel(logging.INFO)

                # 標準出力のハイジャック
                sys.stdout = StreamToLogger(logging.getLogger("stdout"), logging.INFO)
                sys.stderr = StreamToLogger(logging.getLogger("stderr"), logging.ERROR)

            try:
                return func(event, context)
            finally:
                # 終了処理: フラッシュと復元

                # 同期ハンドラーであっても、明示的にflushを呼ぶ習慣をつける
                # (将来的にバッファリングを入れた場合への備え)
                for h in logger.handlers:
                    if isinstance(h, VictoriaLogsHandler):
                        h.flush()

                sys.stdout = original_stdout
                sys.stderr = original_stderr

        return wrapper

    return decorator
