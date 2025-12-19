# 親コンテナ: Docker in Docker (DinD) 環境
FROM docker:24-dind

# Python環境のインストール
RUN apk add --no-cache python3 py3-pip curl

# uvのインストール
RUN pip3 install --no-cache-dir --break-system-packages uv

# Docker Compose v2のインストール（docker-cli-composeを使用）
RUN apk add --no-cache docker-cli-compose

# 作業ディレクトリ
WORKDIR /app

# Lambda関数のイメージ（.tar）を事前にコピー
# ビルド時に build/lambda_functions/ 以下のイメージをビルドして配置する
COPY build/lambda-images/*.tar /app/build/lambda-images/

# アプリケーションコードをコピー
COPY gateway/app/ /app/gateway/app/
COPY pyproject.toml /app/

# 内部用Composeファイルをコピー
COPY compose-internal/ /app/compose-internal/

# 設定ファイルをコピー
COPY gateway/config/ /app/config/

# Python依存関係をpip3でインストール
RUN pip3 install --no-cache-dir --break-system-packages -e .

# データ永続化用ディレクトリを作成
RUN mkdir -p /data/s3_storage /data/scylladb /logs

# エントリーポイントスクリプト
COPY gateway/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
