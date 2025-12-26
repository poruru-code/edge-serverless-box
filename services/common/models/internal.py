from typing import Optional, Dict, List
from dataclasses import dataclass
from pydantic import BaseModel, Field


# =============================================================================
# Auto-Scaling Data Structures
# =============================================================================


@dataclass
class WorkerInfo:
    """
    コンテナの状態管理に必要なメタデータ

    Auto-Scaling対応:
    - frozen=False に変更 (last_used_at 更新のため)
    - __eq__, __hash__ を id ベースに変更 (Set/Dict 内での同一性保持)
    """

    id: str  # コンテナID (Docker ID)
    name: str  # コンテナ名 (lambda-{function}-{suffix})
    ip_address: str  # コンテナIP (実行用)
    port: int = 8080  # サービスポート
    created_at: float = 0.0  # 作成時刻
    last_used_at: float = 0.0  # 最終使用時刻 (Auto-Scaling用)

    def __eq__(self, other):
        if isinstance(other, WorkerInfo):
            return self.id == other.id
        return False

    def __hash__(self):
        return hash(self.id)


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
