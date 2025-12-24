from unittest.mock import patch, MagicMock
from tools.cli.commands.reset import run as run_reset


@patch("builtins.input")
@patch("tools.cli.commands.reset.down.run")
@patch("tools.cli.commands.reset.up.run")
def test_reset_command_cancel(mock_up, mock_down, mock_input):
    """reset コマンドで 'n' を入力した時に中止されるか確認"""
    mock_input.return_value = "n"
    args = MagicMock()
    args.yes = False  # --yes フラグを明示的に False に設定

    run_reset(args)

    # down も up も呼ばれないはず
    mock_down.assert_not_called()
    mock_up.assert_not_called()


@patch("builtins.input")
@patch("tools.cli.commands.reset.down.run")
@patch("tools.cli.commands.reset.up.run")
def test_reset_command_proceed(mock_up, mock_down, mock_input):
    """reset コマンドで 'y' を入力した時に down -v と up --build が呼ばれるか確認"""
    mock_input.return_value = "y"
    args = MagicMock()
    args.yes = False

    run_reset(args)

    # 1. down.run(volumes=True) が呼ばれたか
    mock_down.assert_called_once()
    called_down_args = mock_down.call_args[0][0]
    assert called_down_args.volumes is True

    # 2. up.run(build=True, detach=True) が呼ばれたか
    mock_up.assert_called_once()
    called_up_args = mock_up.call_args[0][0]
    assert called_up_args.build is True
