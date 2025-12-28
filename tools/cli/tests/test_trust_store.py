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
        """WindowsでのCA登録コマンド実行をテスト"""
        mock_system.return_value = "Windows"
        mock_run.return_value = MagicMock(returncode=0)
        
        trust_store.install_root_ca(ca_cert_path)
        
        # Windowsのコマンドが呼ばれたことを確認
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "certutil" in args
        assert "-addstore" in args
        assert str(ca_cert_path) in args

    @patch("platform.system")
    @patch("subprocess.run")
    def test_install_root_ca_macos(self, mock_run, mock_system, ca_cert_path):
        """macOSでのCA登録コマンド実行をテスト"""
        mock_system.return_value = "Darwin"
        mock_run.return_value = MagicMock(returncode=0)
        
        trust_store.install_root_ca(ca_cert_path)
        
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "security" in args
        assert "add-trusted-cert" in args

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
