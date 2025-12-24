import json
import boto3
from common.utils import parse_event_body, create_response


def handle(event, context):
    print(f"Received event: {json.dumps(event)}")

    # ボディのパース
    body = parse_event_body(event)

    target_func = body.get("target")
    payload = body.get("payload", {})
    invoke_type = body.get("type", "RequestResponse")

    if not target_func:
        return create_response(status_code=400, body={"error": "Target function name required"})

    client = boto3.client("lambda")

    print(f"Invoking {target_func} with type {invoke_type} via boto3")

    try:
        # invokeメソッドの呼び出し
        response = client.invoke(
            FunctionName=target_func, InvocationType=invoke_type, Payload=json.dumps(payload)
        )

        # ステータスコードの取得
        status_code = response["StatusCode"]
        print(f"Response Status: {status_code}")

        # Event (非同期) の場合
        if invoke_type == "Event":
            success = status_code == 202
            return create_response(
                body={
                    "success": success,
                    "target": target_func,
                    "type": invoke_type,
                    "status_code": status_code,
                    "message": "Async invocation started",
                }
            )

        # RequestResponse (同期) の場合
        response_payload = response["Payload"].read()

        try:
            response_data = json.loads(response_payload)
        except Exception:
            response_data = response_payload.decode("utf-8")

        return create_response(
            body={
                "success": status_code == 200,
                "target": target_func,
                "type": invoke_type,
                "status_code": status_code,
                "response": response_data,
            }
        )

    except Exception as e:
        print(f"Invocation failed: {e}")
        return create_response(
            status_code=500, body={"success": False, "error": str(e), "target": target_func}
        )
