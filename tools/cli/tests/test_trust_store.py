import pytest
from unittest.mock import patch, MagicMock
from tools.cli.core import trust_store


class TestTrustStore:
    @pytest.fixture
    def ca_cert_path(self, tmp_path):
        path = tmp_path / "rootCA.crt"
        path.touch()
        return path

    @patch("platform.system")
    @patch("subprocess.run")
    def test_install_root_ca_windows(self, mock_run, mock_system, ca_cert_path):
        """WindowsでのCA登録（冪等性チェック含む）をテスト"""
        mock_system.return_value = "Windows"
        # 1回目(チェック): 1(未登録), 2回目(登録): 0(成功)
        mock_run.side_effect = [
            MagicMock(returncode=1),  # Not found
            MagicMock(returncode=0),  # Install success
        ]

        trust_store.install_root_ca(ca_cert_path)

        assert mock_run.call_count == 2
        # 1回目のチェックコマンドを確認
        args_check = mock_run.call_args_list[0][0][0]
        assert "-verifystore" in args_check
        assert "ESB Root CA" in args_check

        # 2回目の登録コマンドを確認
        args_install = mock_run.call_args_list[1][0][0]
        assert "-addstore" in args_install
        assert str(ca_cert_path) in args_install

    @patch("platform.system")
    @patch("subprocess.run")
    def test_install_root_ca_macos(self, mock_run, mock_system, ca_cert_path):
        """macOSでのCA登録（冪等性チェック含む）をテスト"""
        mock_system.return_value = "Darwin"
        mock_run.side_effect = [
            MagicMock(returncode=1),  # Not found
            MagicMock(returncode=0),  # Install success
        ]

        trust_store.install_root_ca(ca_cert_path)

        assert mock_run.call_count == 2
        # 1回目のチェック
        args_check = mock_run.call_args_list[0][0][0]
        assert "find-certificate" in args_check
        assert "ESB Root CA" in args_check

        # 2回目の登録
        args_install = mock_run.call_args_list[1][0][0]
        assert "add-trusted-cert" in args_install

    @patch("platform.system")
    @patch("subprocess.run")
    def test_install_root_ca_linux(self, mock_run, mock_system, ca_cert_path):
        """LinuxでのCA登録コマンド実行をテスト"""
        mock_system.return_value = "Linux"
        mock_run.return_value = MagicMock(returncode=0)

        # モックの動作をシミュレート
        with patch("pathlib.Path.exists", return_value=True):
            trust_store.install_root_ca(ca_cert_path)

            # cp と update-ca-certificates の2回呼ばれることを確認
            assert mock_run.call_count == 2
            args_cp = mock_run.call_args_list[0][0][0]
            args_update = mock_run.call_args_list[1][0][0]
            assert "cp" in args_cp
            assert "update-ca-certificates" in args_update
