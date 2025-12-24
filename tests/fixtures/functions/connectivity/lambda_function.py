"""
サンプルLambda関数: Hello World

requestContextからユーザー名を取得して応答します。
CloudWatch Logs テスト機能も含みます。
"""

import time
import boto3
import logging
from common.utils import handle_ping, parse_event_body, create_response

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    # RIEハートビートチェック対応
    if ping_response := handle_ping(event):
        return ping_response

    """
    Lambda関数のエントリーポイント
    
    Args:
        event: API Gatewayからのイベント
        context: Lambda実行コンテキスト
    
    Returns:
        API Gateway互換のレスポンス
    """
    username = (
        event.get("requestContext", {}).get("authorizer", {}).get("cognito:username", "anonymous")
    )
    logger.info(f"Processing action for user: {username}")

    # Parse body for action
    body = parse_event_body(event)
    action = body.get("action", "hello")

    # CloudWatch Logs テスト
    if action == "test_cloudwatch":
        try:
            logs_client = boto3.client("logs")
            log_group = "/lambda/hello-test"
            log_stream = f"test-stream-{int(time.time())}"

            # CreateLogGroup (既存でもOK)
            try:
                logs_client.create_log_group(logGroupName=log_group)
            except Exception:
                pass  # Already exists

            # CreateLogStream
            try:
                logs_client.create_log_stream(logGroupName=log_group, logStreamName=log_stream)
            except Exception:
                pass  # Already exists

            # PutLogEvents
            timestamp_ms = int(time.time() * 1000)
            # PutLogEvents (sitecustomize.py により透過的に stdout へ出力される)
            logs_client.put_log_events(
                logGroupName=log_group,
                logStreamName=log_stream,
                logEvents=[
                    {
                        "timestamp": timestamp_ms,
                        "message": f"[INFO] Test log from Lambda at {timestamp_ms}",
                    },
                    {"timestamp": timestamp_ms + 1, "message": "[DEBUG] This is a debug message"},
                    {"timestamp": timestamp_ms + 2, "message": "[ERROR] This is an error message"},
                    {
                        "timestamp": timestamp_ms + 3,
                        "message": "CloudWatch Logs E2E verification successful!",
                    },
                ],
            )

            return create_response(
                body={
                    "success": True,
                    "action": "test_cloudwatch",
                    "log_stream": log_stream,
                    "log_group": log_group,
                }
            )
        except Exception as e:
            return create_response(
                status_code=500,
                body={"success": False, "error": str(e), "action": "test_cloudwatch"},
            )

    # デフォルト: Hello レスポンス
    response_body = {
        "message": f"Hello, {username}!",
        "event": event,
        "function": "hello",
    }

    return create_response(body=response_body)
