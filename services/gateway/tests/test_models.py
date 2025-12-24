import pytest
from pydantic import ValidationError
from services.gateway.models.aws_v1 import (
    APIGatewayProxyEvent,
    ApiGatewayRequestContext,
    ApiGatewayIdentity,
    ApiGatewayAuthorizer,
)


class TestAPIGatewayProxyEventModel:
    """APIGatewayProxyEvent Pydantic モデルの型検証テスト"""

    def test_model_required_fields_raises_validation_error(self):
        """必須フィールドが欠落している場合 ValidationError が発生"""
        # 必須フィールドなしでインスタンス化を試みる
        with pytest.raises(ValidationError) as exc_info:
            APIGatewayProxyEvent()

        # resource, path, httpMethod, headers, multiValueHeaders, requestContext は必須
        errors = exc_info.value.errors()
        missing_fields = {e["loc"][0] for e in errors if e["type"] == "missing"}
        assert "resource" in missing_fields
        assert "path" in missing_fields
        assert "httpMethod" in missing_fields

    def test_model_type_validation_raises_error_for_invalid_types(self):
        """不正な型が渡された場合 ValidationError が発生"""
        # headers に int を渡す（str を期待）
        with pytest.raises(ValidationError):
            APIGatewayProxyEvent(
                resource="/test",
                path="/test",
                httpMethod="GET",
                headers={"Content-Type": 123},  # 不正: int
                multiValueHeaders={},
                requestContext=ApiGatewayRequestContext(
                    identity=ApiGatewayIdentity(sourceIp="127.0.0.1"),
                    requestId="req-123",
                ),
            )

    def test_model_valid_construction(self):
        """正しい型で構築した場合、モデルが正常にインスタンス化される"""
        event = APIGatewayProxyEvent(
            resource="/users/{id}",
            path="/users/123",
            httpMethod="GET",
            headers={"Content-Type": "application/json"},
            multiValueHeaders={"Content-Type": ["application/json"]},
            requestContext=ApiGatewayRequestContext(
                identity=ApiGatewayIdentity(sourceIp="192.168.1.1", userAgent="test-agent"),
                authorizer=ApiGatewayAuthorizer(claims={"cognito:username": "testuser"}),
                requestId="req-abc123",
                stage="prod",
                protocol="HTTP/1.1",
            ),
            body='{"key": "value"}',
            isBase64Encoded=False,
        )

        assert event.resource == "/users/{id}"
        assert event.path == "/users/123"
        assert event.httpMethod == "GET"
        assert event.requestContext.identity.sourceIp == "192.168.1.1"
        assert event.requestContext.identity.userAgent == "test-agent"
        assert event.requestContext.stage == "prod"

    def test_model_dump_excludes_none(self):
        """model_dump(exclude_none=True) で None フィールドが除外される"""
        event = APIGatewayProxyEvent(
            resource="/test",
            path="/test",
            httpMethod="GET",
            headers={},
            multiValueHeaders={},
            queryStringParameters=None,  # 明示的に None
            requestContext=ApiGatewayRequestContext(
                identity=ApiGatewayIdentity(sourceIp="127.0.0.1"),
                requestId="req-123",
            ),
        )

        dumped = event.model_dump(exclude_none=True)
        assert "queryStringParameters" not in dumped
        assert "body" not in dumped  # デフォルト None
