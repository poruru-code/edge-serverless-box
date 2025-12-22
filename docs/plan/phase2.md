提案された「Phase 2: 設計の疎結合化 (Should)」について、詳細な実装計画を作成しました。
このフェーズの目的は、**「テスト容易性（Testability）の向上」**と**「将来的な仕様変更（API Gateway V2対応など）への柔軟性確保」**です。

具体的には、グローバル変数への依存を排除し、依存性の注入（DI）とStrategyパターンを適用します。

---

### 📋 Phase 2 実装計画概要

1. **Manager通信の抽象化**: 関数呼び出しではなく、インターフェース（Protocol）を持つクラスへ移行。
2. **LambdaInvokerのDI化**: グローバル `config` と `get_lambda_host` への依存を排除。
3. **イベント構築のStrategy化**: 巨大な `build_event` 関数をクラス設計へリファクタリング。
4. **Composition Rootの整備**: `main.py` で依存関係を組み立てる。

---

### Step 1: Container Manager Client の抽象化

現在、`lambda_invoker.py` は `get_lambda_host` という関数を直接インポートしていますが、これをクラス化し、Protocol（インターフェース）を定義します。これにより、テスト時にManagerサーバーなしでモックが可能になります。

**新規作成:** `services/gateway/services/container_manager.py`

```python
from typing import Protocol, Dict, Optional
import httpx
from ..config import GatewayConfig

class ContainerManagerProtocol(Protocol):
    async def get_lambda_host(self, function_name: str, image: str, env: Dict[str, str]) -> str:
        ...

class HttpContainerManager:
    """ManagerサービスとHTTP通信を行う実装"""
    def __init__(self, config: GatewayConfig, client: httpx.AsyncClient):
        self.config = config
        self.client = client

    async def get_lambda_host(self, function_name: str, image: str, env: Dict[str, str]) -> str:
        # 既存の get_lambda_host ロジックをここに移植
        # self.client.post(...) を使用してManagerへリクエスト
        pass

```

---

### Step 2: LambdaInvoker への依存性注入 (DI)

`LambdaInvoker` がグローバルな `config` や関数に依存しないよう、コンストラクタで全て受け取るように変更します。

**対象:** `services/gateway/services/lambda_invoker.py`

**変更計画:**

1. `config` (GatewayConfig) と `container_manager` (ContainerManagerProtocol) を `__init__` で受け取る。
2. `get_lambda_host` の直接呼び出しを `self.container_manager.get_lambda_host` に置換。
3. `env["GATEWAY_INTERNAL_URL"]` の取得元を `self.config` に変更。

```python
# 変更後のイメージ
class LambdaInvoker:
    def __init__(
        self, 
        client: httpx.AsyncClient, 
        registry: FunctionRegistry,
        container_manager: ContainerManagerProtocol, # 追加
        config: GatewayConfig # 追加
    ):
        self.client = client
        self.registry = registry
        self.container_manager = container_manager
        self.config = config

    async def invoke_function(self, function_name: str, payload: bytes, timeout: int = 300) -> httpx.Response:
        # ... (省略) ...
        
        # グローバル config ではなく self.config を使用
        gateway_internal_url = self.config.GATEWAY_INTERNAL_URL
        
        # 関数呼び出しではなくメソッド呼び出し
        try:
            host = await self.container_manager.get_lambda_host(
                function_name=function_name,
                image=func_config.get("image"),
                env=env,
            )
        except Exception as e:
            # ...

```

---

### Step 3: イベント構築ロジックの Strategy パターン化

`proxy.py` にある `build_event` は API Gateway V1 (REST API) 形式に固定されています。これを V2 (HTTP API) にも対応できるよう、クラスベースに分割します。

**対象:** `services/gateway/core/proxy.py` (または新規 `event_builder.py`)

**実装プラン:**

1. 基底クラス `BaseEventBuilder` を定義。
2. `V1ProxyEventBuilder` クラスを作成し、現在の `build_event` のロジックを `build` メソッドに移動。
3. `proxy.py` はビルダーを使用する形に変更。

```python
from abc import ABC, abstractmethod
from fastapi import Request

class EventBuilder(ABC):
    @abstractmethod
    async def build(self, request: Request, body: bytes, **kwargs) -> dict:
        pass

class V1ProxyEventBuilder(EventBuilder):
    """API Gateway V1 (REST API) 互換のイベントビルダー"""
    def __init__(self, include_multi_value_headers: bool = True):
        self.include_multi_value_headers = include_multi_value_headers

    async def build(self, request: Request, body: bytes, **kwargs) -> dict:
        # ここに現在の build_event のロジックを移動
        # self.include_multi_value_headers などの設定を活用可能
        pass

```

---

### Step 4: Main Entrypoint での結合 (Wiring)

最後に、`main.py` または `deps.py` でこれらのクラスをインスタンス化し、依存関係を解決します。FastAPIの `lifespan` または `Dependency` を活用します。

**対象:** `services/gateway/main.py` および `api/deps.py`

**変更計画:**

1. `lifespan` (旧 `on_event`) で、`GatewayConfig`, `HttpContainerManager`, `LambdaInvoker` を初期化し、`app.state` に保持する。
2. APIエンドポイントでは `Request.app.state` から完成済みの `LambdaInvoker` を取得して使用する。

```python
# services/gateway/main.py の lifespan イメージ

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Config ロード
    config = GatewayConfig()
    
    # 2. 共通 HTTP Client 作成
    http_client = httpx.AsyncClient()
    
    # 3. 依存オブジェクトの作成 (Wiring)
    container_manager = HttpContainerManager(config, http_client)
    registry = FunctionRegistry() # 必要ならロード処理
    
    invoker = LambdaInvoker(
        client=http_client,
        registry=registry,
        container_manager=container_manager,
        config=config
    )
    
    # 4. State に保存
    app.state.invoker = invoker
    app.state.event_builder = V1ProxyEventBuilder()
    
    yield
    
    await http_client.aclose()

```

### ✅ 検証計画 (Verification)

リファクタリングの影響範囲が広いため、以下の順序で動作確認を行います。

1. **単体テストの修正**:
* `LambdaInvoker` のテストで、`ContainerManagerProtocol` のモックを作成し、実際にHTTP通信を行わずに `invoke_function` のロジックだけをテストできることを確認する。
* グローバル `config` を書き換えるテストコード（`monkeypatch`等）を廃止し、コンストラクタにConfigオブジェクトを渡すテストに変更する。


2. **E2Eテストの実行**:
* 既存の `tests/e2e` を実行し、リファクタリング前後で挙動が変わっていない（回帰していない）ことを確認する。特にイベント構造（ヘッダーやボディの形式）が維持されているか確認する。



このフェーズを完了することで、コードの見通しが良くなり、後の機能追加（新しいAWS機能のサポートなど）が格段にやりやすくなります。