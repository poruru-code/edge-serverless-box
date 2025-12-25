from pathlib import Path


import os


def find_project_root(current_path: Path = None) -> Path:
    """pyproject.toml を探してプロジェクトルートを特定する"""
    if current_path is None:
        current_path = Path.cwd()

    for path in [current_path] + list(current_path.parents):
        if (path / "pyproject.toml").exists():
            return path

    return Path(__file__).parent.parent.parent.resolve()


PROJECT_ROOT = find_project_root()
TOOLS_DIR = PROJECT_ROOT / "tools"
GENERATOR_DIR = TOOLS_DIR / "generator"
PROVISIONER_DIR = TOOLS_DIR / "provisioner"


def _resolve_template_yaml() -> Path:
    """テンプレートパスを解決する（デフォルト探索）"""
    # パス優先順位:
    # 1. 環境変数 ESB_TEMPLATE
    # 2. カレントディレクトリの template.yaml
    # 3. プロジェクトルート直下の template.yaml
    # 4. tests/fixtures/template.yaml (デフォルト)
    env_template = os.environ.get("ESB_TEMPLATE")
    if env_template:
        return Path(env_template).resolve()
    elif (Path.cwd() / "template.yaml").exists():
        return Path.cwd() / "template.yaml"
    elif (PROJECT_ROOT / "template.yaml").exists():
        return PROJECT_ROOT / "template.yaml"
    else:
        return PROJECT_ROOT / "tests" / "fixtures" / "template.yaml"


# デフォルト値で初期化
TEMPLATE_YAML = _resolve_template_yaml()
E2E_DIR = TEMPLATE_YAML.parent
DEFAULT_ROUTING_YML = E2E_DIR / "config" / "routing.yml"
DEFAULT_FUNCTIONS_YML = E2E_DIR / "config" / "functions.yml"


def set_template_yaml(template_path: str) -> None:
    """CLI引数からテンプレートパスを設定する（最優先）"""
    global TEMPLATE_YAML, E2E_DIR, DEFAULT_ROUTING_YML, DEFAULT_FUNCTIONS_YML
    TEMPLATE_YAML = Path(template_path).resolve()
    E2E_DIR = TEMPLATE_YAML.parent
    DEFAULT_ROUTING_YML = E2E_DIR / "config" / "routing.yml"
    DEFAULT_FUNCTIONS_YML = E2E_DIR / "config" / "functions.yml"
