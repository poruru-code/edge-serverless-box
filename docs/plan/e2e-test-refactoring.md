# E2E テストリファクタリング調査

## 目的

外部から検証可能な全機能を洗い出し、それぞれを問題なく通過することを E2E テストで担保する。

## 現状調査

### テストファイル構造

```
tests/
├── .env.test                    # テスト用環境変数
├── docker-compose.test.yml      # テスト用 Docker Compose オーバーライド
├── run_tests.py                 # E2E テスト実行スクリプト
├── test_e2e.py                  # 全 E2E テストを含む単一ファイル (828行)
├── e2e/
│   ├── config/
│   │   └── routing.yml          # 自動生成されるルーティング設定
│   ├── functions/               # テスト用 Lambda 関数
│   │   ├── faulty/              # 故障シミュレーション用
│   │   ├── hello/               # 基本的な Lambda
│   │   ├── invoke-test/         # 関数間呼び出しテスト用
│   │   ├── s3-test/             # S3 連携テスト用
│   │   └── scylla-test/         # ScyllaDB 連携テスト用
│   ├── generator.yml            # Generator 設定
│   └── template.yaml            # SAM テンプレート形式の関数定義
└── unit/                        # ユニットテスト (別ディレクトリ)
```

### 現在の E2E テスト一覧 (TestE2E クラス)

| # | テスト名 | 検証内容 | 対象機能 |
|---|----------|----------|----------|
| 1 | `test_health` | Gateway ヘルスチェック | Gateway 基本 |
| 2 | `test_auth` | 認証フロー (JWT 取得) | 認証 |
| 3 | `test_routing_401` | 認証なしで 401 | 認証 |
| 4 | `test_routing_404` | 存在しないルートで 404 | ルーティング |
| 5 | `test_lambda_invocation` | 認証→ルーティング→Lambda呼び出し | Lambda 呼び出し |
| 6 | `test_scylla_integration` | ScyllaDB 連携 | DynamoDB 互換 |
| 7 | `test_function_invocation_sync` | 同期 Lambda 呼び出し (invoke-test → hello) | Lambda 間呼び出し |
| 8 | `test_function_invocation_async` | 非同期 Lambda 呼び出し (invoke-test → s3-test) | Lambda 間呼び出し |
| 9 | `test_request_id_tracing_in_victorialogs` | RequestID トレーシング | ロギング |
| 10 | `test_log_quality_and_level_control` | ログ品質とレベル制御 | ロギング |
| 11 | `test_manager_restart_container_adoption` | Manager 再起動後のコンテナ復元 | Manager 耐障害性 |
| 12 | `test_cloudwatch_logs_via_boto3` | CloudWatch Logs API 透過的リダイレクト | ロギング |
| 13 | `test_container_host_caching_e2e` | コンテナホストキャッシュ | パフォーマンス |
| 14 | `test_circuit_breaker_open_e2e` | Circuit Breaker 動作 | 耐障害性 |

---

## 問題点

### 1. テスト名が不明瞭
- `test_lambda_invocation` vs `test_function_invocation_sync` の違いがわかりにくい
- 接尾辞 `_e2e` が付いているものと付いていないものが混在

### 2. ファイル構造が不適切
- 全テストが `test_e2e.py` という単一ファイルに集約されている (828行)
- 機能カテゴリごとにファイルが分かれていない

### 3. テスト対象の整理ができていない
- 何が「外部から検証可能な機能」なのかが明確でない
- テストの網羅性が不明

---

## 外部から検証可能な機能の洗い出し

### A. Gateway 基本機能

| 機能 | エンドポイント | 現在のテスト | 備考 |
|------|----------------|--------------|------|
| ヘルスチェック | `GET /health` | `test_health` | ✓ |
| 認証 (JWT 発行) | `POST /user/auth/v1` | `test_auth` | ✓ |
| 認証なし拒否 | 任意のルート (Bearer なし) | `test_routing_401` | ✓ |
| 存在しないルート | `GET /nonexistent` | `test_routing_404` | ✓ |

### B. Lambda 呼び出し

| 機能 | エンドポイント | 現在のテスト | 備考 |
|------|----------------|--------------|------|
| 基本呼び出し | `POST /api/hello` | `test_lambda_invocation` | ✓ |
| 同期関数間呼び出し | `POST /api/invoke/test` → hello | `test_function_invocation_sync` | ✓ |
| 非同期関数間呼び出し | `POST /api/invoke/test` → s3-test | `test_function_invocation_async` | ✓ |

### C. AWS サービス互換

| 機能 | エンドポイント | 現在のテスト | 備考 |
|------|----------------|--------------|------|
| DynamoDB 互換 (ScyllaDB) | Lambda 内で DynamoDB API 使用 | `test_scylla_integration` | ✓ |
| S3 互換 (RustFS) | Lambda 内で S3 API 使用 | `test_function_invocation_async` | 間接的 |
| CloudWatch Logs 互換 | Lambda 内で put_log_events | `test_cloudwatch_logs_via_boto3` | ✓ |

### D. ロギング・オブザーバビリティ

| 機能 | 検証方法 | 現在のテスト | 備考 |
|------|----------|--------------|------|
| RequestID トレーシング | VictoriaLogs クエリ | `test_request_id_tracing_in_victorialogs` | ✓ |
| ログ品質・レベル制御 | VictoriaLogs クエリ | `test_log_quality_and_level_control` | ✓ |

### E. 耐障害性・パフォーマンス

| 機能 | 検証方法 | 現在のテスト | 備考 |
|------|----------|--------------|------|
| Manager 再起動復元 | Manager 再起動後の呼び出し | `test_manager_restart_container_adoption` | ✓ |
| Circuit Breaker | 連続失敗後の即時エラー | `test_circuit_breaker_open_e2e` | ✓ |
| コンテナホストキャッシュ | Manager ログ確認 | `test_container_host_caching_e2e` | ✓ |

---

## 未カバーの機能 (検討対象)

- [ ] Gateway タイムアウト設定の動作確認
- [ ] Lambda コールドスタート vs ウォームスタートの時間比較
- [ ] 複数同時リクエストの処理 (並行性)
- [ ] コンテナアイドルタイムアウトによる自動停止
- [ ] エラーレスポンスの形式・内容

---

### リファクタリング後の構造 (完了)

```
tests/
├── conftest.py                  # 共通 Fixture
├── fixtures/                    # テスト用リソース (旧 e2e/)
│   ├── config/                  # 自動生成設定 (git管理外)
│   ├── functions/               # テスト用 Lambda 関数
│   ├── generator.yml
│   └── template.yaml
├── test_gateway_basics.py       # A. Gateway 基本機能
├── test_lambda_invoke.py        # B. Lambda 呼び出し
├── test_aws_compat.py           # C. AWS サービス互換
├── test_observability.py        # D. ロギング・オブザーバビリティ
├── test_resilience.py           # E. 耐障害性・パフォーマンス
└── run_tests.py
```

tools/cli/tests/                 # CLI ユニットテスト (移動済み)
├── test_cert.py
├── test_up.py
└── ...

---

## 完了したアクション

1. [x] リファクタリング案の計画
2. [x] `tests/e2e` を `tests/fixtures` にリネーム
3. [x] CLI テストを `tests/unit` から `tools/cli/tests` に移動
4. [x] 共通 Fixture の抽出 (`conftest.py`)
5. [x] テストファイルの分割
    - `test_gateway_basics.py`
    - `test_lambda_invoke.py`
    - `test_aws_compat.py`
    - `test_observability.py`
    - `test_resilience.py`
6. [x] 全テストのパス確認
