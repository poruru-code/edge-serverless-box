from typing import Any, Protocol
from services.common.models.internal import WorkerInfo
from .container_manager import HttpContainerManager
from ..config import GatewayConfig

class InvocationBackend(Protocol):
    """
    実行バックエンドの抽象インターフェース
    PoolManager (Python) や将来の AgentClient (Go/gRPC) がこれを実装する
    """
    async def acquire_worker(self, function_name: str) -> WorkerInfo:
        """関数実行用のワーカーを取得"""
        ...

    async def release_worker(self, function_name: str, worker: WorkerInfo) -> None:
        """ワーカーを返却"""
        ...

    async def evict_worker(self, function_name: str, worker: WorkerInfo) -> None:
        """ワーカーを破棄"""
        ...

class LegacyBackendAdapter:
    """
    既存の HttpContainerManager を InvocationBackend インターフェースに適合させるアダプター。
    Step 1 で LambdaInvoker を Strategy パターンに移行するために使用。
    """
    def __init__(self, manager: HttpContainerManager, config: GatewayConfig, registry: Any):
        self.manager = manager
        self.config = config
        self.registry = registry

    async def acquire_worker(self, function_name: str) -> WorkerInfo:
        # Legacy Manager は IP (str) しか返さないので、WorkerInfo に偽装する
        func_config = self.registry.get_function_config(function_name)
        if func_config is None:
             raise ValueError(f"Function not found: {function_name}")
             
        env = func_config.get("environment", {}).copy()
        env["GATEWAY_INTERNAL_URL"] = self.config.GATEWAY_INTERNAL_URL
        env.setdefault("_HANDLER", "lambda_function.lambda_handler")
        # Trace ID は LambdaInvoker 側で埋め込むか、ここでやるか。
        # 現状の LambdaInvoker は get_lambda_host を呼ぶ前に env を作っている。
        
        host = await self.manager.get_lambda_host(
            function_name=function_name,
            image=func_config.get("image"),
            env=env,
        )
        
        # WorkerInfo に偽装
        return WorkerInfo(
            id=f"legacy-{function_name}",
            name=f"legacy-{function_name}",
            ip_address=host,
            port=self.config.LAMBDA_PORT
        )

    async def release_worker(self, function_name: str, worker: WorkerInfo) -> None:
        # Legacy モードには「返却」の概念がないため何もしない
        pass

    async def evict_worker(self, function_name: str, worker: WorkerInfo) -> None:
        # Legacy モードには「除外（再起動）」の概念がないため何もしない
        # (HttpContainerManager 内で失敗時にキャッシュを消す仕組みはあるが、
        #  このアダプター経由では現状維持)
        pass
