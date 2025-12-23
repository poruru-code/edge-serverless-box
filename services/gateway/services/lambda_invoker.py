"""
Lambda Invoker Service

ManagerClientを通じてコンテナを起動し、Lambda RIEに対してInvokeリクエストを送信します。
boto3.client('lambda').invoke() 互換のエンドポイント用のビジネスロジック層です。
"""

import logging
import json
import httpx
from typing import Dict
from services.gateway.services.function_registry import FunctionRegistry
from services.gateway.services.container_manager import ContainerManagerProtocol
from services.gateway.config import GatewayConfig
from services.gateway.core.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError
from services.gateway.core.exceptions import (
    FunctionNotFoundError,
    ContainerStartError,
    LambdaExecutionError,
)

logger = logging.getLogger("gateway.lambda_invoker")


class LambdaInvoker:
    def __init__(
        self,
        client: httpx.AsyncClient,
        registry: FunctionRegistry,
        container_manager: ContainerManagerProtocol,
        config: GatewayConfig,
    ):
        """
        Args:
            client: Shared httpx.AsyncClient
            registry: FunctionRegistry instance
            container_manager: ContainerManagerProtocol instance
            config: GatewayConfig instance
        """
        self.client = client
        self.registry = registry
        self.container_manager = container_manager
        self.config = config
        # 関数名ごとのブレーカーを保持
        self.breakers: Dict[str, CircuitBreaker] = {}

    async def invoke_function(
        self, function_name: str, payload: bytes, timeout: int = 300
    ) -> httpx.Response:
        """
        Lambda関数を呼び出す

        Args:
            function_name: 呼び出す関数名
            payload: リクエストボディ
            timeout: リクエストタイムアウト

        Returns:
            Lambda RIEからのレスポンス

        Raises:
            ContainerStartError: コンテナ起動失敗
            LambdaExecutionError: Lambda実行失敗
        """
        # config check
        func_config = self.registry.get_function_config(function_name)
        if func_config is None:
            raise FunctionNotFoundError(function_name)

        # Prepare env
        env = func_config.get("environment", {}).copy()

        # Resolve Gateway URL using injected config
        gateway_internal_url = self.config.GATEWAY_INTERNAL_URL
        env["GATEWAY_INTERNAL_URL"] = gateway_internal_url

        # Ensure container (via Manager)
        try:
            host = await self.container_manager.get_lambda_host(
                function_name=function_name,
                image=func_config.get("image"),
                env=env,
            )
        except Exception as e:
            raise ContainerStartError(function_name, e) from e

        # POST to Lambda RIE
        rie_url = (
            f"http://{host}:{self.config.LAMBDA_PORT}/2015-03-31/functions/function/invocations"
        )
        logger.info(f"Invoking {function_name} at {rie_url}")

        # ブレーカー取得または作成
        if function_name not in self.breakers:
            self.breakers[function_name] = CircuitBreaker(
                failure_threshold=self.config.CIRCUIT_BREAKER_THRESHOLD,
                recovery_timeout=self.config.CIRCUIT_BREAKER_RECOVERY_TIMEOUT,
            )

        breaker = self.breakers[function_name]

        try:
            # ブレーカー経由で実行
            async def do_post():
                response = await self.client.post(
                    rie_url,
                    content=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=timeout,
                )

                # 判定: 回路を遮断すべき「失敗」かどうか
                is_failure = False

                # 1. HTTP 5xx エラー
                if response.status_code >= 500:
                    is_failure = True
                # 2. AWS Lambda 実行エラーヘッダー (X-Amz-Function-Error: Unhandled 等)
                elif response.headers.get("X-Amz-Function-Error"):
                    is_failure = True
                # 3. HTTP 200 だが、ボディーにエラー情報が含まれる場合 (RIE の挙動)
                elif response.status_code == 200:
                    try:
                        # ボディーが短い場合にのみ JSON パースを試みる (パフォーマンス考慮)
                        # RIE のエラー応答は通常数 KB 以下
                        if len(response.content) < 1024 * 10:
                            data = response.json()
                            if isinstance(data, dict) and (
                                "errorType" in data or "errorMessage" in data
                            ):
                                is_failure = True
                    except (ValueError, json.JSONDecodeError):
                        pass

                if is_failure:
                    # 5xx または論理エラーの場合、CircuitBreakerが「失敗」と認識できるよう例外を投げる
                    if response.status_code >= 400:
                        response.raise_for_status()
                    else:
                        # 200だが内容がエラーの場合、カスタム例外を投げる
                        # httpx.HTTPStatusErrorを模倣してCircuitBreakerに渡す
                        raise httpx.HTTPStatusError(
                            f"Lambda Logical Error detected in 200 response: {response.text[:100]}",
                            request=response.request,
                            response=response,
                        )

                return response

            return await breaker.call(do_post)

        except CircuitBreakerOpenError as e:
            logger.error(f"Circuit breaker open for {function_name}: {e}")
            raise LambdaExecutionError(function_name, "Circuit Breaker Open") from e
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            logger.error(
                f"Lambda invocation failed for function '{function_name}'",
                extra={
                    "function_name": function_name,
                    "target_url": rie_url,
                    "error_type": type(e).__name__,
                    "error_detail": str(e),
                },
            )
            # すでに response.raise_for_status() などで例外になっている場合もここに来る
            raise LambdaExecutionError(function_name, e) from e


# Backward compatibility or helper if needed? No, we are fully refactoring to DI.
