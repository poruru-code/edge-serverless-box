"""
RIE 環境での Trace ID ブリッジ用デコレータ

AWS Lambda 本番環境では _X_AMZN_TRACE_ID 環境変数が自動設定されますが、
RIE (Runtime Interface Emulator) ではこの機能がないため、
ClientContext 経由で Trace ID を受け渡します。
"""

import asyncio
import os
import logging
from functools import wraps

logger = logging.getLogger(__name__)


def _set_trace_id_from_context(context):
    """ClientContext から Trace ID を取り出し、環境変数にセットする"""
    if hasattr(context, "client_context") and context.client_context:
        custom = getattr(context.client_context, "custom", None)
        if custom and isinstance(custom, dict) and "trace_id" in custom:
            trace_id = custom["trace_id"]
            if not os.environ.get("_X_AMZN_TRACE_ID"):
                os.environ["_X_AMZN_TRACE_ID"] = trace_id
                logger.debug(f"Hydrated _X_AMZN_TRACE_ID from ClientContext: {trace_id}")


def hydrate_trace_id(handler):
    """
    RIE 環境において、ClientContext から Trace ID を取り出し、
    環境変数 _X_AMZN_TRACE_ID にセットするデコレータ。

    sync/async 両方のハンドラに対応。

    Usage:
        @hydrate_trace_id
        def lambda_handler(event, context):
            ...

        @hydrate_trace_id
        async def lambda_handler(event, context):
            ...
    """
    if asyncio.iscoroutinefunction(handler):

        @wraps(handler)
        async def async_wrapper(event, context):
            _set_trace_id_from_context(context)
            return await handler(event, context)

        return async_wrapper
    else:

        @wraps(handler)
        def sync_wrapper(event, context):
            _set_trace_id_from_context(context)
            return handler(event, context)

        return sync_wrapper
