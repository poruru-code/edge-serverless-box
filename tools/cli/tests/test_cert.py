import pytest
from cryptography import x509
from tools.cli.core import cert


class TestCertGeneration:
    @pytest.fixture
    def cert_dir(self, tmp_path):
        """Mock directory for certificates"""
        return tmp_path / "certs"

    def test_ensure_certs_creates_all_files(self, cert_dir):
        """Root CAとサーバー証明書が生成されることをテスト"""
        cert.ensure_certs(cert_dir)

        assert (cert_dir / "rootCA.crt").exists()
        assert (cert_dir / "rootCA.key").exists()
        assert (cert_dir / "server.crt").exists()
        assert (cert_dir / "server.key").exists()

        # 証明書の内容を確認
        with open(cert_dir / "server.crt", "rb") as f:
            server_cert = x509.load_pem_x509_certificate(f.read())
        with open(cert_dir / "rootCA.crt", "rb") as f:
            ca_cert = x509.load_pem_x509_certificate(f.read())

        # Root CAの名称確認
        assert "ESB Root CA" in str(ca_cert.subject)

        # 署名関係を確認
        assert server_cert.issuer == ca_cert.subject

        # SANの確認
        san = server_cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        dns_names = san.get_values_for_type(x509.DNSName)
        assert "localhost" in dns_names
        assert "esb-registry" in dns_names

    def test_ensure_certs_skips_ca_if_exists(self, cert_dir):
        """Root CAが既に存在する場合、再生成されないことをテスト"""
        cert_dir.mkdir(parents=True)
        ca_cert_path, ca_key_path = cert.generate_root_ca(cert_dir)

        import os

        orig_mtime = os.path.getmtime(ca_cert_path)

        # 少し待機してから再実行
        import time

        time.sleep(0.01)

        cert.ensure_certs(cert_dir)

        # mtimeが変わっていない＝再生成されていない
        assert os.path.getmtime(ca_cert_path) == orig_mtime

    def test_ensure_certs_skips_server_cert_if_newer(self, cert_dir):
        """サーバー証明書がCAより新しい場合、再生成されないことをテスト"""
        cert.ensure_certs(cert_dir)
        server_cert_path = cert_dir / "server.crt"

        import os

        orig_mtime = os.path.getmtime(server_cert_path)

        import time

        time.sleep(0.01)

        cert.ensure_certs(cert_dir)
        assert os.path.getmtime(server_cert_path) == orig_mtime
