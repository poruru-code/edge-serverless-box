import json
import logging
import uuid
import time
import boto3
from common.utils import create_response

logger = logging.getLogger()
logger.setLevel(logging.INFO)

TABLE_NAME = "e2e-test-table"


def handle(event, context):
    logger.info(f"Received event: {json.dumps(event)}")

    try:
        # 透過的パッチに依存してクライアントを作成
        dynamodb = boto3.client("dynamodb")

        # Create item
        item_id = str(uuid.uuid4())
        timestamp = int(time.time())
        item = {
            "id": {"S": item_id},
            "timestamp": {"N": str(timestamp)},
            "message": {"S": "Hello from ScyllaDB Lambda"},
        }

        logger.info(f"Putting item: {item}")
        dynamodb.put_item(TableName=TABLE_NAME, Item=item)

        # Get item
        logger.info(f"Getting item: {item_id}")
        response = dynamodb.get_item(TableName=TABLE_NAME, Key={"id": {"S": item_id}})
        retrieved = response.get("Item", {})

        return create_response(
            body={"success": True, "item_id": item_id, "retrieved_item": retrieved}
        )

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return create_response(status_code=500, body={"success": False, "error": str(e)})
