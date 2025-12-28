### ⚠️ 次のステップ（Cleanup）に関する重要な変更

以前提示した **[Phase 4 Step 3: Legacy Code Cleanup]** の計画ですが、**「Docker ランタイムを正式採用した」** ことに伴い、一部変更が必要です。

**Go Agent 内の Docker Runtime コードは「削除対象」から「永続化対象」に変わりました。**

修正した Step 3 の実施計画を提示します。

# Phase 4 Step 3: Legacy Code Cleanup (Revised)

## 目的

不要となった「Python 製コンテナ管理システム (Orchestrator)」および「Fluent Bit」を削除し、システムをスリム化する。
※ **Go Agent 内の Docker Runtime は削除しません。**

## 実装タスク

### 1. Python Orchestrator の削除 (Confirmed)

Go Agent が完全に置き換わったため、旧サービスを削除します。

* **削除対象**: `services/orchestrator/` ディレクトリ全体
* **設定変更**:
* `docker-compose.yml` から `orchestrator` サービスを削除。
* `services/gateway/config.py` から `ORCHESTRATOR_URL` 等の環境変数を削除。



### 2. Fluent Bit の削除 (Confirmed)

Python からの直接送信 (`VictoriaLogsHandler`) に一本化したため、サイドカーを削除します。

* **削除対象**:
* `config/fluent-bit.conf`
* `config/parsers.conf`
* `docker-compose.yml` の `fluent-bit` サービス（もし残っていれば）。



### 3. [変更] Go Agent の整理

* **Docker Runtime (`internal/runtime/docker`)**: **残します**（現在のメインエンジンのため）。
* **containerd Runtime (`internal/runtime/containerd`)**: **残します**（将来のための Experimental 機能として温存）。
* **`main.go`**:
* デフォルトのランタイム設定を `docker` に固定します（環境変数 `AGENT_RUNTIME` のデフォルト値を変更するなど）。



### 4. CLI / ツールの修正

* `tools/cli/commands/logs.py` などで `orchestrator` コンテナを参照している箇所があれば削除します。

---

この修正版プランで Step 3 (最終仕上げ) に着手してよろしいでしょうか？
「Orchestrator さようなら」の準備ができ次第、Goサインをお願いします。