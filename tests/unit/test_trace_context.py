"""
TraceContext のテスト (Trace ID 対応版)
"""

import pytest
from services.common.core.request_context import (
    get_trace_id,
    set_trace_id,
    clear_trace_id,
)


def test_get_trace_id_default_is_none():
    """初期状態では TraceId は None"""
    clear_trace_id()
    assert get_trace_id() is None


def test_set_trace_id_with_valid_string():
    """TraceId (Root=...) を明示的に設定できる"""
    trace_str = "Root=1-676b8f34-e432f8314483756f7098e60b;Sampled=1"
    result = set_trace_id(trace_str)
    assert result == trace_str
    assert get_trace_id() == trace_str
    clear_trace_id()


def test_set_trace_id_generates_root_id_side_effect():
    """set_trace_id は副作用として Request ID (Root ID) も設定する (互換性)"""
    from services.common.core.request_context import get_request_id

    trace_str = "Root=1-676b8f34-e432f8314483756f7098e60b;Sampled=1"
    set_trace_id(trace_str)

    # get_request_id() は警告が出るが動作はする
    with pytest.warns(DeprecationWarning):
        root_id = get_request_id()

    assert root_id == "1-676b8f34-e432f8314483756f7098e60b"
    clear_trace_id()


def test_clear_trace_id():
    """TraceId をクリアできる"""
    trace_str = "Root=1-676b8f34-e432f8314483756f7098e60b;Sampled=1"
    set_trace_id(trace_str)
    assert get_trace_id() == trace_str

    clear_trace_id()
    assert get_trace_id() is None


@pytest.mark.asyncio
async def test_trace_id_isolation_in_async_context():
    """非同期タスク間で TraceId が分離される (ContextVar の動作確認)"""
    import asyncio

    trace_a = "Root=1-aaaaaaaa-aaaaaaaaaaaaaaaaaaaaaaaa;Sampled=1"
    trace_b = "Root=1-bbbbbbbb-bbbbbbbbbbbbbbbbbbbbbbbb;Sampled=1"

    async def task_a():
        set_trace_id(trace_a)
        await asyncio.sleep(0.01)
        return get_trace_id()

    async def task_b():
        set_trace_id(trace_b)
        await asyncio.sleep(0.01)
        return get_trace_id()

    result_a, result_b = await asyncio.gather(task_a(), task_b())
    assert result_a == trace_a
    assert result_b == trace_b
    clear_trace_id()


def test_legacy_request_id_compatibility():
    """従来の Request ID 機能が警告付きで維持されていること"""
    from services.common.core.request_context import (
        get_request_id,
        set_request_id,
        clear_request_id,
    )

    rid = "test-rid"

    # set_request_id (Deprecated)
    with pytest.warns(DeprecationWarning):
        set_request_id(rid)

    # get_request_id (Deprecated)
    with pytest.warns(DeprecationWarning):
        got = get_request_id()
    assert got == rid

    # clear_request_id (Deprecated)
    with pytest.warns(DeprecationWarning):
        clear_request_id()

    with pytest.warns(DeprecationWarning):
        assert get_request_id() is None
