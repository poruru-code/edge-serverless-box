import json
import logging
import uuid
import time
import dynamodb_util

logger = logging.getLogger()
logger.setLevel(logging.INFO)

TABLE_NAME = "test_table"


def lambda_handler(event, context):
    # RIEハートビートチェック対応
    if isinstance(event, dict) and event.get("ping"):
        return {"statusCode": 200, "body": "pong"}

    logger.info(f"Received event: {json.dumps(event)}")

    try:
        # Create table if not exists
        dynamodb_util.create_table(
            table_name=TABLE_NAME,
            key_schema=[{"AttributeName": "id", "KeyType": "HASH"}],
            attribute_definitions=[{"AttributeName": "id", "AttributeType": "S"}],
        )

        # Give it a moment if it was just created (though Alternator is usually instant)
        # In a real app we might wait_for_table_exists, but for this test we proceed.

        # Create item
        item_id = str(uuid.uuid4())
        timestamp = int(time.time())
        item = {
            "id": {"S": item_id},
            "timestamp": {"N": str(timestamp)},
            "message": {"S": "Hello from ScyllaDB Lambda"},
        }

        logger.info(f"Putting item: {item}")
        dynamodb_util.put_item(TABLE_NAME, item)

        # Get item
        logger.info(f"Getting item: {item_id}")
        retrieved = dynamodb_util.get_item(TABLE_NAME, {"id": {"S": item_id}})

        return {
            "statusCode": 200,
            "body": json.dumps({"success": True, "item_id": item_id, "retrieved_item": retrieved}),
        }

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return {"statusCode": 500, "body": json.dumps({"success": False, "error": str(e)})}
