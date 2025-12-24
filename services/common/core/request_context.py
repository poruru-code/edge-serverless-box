"""
RequestContext コンテキスト管理
ContextVar を使用して、非同期処理間で RequestId および TraceId を共有します。
"""

from contextvars import ContextVar
from typing import Optional
from .trace import TraceId

import warnings

# リクエストID (Root IDのみ) を格納するコンテキスト変数
_request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
# Trace ID (フルヘッダー形式) を格納するコンテキスト変数
_trace_id_var: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)


def get_request_id() -> Optional[str]:
    """
    Deprecated: get_trace_id を使用してください。
    現在のリクエストID (Trace Root ID) を取得
    """
    warnings.warn(
        "get_request_id is deprecated, use get_trace_id", DeprecationWarning, stacklevel=2
    )
    return _request_id_var.get()


def set_request_id(request_id: Optional[str] = None) -> str:
    """
    Deprecated: set_trace_id を使用してください。
    リクエストIDを設定 (互換性維持のため)

    Args:
        request_id: 設定するリクエストID。Noneの場合は新規にUUIDを生成してTrace IDも生成
    """
    warnings.warn(
        "set_request_id is deprecated, use set_trace_id", DeprecationWarning, stacklevel=2
    )
    if request_id is None:
        # 新規生成なら Trace ID を生成してセットするのが正しい移行
        trace = TraceId.generate()
        _trace_id_var.set(str(trace))
        request_id = trace.to_root_id()
        _request_id_var.set(request_id)
        return request_id

    # 指定された場合は Trace ID との整合性が取れない可能性があるが、一旦セットする
    _request_id_var.set(request_id)
    return request_id


def get_trace_id() -> Optional[str]:
    """現在の Trace ID を取得"""
    return _trace_id_var.get()


def set_trace_id(trace_id_str: str) -> str:
    """
    Trace ID を設定し、Request ID も同期する

    Args:
        trace_id_str: X-Amzn-Trace-Id ヘッダー形式の文字列

    Returns:
        設定されたフル Trace ID 文字列
    """
    # print(f"[request_context] Setting trace_id from string: '{trace_id_str}'")
    try:
        trace = TraceId.parse(trace_id_str)
        _trace_id_var.set(str(trace))

        # Request ID には Root ID (1-xxx-xxx) をセットする
        root_id = trace.to_root_id()
        _request_id_var.set(root_id)
        # print(f"[request_context] Trace ID set to '{trace}', Request ID set to '{root_id}'")

        return str(trace)
    except Exception as e:
        # print(f"[request_context] Failed to set trace_id: {e}")
        raise e


def clear_trace_id() -> None:
    """Trace ID と Request ID のコンテキストをクリア"""
    _request_id_var.set(None)
    _trace_id_var.set(None)


# 後方互換エイリアス
def clear_request_id() -> None:
    """Deprecated: clear_trace_id を使用してください"""
    warnings.warn(
        "clear_request_id is deprecated, use clear_trace_id", DeprecationWarning, stacklevel=2
    )
    clear_trace_id()
