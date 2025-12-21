"""
Lambda Layer Common Configuration
"""

import os


class LayerConfig:
    # Lambda Connection
    LAMBDA_ENDPOINT = os.environ.get("LAMBDA_ENDPOINT", "https://onpre-gateway:443")
    LAMBDA_RETRIES = 3
    LAMBDA_CONNECT_TIMEOUT = 5
    LAMBDA_READ_TIMEOUT = 300

    # Storage Connection
    S3_ENDPOINT = os.environ.get("S3_ENDPOINT", "http://onpre-storage:9000")
    RUSTFS_ROOT_USER = os.environ.get("RUSTFS_ROOT_USER", "rustfsadmin")
    RUSTFS_ROOT_PASSWORD = os.environ.get("RUSTFS_ROOT_PASSWORD", "rustfsadmin")
    AWS_REGION = "ap-northeast-1"

    # SSL Validation
    VERIFY_SSL = os.environ.get("VERIFY_SSL", "false").lower() == "true"


config = LayerConfig()
