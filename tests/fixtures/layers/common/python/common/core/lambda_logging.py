"""
Lambda Logging Utilities (Layer Version)

Provides robust logging for short-lived Lambda environments.
Self-contained version for Lambda layer (no external dependencies).
"""

import functools
import json
import logging
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone


class CustomJsonFormatter(logging.Formatter):
    """VictoriaLogs optimized JSON Formatter."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "_time": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(
                timespec="milliseconds"
            ),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, ensure_ascii=False)


class VictoriaLogsHandler(logging.Handler):
    """
    VictoriaLogsへHTTPで直接ログを送信するハンドラー。
    失敗時は __stderr__ へフォールバック。
    """

    def __init__(self, url: str, stream_fields: dict = None, timeout: float = 0.5):
        super().__init__()
        self.url = url
        self.stream_fields = stream_fields or {}
        self.timeout = timeout

    def emit(self, record: logging.LogRecord):
        try:
            if self.formatter:
                msg = self.formatter.format(record)
            else:
                msg = record.getMessage()

            try:
                log_entry = json.loads(msg)
            except json.JSONDecodeError:
                log_entry = {"message": msg, "level": record.levelname}

            params = [
                ("_stream_fields", ",".join(self.stream_fields.keys())),
                ("_msg_field", "message"),
                ("_time_field", "_time"),
            ]
            for k, v in self.stream_fields.items():
                params.append((k, str(v)))

            query_string = urllib.parse.urlencode(params)
            full_url = f"{self.url}?{query_string}"

            data = json.dumps(log_entry, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(
                full_url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as res:
                    res.read()
            except (OSError, urllib.error.URLError) as e:
                fallback_msg = json.dumps(
                    {
                        "fallback": "victorialogs_failed",
                        "error": str(e),
                        "original_log": log_entry,
                    },
                    ensure_ascii=False,
                )
                stream = getattr(sys, "__stderr__", sys.stderr)
                try:
                    stream.write(fallback_msg + "\n")
                except Exception:
                    pass

        except Exception:
            self.handleError(record)

    def flush(self):
        pass


class StreamToLogger:
    """Redirects stdout/stderr to a logger instance."""

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
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(event, context):
            vl_url = os.getenv("VICTORIALOGS_URL")
            original_stdout = sys.stdout
            original_stderr = sys.stderr

            logger = logging.getLogger()

            if vl_url:
                if not any(isinstance(h, VictoriaLogsHandler) for h in logger.handlers):
                    handler = VictoriaLogsHandler(
                        url=vl_url,
                        stream_fields={"container_name": service_name, "job": "lambda"},
                    )
                    handler.setFormatter(CustomJsonFormatter())
                    logger.addHandler(handler)

                    if logger.getEffectiveLevel() > logging.INFO:
                        logger.setLevel(logging.INFO)

                sys.stdout = StreamToLogger(logging.getLogger("stdout"), logging.INFO)
                sys.stderr = StreamToLogger(logging.getLogger("stderr"), logging.ERROR)

            try:
                return func(event, context)
            finally:
                for h in logger.handlers:
                    if isinstance(h, VictoriaLogsHandler):
                        h.flush()

                sys.stdout = original_stdout
                sys.stderr = original_stderr

        return wrapper

    return decorator
