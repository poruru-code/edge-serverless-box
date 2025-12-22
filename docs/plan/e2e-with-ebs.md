### 📅 実装計画概要

---

### Phase 1: CLI (`tools/cli`) の機能強化

テストランナーが依存している「環境構築ロジック」を CLI に吸収させます。

#### Step 1: SSL証明書生成のコアロジック化

現在 `run_tests.py` にある証明書生成ロジック を、CLI のコアモジュールとして独立させます。

**作成:** `tools/cli/core/cert.py`
`tests/run_tests.py` の `generate_ssl_certificate` 関数を移植します。

```python
import socket
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import ipaddress

# プロジェクトルートの解決ロジックが必要（config.py等からimport推奨）
from tools.cli.config import PROJECT_ROOT 

logger = logging.getLogger(__name__)

def generate_ssl_certificate():
    """自己署名SSL証明書を生成 (run_tests.pyから移植)"""
    certs_dir = PROJECT_ROOT / "certs"
    cert_file = certs_dir / "server.crt"
    key_file = certs_dir / "server.key"

    if cert_file.exists() and key_file.exists():
        logger.debug("Using existing SSL certificates")
        return

    logger.info("Generating self-signed SSL certificate...")
    # ... (run_tests.py の generate_ssl_certificate の中身をここに配置) ...
    # 証明書保存処理

```

#### Step 2: `up` コマンドへの統合と待機オプション追加

`esb up` コマンド実行時に、自動的に証明書を確認し、オプションで起動完了を待てるようにします。

**変更:** `tools/cli/commands/up.py`

1. **SSL生成の呼び出し:** `run` 関数または `up_cmd` 関数の冒頭で `tools.cli.core.cert.generate_ssl_certificate()` を呼び出します。
2. **`--wait` オプションの追加:** `argparse` に引数を追加し、有効な場合はヘルスチェックを実行します。

```python
import time
import requests
from tools.cli.core import logging
from tools.cli.core.cert import generate_ssl_certificate # 追加

def wait_for_gateway(timeout=60):
    """Gatewayが応答するまで待機"""
    start_time = time.time()
    url = "https://localhost/health" # ポートは設定から取得推奨だが、一旦固定または環境変数
    
    logging.step("Waiting for Gateway...")
    while time.time() - start_time < timeout:
        try:
            # verify=False で自己署名証明書を許容
            if requests.get(url, verify=False, timeout=1).status_code == 200:
                logging.success("Gateway is ready!")
                return True
        except Exception:
            time.sleep(1)
    
    logging.error("Gateway failed to start.")
    return False

def up_cmd(args):
    # 1. 証明書生成
    generate_ssl_certificate()

    # ... (既存の docker compose up ロジック) ...

    # 2. 待機ロジック
    if getattr(args, "wait", False):
        if not wait_for_gateway():
            exit(1)

def run(args):
    # parser setup ...
    parser.add_argument("--wait", action="store_true", help="Wait for services to be ready")
    # ...

```

---

### Phase 2: `tests/run_tests.py` の完全リファクタリング

CLI側の準備が整い次第、`run_tests.py` を軽量なラッパーに書き換えます。

**方針:**

* 自前のビルド・起動・SSLロジックは全削除。
* 環境変数 `ESB_TEMPLATE` をセットすることで、CLI (`config.py`) に「テスト用の設定」を読み込ませる。
* 環境変数 `COMPOSE_FILE` をセットして、テスト用の `docker-compose.test.yml` を読み込ませる。

**修正後の `tests/run_tests.py`:**

```python
#!/usr/bin/env python3
import argparse
import os
import sys
import subprocess
from pathlib import Path

# プロジェクトルート
PROJECT_ROOT = Path(__file__).parent.parent.resolve()

def run_esb(args: list[str], check: bool = True):
    """esb CLIを実行するヘルパー"""
    # インストール済みコマンドではなく、現在のソースコードを使用
    cmd = [sys.executable, "-m", "tools.cli.main"] + args
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, cwd=PROJECT_ROOT, check=check)

def main():
    parser = argparse.ArgumentParser(description="E2E Test Runner (ESB CLI Wrapper)")
    parser.add_argument("--build", action="store_true", help="Rebuild images before running")
    parser.add_argument("--cleanup", action="store_true", help="Stop containers after tests")
    parser.add_argument("--reset", action="store_true", help="Full reset before running")
    
    args = parser.parse_args()

    # --- 環境設定 ---
    env = os.environ.copy()
    
    # 1. ESB_TEMPLATE: CLIにテスト用テンプレート (tests/e2e/template.yaml) を認識させる
    # これにより build コマンドなどが自動的にテスト用Lambdaを対象にする
    env["ESB_TEMPLATE"] = str(PROJECT_ROOT / "tests" / "e2e" / "template.yaml")

    # 2. COMPOSE_FILE: テスト用定義をマージする
    # Windows/Linuxで区切り文字が異なるため注意
    separator = ";" if os.name == "nt" else ":"
    compose_files = [
        "docker-compose.yml", 
        "tests/docker-compose.test.yml"
    ]
    env["COMPOSE_FILE"] = separator.join(compose_files)
    
    # 子プロセス実行用に環境変数を適用
    os.environ.update(env)

    try:
        # --- ステップ実行 ---

        # 1. Reset (任意)
        if args.reset:
            run_esb(["reset"])

        # 2. Build (任意)
        # ESB_TEMPLATE が効いているため、自動的にテスト用Lambdaがビルドされる
        if args.build or args.reset:
            run_esb(["build"])

        # 3. Up
        # 証明書生成は内部で行われ、--waitで起動完了までブロックする
        run_esb(["up", "--detach", "--wait"])

        # 4. Run Tests (Pytest)
        print("\n=== Running E2E Tests ===\n")
        # pytest実行時は環境変数(COMPOSE_FILE等)が渡った状態で実行される
        pytest_cmd = [sys.executable, "-m", "pytest", "tests/test_e2e.py", "-v"]
        result = subprocess.run(pytest_cmd, cwd=PROJECT_ROOT, check=False)

        if result.returncode != 0:
            print("\n❌ Tests failed.")
            sys.exit(result.returncode)
            
        print("\n🎉 Tests passed successfully!")

    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {e}")
        sys.exit(1)
        
    finally:
        # 5. Cleanup
        if args.cleanup:
            # downコマンドも COMPOSE_FILE を参照して正しく終了させる
            run_esb(["down"])

if __name__ == "__main__":
    sys.exit(main())

```

---

### ✅ 検証手順

リファクタリング適用後、以下の手順で動作を確認してください。

1. **CLIの単体動作確認:**
```bash
# テスト用テンプレートを指定してビルドできるか
export ESB_TEMPLATE=$(pwd)/tests/e2e/template.yaml
python -m tools.cli.main build
# -> tests/e2e/functions 以下のLambdaがビルドされればOK

```


2. **テストランナーの動作確認:**
```bash
# フル実行
python tests/run_tests.py --reset --cleanup

```


* `esb reset` -> `esb build` -> `esb up --wait` -> `pytest` -> `esb down` の順に実行されることを確認。
* `certs/` ディレクトリに証明書が生成されていることを確認。



この計画により、`run_tests.py` は環境構築の複雑さから解放され、将来的なCLIの機能追加（ログ閲覧機能の強化など）の恩恵を自動的に受けられるようになります。