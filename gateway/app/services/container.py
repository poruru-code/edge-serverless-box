"""
ContainerManager - Lambda コンテナのライフサイクル管理

オンデマンドでコンテナを起動し、アイドル状態のコンテナを停止する。
"""

import docker
import docker.errors
import time
import logging
import os
from typing import Dict, Optional

import requests

logger = logging.getLogger("gateway.container_manager")


class ContainerManager:
    """
    Lambdaコンテナのライフサイクルを管理するクラス

    - ensure_container_running(): コンテナが起動していなければ起動
    - stop_idle_containers(): アイドル状態のコンテナを停止
    """

    def __init__(self, network: Optional[str] = None):
        """
        Args:
            network: コンテナを接続するDockerネットワーク名
                     省略時は環境変数 DOCKER_NETWORK から取得
        """
        self.client = docker.from_env()
        self.network = network or os.environ.get("DOCKER_NETWORK", "bridge")
        self.last_accessed: Dict[str, float] = {}

    def ensure_container_running(
        self, name: str, image: Optional[str] = None, env: Optional[Dict[str, str]] = None
    ) -> str:
        """
        コンテナが起動していなければ起動し、ホスト名を返す

        Args:
            name: コンテナ名（Dockerネットワーク内のホスト名としても使用）
            image: Dockerイメージ名（省略時は name:latest）
            env: 環境変数の辞書

        Returns:
            コンテナのホスト名（= name）
        """
        # 最終アクセス時刻を更新
        self.last_accessed[name] = time.time()

        # imageのデフォルト値
        if image is None:
            image = f"{name}:latest"

        try:
            container = self.client.containers.get(name)

            if container.status == "running":
                logger.debug(f"Container {name} is already running")
                return name

            elif container.status == "exited":
                logger.info(f"Warm-up: Restarting container {name}...")
                container.start()
                self._wait_for_readiness(name)
                return name

            else:
                # created, paused, etc. - 停止して再作成
                logger.info(f"Container {name} in state {container.status}, removing...")
                container.remove(force=True)
                raise docker.errors.NotFound(f"Removed {name}")

        except docker.errors.NotFound:
            logger.info(f"Cold Start: Creating and starting container {name}...")
            self.client.containers.run(
                image,
                name=name,
                detach=True,
                environment=env or {},
                network=self.network,
                restart_policy={"Name": "no"},
            )
            self._wait_for_readiness(name)
            return name

    def _wait_for_readiness(self, host: str, timeout: int = 10) -> None:
        """
        Lambda RIEが応答可能になるまで待機

        Args:
            host: コンテナのホスト名
            timeout: 待機タイムアウト（秒）
        """
        url = f"http://{host}:8080/2015-03-31/functions/function/invocations"
        start = time.time()

        while time.time() - start < timeout:
            try:
                # RIEにPOSTリクエストを送信してヘルスチェック
                # (空のペイロードでもレスポンスが返れば起動完了)
                requests.post(url, json={}, timeout=1)
                logger.debug(f"Container {host} is ready")
                return
            except requests.exceptions.ConnectionError:
                time.sleep(0.5)
            except requests.exceptions.Timeout:
                time.sleep(0.5)

        logger.warning(f"Container {host} did not become ready in {timeout}s")

    def stop_idle_containers(self, timeout_seconds: int = 900) -> None:
        """
        タイムアウトしたコンテナを停止

        Args:
            timeout_seconds: アイドルタイムアウト（秒）。デフォルト15分
        """
        now = time.time()
        to_remove = []

        for name, last_access in self.last_accessed.items():
            if now - last_access > timeout_seconds:
                try:
                    logger.info(f"Scale-down: Stopping idle container {name}")
                    container = self.client.containers.get(name)
                    if container.status == "running":
                        container.stop()
                    to_remove.append(name)
                except docker.errors.NotFound:
                    # コンテナが既に削除されている
                    to_remove.append(name)
                except Exception as e:
                    logger.error(f"Failed to stop {name}: {e}")

        for name in to_remove:
            del self.last_accessed[name]


# シングルトンインスタンス（遅延初期化）
_manager_instance: Optional[ContainerManager] = None


def get_manager() -> ContainerManager:
    """
    ContainerManagerのシングルトンインスタンスを取得

    遅延初期化により、インポート時にDockerに接続しない
    """
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = ContainerManager()
    return _manager_instance
