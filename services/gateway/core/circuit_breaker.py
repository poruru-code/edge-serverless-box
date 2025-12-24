import time
import logging
from typing import Callable, Any

logger = logging.getLogger("gateway.circuit_breaker")


class CircuitBreakerOpenError(Exception):
    """回路が遮断されている（OPEN）場合に投げられる例外"""

    pass


class CircuitBreaker:
    """
    サーキットブレーカーのコアロジック。
    特定の外部サービス（コンテナ）へのリクエスト失敗を監視し、
    しきい値を超えた場合に一時的にリクエストを遮断する。
    """

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 30):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failures = 0
        self.last_failure_time: float = 0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        想定される関数を実行し、必要に応じて遮断・復帰を行う。
        """
        if self.state == "OPEN":
            # タイムアウト経過を確認
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "HALF_OPEN"
                logger.info("Circuit Breaker transitions to HALF_OPEN")
            else:
                raise CircuitBreakerOpenError(f"Circuit is open (failures: {self.failures})")

        try:
            result = await func(*args, **kwargs)
            # 成功した場合
            if self.state == "HALF_OPEN":
                self.reset()
                logger.info("Circuit Breaker recovered (back to CLOSED)")
            return result
        except Exception as e:
            self.failures += 1
            self.last_failure_time = time.time()

            # HALF_OPEN での失敗は即座に OPEN に戻る
            if self.failures >= self.failure_threshold or self.state == "HALF_OPEN":
                self.state = "OPEN"
                logger.warning(f"Circuit Breaker opened due to error: {e}")

            raise e

    def reset(self):
        """状態を初期化（CLOSED）に戻す"""
        self.failures = 0
        self.state = "CLOSED"
        self.last_failure_time = 0
