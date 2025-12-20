"""
サービスパッケージ

ビジネスロジックと外部連携を提供します。
"""

from .container import ContainerManager, get_manager
from .route_matcher import load_routing_config, match_route, get_routing_config

__all__ = [
    "ContainerManager",
    "get_manager",
    "load_routing_config",
    "match_route",
    "get_routing_config",
]
