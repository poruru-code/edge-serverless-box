from unittest.mock import patch
import httpx
from services.gateway.core.utils import parse_lambda_response


def test_parse_lambda_response_logs_warning_on_invalid_json_body():
    """
    TDD Red: Lambda応答bodyがJSON文字列だがパース失敗時にwarningログを出力する
    """
    # Lambda応答: statusCode付きだがbodyが不正なJSON
    response_data = {
        "statusCode": 200,
        "headers": {},
        "body": "{invalid json here",  # 不正なJSON
    }
    mock_response = httpx.Response(200, json=response_data)

    with patch("services.gateway.core.utils.logger") as mock_logger:
        result = parse_lambda_response(mock_response)

        # 警告ログが出力されることを確認
        mock_logger.warning.assert_called_once()
        # ログにsnippetが含まれることを確認
        call_args = mock_logger.warning.call_args
        assert "extra" in call_args.kwargs
        assert "snippet" in call_args.kwargs["extra"]

        # 結果は元の文字列のまま返される
        assert result["content"] == "{invalid json here"
