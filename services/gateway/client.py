from typing import Optional, Dict
import httpx
import os
import logging
from .core.exceptions import (
    FunctionNotFoundError,
    ManagerError,
    ManagerTimeoutError,
    ManagerUnreachableError,
)
from .services.container_cache import ContainerHostCache
from services.common.core.request_context import get_request_id

logger = logging.getLogger("gateway.client")

MANAGER_URL = os.getenv("MANAGER_URL", "http://manager:8081")


class ManagerClient:
    def __init__(self, http_client: httpx.AsyncClient, cache: Optional[ContainerHostCache] = None):
        self.client = http_client
        self.cache = cache or ContainerHostCache()

    def invalidate_cache(self, function_name: str) -> None:
        """
        Invalidate cache for a specific function.

        Call this when Lambda connection fails to ensure next request
        re-fetches container info from Manager.
        """
        self.cache.invalidate(function_name)
        logger.debug(f"Cache invalidated for {function_name}")

    async def ensure_container(
        self, function_name: str, image: Optional[str] = None, env: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Calls Manager Service to ensure container is running and get its host/IP.

        Uses TTL-based cache to avoid redundant Manager calls on warm starts.

        Raises:
            FunctionNotFoundError: 関数/イメージが存在しない (404)
            ManagerError: Docker API エラーなど (400, 409など)
            ManagerTimeoutError: タイムアウト (408)
            ManagerUnreachableError: Manager への接続失敗
        """
        # 1. キャッシュチェック
        cached_host = self.cache.get(function_name)
        if cached_host:
            logger.debug(f"Cache hit for {function_name}: {cached_host}")
            return cached_host

        # 2. キャッシュミス → Manager に問い合わせ
        url = f"{MANAGER_URL}/containers/ensure"
        payload = {"function_name": function_name, "image": image, "env": env or {}}

        # X-Request-Id ヘッダーを伝播
        headers = {}
        request_id = get_request_id()
        if request_id:
            headers["X-Request-Id"] = request_id

        try:
            resp = await self.client.post(
                url,
                json=payload,
                headers=headers,
                timeout=30.0,
            )
            resp.raise_for_status()
            data = resp.json()
            host = data["host"]

            # 3. 成功時にキャッシュ登録
            self.cache.set(function_name, host)
            logger.debug(f"Cached {function_name}: {host}")

            return host

        except httpx.TimeoutException as e:
            logger.error(f"Manager request timed out: {e}")
            raise ManagerTimeoutError(f"Container startup timeout for {function_name}") from e

        except httpx.RequestError as e:
            # 接続失敗 (ネットワークエラー、DNS解決失敗など)
            logger.error(f"Failed to connect to Manager: {e}")
            raise ManagerUnreachableError(e) from e

        except httpx.HTTPStatusError as e:
            # Manager からの HTTP エラーレスポンス
            status = e.response.status_code
            detail = e.response.text

            logger.error(f"Manager returned {status}: {detail}")

            # エラーコードマッピング
            if status == 404:
                raise FunctionNotFoundError(function_name) from e
            elif status in [400, 408, 409]:
                # 400: Docker API エラー
                # 408: タイムアウト
                # 409: コンテナ競合
                raise ManagerError(status, detail) from e
            else:
                # その他のエラー
                raise ManagerError(status, detail) from e


# Backward compatibility (optional, or just remove)
async def get_lambda_host(
    function_name: str, image: Optional[str] = None, env: Optional[Dict[str, str]] = None
) -> str:
    """
    Deprecated: Use ManagerClient instead.
    Temporarily kept for un-refactored code in main.py if any.
    But we will refactor main.py to use ManagerClient.
    """
    async with httpx.AsyncClient() as client:
        manager = ManagerClient(client)
        return await manager.ensure_container(function_name, image, env)
