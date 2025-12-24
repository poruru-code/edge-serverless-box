"""
VictoriaLogsHandler Unit Tests

Tests for the VictoriaLogsHandler class which sends logs directly to VictoriaLogs
and falls back to stdout on failure.
"""

import json
import logging
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from services.common.core.logging_config import VictoriaLogsHandler


class TestVictoriaLogsHandler:
    @pytest.fixture
    def handler(self):
        return VictoriaLogsHandler(
            url="http://localhost:9428/insert/jsonline",
            stream_fields={"container_name": "test-container"},
            timeout=0.1,
        )

    @pytest.fixture
    def log_record(self):
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname=__file__,
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        # CustomJsonFormatter が作るようなフィールドを想定
        record.created = 1678886400.0  # 2023-03-15T13:20:00Z
        return record

    def test_emit_sends_http_post(self, handler, log_record):
        """正常系: HTTP POST が送信されること"""
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_urlopen.return_value.__enter__.return_value = mock_response

            handler.emit(log_record)

            assert mock_urlopen.called
            args, kwargs = mock_urlopen.call_args
            req = args[0]

            # URLパラメータの検証
            assert "_stream_fields=container_name" in req.full_url
            assert "container_name=test-container" in req.full_url

            # ボディの検証
            data = json.loads(req.data.decode("utf-8"))
            assert data["message"] == "Test message"
            assert data["level"] == "INFO"

    def test_emit_fallback_to_stderr_on_failure(self, handler, log_record, capsys):
        """異常系: ネットワークエラー時に標準エラー出力へフォールバックすること"""
        with patch("urllib.request.urlopen") as mock_urlopen:
            # ネットワークエラーを発生させる
            mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

            handler.emit(log_record)

            # 標準エラー出力をキャプチャして検証
            captured = capsys.readouterr()
            assert captured.err != ""

            fallback_log = json.loads(captured.err)
            assert fallback_log["fallback"] == "victorialogs_failed"
            assert "Connection refused" in fallback_log["error"]
            assert fallback_log["original_log"]["message"] == "Test message"

    def test_flush_is_safe_to_call(self, handler):
        """flush() がエラーなく呼び出せること"""
        try:
            handler.flush()
        except Exception as e:
            pytest.fail(f"flush() raised {e}")

    def test_emit_handles_non_json_message(self, handler, log_record, capsys):
        """フォーマッタがJSON以外を返した場合でも適切に処理されること"""
        # フォーマッタをセットしない場合、getMessage() の結果がそのまま使われる
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_urlopen.return_value.__enter__.return_value = mock_response

            handler.emit(log_record)

            args, _ = mock_urlopen.call_args
            req = args[0]
            data = json.loads(req.data.decode("utf-8"))
            # getMessage() の結果がラップされていること
            assert data["message"] == "Test message"
            assert data["level"] == "INFO"
