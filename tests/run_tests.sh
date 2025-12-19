#!/bin/bash
set -e

# カレントディレクトリをプロジェクトルートに設定
cd "$(dirname "$0")/.."

echo "=== Sample DinD Lambda E2E Test Runner ==="

# オプション解析
BUILD=false
CLEANUP=false

for arg in "$@"; do
    case $arg in
        --build)
            BUILD=true
            shift
            ;;
        --cleanup)
            CLEANUP=true
            shift
            ;;
        --help)
            echo "Usage: ./tests/run_tests.sh [--build] [--cleanup]"
            echo "  --build   : Rebuild Gateway image before running tests"
            echo "  --cleanup : Stop containers after tests"
            exit 0
            ;;
    esac
done

# ビルド実行
if [ "$BUILD" = true ]; then
    echo "[1/4] Building Gateway image..."
    # 既存のlambdaイメージ作成もここで行うのが理想だが、今回はGatewayのみ
    docker compose build gateway
else
    echo "[1/4] Skipping build (use --build to rebuild)"
fi

# SSL証明書の準備
CERT_DIR="./certs"
CERT_FILE="$CERT_DIR/server.crt"
KEY_FILE="$CERT_DIR/server.key"

if [ ! -f "$CERT_FILE" ] || [ ! -f "$KEY_FILE" ]; then
    echo "Generating self-signed SSL certificates for testing..."
    mkdir -p "$CERT_DIR"
    # opensslがインストールされているか確認
    if command -v openssl >/dev/null 2>&1; then
        openssl req -x509 -newkey rsa:4096 -keyout "$KEY_FILE" -out "$CERT_FILE" -days 365 -nodes -subj "/C=JP/ST=Tokyo/L=Minato/O=Test/CN=localhost"
        chmod 644 "$CERT_FILE"
        chmod 600 "$KEY_FILE"
        echo "Certificates generated in $CERT_DIR"
    else
        echo "Warning: openssl not found. Skipping certificate generation."
        echo "Please install openssl or place certificates in $CERT_DIR manually."
    fi
else
    echo "Using existing SSL certificates in $CERT_DIR"
fi

# Gateway起動
echo "[2/4] Starting Gateway container..."
docker compose up -d gateway

# ヘルスチェック待機
echo "[3/4] Waiting for Gateway to be ready..."
MAX_RETRIES=60
for i in $(seq 1 $MAX_RETRIES); do
    if curl -s http://localhost:8000/health > /dev/null; then
        echo "Gateway is ready!"
        break
    fi
    echo "Waiting for Gateway... ($i/$MAX_RETRIES)"
    sleep 3
done

if [ $i -eq $MAX_RETRIES ]; then
    echo "Error: Gateway failed to start within timeout."
    docker compose logs gateway
    exit 1
fi

# テスト実行
echo "[4/4] Running E2E tests..."
# 仮想環境が有効でなければ警告
if [ -z "$VIRTUAL_ENV" ] && [ -d ".venv" ]; then
    echo "Warning: Virtual environment not active. Activating .venv..."
    source .venv/bin/activate
fi

python -m pytest tests/test_e2e.py -v

TEST_EXIT_CODE=$?

# クリーンアップ
if [ "$CLEANUP" = true ]; then
    echo "Cleaning up containers..."
    docker compose down
fi

if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo ""
    echo "🎉 Tests passed successfully!"
else
    echo ""
    echo "❌ Tests failed."
fi

exit $TEST_EXIT_CODE
