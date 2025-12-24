"""
Gateway Utility Module
"""

import json
import logging
from typing import Dict, Any

import httpx

logger = logging.getLogger("gateway.utils")


def parse_lambda_response(lambda_response: httpx.Response) -> Dict[str, Any]:
    """
    Lambda RIEからのレスポンスをパースしてFastAPI用のレスポンスデータに変換

    Args:
        lambda_response: Lambda RIEからの生レスポンス

    Returns:
        FastAPIレスポンス用の辞書:
        {
            "status_code": int,
            "content": Any,
            "headers": dict,
            "raw_content": bytes (JSONパース失敗時のみ)
        }
    """
    try:
        response_data = lambda_response.json()

        # Lambda応答がAPI Gateway形式の場合
        if isinstance(response_data, dict) and "statusCode" in response_data:
            status_code = response_data.get("statusCode", 200)
            response_headers = response_data.get("headers", {})
            response_body = response_data.get("body", "")

            # bodyがJSON文字列の場合はパース
            if isinstance(response_body, str):
                try:
                    response_body = json.loads(response_body)
                except json.JSONDecodeError:
                    logger.warning(
                        "Failed to parse Lambda response body as JSON. Returning as string.",
                        extra={
                            "snippet": response_body[:200] if response_body else "",
                            "status_code": status_code,
                        },
                    )

            return {
                "status_code": status_code,
                "content": response_body,
                "headers": response_headers,
            }
        else:
            return {"status_code": 200, "content": response_data, "headers": {}}

    except json.JSONDecodeError:
        return {
            "status_code": lambda_response.status_code,
            "raw_content": lambda_response.content,
            "headers": dict(lambda_response.headers),
        }
