# DinD Lambda - Edge Serverless Simulator

完全内包型のDocker in Docker (DinD) 環境を使用した、AWS API Gateway互換のエッジサーバーレスシミュレーターです。
外部ネットワーク接続なしで、Lambda関数、S3互換ストレージ(RustFS)、DynamoDB互換DB(ScyllaDB)のローカル実行環境を提供します。

## 🚀 クイックスタート

開発環境には既に必要なツールが含まれています。以下のコマンドでビルドからテストまで一括実行できます。

```bash
# Gatewayのビルド、起動、E2Eテストを実行
./tests/run_tests.sh --build --cleanup
```

## 🏗 アーキテクチャ

FastAPI Gatewayが親コンテナとして動作し、Dockerソケットを通じて子コンテナ（Lambda RIE、ストレージ、DB）のライフサイクルを管理します。

```mermaid
graph TD
    User[HTTP Client] -->|Request| GW[FastAPI Gateway]
    
    subgraph "Parent Container (DinD)"
        GW -->|Auth check| GW
        GW -->|Launch/Manage| Docker[Docker Engine]
        
        Docker -->|Run| Lambda[Lambda RIE Container]
        Docker -->|Run| S3[RustFS (S3 Compatible)]
        Docker -->|Run| DB[ScyllaDB (DynamoDB Compatible)]
        
        GW -->|Proxy Request| Lambda
        Lambda -->|Access data| S3
        Lambda -->|Access data| DB
    end
```

## 🛠 開発環境セットアップ

### 前提条件
- Docker
- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (推奨パッケージマネージャー)

### セットアップ手順

1. 依存関係のインストール
   ```bash
   uv venv
   source .venv/bin/activate
   uv pip install -e .[dev]
   ```

2. Gatewayの手動起動
   ```bash
   docker compose up -d gateway
   ```
   Gatewayは `http://localhost:8000` で起動します。

## 📁 ディレクトリ構造

```text
/
├── gateway/                # API Gateway アプリケーション (FastAPI)
│   ├── app/                # アプリケーションコード
│   ├── Dockerfile          # 親コンテナ定義 (DinD環境含む)
│   └── entrypoint.sh       # 起動スクリプト
│
├── lambda_functions/       # Lambda関数ソースコード
│
├── compose-internal/       # 内部サービス定義 (RustFS, ScyllaDB等)
│   └── docker-compose.internal.yml
│
├── tests/                  # テストコード
│   ├── test_e2e.py         # 統合テスト
│   └── run_tests.sh        # テストランナー
│
├── docs/                   # ドキュメント
└── docker-compose.yml      # 開発用Gateway起動構成
```

## 🧪 テスト

### E2Eテスト (HTTP → Gateway → Lambda)
GatewayをDockerコンテナとして起動し、外部からHTTPリクエストを送って各種動作（ルーティング、認証、Lambda実行）を検証します。

```bash
# テストランナーを使用 (推奨)
./tests/run_tests.sh --build

# 手動実行
python -m pytest tests/test_e2e.py -v
```

## 💡 API使用例

### 認証 (IDトークン取得)
```bash
curl -X POST http://localhost:8000/user/auth/v1 \
  -H "x-api-key: dev-api-key-change-in-production" \
  -H "Content-Type: application/json" \
  -d '{
    "AuthParameters": {
      "USERNAME": "testuser",
      "PASSWORD": "testpass"
    }
  }'
```

### Lambda呼び出し
```bash
curl -X POST http://localhost:8000/api/s3/test \
  -H "Authorization: Bearer <IdToken>" \
  -d '{"action": "test"}'
```

## 📝 新しいLambda関数の追加

1. `lambda_functions/` 配下に新しいディレクトリを作成し、コードとDockerfileを配置。
2. `build/lambda-images/` ディレクトリにビルドしたイメージのtarボールを配置（またはGatewayビルドプロセスに追加）。
3. Gateway起動時に自動的にイメージがロードされます。

## ⚠️ トラブルシューティングと運用時の注意

### 設定変更が反映されない場合

RustFSの認証情報や内部設定を変更した際、単純な再起動では反映されない場合があります。その際は以下の手順を試してください。

1.  **データの初期化 (データ削除)**:
    RustFSなどのストレージ・DBサービスは、初回起動時のみ管理者ユーザーを作成します。設定を変更して反映させるには、既存データを削除する必要があります。
    ```bash
    docker compose down
    sudo rm -rf ./data/s3_storage
    ```

2.  **コンテナの再ビルド**:
    本環境はDinD構成のため、内部設定ファイルはGatewayイメージ内に含まれています。ファイルを修正した後はイメージの再ビルドが必要です。
    ```bash
    docker compose up -d --build
    ```

### 共通の解決コマンド
困ったときは、以下の「全削除・再ビルド」を実行してください。
```bash
docker compose down
sudo rm -rf ./data/*
docker compose up -d --build
```
