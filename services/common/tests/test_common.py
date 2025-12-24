import logging
import json
import pytest
import asyncio
import warnings
from services.common.core.request_context import (
    set_request_id,
    get_request_id,
    clear_request_id,
    set_trace_id,
    clear_trace_id,
)
from services.common.core.logging_config import CustomJsonFormatter


def test_request_context_basic():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        clear_request_id()
        assert get_request_id() is None

        rid = set_request_id("test-id")
        assert rid == "test-id"
        assert get_request_id() == "test-id"

        clear_request_id()
        assert get_request_id() is None


@pytest.mark.asyncio
async def test_request_context_isolation():
    async def task(name, delay):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            set_request_id(name)
            await asyncio.sleep(delay)
            return get_request_id()

    results = await asyncio.gather(task("rid-1", 0.02), task("rid-2", 0.01))
    assert results[0] == "rid-1"
    assert results[1] == "rid-2"


def test_custom_json_formatter():
    formatter = CustomJsonFormatter()
    log_record = logging.LogRecord(
        name="test-logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Test message",
        args=None,
        exc_info=None,
    )

    # Without TraceID
    clear_trace_id()
    output = json.loads(formatter.format(log_record))
    assert output["message"] == "Test message"
    assert "trace_id" not in output

    # With TraceID (using new API)
    set_trace_id("Root=1-12345678-abcdef123456789012345678;Sampled=1")
    output = json.loads(formatter.format(log_record))
    assert output["trace_id"] == "Root=1-12345678-abcdef123456789012345678;Sampled=1"

    clear_trace_id()
