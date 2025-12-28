承知いたしました。「Phase 5 Step 0: Local Registry & Private CA Integration (User Directory Edition)」の最終確定した実装計画を、この単体ドキュメントで完結する形式でまとめます。

---

# Implementation Plan: Local Registry & Private CA Integration

## 1. 概要と目的

本フェーズの目的は、開発環境において **HTTPS化されたローカルレジストリ** を導入し、本番環境と同等の「Build (Push) → Pull → Run」のデプロイフローを確立することです。
セキュリティと開発体験を両立させるため、以下のアーキテクチャを採用します。

* **Private CA方式**: オレオレ認証局 (Private CA) を構築し、OSとAgentに信頼させる「正攻法」を採用。
* **User Directory保管**: 証明書ファイルはプロジェクト内ではなく、ユーザーディレクトリ (`~/.esb/certs`) で一元管理し、誤削除や流出を防ぐ。
* **自動化**: CA生成からOSへの信頼登録までをCLIツール (`esb init`) で自動化する。

## 2. ディレクトリ構成と管理方針

証明書はプロジェクトリポジトリ外のユーザー領域に保存し、Docker Compose には環境変数経由でパスを渡します。

### ホスト側の配置 (`~` はユーザーホーム)

```text
~/.esb/certs/
├── rootCA.key        # [生成] CA秘密鍵 (再生成禁止/流出厳禁)
├── rootCA.crt        # [生成] CAルート証明書 (OS & Agentへ配布)
├── server.key        # [生成] サーバー秘密鍵 (Registry/Gateway用)
└── server.crt        # [生成] サーバー証明書 (localhost, esb-registry等をSANに含む)

```

## 3. 実装タスク詳細

### 3.1. CLIツール改修 (`tools/cli`)

開発者体験の中核となる証明書管理機能を実装します。

#### A. 設定管理 (`tools/cli/config.py`)

* デフォルトの証明書ディレクトリパス定数を定義。
```python
DEFAULT_CERT_DIR = Path.home() / ".esb" / "certs"

```



#### B. 証明書生成ロジック (`tools/cli/core/cert.py`)

既存の自己署名ロジックを廃棄し、CA署名モデルへ刷新します。

* **`ensure_certs(cert_dir)`**: エントリーポイント。
* **`generate_root_ca(cert_dir)`**:
* `rootCA.key` が存在すればスキップ (冪等性)。
* なければ RSA 4096bit 鍵と、それを自己署名した `rootCA.crt` (有効期限10年) を生成。


* **`generate_server_cert(cert_dir, ca_key, ca_cert)`**:
* `server.key` / `server.crt` を毎回（または存在しなければ）生成。
* **SAN (Subject Alternative Name)** に以下を必ず含める:
* `localhost`
* `127.0.0.1`
* `esb-registry` (コンテナ間通信用)
* `host.docker.internal`
* `esb-gateway` (将来用)





#### C. トラストストア登録ロジック (`tools/cli/core/trust_store.py`) [新規]

生成した `rootCA.crt` をOSに信頼させるロジックを実装します。**管理者権限 (sudo/Admin)** を要求します。

* **共通**: 登録前に「既に信頼されているか」を確認し、二重登録を防ぐ（冪等性）。
* **Windows**: `certutil -addstore -f "Root" ...`
* **macOS**: `security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain ...`
* **Linux**: `/usr/local/share/ca-certificates/` へコピーし `update-ca-certificates`。

#### D. コマンド統合 (`tools/cli/commands`)

* **`init.py`**:
* `cert.ensure_certs` と `trust_store.install_cert` を呼び出すフローを追加。


* **`up.py`, `build.py` 等**:
* `docker-compose` コマンド実行時の環境変数 (`os.environ`) に `ESB_CERT_DIR` を注入する処理を追加。



### 3.2. インフラ定義 (`docker-compose.yml`)

HTTPS対応のレジストリと、CAを信頼するAgentを構成します。

#### A. Registry サービスの追加

```yaml
  registry:
    image: registry:2
    container_name: esb-registry
    ports:
      - "5000:5000"
    environment:
      REGISTRY_HTTP_TLS_CERTIFICATE: /certs/server.crt
      REGISTRY_HTTP_TLS_KEY: /certs/server.key
    volumes:
      # CLIから注入された ESB_CERT_DIR をマウント
      - ${ESB_CERT_DIR}/server.crt:/certs/server.crt:ro
      - ${ESB_CERT_DIR}/server.key:/certs/server.key:ro
    networks:
      - internal_network
      - external_network
    healthcheck:
      # HTTPSでヘルスチェック (wgetのオプション注意)
      test: ["CMD", "wget", "--no-check-certificate", "-q", "--spider", "https://localhost:5000/v2/"]

```

#### B. Agent サービスの修正

Agentコンテナ内からHTTPSレジストリへアクセス可能にします。

```yaml
  agent:
    # ...
    environment:
      # Docker Runtime (Step 0) はホストデーモンを使うため localhost 指定
      - CONTAINER_REGISTRY=localhost:5000
    volumes:
      # CA証明書を取り込む
      - ${ESB_CERT_DIR}/rootCA.crt:/usr/local/share/ca-certificates/esb-rootCA.crt:ro
    # 起動時にCAをシステムに登録する
    command: >
      sh -c "update-ca-certificates && /app/agent"
    depends_on:
      registry:
        condition: service_healthy

```

### 3.3. Agent ロジック改修 (`services/agent`)

リクエストされた関数イメージ名にレジストリプレフィックスを付与します。

* **対象**: `internal/runtime/docker/runtime.go` (および `containerd/runtime.go`)
* **修正**: `Ensure` メソッド内で環境変数 `CONTAINER_REGISTRY` を確認。
* 値がある場合: `Image = registry + "/" + FunctionName + ":latest"`
* 値がない場合: 従来通り



### 3.4. ビルドツール改修 (`tools/cli/commands/build.py`)

* **タグ付け変更**: `localhost:5000/<func>:latest` としてビルド。
* **Push追加**: ビルド後に `docker push` を実行。
* **エラーハンドリング**: Registry未到達時のエラーメッセージを明確化。

---

## 4. 検証手順 (Verification Plan)

以下の手順ですべてが成功することをもって完了とします。

1. **初期化**:
```bash
./esb init
# -> "~/.esb/certs に証明書生成" ログ確認
# -> OSのパスワード入力要求 (Trust Store登録)
# -> "Success" 確認

```


2. **起動**:
```bash
./esb up
# -> Registryなどが起動

```


3. **HTTPS接続確認**:
```bash
curl -v https://localhost:5000/v2/
# -> エラーが出ず、HTTP 200 OK {} が返ること (証明書エラーなら失敗)

```


4. **ビルド & Push**:
```bash
./esb build lambda-dynamo
# -> "Pushing..." ログ確認

```


5. **Pull検証 (最重要)**:
```bash
# ローカルキャッシュを削除
docker rmi localhost:5000/lambda-dynamo:latest
# テスト実行 (AgentがRegistryからPullするはず)
pytest tests/scenarios/standard/test_dynamo.py
# -> PASSED 確認

```



## 5. 次のステップへの考慮事項

* **Step 1 (containerd移行) への布石**:
* Agent の環境変数を `CONTAINER_REGISTRY=esb-registry:5000` に変更するだけで、コンテナ間HTTPS通信が成立するよう設計済み（証明書のSANに `esb-registry` を含めるため）。