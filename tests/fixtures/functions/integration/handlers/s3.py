import json
import boto3
from datetime import datetime, timezone
from common.utils import parse_event_body, create_response


def handle(event, context):
    # requestContextからユーザー名を取得
    request_context = event.get("requestContext", {})
    username = request_context.get("authorizer", {}).get("cognito:username", "anonymous")
    request_id = request_context.get("requestId", "unknown")

    # Body extraction setup for logging
    body = parse_event_body(event)
    log_action = body.get("action", "unknown")

    # 構造化ログ出力 (for VictoriaLogs)
    timestamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    print(
        json.dumps(
            {
                "_time": timestamp,
                "level": "INFO",
                "request_id": request_id,
                "message": f"Received event: action={log_action}",
                "function": "integration-s3",
            }
        )
    )

    action = body.get("action", "test")
    bucket = body.get("bucket", "test-bucket")
    key = body.get("key", "test-key.txt")
    data = body.get("data", "Hello from Lambda!")

    try:
        # 透過的パッチ(sitecustomize.py)に依存してクライアントを作成
        s3_client = boto3.client("s3")

        if action == "test":
            # 接続テスト: バケット一覧を取得
            response = s3_client.list_buckets()
            result = {
                "action": "test",
                "success": True,
                "buckets": [b["Name"] for b in response.get("Buckets", [])],
                "user": username,
            }

        elif action == "put":
            # オブジェクトをアップロード
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
            # オブジェクトを取得
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
            # オブジェクト一覧を取得
            response = s3_client.list_objects_v2(Bucket=bucket, Prefix=body.get("prefix", ""))
            result = {
                "action": "list",
                "success": True,
                "bucket": bucket,
                "objects": [obj["Key"] for obj in response.get("Contents", [])],
                "user": username,
            }

        elif action == "create_bucket":
            # バケット作成
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
