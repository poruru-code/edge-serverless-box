#!/bin/sh
set -e

echo "Starting Docker daemon..."
# Docker daemonをバックグラウンドで起動
dockerd-entrypoint.sh &

# Docker daemonの起動を待機
timeout=30
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

# Lambda関数イメージをロード
echo "Loading Lambda function images..."
for tarfile in /app/build/lambda-images/*.tar; do
    if [ -f "$tarfile" ]; then
        echo "Loading $tarfile..."
        docker load -i "$tarfile"
    fi
done

echo "Image loading completed"
docker images

# 内部用Composeで子コンテナ（S3互換、DB、Lambda）を起動
echo "Starting internal services (RustFS, ScyllaDB, Lambda)..."
cd /app/compose-internal
docker compose -f docker-compose.internal.yml up -d

# ヘルスチェック待機
echo "Waiting for internal services to be healthy..."
sleep 10

# 環境変数のデフォルト値設定
export SSL_CERT_PATH=${SSL_CERT_PATH:-/app/config/ssl/server.crt}
export SSL_KEY_PATH=${SSL_KEY_PATH:-/app/config/ssl/server.key}
export UVICORN_BIND_ADDR=${UVICORN_BIND_ADDR:-0.0.0.0:8000}
export UVICORN_WORKERS=${UVICORN_WORKERS:-4}
export ENABLE_SSL=${ENABLE_SSL:-false}

# SSL証明書自動生成 (SSL有効時のみ)
if [ "$ENABLE_SSL" = "true" ] && [ ! -f "$SSL_CERT_PATH" ]; then
    echo "Generating self-signed SSL certificate..."
    mkdir -p $(dirname "$SSL_CERT_PATH")
    apk add --no-cache openssl
    openssl req -x509 -newkey rsa:4096 -keyout "$SSL_KEY_PATH" -out "$SSL_CERT_PATH" -days 365 -nodes -subj "/C=JP/ST=Tokyo/L=Minato/O=Test/CN=localhost"
    chmod 644 "$SSL_CERT_PATH"
    chmod 600 "$SSL_KEY_PATH"
fi

# Uvicorn起動オプション構築
host=$(echo $UVICORN_BIND_ADDR | cut -d: -f1)
port=$(echo $UVICORN_BIND_ADDR | cut -d: -f2)
UVICORN_ARGS="--host $host --port $port --workers $UVICORN_WORKERS"

if [ "$ENABLE_SSL" = "true" ]; then
    UVICORN_ARGS="$UVICORN_ARGS --ssl-keyfile $SSL_KEY_PATH --ssl-certfile $SSL_CERT_PATH"
    echo "Starting Lambda Gateway (HTTPS) on $host:$port..."
else
    echo "Starting Lambda Gateway (HTTP) on $host:$port..."
fi

cd /app
python3 -m uvicorn gateway.app.main:app $UVICORN_ARGS
