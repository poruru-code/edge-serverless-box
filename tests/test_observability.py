"""
オブザーバビリティ機能テスト

- RequestID トレーシング
- ログ品質とレベル制御
- CloudWatch Logs 透過的リダイレクト
"""

import json
import time
import uuid

import requests

from tests.fixtures.conftest import (
    GATEWAY_URL,
    VICTORIALOGS_URL,
    VERIFY_SSL,
    LOG_WAIT_TIMEOUT,
    query_victorialogs,
)


class TestObservability:
    """ロギング・オブザーバビリティ機能の検証"""

    def test_log_quality_and_level_control(self, auth_token):
        """
        E2E: ロギングの品質と環境変数によるレベル制御の検証
        """

        # 検証用のユニークな Trace ID とメッセージ
        epoch_hex = hex(int(time.time()))[2:]
        unique_id = uuid.uuid4().hex[:24]
        trace_id = f"Root=1-{epoch_hex}-{unique_id};Sampled=1"
        root_id = f"1-{epoch_hex}-{unique_id}"

        debug_msg = f"DEBUG_LOG_VALIDATION_{uuid.uuid4()}"

        # ヘッダーに検証用IDをセットしてリクエスト（Gatewayでログ出力されることを期待）
        # 同時に、ボディにデバッグメッセージを含めて、Lambda側でも（あれば）出力させる
        response = requests.post(
            f"{GATEWAY_URL}/api/s3",
            json={
                "action": "test",
                "bucket": "e2e-test-bucket",
                "debug_msg": debug_msg,
            },
            headers={
                "Authorization": f"Bearer {auth_token}",
                "X-Amzn-Trace-Id": trace_id,
            },
            verify=VERIFY_SSL,
        )
        assert response.status_code == 200

        # Gatewayコンテナのログを検索
        print(f"Waiting for logs with Root ID: {root_id} ...")

        start_time = time.time()
        found_structured_log = False
        found_debug_log = False
        found_time_field = False

        while time.time() - start_time < LOG_WAIT_TIMEOUT:
            logs = query_victorialogs(root_id, timeout=1)

            hits = logs.get("hits", [])
            if hits:
                for log in hits:
                    # 1. 構造化ログ（JSON）であることの確認（hitsに入っている時点でJSONパース済み）
                    # 必須フィールドの確認
                    if "level" in log and ("message" in log or "_msg" in log):
                        found_structured_log = True

                    # 2. _time フィールドの確認
                    if "_time" in log:
                        # 形式確認（数値または文字列のタイムスタンプ）
                        ts = log["_time"]
                        if isinstance(ts, (int, float)) or (
                            isinstance(ts, str) and ts.replace(".", "").isdigit()
                        ):
                            found_time_field = True
                        elif isinstance(ts, str):
                            # ISO format check could be here
                            found_time_field = True

                    # 3. DEBUG レベルのログ確認
                    if log.get("level") == "DEBUG" or log.get("level") == "debug":
                        found_debug_log = True

            if found_structured_log and found_time_field and found_debug_log:
                break

            time.sleep(2)

        assert found_structured_log, "Structured logs (JSON) not found"
        assert found_time_field, "_time field not found or invalid"
        assert found_debug_log, "DEBUG level log not found. Check LOG_LEVEL env var."

    def test_cloudwatch_logs_via_boto3(self, gateway_health):
        """
        E2E: CloudWatch Logs API 透過的リダイレクト検証
        """
        # 1. Lambda 呼び出し (action=test_cloudwatch)
        invoke_url = f"{GATEWAY_URL}/2015-03-31/functions/lambda-connectivity/invocations"
        payload = {"body": '{"action": "test_cloudwatch"}'}

        response = requests.post(invoke_url, json=payload, verify=VERIFY_SSL, timeout=30)
        assert response.status_code == 200, f"Lambda invocation failed: {response.text}"

        resp_data = response.json()
        resp_body = json.loads(resp_data.get("body", "{}"))
        assert resp_body.get("success") is True, f"CloudWatch test failed: {resp_body.get('error')}"

        log_group = resp_body.get("log_group")
        log_stream = resp_body.get("log_stream")
        print(f"CloudWatch test: log_group={log_group}, log_stream={log_stream}")

        # 2. ログが VictoriaLogs に伝搬するまで待機
        time.sleep(5)

        # 3. VictoriaLogs でログを検索
        vlogs_url = f"{VICTORIALOGS_URL}/select/logsql/query"
        query = f'logger:boto3.mock AND log_group:"{log_group}" AND log_stream:"{log_stream}"'

        max_retries = 10
        found_logs = False
        log_entries = []
        for i in range(max_retries):
            r = requests.get(vlogs_url, params={"query": query, "limit": 20}, timeout=10)
            if r.status_code == 200 and r.text.strip():
                lines = r.text.strip().split("\n")
                if lines and lines[0]:
                    log_entries = [json.loads(line) for line in lines if line.strip()]
                    # 4つ全てのログが届くまでリトライする
                    if len(log_entries) >= 4:
                        found_logs = True
                        print(f"Found {len(log_entries)} log entries in VictoriaLogs")
                        break
                    else:
                        print(
                            f"Found only {len(log_entries)}/4 logs, retrying... ({i + 1}/{max_retries})"
                        )
            time.sleep(2)

        assert found_logs, (
            f"CloudWatch Logs not found in VictoriaLogs for log_group={log_group}. "
            "Check Gateway /aws/logs endpoint and Fluent Bit configuration."
        )

        for entry in log_entries:
            container_name = entry.get("container_name", "")
            assert container_name == "lambda-connectivity", (
                f"Expected container_name='lambda-connectivity', got '{container_name}'. "
                "CloudWatch Logs should be attributed to Lambda container, not Gateway."
            )

        # 5. ログレベルが正しく設定されていることを検証
        levels = [entry.get("level", "") for entry in log_entries]
        print(f"Detected levels in VictoriaLogs: {levels}")

        assert "DEBUG" in levels, "DEBUG level log not found in VictoriaLogs"
        assert "ERROR" in levels, "ERROR level log not found in VictoriaLogs"
        assert "INFO" in levels, "INFO level log not found in VictoriaLogs"

        # 6. メッセージの内容が Lambda から送信されたものか検証
        messages = [entry.get("_msg", "") for entry in log_entries]
        expected_message = "CloudWatch Logs E2E verification successful!"
        found_expected_message = any(expected_message in msg for msg in messages)
        assert found_expected_message, (
            f"Expected message '{expected_message}' not found in logs. Got messages: {messages}"
        )
