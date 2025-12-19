"""
APScheduler - ライフサイクル管理とcron実行

- アイドルコンテナのクリーンアップ
- 定期実行Lambda関数のトリガー
"""
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
import docker
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Docker クライアント
docker_client = docker.from_env()

# アイドルタイムアウト（秒）
IDLE_TIMEOUT = 300  # 5分


def cleanup_idle_containers():
    """
    アイドル状態のLambdaコンテナを停止・削除
    """
    logger.info("Starting idle container cleanup...")
    
    try:
        # lambda- プレフィックスを持つコンテナを検索
        containers = docker_client.containers.list(
            filters={"name": "lambda-"}
        )
        
        current_time = time.time()
        
        for container in containers:
            # コンテナのメタデータから最終アクセス時刻を取得
            # （実際にはlambda_gatewayのcontainer_poolと連携が必要）
            
            # TODO: 共有ストレージ（Redis/DB）から最終アクセス時刻を取得
            # 現在は簡易的にコンテナの起動時刻を使用
            
            started_at = container.attrs['State']['StartedAt']
            # 簡易実装：起動から5分以上経過したコンテナを削除
            
            logger.info(f"Checking container: {container.name}")
            
            # 実際の実装では、last_accessedを確認
            # if current_time - last_accessed > IDLE_TIMEOUT:
            #     logger.info(f"Removing idle container: {container.name}")
            #     container.remove(force=True)
        
        logger.info("Cleanup completed")
        
    except Exception as e:
        logger.error(f"Cleanup failed: {str(e)}")


def scheduled_lambda_execution():
    """
    定期実行されるLambda関数のトリガー
    """
    logger.info("Executing scheduled Lambda function...")
    
    # TODO: lambda_gatewayのinvoke機能を呼び出す
    # または直接コンテナを起動してイベントを送信
    
    pass


def main():
    """
    スケジューラーのメインループ
    """
    scheduler = BlockingScheduler()
    
    # アイドルコンテナのクリーンアップ（毎分実行）
    scheduler.add_job(
        cleanup_idle_containers,
        trigger=CronTrigger(minute="*"),
        id="cleanup_idle_containers",
        name="Cleanup idle Lambda containers"
    )
    
    # 定期実行Lambda（例：毎時0分に実行）
    # scheduler.add_job(
    #     scheduled_lambda_execution,
    #     trigger=CronTrigger(hour="*", minute="0"),
    #     id="scheduled_lambda",
    #     name="Scheduled Lambda execution"
    # )
    
    logger.info("APScheduler started")
    
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("APScheduler stopped")


if __name__ == "__main__":
    main()
