"""
S3 互換 Lambda (RustFS/MinIO)

S3 API 操作を提供するシンプルな Lambda 関数。
"""

import json
import boto3
from datetime import datetime, timezone
from common.utils import handle_ping, parse_event_body, create_response
from common.core.lambda_logging import robust_lambda_logger


@robust_lambda_logger(service_name="lambda-s3")
def lambda_handler(event, context):
    # RIE Heartbeat
    if ping_response := handle_ping(event):
        return ping_response

    # requestContext からユーザー名を取得
    request_context = event.get("requestContext", {})
    username = request_context.get("authorizer", {}).get("cognito:username", "anonymous")
    request_id = request_context.get("requestId", "unknown")

    body = parse_event_body(event)
    action = body.get("action", "test")

    # 構造化ログ出力
    timestamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    print(
        json.dumps(
            {
                "_time": timestamp,
                "level": "INFO",
                "request_id": request_id,
                "message": f"Received event: action={action}",
                "function": "s3-integration",
            }
        )
    )

    bucket = body.get("bucket", "test-bucket")
    key = body.get("key", "test-key.txt")
    data = body.get("body", body.get("data", "Hello from Lambda!"))

    try:
        s3_client = boto3.client("s3")

        if action == "test":
            response = s3_client.list_buckets()
            result = {
                "action": "test",
                "success": True,
                "buckets": [b["Name"] for b in response.get("Buckets", [])],
                "user": username,
            }

        elif action == "put":
            response = s3_client.put_object(
                Bucket=bucket,
                Key=key,
                Body=data.encode("utf-8"),
                ContentType="application/octet-stream",
            )
            result = {
                "action": "put",
                "success": True,
                "bucket": bucket,
                "key": key,
                "etag": response.get("ETag"),
                "user": username,
            }

        elif action == "get":
            response = s3_client.get_object(Bucket=bucket, Key=key)
            content = response["Body"].read().decode("utf-8")
            result = {
                "action": "get",
                "success": True,
                "bucket": bucket,
                "key": key,
                "content": content,
                "user": username,
            }

        elif action == "list":
            response = s3_client.list_objects_v2(Bucket=bucket, Prefix=body.get("prefix", ""))
            result = {
                "action": "list",
                "success": True,
                "bucket": bucket,
                "objects": [obj["Key"] for obj in response.get("Contents", [])],
                "user": username,
            }

        elif action == "delete":
            s3_client.delete_object(Bucket=bucket, Key=key)
            result = {
                "action": "delete",
                "success": True,
                "bucket": bucket,
                "key": key,
                "user": username,
            }

        elif action == "create_bucket":
            try:
                s3_client.create_bucket(
                    Bucket=bucket,
                    CreateBucketConfiguration={"LocationConstraint": "ap-northeast-1"},
                )
                result = {
                    "action": "create_bucket",
                    "success": True,
                    "bucket": bucket,
                    "user": username,
                }
            except s3_client.exceptions.BucketAlreadyOwnedByYou:
                result = {
                    "action": "create_bucket",
                    "success": True,
                    "bucket": bucket,
                    "message": "Bucket already exists",
                    "user": username,
                }

        else:
            result = {
                "action": action,
                "success": False,
                "error": f"Unknown action: {action}",
                "user": username,
            }

        return create_response(body=result)

    except Exception as e:
        return create_response(
            status_code=500,
            body={"success": False, "error": str(e), "action": action, "user": username},
        )
