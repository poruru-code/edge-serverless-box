import platform
import subprocess
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def install_root_ca(ca_cert_path: Path):
    """OSのトラストストアにRoot CAを登録する"""
    system = platform.system()
    ca_cert_path = ca_cert_path.resolve()

    if not ca_cert_path.exists():
        raise FileNotFoundError(f"Root CA cert not found at {ca_cert_path}")

    logger.info(f"Installing Root CA to {system} trust store...")

    try:
        if system == "Windows":
            # Windows: certutilを使用
            # Trusted Root Certification Authorities (Root) に追加
            cmd = ["certutil", "-addstore", "-f", "Root", str(ca_cert_path)]
            subprocess.run(cmd, check=True, capture_output=True)
            
        elif system == "Darwin":
            # macOS: securityを使用
            cmd = [
                "sudo", "security", "add-trusted-cert",
                "-d", "-r", "trustRoot",
                "-k", "/Library/Keychains/System.keychain",
                str(ca_cert_path)
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            
        elif system == "Linux":
            # Linux: update-ca-certificatesを使用
            dest_dir = Path("/usr/local/share/ca-certificates")
            if not dest_dir.exists():
                logger.warning(f"{dest_dir} does not exist. Skipping trust store update.")
                return

            dest_path = dest_dir / "esb-rootCA.crt"
            logger.info(f"Copying CA cert to {dest_path}...")
            # sudoが必要な場合が多いが、ここでは単純にコピーを試みる
            # 実際にはCLIが管理者権限で実行されるか、内部でsudoを使う必要がある
            subprocess.run(["sudo", "cp", str(ca_cert_path), str(dest_path)], check=True)
            subprocess.run(["sudo", "update-ca-certificates"], check=True)
            
        else:
            logger.warning(f"Unsupported system for trust store integration: {system}")
            return

        logger.info("Successfully installed Root CA to trust store.")

    except subprocess.CalledProcessError as e:
        if "2147942405" in str(e) or "Access is denied" in (e.stderr.decode() if e.stderr else ""):
            logger.warning("Permission denied while installing Root CA. Please run the terminal as Administrator.")
            print("\n⚠️  Permission denied while installing Root CA. Please run the terminal as Administrator to trust the ESB Private CA.")
        else:
            logger.error(f"Failed to install Root CA: {e.stderr.decode() if e.stderr else str(e)}")
            raise
    except Exception as e:
        logger.error(f"Error installing Root CA: {e}")
        raise
