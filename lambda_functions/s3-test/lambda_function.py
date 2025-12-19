"""
S3テスト用Lambda関数

Lambda Layerのs3_util.pyを使用してRustFS (S3互換) にアクセスします。
"""
import json
import os

# Lambda Layerからインポート
from s3_util import init_storage, get_object, put_object, list_objects


def lambda_handler(event, context):
    """
    S3操作を行うLambda関数
    
    Args:
        event: API Gatewayからのイベント
            - action: "put" | "get" | "list" | "test"
            - bucket: バケット名
            - key: オブジェクトキー
            - data: アップロードするデータ (put時)
        context: Lambda実行コンテキスト
    
    Returns:
        API Gateway互換のレスポンス
    """
    # requestContextからユーザー名を取得
    username = event.get("requestContext", {}).get("authorizer", {}).get("cognito:username", "anonymous")
    
    # リクエストボディをパース
    body = event.get("body", "{}")
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except json.JSONDecodeError:
            body = {}
    
    action = body.get("action", "test")
    bucket = body.get("bucket", "test-bucket")
    key = body.get("key", "test-key.txt")
    data = body.get("data", "Hello from Lambda!")
    
    try:
        s3_client = init_storage()
        
        if action == "test":
            # 接続テスト: バケット一覧を取得
            response = s3_client.list_buckets()
            result = {
                "action": "test",
                "success": True,
                "buckets": [b["Name"] for b in response.get("Buckets", [])],
                "user": username
            }
        
        elif action == "put":
            # オブジェクトをアップロード
            result_data = put_object(bucket, key, data.encode("utf-8"))
            result = {
                "action": "put",
                "success": True,
                "bucket": bucket,
                "key": key,
                "etag": result_data.get("ETag"),
                "user": username
            }
        
        elif action == "get":
            # オブジェクトを取得
            content = get_object(bucket, key)
            result = {
                "action": "get",
                "success": True,
                "bucket": bucket,
                "key": key,
                "content": content.decode("utf-8"),
                "user": username
            }
        
        elif action == "list":
            # オブジェクト一覧を取得
            objects = list_objects(bucket, body.get("prefix", ""))
            result = {
                "action": "list",
                "success": True,
                "bucket": bucket,
                "objects": [obj["Key"] for obj in objects],
                "user": username
            }
        
        elif action == "create_bucket":
            # バケット作成
            try:
                s3_client.create_bucket(
                    Bucket=bucket,
                    CreateBucketConfiguration={"LocationConstraint": "ap-northeast-1"}
                )
                result = {
                    "action": "create_bucket",
                    "success": True,
                    "bucket": bucket,
                    "user": username
                }
            except s3_client.exceptions.BucketAlreadyOwnedByYou:
                result = {
                    "action": "create_bucket",
                    "success": True,
                    "bucket": bucket,
                    "message": "Bucket already exists",
                    "user": username
                }
        
        else:
            result = {
                "action": action,
                "success": False,
                "error": f"Unknown action: {action}",
                "user": username
            }
        
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(result)
        }
    
    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "success": False,
                "error": str(e),
                "action": action,
                "user": username
            })
        }
