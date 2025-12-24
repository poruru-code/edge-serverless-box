import logging
import socket
from datetime import datetime, timedelta, timezone

from cryptography import x509
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import ipaddress

from tools.cli.config import PROJECT_ROOT

logger = logging.getLogger(__name__)

SSL_CERT_VALIDITY_DAYS = 365
SSL_KEY_SIZE = 4096


def get_local_ip() -> str:
    """ローカルIPアドレスを取得"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def generate_ssl_certificate():
    """自己署名SSL証明書を生成"""
    certs_dir = PROJECT_ROOT / "certs"
    cert_file = certs_dir / "server.crt"
    key_file = certs_dir / "server.key"

    if cert_file.exists() and key_file.exists():
        logger.debug("Using existing SSL certificates")
        return

    logger.info("Generating self-signed SSL certificate with SAN...")

    # RSA秘密鍵を生成
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=SSL_KEY_SIZE,
    )

    # SAN (Subject Alternative Name) を構築
    hostname = socket.gethostname()
    local_ip = get_local_ip()

    san_list = [
        x509.DNSName("localhost"),
        x509.DNSName(hostname),
        x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
    ]

    # ローカルIPが127.0.0.1でなければ追加
    if local_ip != "127.0.0.1":
        san_list.append(x509.IPAddress(ipaddress.IPv4Address(local_ip)))

    # 証明書を構築
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "JP"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Tokyo"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "Minato"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Development"),
            x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
        ]
    )

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=SSL_CERT_VALIDITY_DAYS))
        .add_extension(
            x509.SubjectAlternativeName(san_list),
            critical=False,
        )
        .add_extension(
            x509.BasicConstraints(ca=False, path_length=None),
            critical=True,
        )
        .add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),
            critical=False,
        )
        .sign(private_key, hashes.SHA256())
    )

    # ディレクトリ作成
    certs_dir.mkdir(parents=True, exist_ok=True)

    # 証明書を保存
    with open(cert_file, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    # 秘密鍵を保存
    with open(key_file, "wb") as f:
        f.write(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )

    logger.info(f"Certificate saved to: {cert_file}")
