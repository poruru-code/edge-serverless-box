import os
import sys
import yaml
import subprocess
from . import build
from tools.provisioner import main as provisioner
from tools.cli import config as cli_config
from tools.cli.config import PROJECT_ROOT
from dotenv import load_dotenv


from tools.cli.core import logging
from tools.cli.core.cert import ensure_certs
import time
import requests


def wait_for_gateway(timeout=60):
    """Gatewayが応答するまで待機"""
    start_time = time.time()
    # 実際にはCLIからは動的に取得するべきだが、テスト環境ではlocalhost:443 (Gateway) を想定
    # config.py から取得するか、デフォルト値を使用
    url = "https://localhost/health"

    logging.step("Waiting for Gateway...")
    while time.time() - start_time < timeout:
        try:
            # verify=False で自己署名証明書を許容
            if requests.get(url, verify=False, timeout=1).status_code == 200:
                logging.success("Gateway is ready!")
                return True
        except Exception:
            time.sleep(1)
            # 進捗表示としてドットを出すのはloggingの仕様次第だが、ここではシンプルに待機

    logging.error("Gateway failed to start.")
    return False


def run(args):
    # 0. SSL証明書の準備
    ensure_certs(PROJECT_ROOT / "certs")

    # .env.test の読み込み (run_tests.py と同様)
    env_file = PROJECT_ROOT / "tests" / ".env.test"
    if env_file.exists():
        logging.info(f"Loading environment variables from {logging.highlight(env_file)}")
        load_dotenv(env_file, override=False)

    # 1. カスタム設定の反映 (generator.yml があればパスを環境変数にセット)
    config_path = cli_config.E2E_DIR / "generator.yml"
    if config_path.exists():
        try:
            with open(config_path, "r") as f:
                config = yaml.safe_load(f)

            paths = config.get("paths", {})
            if "functions_yml" in paths:
                os.environ["GATEWAY_FUNCTIONS_YML"] = str(paths["functions_yml"])
            if "routing_yml" in paths:
                os.environ["GATEWAY_ROUTING_YML"] = str(paths["routing_yml"])
        except Exception as e:
            logging.warning(f"Failed to load generator.yml for environment injection: {e}")

    # 2. ビルド要求があれば実行
    if getattr(args, "build", False):
        build.run(args)

    # 2. サービス起動
    logging.step("Starting services...")
    cmd = ["docker", "compose", "up"]
    if getattr(args, "detach", True):
        cmd.append("-d")

    # サービス自体の再ビルドも行う
    if getattr(args, "build", False):
        cmd.append("--build")

    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to start services: {e}")
        sys.exit(1)

    # 3. インフラプロビジョニング
    logging.step("Preparing infrastructure...")
    from tools.cli.config import TEMPLATE_YAML

    provisioner.main(template_path=TEMPLATE_YAML)

    logging.success("Environment is ready! (https://localhost:443)")

    # 4. 待機ロジック (オプション)
    if getattr(args, "wait", False):
        if not wait_for_gateway():
            sys.exit(1)
