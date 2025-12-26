"""
Tests for Provisioning Cleanup logic in ContainerManager
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import docker.errors

@pytest.mark.asyncio
async def test_provision_cleanup_on_failure():
    """
    provision_containers でエラーが発生した際、
    それまでに作成されたコンテナがクリーンアップされることを確認
    """
    from services.manager.service import ContainerManager
    from services.common.models.internal import WorkerInfo

    # Mock DockerAdaptor
    manager = ContainerManager(network="test-net")
    manager.docker = AsyncMock()
    
    # 1つ目は成功、2つ目でエラーを出すように設定
    success_container = MagicMock()
    success_container.id = "id-1"
    success_container.attrs = {"NetworkSettings": {"Networks": {"test-net": {"IPAddress": "10.0.0.1"}}}}
    
    manager.docker.run_container.side_effect = [
        success_container,
        Exception("Simulated Docker failure")
    ]
    
    # readiness check は成功させる（1つ目用）
    with patch.object(manager, "_wait_for_readiness", AsyncMock()):
        with pytest.raises(Exception) as excinfo:
            await manager.provision_containers("hello", count=2)
            
    assert "Simulated Docker failure" in str(excinfo.value)
    
    # 1つ目のコンテナ (lambda-hello-xxxx) が削除されているか
    # remove_container_by_name が呼ばれたことを確認
    assert manager.docker.remove_container_by_name.call_count == 1
    # 呼ばれた名前を取得
    cleanup_name = manager.docker.remove_container_by_name.call_args[0][0]
    assert cleanup_name.startswith("lambda-hello-")
    
    # last_accessed からも消えているか
    assert cleanup_name not in manager.last_accessed
