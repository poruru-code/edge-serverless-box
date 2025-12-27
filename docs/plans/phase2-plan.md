Phase 1 の完了おめでとうございます！基盤となる gRPC 通信と Go Agent が稼働したことで、いよいよ本丸である **Phase 2: Deep Dive (containerd Native)** に進むことができます。

このフェーズは技術的な難易度が高いため、**「コンテナのライフサイクル管理」** と **「ネットワーキング（CNI）」** を慎重に実装する必要があります。

以下に詳細な実装プランを提示します。

---

# Phase 2: Deep Dive (containerd Native) 実装プラン

## 目的

Agent (Go) のバックエンドを `Docker SDK` から **`containerd` クライアント** へ完全に切り替えます。
これにより、Docker デーモンのオーバーヘッドを回避し、AWS Lambda の "Freeze/Thaw"（サスペンド/レジューム）機能を実現します。

## 構成の変更点

* **Runtime**: `Docker Engine` -> `containerd` (Direct)
* **Namespace**: `moby` (Docker default) -> `esb` (Isolated namespace)
* **Network**: Docker Network -> **CNI (Container Network Interface)**
* **Snapshotter**: `overlayfs` (Standard)

---

## Step 1: 環境と依存関係の整備

containerd を操作するためのライブラリ導入と、開発環境（DinD）のマウント設定を変更します。

### Task 1.1: Go Modules の追加

`services/agent/go.mod` に必要なライブラリを追加します。

```bash
go get github.com/containerd/containerd
go get github.com/opencontainers/runtime-spec/specs-go
go get github.com/containernetworking/cni/libcni

```

### Task 1.2: 開発用 Dockerfile への CNI プラグイン追加

containerd でネットワーク（IPアドレス割り当て）を行うには **CNI プラグイン** が必須です。
`services/agent/Dockerfile.dev` (および本番用 `Dockerfile`) に CNI プラグインをインストールする手順を追加します。

```dockerfile
# services/agent/Dockerfile.dev
# ... (Go install など)

# CNI Plugins のインストール
RUN curl -L -o cni-plugins.tgz "https://github.com/containernetworking/plugins/releases/download/v1.3.0/cni-plugins-linux-$(go env GOARCH)-v1.3.0.tgz" && \
    mkdir -p /opt/cni/bin && \
    tar -C /opt/cni/bin -xzf cni-plugins.tgz

```

### Task 1.3: Docker Compose マウント設定

`docker-compose.yml` (および `.dev.yml`) を修正し、`containerd` のソケットをマウントします。

```yaml
services:
  agent:
    privileged: true  # CNIでのネットワーク操作に必要
    volumes:
      # Docker Socket (Phase 1用 - 徐々に廃止)
      - /var/run/docker.sock:/var/run/docker.sock
      # Containerd Socket (Phase 2用 - 本丸)
      - /run/containerd/containerd.sock:/run/containerd/containerd.sock
      # CNI設定やデータを永続化する場合 (Optional)
      - esb_cni_data:/var/lib/cni

```

---

## Step 2: Runtime Interface のリファクタリング

Docker 実装と containerd 実装を切り替えられるよう、Go 内部のインターフェースを整理します。

### Task 2.1: `ContainerRuntime` インターフェースの定義

`internal/runtime/interface.go` を作成し、既存の `docker.go` がこれを満たすようにします。

```go
type ContainerRuntime interface {
    Ensure(ctx context.Context, req EnsureRequest) (WorkerInfo, error)
    Destroy(ctx context.Context, containerID string) error
    // Pause/Resume は Phase 2 の目玉機能
    Pause(ctx context.Context, containerID string) error
    Resume(ctx context.Context, containerID string) error
}

```

---

## Step 3: containerd 実装 (Core Logic)

ここが実装の核心部分です。`internal/runtime/containerd/` パッケージを作成して実装します。

### Task 3.1: クライアント接続と名前空間

`containerd.New("/run/containerd/containerd.sock")` で接続し、コンテキストに `namespaces.WithNamespace(ctx, "esb")` を設定して、Docker の管理外（`esb` 名前空間）で操作するようにします。

### Task 3.2: Image Pull (Snapshotter)

指定されたイメージを Pull します。

* **Point**: `client.Pull` を使用。`docker.io/library/python:3.9` のように完全修飾名が必要になる場合があります。

### Task 3.3: コンテナ作成 (OCI Spec)

`client.NewContainer` を使用します。ここで **AWS Lambda RIE** を動かすための OCI Spec (`oci.Spec`) を組み立てます。

```go
spec := oci.Compose(
    oci.WithImageConfig(image),
    oci.WithEnv([]string{
        "AWS_LAMBDA_FUNCTION_NAME=" + funcName,
        "_LAMBDA_SERVER_PORT=8080",
    }),
    // RIE をエントリーポイントにする
    oci.WithProcessArgs("/usr/local/bin/aws-lambda-rie", "python3", "-m", "awslambdaric", "lambda_function.handler"),
)

```

### Task 3.4: ネットワーク接続 (CNI)

これが最も難所です。`libcni` を使用して、コンテナ作成時にネットワークインターフェースをアタッチします。

1. **CNI Config**: エージェント起動時に単純なブリッジネットワーク設定（JSON）をロードします。
2. **Attach**: コンテナ作成後、Task 開始前に `cni.AddNetwork` を呼び出し、コンテナの Network Namespace にインターフェースを追加します。
3. **IP取得**: CNI の結果から IP アドレスを取得し、`WorkerInfo` として Gateway に返します。

---

## Step 4: Pause / Resume (Fast Freeze)

AWS Lambda の「コールドスタート後の待機状態」を再現します。

### Task 4.1: `Pause` 実装

`docker stop` (SIGTERM) ではなく、cgroups の freezer 機能を使います。

```go
task, _ := container.Task(ctx, nil)
task.Pause(ctx) // CPUサイクルを消費しなくなる

```

### Task 4.2: `Resume` 実装

リクエストが来たら、Pause 状態のコンテナを叩き起こします。

```go
task.Resume(ctx)

```

### Task 4.3: `Ensure` ロジックの改修

`Ensure` メソッドのロジックを以下のように高度化します。

1. コンテナ検索 (`esb` namespace)。
2. **存在する場合**:
* Status が `Running` → そのまま IP 返却。
* Status が `Paused` → **`Resume()` 実行** → IP 返却 (Warm Start)。
* Status が `Stopped` → `Delete` & `Create` (Restart)。


3. **存在しない場合**:
* `Create` -> `Start` -> IP 返却 (Cold Start)。



---

## Step 5: 切り替えと検証

### Task 5.1: `main.go` での切り替え

環境変数 `RUNTIME_TYPE=containerd` (デフォルト) で containerd 実装を使用するように `main.go` を修正します。

### Task 5.2: 検証項目

1. **起動確認**: `esb up` で Agent がエラーなく起動するか。
2. **隔離確認**: `docker ps` を叩いても Lambda コンテナが見えないこと（`moby` 名前空間にいないため）。
* 確認方法: `ctr -n esb containers list` (ctrコマンドは別途必要) またはログ。


3. **通信確認**: Gateway から関数を実行し、正常に応答があるか。
4. **Pause確認**: しばらく放置した後、Gateway から再度リクエストした際に「高速に復帰（Resume）」するか。

---

## 実装のヒント (Networking)

Phase 2 で最もハマりやすいのが「Gateway (Docker Network) から containerd コンテナ (CNI Network) への通信」です。

**推奨する簡易アプローチ (Dev)**:
厳密な CNI ブリッジを作るのが難しい場合、開発用として **Host Networking** のような挙動を模倣させることが可能です。
OCI Spec で `oci.WithHostNamespace(specs.NetworkNamespace)` を指定すると、コンテナは Agent (Host) と同じネットワークスタックを使います。

* **メリット**: IP ルーティング不要。`localhost:xxxxx` で繋がる。
* **デメリット**: ポート競合するため、コンテナごとに `8081`, `8082`... とポートをずらす管理が必要になる。

**本来のアプローチ (CNI Bridge)**:
CNI で `esb-bridge` を作成し、IP を振る方法。Agent コンテナが `privileged` であれば機能しますが、ルーティングテーブルの設定が必要になる場合があります。

**今回は「本来のアプローチ (CNI Bridge)」に挑戦し、難しければ「Host Namespace + Port管理」に倒す** という方針をお勧めします。