#!/bin/bash
set -e

echo "Starting Docker daemon..."
# Docker daemonをバックグラウンドで起動
dockerd-entrypoint.sh &

# Docker daemonの起動を待機
timeout=${DOCKER_DAEMON_TIMEOUT:-60}
while ! docker info > /dev/null 2>&1; do
    if [ $timeout -le 0 ]; then
        echo "ERROR: Docker daemon failed to start"
        exit 1
    fi
    echo "Waiting for Docker daemon to start... ($timeout seconds remaining)"
    sleep 1
    timeout=$((timeout - 1))
done

echo "Docker daemon started successfully"

# ESB CLI が使用する環境変数の準備
# tests/.env.test が存在しない場合はテンプレートから作成
if [ ! -f /app/tests/.env.test ]; then
    echo "Initializing environment variables from .env.example..."
    mkdir -p /app/tests
    cp /app/.env.example /app/tests/.env.test
fi

# プリビルドされたイメージ (.tar) があればロード (起動高速化のため)
if [ -d /app/build/lambda-images ]; then
    echo "Checking for pre-built images..."
    for tarfile in /app/build/lambda-images/*.tar; do
        if [ -f "$tarfile" ]; then
            echo "Loading pre-built image: $tarfile..."
            docker load -i "$tarfile"
        fi
    done
fi

# ESB CLI を使って環境を起動
# --build: 内部で設定を生成し、不足しているイメージをビルド
# --detach: サービスをバックグラウンドで起動
echo "Starting Edge Serverless Box via CLI..."
cd /app
esb up --build --detach

# ログを表示して待機（コンテナ終了を防ぐ）
echo "All services started. Tailing logs..."
docker compose logs -f
