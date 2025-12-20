"""
Lambda呼び出しユーティリティ（ローカル環境用）

boto3 を使用して他のLambda関数を呼び出すヘルパー関数を提供します。
ローカル環境（Gateway）への接続設定を隠蔽します。
"""

import os
import json
import logging
from typing import Any

import boto3
from botocore.config import Config

# SSL警告を抑制（自己署名証明書使用時）
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


def init_lambda_client():
    """
    ローカルGatewayに向けたLambdaクライアントを初期化

    環境変数 LAMBDA_ENDPOINT でエンドポイントを指定可能
    （デフォルト: https://onpre-gateway:443）
    """
    endpoint = os.environ.get("LAMBDA_ENDPOINT", "https://onpre-gateway:443")
    logger.info(f"Initializing Lambda client with endpoint: {endpoint}")

    return boto3.client(
        "lambda",
        endpoint_url=endpoint,
        verify=False,  # 自己署名証明書対応
        region_name="ap-northeast-1",
        config=Config(
            retries={"max_attempts": 3},
            connect_timeout=5,
            read_timeout=300,
        ),
    )


def invoke_lambda(
    function_name: str,
    payload: dict[str, Any],
    invocation_type: str = "RequestResponse",
) -> dict[str, Any]:
    """
    Lambda関数を呼び出す

    Args:
        function_name: 呼び出す関数名（コンテナ名）
        payload: リクエストペイロード
        invocation_type: 呼び出しタイプ
            - "RequestResponse": 同期呼び出し（結果を待つ）
            - "Event": 非同期呼び出し（即座に202を返す）

    Returns:
        dict with:
            - StatusCode: HTTPステータスコード
            - Payload: レスポンスデータ（同期時のみ）
    """
    client = init_lambda_client()

    response = client.invoke(
        FunctionName=function_name,
        InvocationType=invocation_type,
        Payload=json.dumps(payload) if isinstance(payload, dict) else payload,
    )

    response_payload = response["Payload"].read()

    return {
        "StatusCode": response["StatusCode"],
        "Payload": json.loads(response_payload) if response_payload else None,
    }
