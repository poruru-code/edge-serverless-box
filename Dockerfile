# Root DinD Container
# 親コンテナ: Docker daemonを実行し、内部コンテナを管理する

FROM docker:24-dind

# 必要なツールをインストール
RUN apk add --no-cache bash curl git docker-cli-compose

WORKDIR /app

# Lambda関数のイメージ（.tar）を事前にコピー（ビルドプロセスの簡素化のため）
# 注: 本番ではボリュームマウントやレジストリ経由が望ましいが、現状の構成を踏襲
COPY build/lambda-images/*.tar /app/build/lambda-images/

# 内部用Composeファイルをコピー
COPY docker-compose.yml /app/docker-compose.yml

# Gatewayアプリのビルドコンテキスト用（内部でビルドする場合）
# 今回はGatewayもイメージとして扱うため、事前にビルド済みのものを使うか、
# ここでビルドコンテキストを用意する。
# ユーザー提案では「image: my-gateway-api:latest」となっているため、
# 親コンテナ起動時に内部でビルドするか、loadする必要がある。
# 簡略化のため、Gatewayのコードもコピーしておく
COPY gateway/ /app/gateway/
COPY lambda_functions/ /app/lambda_functions/
COPY pyproject.toml /app/

# エントリーポイントスクリプト
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
