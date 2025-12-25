from unittest.mock import patch, MagicMock
from tools.cli.commands.build import run


@patch("tools.cli.commands.build.build_function_images")
@patch("tools.cli.commands.build.build_base_image")
@patch("tools.cli.commands.build.generator.generate_files")
@patch("tools.cli.commands.build.generator.load_config")
def test_build_command_flow(mock_load_config, mock_generate_files, mock_build_base, mock_build_funcs):
    """build コマンドが Generator と Docker ビルドを正しく呼び出すか確認"""
    # Mock setup
    mock_load_config.return_value = {"app": {"name": "", "tag": "latest"}, "paths": {}}
    mock_generate_files.return_value = [{"name": "test-func", "dockerfile_path": "/path/to/Dockerfile"}]
    mock_build_base.return_value = True

    # テスト用のダミー引数 - dry_run を False に設定
    args = MagicMock()
    args.dry_run = False
    args.verbose = False
    args.no_cache = True

    # 実行
    run(args)

    # 1. Generator が呼ばれたか
    mock_generate_files.assert_called_once()

    # 2. ベースイメージビルドが呼ばれたか
    mock_build_base.assert_called_once()

    # 3. 関数イメージビルドが呼ばれたか
    mock_build_funcs.assert_called_once()
