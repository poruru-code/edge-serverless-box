import os
import json
import boto3
import logging
from trace_bridge import hydrate_trace_id

logger = logging.getLogger()
logger.setLevel(logging.INFO)


@hydrate_trace_id
def lambda_handler(event, context):
    # 環境変数から Trace ID を取得 (hydrate_trace_id により ClientContext から補完される)
    trace_id = os.environ.get("_X_AMZN_TRACE_ID", "not-found")
    logger.info(f"Trace ID in environment: {trace_id}")

    # Context からの Request ID も記録
    aws_request_id = context.aws_request_id
    logger.info(f"AWS Request ID in context: {aws_request_id}")

    # 次のターゲットがあれば呼び出す (連鎖)
    next_target = event.get("next_target")
    child_info = None

    if next_target:
        logger.info(f"Chaining invocation to {next_target}")
        client = boto3.client("lambda")
        # sitecustomize.py のパッチが効いていれば、ここで自動的にヘッダーと ClientContext が乗る
        response = client.invoke(
            FunctionName=next_target,
            Payload=json.dumps({"action": "echo", "msg": "from-chain"}).encode("utf-8"),
        )
        child_payload = response["Payload"].read().decode("utf-8")
        child_info = json.loads(child_payload)

    return {
        "statusCode": 200,
        "body": json.dumps(
            {"trace_id": trace_id, "aws_request_id": aws_request_id, "child": child_info}
        ),
    }
