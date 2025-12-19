"""
サンプルLambda関数: Hello World

requestContextからユーザー名を取得して応答します。
"""
import json


def lambda_handler(event, context):
    """
    Lambda関数のエントリーポイント
    
    Args:
        event: API Gatewayからのイベント
        context: Lambda実行コンテキスト
    
    Returns:
        API Gateway互換のレスポンス
    """
    # requestContextからユーザー名を取得
    username = event.get("requestContext", {}).get("authorizer", {}).get("cognito:username", "anonymous")
    
    # レスポンスボディ
    response_body = {
        "message": f"Hello, {username}!",
        "event": event,
        "function": "hello"
    }
    
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": json.dumps(response_body)
    }
