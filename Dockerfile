# Root DinD Container
# 親コンテナ: Docker daemonを実行し、内部コンテナを管理する

FROM docker:24-dind

# 必要なツールをインストール
RUN apk add --no-cache bash curl git python3 py3-pip

WORKDIR /app

# プロジェクト全体をコピー
COPY . /app/

# 仮想環境を使わずシステム環境にインストール（DinDコンテナ専用のため）
# PEP 668 の制約を回避するために --break-system-packages を使用
RUN pip install --break-system-packages -e ".[dev]"

# エントリーポイントスクリプト
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
