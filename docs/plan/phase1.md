### 📋 Phase 1 実装計画概要

1. **Docker操作の分離と保護**: 専用スレッドプールの導入とタイムアウト設定。
2. **設定の外部化**: スレッドプール設定のConfig追加。
3. **可観測性の向上**: `proxy.py` と `lambda_invoker.py` でのログ欠落の修正。

---

### Step 1: Manager設定の拡張

まず、Docker操作用のスレッドプールサイズを設定できるように `ManagerConfig` を拡張します。

**対象ファイル:** `services/manager/config.py`

**変更内容:**
`DOCKER_MAX_WORKERS` と `DOCKER_CLIENT_TIMEOUT` を追加します。

```python
class ManagerConfig(BaseAppConfig):
    # ... (既存のフィールド) ...

    # 追加: Docker操作の安全性確保用設定
    DOCKER_MAX_WORKERS: int = Field(
        default=20, 
        description="Docker操作用スレッドプールの最大ワーカー数"
    )
    DOCKER_CLIENT_TIMEOUT: int = Field(
        default=60, 
        description="Dockerクライアントの通信タイムアウト(秒)"
    )

```

---

### Step 2: DockerAdaptor の堅牢化 (最重要)

デフォルトのExecutor（CPU数ベース）への依存を排除し、Docker専用のプールを作成します。また、クライアント生成時にタイムアウトを明示します。

**対象ファイル:** `services/manager/docker_adaptor.py`

**実装プラン:**

1. `concurrent.futures.ThreadPoolExecutor` をインポート。
2. `__init__` で専用の `executor` を作成。
3. `docker.from_env()` にタイムアウトを設定。
4. 全ての `loop.run_in_executor(None, ...)` を `loop.run_in_executor(self.executor, ...)` に変更。

**修正後のコードイメージ:**

```python
import asyncio
import docker
import logging
from typing import Any, List
from concurrent.futures import ThreadPoolExecutor # 追加
from .config import config # 追加

logger = logging.getLogger("manager.docker_adaptor")

class DockerAdaptor:
    def __init__(self):
        # タイムアウトを設定して無限待ちを防ぐ
        self._client = docker.from_env(timeout=config.DOCKER_CLIENT_TIMEOUT)
        
        # Docker操作専用のスレッドプール
        # これにより、Dockerが詰まっても他の非同期処理(HTTPなど)は生き残る
        self.executor = ThreadPoolExecutor(
            max_workers=config.DOCKER_MAX_WORKERS,
            thread_name_prefix="docker_worker"
        )

    async def get_container(self, name: str) -> Any:
        loop = asyncio.get_running_loop()
        # None ではなく self.executor を指定
        return await loop.run_in_executor(
            self.executor, 
            self._client.containers.get, 
            name
        )

    # ... 他のメソッドも同様に self.executor を使用 ...

    # アプリケーション終了時にプールを閉じるメソッドを追加推奨
    def shutdown(self):
        self.executor.shutdown(wait=True)

```

---

### Step 3: Gatewayのエラーハンドリングとログ改善

エラーを握りつぶしている箇所と、通信エラー時に情報が足りない箇所を修正します。

#### 3-1. JSONパースエラーの可視化

**対象ファイル:** `services/gateway/core/proxy.py`

**変更内容:**
`except json.JSONDecodeError: pass` を削除し、警告ログを出力するように変更します。

```python
# services/gateway/core/proxy.py の parse_lambda_response 内

# ...
            # bodyがJSON文字列の場合はパース
            if isinstance(response_body, str):
                try:
                    response_body = json.loads(response_body)
                except json.JSONDecodeError:
                    # 修正: エラーを握りつぶさず、構造化ログに残す
                    # コンテンツが大きすぎる可能性を考慮し、先頭部分のみログに出す等の配慮があると良い
                    from logging import getLogger
                    logger = getLogger("gateway.proxy")
                    logger.warning(
                        "Failed to parse Lambda response body as JSON. Returning as string.",
                        extra={
                            "snippet": response_body[:200] if response_body else "",
                            "status_code": status_code
                        }
                    )
                    # パース失敗時は元の文字列のまま扱う（既存動作の維持）
                    pass
# ...

```

#### 3-2. Lambda呼び出し失敗時のログ強化

**対象ファイル:** `services/gateway/services/lambda_invoker.py`

**変更内容:**
例外発生時に、どの関数へのリクエストで、どのURLに対して失敗したかをログ出力します。

```python
# services/gateway/services/lambda_invoker.py の invoke_function 内

        # ...
        try:
            response = await self.client.post(
                rie_url,
                content=payload,
                headers={"Content-Type": "application/json"},
                timeout=timeout,
            )
            return response
        except httpx.RequestError as e:
            # 修正: エラーの詳細をログに出力してから wrap する
            logger.error(
                f"Lambda invocation failed for function '{function_name}'",
                extra={
                    "function_name": function_name,
                    "target_url": rie_url,
                    "error_type": type(e).__name__,
                    "error_detail": str(e)
                }
            )
            raise LambdaExecutionError(function_name, e) from e

```

---

### ✅ 検証計画 (Verification)

修正適用後、以下の手順で動作を確認してください。

1. **Dockerプール分離の確認**:
* 意図的に重いDocker操作（例: 大量のコンテナリスト取得やイメージPull）を連続して走らせる。
* その最中でも、`manager` サービスのヘルスチェック用API（もしあれば）や、単純なログ出力がブロックされずに機能することを確認する。


2. **スレッド名の確認**:
* ログに `threadName` を含めるように一時的に設定し、Docker操作時のログが `docker_worker-X` というスレッド名から出ているか確認する。


3. **ログ出力の確認**:
* Lambda関数から「壊れたJSON」を返すようにモックし、Gatewayのログに `WARNING` レベルで `Failed to parse Lambda response body` が出るか確認する。
* 存在しないコンテナIPに対してInvokeを行い、`Lambda invocation failed` の `ERROR` ログが出るか確認する。



この計画に沿って修正を行うことで、本番運用に耐えうる最低限の安全性を確保できます。