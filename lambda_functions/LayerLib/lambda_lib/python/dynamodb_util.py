"""
DynamoDB互換データベース (ScyllaDB Alternator) 接続ユーティリティ

Lambda関数からScyllaDB AlternatorへのDynamoDB互換APIアクセスを提供します。
"""
import boto3
import botocore
import logging
import os

logger = logging.getLogger(__name__)


def init_database():
    """
    DynamoDB互換データベースクライアントを初期化して返す
    
    環境変数:
        DYNAMODB_ENDPOINT: DynamoDB互換エンドポイント (デフォルト: http://onpre-database:8000)
    
    Returns:
        boto3.client: DynamoDBクライアント
    """
    dynamodb_endpoint = os.environ.get("DYNAMODB_ENDPOINT", "http://onpre-database:8000")
    
    dynamodb_client = boto3.client(
        "dynamodb",
        endpoint_url=dynamodb_endpoint,
        aws_access_key_id="dummy",  # Alternatorは認証不要だがboto3に必須
        aws_secret_access_key="dummy",
        region_name="ap-northeast-1",
        config=botocore.config.Config(
            retries={"max_attempts": 3}
        )
    )
    
    logger.info(f"DynamoDB client initialized with endpoint: {dynamodb_endpoint}")
    return dynamodb_client


def init_database_resource():
    """
    DynamoDB互換データベースリソースを初期化して返す（Table操作用）
    
    Returns:
        boto3.resource: DynamoDBリソース
    """
    dynamodb_endpoint = os.environ.get("DYNAMODB_ENDPOINT", "http://onpre-database:8000")
    
    dynamodb_resource = boto3.resource(
        "dynamodb",
        endpoint_url=dynamodb_endpoint,
        aws_access_key_id="dummy",
        aws_secret_access_key="dummy",
        region_name="ap-northeast-1"
    )
    
    return dynamodb_resource


def get_item(table_name: str, key: dict) -> dict:
    """
    DynamoDBからアイテムを取得
    
    Args:
        table_name: テーブル名
        key: プライマリキー
    
    Returns:
        dict: アイテム（存在しない場合は空のdict）
    """
    client = init_database()
    response = client.get_item(TableName=table_name, Key=key)
    return response.get("Item", {})


def put_item(table_name: str, item: dict) -> dict:
    """
    DynamoDBにアイテムを保存
    
    Args:
        table_name: テーブル名
        item: 保存するアイテム
    
    Returns:
        dict: 保存結果
    """
    client = init_database()
    return client.put_item(TableName=table_name, Item=item)


def query(table_name: str, key_condition_expression: str, expression_attribute_values: dict) -> list:
    """
    DynamoDBをクエリ
    
    Args:
        table_name: テーブル名
        key_condition_expression: キー条件式
        expression_attribute_values: 式の属性値
    
    Returns:
        list: クエリ結果のアイテム一覧
    """
    client = init_database()
    response = client.query(
        TableName=table_name,
        KeyConditionExpression=key_condition_expression,
        ExpressionAttributeValues=expression_attribute_values
    )
    return response.get("Items", [])


def create_table(table_name: str, key_schema: list, attribute_definitions: list) -> dict:
    """
    DynamoDBテーブルを作成
    
    Args:
        table_name: テーブル名
        key_schema: キースキーマ
        attribute_definitions: 属性定義
    
    Returns:
        dict: 作成結果
    """
    client = init_database()
    try:
        return client.create_table(
            TableName=table_name,
            KeySchema=key_schema,
            AttributeDefinitions=attribute_definitions,
            BillingMode="PAY_PER_REQUEST"
        )
    except client.exceptions.ResourceInUseException:
        logger.info(f"Table {table_name} already exists")
        return {"TableName": table_name}
