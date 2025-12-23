import json


def parse_event_body(event):
    """
    API Gatewayイベントのbodyをパースして辞書を返す
    """
    body = event.get("body", {})
    if isinstance(body, str):
        try:
            return json.loads(body)
        except (ValueError, json.JSONDecodeError):
            return {}
    return body


def handle_ping(event):
    """
    RIEからのハートビート(ping)を処理する
    戻り値がNoneでない場合、それをレスポンスとして返す
    """
    if isinstance(event, dict) and event.get("ping"):
        return {"statusCode": 200, "body": "pong"}
    return None


def create_response(status_code=200, body=None, headers=None):
    """
    API Gateway互換のレスポンス辞書を作成する
    """
    if headers is None:
        headers = {"Content-Type": "application/json"}

    if body is not None and not isinstance(body, str):
        body = json.dumps(body)

    return {"statusCode": status_code, "headers": headers, "body": body}
