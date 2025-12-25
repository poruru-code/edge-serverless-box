#!/usr/bin/env python3
"""
SAM Template Generator

SAMテンプレートからローカル実行用のDockerfileとfunctions.ymlを生成します。

Usage:
    python -m tools.generator.main [options]

Options:
    --config PATH       Generator config path (default: tools/generator/generator.yml)
    --template PATH     SAM template path (overrides config)
    --dry-run           Show what would be generated without writing files
    --verbose           Verbose output
"""

import argparse
import sys
import shutil
import zipfile
import yaml
from pathlib import Path


from .parser import parse_sam_template
from .renderer import render_dockerfile, render_functions_yml, render_routing_yml


def load_config(config_path: Path) -> dict:
    """設定ファイルをロード"""
    if not config_path.exists():
        return {}

    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def generate_files(
    config: dict,
    project_root: Path | None = None,
    dry_run: bool = False,
    verbose: bool = False,
) -> list:
    """
    SAMテンプレートからファイルを生成

    Args:
        config: ジェネレータ設定
        project_root: プロジェクトルート（デフォルト: カレントディレクトリ）
        dry_run: Trueの場合、ファイルを書き込まずに表示のみ
        verbose: 詳細出力
    """
    if project_root is None:
        project_root = Path.cwd()

    paths = config.get("paths", {})
    docker_config = config.get("docker", {})
    # Set default sitecustomize_source if not configured
    if "sitecustomize_source" not in docker_config:
        docker_config["sitecustomize_source"] = "tools/generator/runtime/site-packages/sitecustomize.py"

    # SAMテンプレートを読み込み
    # sam_template パスが絶対パスならそのまま、相対なら project_root から
    sam_template_path = Path(paths.get("sam_template", "template.yaml"))
    if not sam_template_path.is_absolute():
        sam_template_path = (project_root / sam_template_path).resolve()
    
    if not sam_template_path.exists():
        raise FileNotFoundError(f"SAM template not found: {sam_template_path}")

    # 基準ディレクトリ（これ以降の相対パスの起点）をテンプレートの親ディレクトリとする
    base_dir = sam_template_path.parent

    if verbose:
        print(f"Loading SAM template: {sam_template_path}")
        print(f"Base directory for resolution: {base_dir}")

    with open(sam_template_path, encoding="utf-8") as f:
        sam_content = f.read()

    # パラメータ置換設定
    parameters = config.get("parameters", {})

    # パース
    parsed = parse_sam_template(sam_content, parameters)
    functions = parsed["functions"]

    if verbose:
        print(f"Found {len(functions)} function(s)")

    import shutil

    # 出力ディレクトリ (base_dir 相対)
    output_dir_raw = Path(paths.get("output_dir", ".esb/"))
    if not output_dir_raw.is_absolute():
        output_dir = (base_dir / output_dir_raw).resolve()
    else:
        output_dir = output_dir_raw

    functions_staging_dir = output_dir / "functions"

    if not dry_run and functions_staging_dir.exists():
        if verbose:
            print(f"Cleaning up staging directory: {functions_staging_dir}")
        shutil.rmtree(functions_staging_dir)

    def _resolve_resource_path(p: str) -> Path:
        """テンプレートファイルからの相対パスを解決する"""
        # Leading slash がある場合も取り除いて、テンプレート（base_dir）相対として扱う
        path_str = p.lstrip("/")
        target = (base_dir / path_str).resolve()
        if not target.exists():
            if verbose:
                print(f"WARNING: Resource not found at: {target}")
        return target

    # 各関数のDockerfileを生成
    for func in functions:
        func_name = func["name"]
        code_uri = func["code_uri"]

        # 1. Staging Directory の準備 (<output_dir>/functions/<func_name>)
        dockerfile_dir = functions_staging_dir / func_name
        dockerfile_dir.mkdir(parents=True, exist_ok=True)

        # 2. ソースコードのコピー (Staging内)
        func_src_dir = _resolve_resource_path(code_uri)
        staging_src_dir = dockerfile_dir / "src"
        if func_src_dir.exists() and func_src_dir.is_dir():
            shutil.copytree(func_src_dir, staging_src_dir, dirs_exist_ok=True)
        
        # RendererにはStaging内での相対パスを伝える
        func["code_uri"] = "src/"
        func["dockerfile_path"] = str(dockerfile_dir / "Dockerfile")
        func["context_path"] = str(dockerfile_dir)

        # 3. レイヤーのコピー (Staging内)
        new_layers = []
        for layer in func.get("layers", []):
            # 元のオブジェクトを壊さないようにコピー
            layer_copy = layer.copy()
            content_uri = layer_copy.get("content_uri", "")
            if not content_uri:
                continue
                
            layer_src = _resolve_resource_path(content_uri)
            
            if layer_src.exists():
                target_name = layer_src.name
                layers_dir = dockerfile_dir / "layers"
                layers_dir.mkdir(parents=True, exist_ok=True)
                
                # レイヤーごとのディレクトリ: layers/<layer_name>/
                # unzip する場合もディレクトリごとする場合も、最終的にここ以下に配置する
                staging_layer_root = layers_dir / target_name
                # 一度クリーンアップ (念のため)
                if staging_layer_root.exists():
                    shutil.rmtree(staging_layer_root)
                staging_layer_root.mkdir(parents=True, exist_ok=True)

                if layer_src.is_file() and layer_src.suffix == '.zip':
                    # Zipファイルの場合は展開して配置
                    if verbose:
                        print(f"Unzipping layer: {layer_src} -> {staging_layer_root}")
                    with zipfile.ZipFile(layer_src, 'r') as zip_ref:
                        zip_ref.extractall(staging_layer_root)
                    
                    # Dockerfileにはディレクトリとして渡す
                    layer_copy["content_uri"] = f"layers/{target_name}"

                elif layer_src.is_dir():
                    # ディレクトリの場合はそのままコピー
                    if verbose:
                        print(f"Copying layer directory: {layer_src} -> {staging_layer_root}")
                    # staging_layer_root は既に作ったので、中身をコピーするために一度消して copytree するか、
                    # あるいは dirs_exist_ok=True でコピーする
                    shutil.copytree(layer_src, staging_layer_root, dirs_exist_ok=True)
    
                    layer_copy["content_uri"] = f"layers/{target_name}"
                
                else:
                    if verbose:
                        print(f"WARNING: Skipping unsupported layer type: {layer_src}")
                    continue

                new_layers.append(layer_copy)
        
        # この関数専用の、ローカルパスに書き換えたレイヤーリスト
        func["layers"] = new_layers


        # 4. sitecustomize.py のコピー
        # sitecustomize_source も base_dir 相対で解決を試み、なければプロジェクトルート相対
        site_path_raw = Path(docker_config.get("sitecustomize_source"))
        if not site_path_raw.is_absolute():
            site_src = (base_dir / site_path_raw).resolve()
            if not site_src.exists():
                # フォールバック: プロジェクトルート (generatorパッケージ内のデフォルト等)
                site_src = (project_root / site_path_raw).resolve()
        else:
            site_src = site_path_raw

        if verbose:
            print(f"DEBUG: site_src={site_src}, exists={site_src.exists()}")
        if site_src.exists():
            shutil.copy2(site_src, dockerfile_dir / "sitecustomize.py")
        else:
            if verbose:
                print(f"WARNING: sitecustomize.py not found at {site_src}")
        # Dockerfile内からは直下を参照するように上書き
        docker_config_copy = docker_config.copy()
        docker_config_copy["sitecustomize_source"] = "sitecustomize.py"

        # requirements.txt の存在チェック (context内)
        func["has_requirements"] = (staging_src_dir / "requirements.txt").exists()

        # Dockerfileをレンダリング
        dockerfile_content = render_dockerfile(func, docker_config_copy)

        if dry_run:
            print(f"\n📄 [DryRun] Staging: {dockerfile_dir} (Source: {func_src_dir})")
            print("-" * 60)
            print(dockerfile_content.strip())
            print("-" * 60)
        else:
            if verbose:
                print(f"Staging build files: {dockerfile_dir}")
            dockerfile_path = dockerfile_dir / "Dockerfile"
            with open(dockerfile_path, "w", encoding="utf-8") as f:
                f.write(dockerfile_content)

    # functions.yml を生成 (base_dir 相対、未指定なら output_dir/config/ 配下)
    functions_yml_raw = paths.get("functions_yml")
    if functions_yml_raw:
        functions_yml_path_raw = Path(functions_yml_raw)
        if not functions_yml_path_raw.is_absolute():
            functions_yml_path = (base_dir / functions_yml_path_raw).resolve()
        else:
            functions_yml_path = functions_yml_path_raw
    else:
        # デフォルト規約: output_dir/config/functions.yml
        functions_yml_path = output_dir / "config" / "functions.yml"

    functions_yml_content = render_functions_yml(functions)

    if dry_run:
        print(f"\n📄 [DryRun] Target: {functions_yml_path}")
        print("-" * 60)
        print(functions_yml_content.strip())
        print("-" * 60)
    else:
        if verbose:
            print(f"Generating: {functions_yml_path}")
        functions_yml_path.parent.mkdir(parents=True, exist_ok=True)
        with open(functions_yml_path, "w", encoding="utf-8") as f:
            f.write(functions_yml_content)

    # routing.yml を生成 (base_dir 相対、未指定なら output_dir/config/ 配下)
    routing_yml_raw = paths.get("routing_yml")
    if routing_yml_raw:
        routing_yml_path_raw = Path(routing_yml_raw)
        if not routing_yml_path_raw.is_absolute():
            routing_yml_path = (base_dir / routing_yml_path_raw).resolve()
        else:
            routing_yml_path = routing_yml_path_raw
    else:
        # デフォルト規約: output_dir/config/routing.yml
        routing_yml_path = output_dir / "config" / "routing.yml"
    
    routing_yml_content = render_routing_yml(functions)

    if dry_run:
        print(f"\n📄 [DryRun] Target: {routing_yml_path}")
        print("-" * 60)
        print(routing_yml_content.strip())
        print("-" * 60)
    else:
        if verbose:
            print(f"Generating: {routing_yml_path}")
        routing_yml_path.parent.mkdir(parents=True, exist_ok=True)
        with open(routing_yml_path, "w", encoding="utf-8") as f:
            f.write(routing_yml_content)

    if not dry_run:
        print(f"Generated {len(functions)} Dockerfile(s), functions.yml, and routing.yml")
    
    return functions


def main():
    parser = argparse.ArgumentParser(description="Generate local Docker files from SAM template")
    parser.add_argument(
        "--config", default="tools/generator/generator.yml", help="Generator config path"
    )
    parser.add_argument("--template", help="SAM template path (overrides config)")
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be generated without writing files"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    # 設定を読み込み
    config_path = Path(args.config)
    config = load_config(config_path)

    # コマンドラインオプションで上書き
    if args.template:
        if "paths" not in config:
            config["paths"] = {}
        config["paths"]["sam_template"] = args.template

    try:
        generate_files(
            config,
            dry_run=args.dry_run,
            verbose=args.verbose,
        )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
