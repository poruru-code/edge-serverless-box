<!--
Where: docs/environment-variables.md
What: Environment variable reference for ESB components.
Why: Provide a single source of truth for runtime configuration.
-->
# 環境変数一覧

## 概要

本ドキュメントでは、Edge Serverless Box で使用される全ての環境変数を、コンポーネント別に整理して説明します。

## 環境変数の設定方法

環境変数は以下の優先順位で読み込まれます：

1. システム環境変数（最優先）
2. `.env` ファイル（プロジェクトルート）
3. コード内のデフォルト値（最低優先）

**推奨**: `.env.example` をコピーして `.env` を作成し、必要な値を設定してください。

```bash
cp .env.example .env
```

---

## 必須環境変数

以下の環境変数は**必ず設定が必要**です（デフォルト値なし）：

### セキュリティ関連

| 変数名 | 説明 | 例 | 使用コンポーネント |
|--------|------|----|--------------------|
| `JWT_SECRET_KEY` | JWT署名用シークレットキー（最低32文字） | `your-production-jwt-secret-key-min-32-chars` | Gateway |
| `X_API_KEY` | 内部サービス間通信用APIキー | `your-production-api-key` | Gateway |
| `AUTH_USER` | 認証ユーザー名 | `admin` | Gateway |
| `AUTH_PASS` | 認証パスワード | `your-secure-password` | Gateway |

### ストレージ認証情報

| 変数名 | 説明 | 例 | 使用コンポーネント |
|--------|------|----|--------------------|
| `RUSTFS_ACCESS_KEY` | RustFS（S3互換）のアクセスキー | `rustfsadmin` | Gateway, RustFS |
| `RUSTFS_SECRET_KEY` | RustFS（S3互換）のシークレットキー | `rustfsadmin` | Gateway, RustFS |

### ネットワーク設定

| 変数名 | 説明 | 例 | 使用コンポーネント |
|--------|------|----|--------------------|
| `LAMBDA_NETWORK` | Lambda コンテナが接続する内部ネットワーク名 | `onpre-internal-network` | Gateway, Go Agent, docker-compose |
| `EXTERNAL_NETWORK` | 外部公開用ネットワーク名 | `onpre-external` | docker-compose |
| `CONTAINERS_NETWORK` | Gateway が管理するコンテナのネットワーク（`LAMBDA_NETWORK` と同義） | `onpre-internal-network` | Gateway |
| `GATEWAY_INTERNAL_URL` | Lambda コンテナから見た Gateway の URL（既定は WG 経由: `https://10.99.0.1:443`。WG を使わない場合は worker から到達できる URL に上書き） | `https://10.99.0.1:443` | Gateway |

---

## オプション環境変数（デフォルト値あり）

### ポート設定

| 変数名 | デフォルト値 | 説明 | 使用コンポーネント |
|--------|--------------|------|--------------------|
| `GATEWAY_PORT` | `443` | テスト用 Gateway 公開ポート（HTTPS） | tests |
| `RUSTFS_API_PORT` | `9000` | RustFS S3 API ポート | docker-compose |
| `RUSTFS_CONSOLE_PORT` | `9001` | RustFS 管理コンソールポート | docker-compose |
| `SCYLLADB_PORT` | `8001` | ScyllaDB Alternator API ポート | docker-compose |
| `VICTORIALOGS_PORT` | `9428` | VictoriaLogs UI/API ポート | docker-compose |

### ログ設定

| 変数名 | デフォルト値 | 説明 | 使用コンポーネント |
|--------|--------------|------|--------------------|
| `LOG_LEVEL` | `INFO` | ログレベル (`DEBUG`, `INFO`, `WARNING`, `ERROR`) | 全コンポーネント |
| `VICTORIALOGS_URL` | `""` | VictoriaLogs の取り込みURL（`docker-compose.yml` では `http://victorialogs:9428` を既定指定） | Gateway |
| `GATEWAY_VICTORIALOGS_URL` | `""` | Gateway 送信先のVictoriaLogs URL（未設定なら `VICTORIALOGS_URL`/`VICTORIALOGS_HOST` を使用） | Gateway |
| `VICTORIALOGS_HOST` | `victorialogs` | VictoriaLogs のホスト名（URL未設定時のfallback） | Gateway |
| `DISABLE_VICTORIALOGS` | `""` | `1/true/yes/on` で Gateway の VictoriaLogs 送信を無効化 | Gateway |
| `LOG_CONFIG_PATH` | `/app/config/gateway_log.yaml` | Gateway ログ設定ファイルのパス | Gateway |

### Gateway 設定

| 変数名 | デフォルト値 | 説明 |
|--------|--------------|------|
| `UVICORN_WORKERS` | `4` | ワーカープロセス数 |
| `UVICORN_BIND_ADDR` | `0.0.0.0:8000` | リッスンアドレス |
| `JWT_EXPIRES_DELTA` | `3000` | トークン有効期限（秒） |
| `AUTH_ENDPOINT_PATH` | `/user/auth/v1` | 認証エンドポイントパス |
| `ENABLE_SSL` | `true` | SSL/TLS を有効化 |
| `SSL_CERT_PATH` | `/app/config/ssl/server.crt` | SSL証明書パス |
| `SSL_KEY_PATH` | `/app/config/ssl/server.key` | SSL秘密鍵パス |
| `GATEWAY_WORKER_ROUTE_VIA_HOST` | `""` | worker サブネットの経路を指定ホスト経由に上書き（例: `runtime-node`） |
| `GATEWAY_WORKER_ROUTE_VIA` | `""` | worker サブネットの経路を指定IP経由に上書き（`..._HOST` より優先） |
| `GATEWAY_WORKER_ROUTE_CIDR` | `10.88.0.0/16` | worker 経路上書きの対象CIDR（`AllowedIPs` からこの範囲のみ適用） |

### Lambda 関数設定

| 変数名 | デフォルト値 | 説明 |
|--------|--------------|------|
| `LAMBDA_PORT` | `8080` | Lambda RIE コンテナのポート番号 |
| `LAMBDA_INVOKE_TIMEOUT` | `30.0` | Lambda 呼び出しタイムアウト（秒） |
| `READINESS_TIMEOUT` | `30` | コンテナ Readiness チェックのタイムアウト（秒） |
| `DOCKER_DAEMON_TIMEOUT` | `30` | Docker Daemon 起動待機のタイムアウト（秒） |

### 流量制御・サーキットブレーカー

| 変数名 | デフォルト値 | 説明 |
|--------|--------------|------|
| `MAX_CONCURRENT_REQUESTS` | `10` | 関数あたりの同時実行上限 |
| `QUEUE_TIMEOUT_SECONDS` | `10` | キュー待機タイムアウト（秒） |
| `CIRCUIT_BREAKER_THRESHOLD` | `5` | サーキットブレーカーの失敗しきい値 |
| `CIRCUIT_BREAKER_RECOVERY_TIMEOUT` | `30.0` | 復旧試行までの待機時間（秒） |

### Auto-Scaling 設定

| 変数名 | デフォルト値 | 説明 |
|--------|--------------|------|
| `DEFAULT_MAX_CAPACITY` | `1` | デフォルト最大容量 |
| `DEFAULT_MIN_CAPACITY` | `0` | デフォルト最小容量 |
| `POOL_ACQUIRE_TIMEOUT` | `30.0` | ワーカー取得タイムアウト（秒）。`docker-compose.yml` では `5.0` をデフォルト指定 |
| `HEARTBEAT_INTERVAL` | `30` | Janitor の巡回間隔（秒） |
| `GATEWAY_IDLE_TIMEOUT_SECONDS` | `300` | Gateway 側アイドルタイムアウト（秒） |
| `ENABLE_CONTAINER_PAUSE` | `false` | アイドル後にコンテナを一時停止するか（containerdのみ） |
| `PAUSE_IDLE_SECONDS` | `30` | Pause までのアイドル時間（秒） |
| `ORPHAN_GRACE_PERIOD_SECONDS` | `60` | 孤児コンテナ削除の猶予時間（秒） |

### Go Agent 設定

| 変数名 | デフォルト値 | 説明 |
|--------|--------------|------|
| `AGENT_GRPC_ADDRESS` | `esb-agent:50051` | Go Agent の gRPC アドレス（コード既定は `esb-agent:50051`。`docker-compose.yml` では `runtime-node:50051` を設定し、Firecracker 分離では `10.99.0.x:50051` を指定） |
| `AGENT_INVOKE_PROXY` | `false` | Gateway が worker invoke を Agent 経由（L7 代理）で行うか |
| `AGENT_RUNTIME` | `docker` | Agent のランタイム (`docker` または `containerd`) |
| `CONTAINERD_RUNTIME` | `""` | containerd の runtime 名（`AGENT_RUNTIME=containerd` のとき有効。未指定ならデフォルト。例: `aws.firecracker`） |
| `CONTAINERD_SNAPSHOTTER` | `""` | containerd の snapshotter 名。未指定時は `CONTAINERD_RUNTIME=aws.firecracker` なら `devmapper`、それ以外は `overlayfs` |
| `PORT` | `50051` | Go Agent の gRPC ポート |
| `CONTAINER_REGISTRY` | `""` | 取得/プッシュ先のコンテナレジストリ。設定時は `{registry}/{function_name}:latest` を使用 |
| `CNI_CONF_DIR` | `/etc/cni/net.d` | containerd 用 CNI 設定ディレクトリ |
| `CNI_CONF_FILE` | `/etc/cni/net.d/10-esb.conflist` | containerd 用 CNI 設定ファイル |
| `CNI_BIN_DIR` | `/opt/cni/bin` | containerd 用 CNI バイナリディレクトリ |
| `CNI_SUBNET` | `""` | CNI のIP割り当て範囲。設定時は `CNI_CONF_FILE` の範囲をこのCIDRに制限し、`10.88.0.1` 互換は維持 |

### runtime-node (DNAT) 設定

| 変数名 | デフォルト値 | 説明 | 使用コンポーネント |
|--------|--------------|------|--------------------|
| `CNI_GW_IP` | `10.88.0.1` | CNI bridge の gateway IP（DNAT の宛先） | runtime-node |
| `DNAT_S3_IP` | `""` | `10.88.0.1:9000` の転送先 IP（local proxy なら `127.0.0.1`） | runtime-node |
| `DNAT_DB_IP` | `""` | `10.88.0.1:8001` の転送先 IP（local proxy なら `127.0.0.1`） | runtime-node |
| `DNAT_VL_IP` | `""` | `10.88.0.1:9428` の転送先 IP（local proxy なら `127.0.0.1`） | runtime-node |
| `DNAT_DB_DPORT` | `8001` | 10.88.0.1 側の DB 宛ポート | runtime-node |
| `DNAT_DB_PORT` | `8000` | 転送先 DB の実ポート | runtime-node |
| `DNAT_APPLY_OUTPUT` | `1` | `1` のとき OUTPUT へ DNAT を適用（SNAT/MASQUERADE も必要） | runtime-node |
| `WG_CONTROL_NET` | `""` | Gateway へ到達するための制御系ネットワーク（例: `10.99.0.0/24`）。設定時は runtime-node 内にルートを追加 | runtime-node |
| `WG_CONTROL_GW` | `""` | `WG_CONTROL_NET` の next-hop。未設定時は default gateway を使用 | runtime-node |
| `WG_CONTROL_GW_HOST` | `gateway` | `WG_CONTROL_GW` 未設定時に名前解決するホスト名（例: `gateway`） | runtime-node |

### runtime-node (containerd) 設定

| 変数名 | デフォルト値 | 説明 | 使用コンポーネント |
|--------|--------------|------|--------------------|
| `CONTAINERD_BIN` | `containerd` | 起動する containerd バイナリ（`docker-compose.node.yml` では `/usr/local/bin/firecracker-containerd`） | runtime-node |
| `CONTAINERD_CONFIG` | `""` | containerd 設定ファイルパス（`docker-compose.node.yml` では `/etc/firecracker-containerd/config.toml`） | runtime-node |

### runtime-node (devmapper) 設定

| 変数名 | デフォルト値 | 説明 | 使用コンポーネント |
|--------|--------------|------|--------------------|
| `DEVMAPPER_POOL` | `""` | devmapper の thin-pool 名。Firecracker では `fc-dev-pool2` を想定 | runtime-node |
| `DEVMAPPER_DIR` | `/var/lib/containerd/devmapper2` | devmapper の backing ファイル配置先 | runtime-node |
| `DEVMAPPER_DATA_SIZE` | `10G` | devmapper data-device サイズ（loopback 作成時） | runtime-node |
| `DEVMAPPER_META_SIZE` | `2G` | devmapper meta-device サイズ（loopback 作成時） | runtime-node |
| `DEVMAPPER_UDEV` | `0` | `1` で udev を利用。コンテナ環境では `0` 推奨（dmsetup mknodes で補完） | runtime-node |

補足:
- `DEVMAPPER_POOL` / `DEVMAPPER_DIR` / `DEVMAPPER_DATA_SIZE` は `/etc/firecracker-containerd/config.toml` の
  `pool_name` / `root_path` / `base_image_size` と整合させる必要がある。

### ストレージ設定

| 変数名 | デフォルト値 | 説明 |
|--------|--------------|------|
| `RUSTFS_DEDUPLICATION` | `true` | RustFS の重複排除を有効化 |
| `RUSTFS_COMPRESSION` | `auto` | RustFS の圧縮方式 |
| `SCYLLADB_MEMORY` | `1` | ScyllaDB のメモリ割り当て（GB） |

### パス設定

| 変数名 | デフォルト値 | 説明 |
|--------|--------------|------|
| `ROUTING_CONFIG_PATH` | `/app/config/routing.yml` | ルーティング定義ファイルパス |
| `FUNCTIONS_CONFIG_PATH` | `/app/config/functions.yml` | Lambda 関数定義ファイルパス |
| `DATA_ROOT_PATH` | `/data` | 子コンテナデータのルートパス |
| `LOGS_ROOT_PATH` | `/logs` | ログ集約先のルートパス |
| `GATEWAY_FUNCTIONS_YML` | `./config/functions.yml` | Gateway 用関数定義ファイル（ホスト側） |
| `GATEWAY_ROUTING_YML` | `./config/routing.yml` | Gateway 用ルーティング定義ファイル（ホスト側） |
| `ESB_WG_GATEWAY_CONF` | `~/.esb/wireguard/gateway/wg0.conf` | Gateway コンテナにマウントする WireGuard 設定ファイル | docker-compose |
| `ESB_WG_COMPUTE_CONF` | `~/.esb/wireguard/compute/wg0.conf` | `esb node provision` が転送する Compute 側 WireGuard 設定ファイル | tools/cli |
| `ESB_WG_MTU` | `1420` | WireGuard インターフェースの MTU。WSL/Hyper-V で TLS が不安定なら `1340` 前後に下げる | tools/cli |
| `ESB_CONTROL_HOST` | `""` | Compute Node から見た Control のホスト/IP（registry/s3/db/logs/gateway の解決先） | docker-compose.node.yml |
| `RUNTIME_NODE_IP` | `172.20.0.10` | Compute VM 上の runtime-node 固定IP（WireGuard ルートの next-hop） | docker-compose.node.yml |
| `RUNTIME_NET_SUBNET` | `172.20.0.0/16` | Compute VM 上の runtime-node 専用 bridge サブネット | docker-compose.node.yml |

### その他

| 変数名 | デフォルト値 | 説明 |
|--------|--------------|------|
| `VERIFY_SSL` | `false` | SSL証明書の検証を行うか |
| `PYTHONUNBUFFERED` | `1` | Python の出力バッファリングを無効化 |

---

## コンポーネント別環境変数マップ

### Gateway (services/gateway)

**必須**:
- `JWT_SECRET_KEY`
- `X_API_KEY`
- `AUTH_USER`
- `AUTH_PASS`
- `CONTAINERS_NETWORK`
- `GATEWAY_INTERNAL_URL`
- `RUSTFS_ACCESS_KEY`
- `RUSTFS_SECRET_KEY`

**オプション（頻繁に変更）**:
- `AGENT_GRPC_ADDRESS`
- `LOG_LEVEL`
- `LAMBDA_INVOKE_TIMEOUT`
- `CIRCUIT_BREAKER_THRESHOLD`
- `CIRCUIT_BREAKER_RECOVERY_TIMEOUT`
- `GATEWAY_WORKER_ROUTE_VIA_HOST`
- `GATEWAY_WORKER_ROUTE_VIA`
- `GATEWAY_WORKER_ROUTE_CIDR`
- Auto-Scaling 関連変数

### Go Agent (services/agent)

**必須**:
- なし（`AGENT_RUNTIME=docker` の場合は `CONTAINERS_NETWORK` が必要）

**オプション**:
- `LOG_LEVEL`
- `PORT`
- `AGENT_RUNTIME`
- `CONTAINERD_RUNTIME`
- `CONTAINER_REGISTRY`
- `CNI_CONF_DIR`
- `CNI_CONF_FILE`
- `CNI_BIN_DIR`
- `CNI_SUBNET`

### RustFS (S3 互換ストレージ)

**必須**:
- `RUSTFS_ACCESS_KEY`
- `RUSTFS_SECRET_KEY`

**オプション**:
- `RUSTFS_DEDUPLICATION`
- `RUSTFS_COMPRESSION`

### ScyllaDB (DynamoDB 互換 DB)

**オプション**:
- `SCYLLADB_MEMORY`

### VictoriaLogs

**オプション**:
- なし（全てデフォルト値で動作）

---

## テスト環境での設定

テスト環境では以下の追加ファイルが使用されます：

- `tests/environments/.env.standard` - 標準テスト環境用
- `tests/environments/.env.autoscaling` - Auto-Scaling テスト環境用

テスト専用の環境変数：

| 変数名 | デフォルト値 | 説明 |
|--------|--------------|------|
| `ESB_TEMPLATE` | `tests/fixtures/template.yaml` | ESB CLI テンプレートファイル |

---

## 廃止された環境変数

以下の環境変数は Phase 4-3 で削除されました：

| 変数名 | 削除理由 |
|--------|----------|
| `ORCHESTRATOR_URL` | Python Orchestrator の削除に伴い廃止 |
| `ORCHESTRATOR_TIMEOUT` | Python Orchestrator の削除に伴い廃止 |
| `FLUENT_BIT_PORT` | Fluent Bit の削除に伴い廃止（VictoriaLogs 直接送信に移行） |

---

## セキュリティ上の注意事項

### 本番環境での推奨事項

1. **シークレットキーの変更**: `.env.example` の値をそのまま使用せず、必ず変更してください
2. **強力なパスワード**: `AUTH_PASS` には予測困難な strong password を設定してください
3. **JWT シークレットの長さ**: `JWT_SECRET_KEY` は最低 32 文字以上にしてください
4. **`.env` ファイルの管理**: `.env` ファイルは Git にコミットされません（`.gitignore` に登録済み）

### 環境変数の暗号化

本番環境では以下の方法で環境変数を保護することを推奨します：

- Docker Secrets（Docker Swarm 使用時）
- Kubernetes Secrets（Kubernetes 使用時）
- AWS Secrets Manager / Azure Key Vault などのシークレット管理サービス

---

## トラブルシューティング

### 起動時に "Field required" エラーが発生する

**原因**: 必須環境変数が設定されていません。

**解決方法**:
1. `.env.example` を `.env` にコピー
2. 必須環境変数（上記リスト参照）を全て設定
3. サービスを再起動

### Lambda コンテナがネットワークに接続できない

**原因**: `LAMBDA_NETWORK` または `CONTAINERS_NETWORK` の設定が不正です。

**解決方法**:
1. `LAMBDA_NETWORK` と `CONTAINERS_NETWORK` が同じ値であることを確認
2. `docker-compose.yml` のネットワーク定義と一致することを確認

### Go Agent との通信エラー

**原因**: `AGENT_GRPC_ADDRESS` が不正、または Go Agent が起動していません。

**解決方法**:
1. `AGENT_GRPC_ADDRESS` を環境に合わせて確認（`docker-compose.yml` では `runtime-node:50051`）
2. Go Agent コンテナが起動していることを確認

---

## 関連ドキュメント

- [`.env.example`](../.env.example) - 環境変数テンプレート
- [`services/gateway/config.py`](../services/gateway/config.py) - Gateway 設定定義
- [`docker-compose.yml`](../docker-compose.yml) - サービス構成定義
