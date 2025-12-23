# Test Fixture Organization Strategy

ユーザー様からの「1関数にまとめるイメージがつかない」「管理工数とのトレードオフ」という疑問に対して、具体的なコード例と共に比較をまとめました。

## 現状の課題
現在、テスト用関数が5つ (`hello`, `invoke`, `s3`, `scylla`, `faulty`) あります。
これらはそれぞれ個別の `Dockerfile` を持ち、個別にビルド（`docker build`）され、個別のコンテナとして起動します。

*   **課題**: テストが増えるたびにコンテナ起動数が増え、E2Eテストの実行時間（特にコールドスタート待ち）とリソース消費が増大します。

---

## 比較: 独立型 vs 統合型

### パターンA: 独立型 (現状維持) - "1 Case = 1 Function"

テストケースごとに専用のLambda関数を用意します。

*   **ファイル構成**:
    ```
    functions/
      ├── s3-test/       # S3テスト専用
      ├── scylla-test/   # DBテスト専用
      └── faulty/        # エラーテスト専用
    ```
*   **メリット**:
    *   コードが単純明快。`if` 分岐が不要。
    *   `template.yaml` を見ればどの関数が何をするか一目瞭然。
*   **デメリット**:
    *   ビルド時間が長い (5回のビルド)。
    *   コンテナが多い。

### パターンB: 統合型 (推奨案) - "1 Capability = Many Cases"

「結合テスト用便利関数」として1つにまとめ、引数 (`action`) で振る舞いを切り替えます。

*   **ファイル構成**:
    ```
    functions/
      ├── integration-func/  # 統合テスト用万能関数
      └── chaos-func/        # 異常系用関数 (必要なら分ける)
    ```

*   **コードイメージ (`integration-func/lambda_function.py`)**:
    ```python
    from common.utils import handle_ping
    import s3_logic      # 内部でモジュール分けすれば管理も楽
    import scylla_logic

    def lambda_handler(event, context):
        if handle_ping(event): return ...
        
        # Actionによってディスパッチ（分岐）する
        action = event.get("body", {}).get("action")
        
        if action == "s3-put":
            return s3_logic.put(event)
        elif action == "scylla-get":
            return scylla_logic.get(event)
        elif action == "invoke":
            return invoke_logic.run(event)
        else:
            return {"error": "unknown action"}
    ```

*   **テストコード側 (`test_aws_compat.py`) のイメージ**:
    ```python
    # テストケースはPython側で分けるので、管理は明確なままです
    
    def test_s3_upload():
        # 同じ関数に対して、アクション指定で呼び出す
        invoke("integration-func", {"action": "s3-put", "data": "..."})

    def test_dynamo_check():
        invoke("integration-func", {"action": "scylla-get", "id": "..."})
    ```

*   **メリット**:
    *   **ビルドが1回で済む**。
    *   コンテナが1つ（または少数）で済むため、リソース効率が良い。
*   **デメリット**:
    *   Lambda関数内に分岐ロジックが必要（ただしモジュール分割で綺麗に保てる）。

---

## 私の推奨と次のステップ

**結論**: `s3`, `scylla`, `invoke` は、依存ライブラリ（boto3）が同じであり、統合コストが低いため **「統合」** を推奨します。`faulty` や `hello` は特殊性が高いため、そのままでも構いません。

**提案するアクション**:
今回は、「大幅な統合」までは行わず、まずは **「現状維持（独立型）」のまま進める** のが良いかもしれません。
理由：
1.  リファクタリングによりコード重複は既に `common` で解消されている。
2.  Pythonのビルドは比較的高速。
3.  ユーザー様が「イメージがつかない」と感じている状態で無理に統合すると、後のメンテナンスが不安になる。

まずは現状のリファクタリング（Layer導入）で良しとし、**「ビルド時間が遅すぎる」という問題が顕在化した時点で統合を検討する** という進め方はいかがでしょうか？
