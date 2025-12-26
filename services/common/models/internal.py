from typing import Optional, Dict, List
from dataclasses import dataclass, field
from pydantic import BaseModel, Field


# =============================================================================
# Auto-Scaling Data Structures
# =============================================================================


@dataclass(frozen=True)
class WorkerInfo:
    """
    コンテナの状態管理に必要なメタデータ

    frozen=True で hashable になり、Set で使用可能。
    """

    id: str  # コンテナID (Docker ID)
    name: str  # コンテナ名 (lambda-{function}-{suffix})
    ip_address: str  # コンテナIP (実行用)
    port: int = 8080  # サービスポート
    created_at: float = 0.0  # 作成時刻


class ContainerProvisionRequest(BaseModel):
    """Gateway -> Manager: コンテナプロビジョニングリクエスト"""

    function_name: str = Field(..., description="関数名")
    count: int = Field(default=1, ge=1, le=10, description="作成するコンテナ数")
    image: Optional[str] = Field(None, description="使用するDockerイメージ")
    env: Dict[str, str] = Field(default_factory=dict, description="注入する環境変数")
    request_id: Optional[str] = Field(None, description="トレース用リクエストID")
    dry_run: bool = Field(default=False, description="ドライラン")


class ContainerProvisionResponse(BaseModel):
    """Manager -> Gateway: プロビジョニング結果"""

    workers: List[WorkerInfo] = Field(..., description="作成されたワーカーリスト")


class HeartbeatRequest(BaseModel):
    """Gateway -> Manager: Heartbeat (Janitor用)"""

    function_name: str = Field(..., description="関数名")
    container_names: List[str] = Field(..., description="現在プールで保持しているコンテナ名リスト")


# =============================================================================
# Existing Models (Legacy - ensure API)
# =============================================================================


class ContainerEnsureRequest(BaseModel):
    """
    Gateway -> Manager: コンテナ起動リクエスト
    """

    function_name: str = Field(..., description="起動対象の関数名（コンテナ名）")
    image: Optional[str] = Field(None, description="使用するDockerイメージ")
    env: Dict[str, str] = Field(default_factory=dict, description="注入する環境変数")


class ContainerInfoResponse(BaseModel):
    """
    Manager -> Gateway: コンテナ接続情報
    """

    host: str = Field(..., description="コンテナのホスト名またはIP")
    port: int = Field(..., description="サービスポート番号")

