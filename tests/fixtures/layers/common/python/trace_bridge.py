"""
RIE 環境での Trace ID ブリッジ用デコレータ

AWS Lambda 本番環境では _X_AMZN_TRACE_ID 環境変数が自動設定されますが、
RIE (Runtime Interface Emulator) ではこの機能がないため、
ClientContext 経由で Trace ID を受け渡します。
"""

import os
import logging
from functools import wraps

logger = logging.getLogger(__name__)


def hydrate_trace_id(handler):
    """
    RIE 環境において、ClientContext から Trace ID を取り出し、
    環境変数 _X_AMZN_TRACE_ID にセットするデコレータ。

    Usage:
        @hydrate_trace_id
        def lambda_handler(event, context):
            # ここに来た時点で os.environ['_X_AMZN_TRACE_ID'] がセット済み
            ...
    """

    @wraps(handler)
    def wrapper(event, context):
        trace_id = None

        # 1. ClientContext から Trace ID を探す
        if hasattr(context, "client_context") and context.client_context:
            custom = getattr(context.client_context, "custom", None)
            if custom and isinstance(custom, dict) and "trace_id" in custom:
                trace_id = custom["trace_id"]

        # 2. 環境変数が未設定、かつ取得できた場合にセット
        if trace_id and not os.environ.get("_X_AMZN_TRACE_ID"):
            os.environ["_X_AMZN_TRACE_ID"] = trace_id
            logger.debug(f"Hydrated _X_AMZN_TRACE_ID from ClientContext: {trace_id}")

        # 3. 元のハンドラを実行
        return handler(event, context)

    return wrapper
