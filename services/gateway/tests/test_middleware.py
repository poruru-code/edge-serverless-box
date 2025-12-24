import pytest
from unittest.mock import Mock
from fastapi import Request, Response
from services.gateway.main import request_id_middleware
from services.common.core.request_context import get_trace_id, clear_trace_id


@pytest.mark.asyncio
async def test_request_id_middleware_sets_context():
    # Setup
    clear_trace_id()
    expected_rid = "Root=1-6789abcd-1234567890abcdef12345678;Sampled=1"

    # Mock Request
    mock_request = Mock(spec=Request)
    mock_request.headers = {"X-Amzn-Trace-Id": expected_rid}
    mock_request.method = "GET"
    mock_request.url.path = "/test"

    # Mock call_next
    async def mock_call_next(request):
        # Verify context INSIDE the next call
        current_rid = get_trace_id()
        assert current_rid == expected_rid, f"Context RID inside call_next mismatch: {current_rid}"
        return Response(status_code=200)

    # Execute
    response = await request_id_middleware(mock_request, mock_call_next)

    # Verify Response Header
    assert response.headers["X-Amzn-Trace-Id"] == expected_rid

    # Verify Context Cleanliness (Optional, depending on implementation,
    # context is thread-local/task-local so it persists in the task.
    # But usually we check if it WAS set during the call)


@pytest.mark.asyncio
async def test_request_id_middleware_generates_id_if_missing():
    clear_trace_id()

    mock_request = Mock(spec=Request)
    mock_request.headers = {}  # No X-Amzn-Trace-Id
    mock_request.method = "GET"
    mock_request.url.path = "/test"

    captured_rid = None

    async def mock_call_next(request):
        nonlocal captured_rid
        captured_rid = get_trace_id()
        return Response(status_code=200)

    response = await request_id_middleware(mock_request, mock_call_next)

    assert captured_rid is not None
    assert response.headers["X-Amzn-Trace-Id"] == captured_rid
    assert captured_rid.startswith("Root=1-")
