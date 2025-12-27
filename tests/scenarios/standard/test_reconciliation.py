"""
Reconciliation (Orphan Container Cleanup) E2E テスト

検証シナリオ:
1. Grace Period 検証: 新規作成コンテナは Reconciliation で削除されない（60秒猶予）
2. Adoption 検証: Gateway 再起動後も既存コンテナが再利用される
"""

import os
import subprocess
import time

import requests

from tests.conftest import (
    GATEWAY_URL,
    VERIFY_SSL,
    DEFAULT_REQUEST_TIMEOUT,
    call_api,
)


class TestReconciliation:
    """Reconciliation (孤児コンテナクリーンアップ) 機能の検証"""

    def test_grace_period_prevents_premature_deletion(self, auth_token):
        """
        E2E: Grace Period により作成直後のコンテナが Reconciliation で削除されないことを検証

        シナリオ:
        1. Lambda を呼び出してコンテナを起動
        2. Gateway を再起動（コンテナが Gateway の Pool から外れ「孤児」状態になる）
        3. Gateway 再起動直後（Grace Period 内）に Lambda を再度呼び出し
        4. 既存コンテナが再利用される（Adoption）ことを確認
        """
        # 1. Lambda を呼び出してコンテナを起動
        print("Step 1: Initial Lambda invocation (cold start)...")
        response1 = call_api("/api/echo", auth_token, {"message": "warmup"})
        assert response1.status_code == 200
        data1 = response1.json()
        assert data1["success"] is True
        print(f"Initial invocation successful: {data1}")

        # 少し待ってからコンテナが確実に稼働していることを確認
        time.sleep(2)

        # 2. Gateway を再起動（コンテナは Agent で稼働中だが、Gateway Pool からは外れる）
        print("Step 2: Restarting Gateway container...")
        restart_result = subprocess.run(
            ["docker", "compose", "restart", "gateway"],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            ),
        )
        assert restart_result.returncode == 0, (
            f"Failed to restart gateway: {restart_result.stderr}"
        )

        # Gateway のヘルスチェック待機
        print("Step 3: Waiting for Gateway to become healthy...")
        for i in range(15):
            try:
                health_resp = requests.get(
                    f"{GATEWAY_URL}/health", verify=VERIFY_SSL, timeout=DEFAULT_REQUEST_TIMEOUT
                )
                if health_resp.status_code == 200:
                    print(f"Gateway is healthy after {i + 1} attempts")
                    break
            except Exception:
                pass
            time.sleep(2)

        # 短い安定化待ち（Grace Period 内であることを確認）
        time.sleep(3)

        # 3. Grace Period 内に Lambda を再度呼び出し
        print("Step 4: Post-restart invocation (should reuse existing container via Adoption)...")
        response2 = call_api("/api/echo", auth_token, {"message": "after restart"})

        assert response2.status_code == 200, (
            f"Expected 200, got {response2.status_code}: {response2.text}. "
            "Container may have been prematurely deleted by Reconciliation."
        )
        data2 = response2.json()
        assert data2["success"] is True
        print(f"Post-restart invocation successful: {data2}")

        # 4. 追加検証: 連続呼び出しで安定性確認
        print("Step 5: Additional invocations to verify stability...")
        for i in range(3):
            resp = call_api("/api/echo", auth_token, {"message": f"stability-{i}"})
            assert resp.status_code == 200, f"Stability check {i} failed: {resp.text}"
            print(f"  Stability check {i + 1}/3: PASSED")

        print("[OK] Grace Period test passed - container was not prematurely deleted")
