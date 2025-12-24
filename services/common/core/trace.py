import time
import secrets
from typing import Optional


class TraceId:
    """
    AWS X-Ray Trace ID format:
    Root=1-timestamp-randomuuid;Parent=parentid;Sampled=sampled
    """

    def __init__(self, root: str, parent: Optional[str] = None, sampled: str = "1"):
        self.root = root
        self.parent = parent
        self.sampled = sampled

    @classmethod
    def generate(cls) -> "TraceId":
        """新規 Trace ID を生成する (Root=1-timehex-uniqueid)"""
        # AWS 準拠: 8桁の 16進数 timestamp
        epoch_hex = f"{int(time.time()):08x}"
        unique_id = secrets.token_hex(12)  # 24 chars
        root = f"1-{epoch_hex}-{unique_id}"
        return cls(root=root, sampled="1")

    @classmethod
    def parse(cls, header: str) -> "TraceId":
        """X-Amzn-Trace-Id ヘッダー文字列をパースする"""
        # print(f"[TraceId] Parsing header: '{header}'")
        parts = {}
        for part in header.split(";"):
            if "=" in part:
                try:
                    k, v = part.split("=", 1)
                    parts[k.strip()] = v.strip()
                except ValueError:
                    continue

        root = parts.get("Root", "")
        parent = parts.get("Parent")
        sampled = parts.get("Sampled", "1")

        # もし Root= 形式ではないが ID らしきものが直接渡された場合のフォールバック
        if not root and header and "-" in header and "=" not in header:
            # print(f"[TraceId] Header looks like a raw ID, using it as root")
            root = header.strip()

        # print(f"[TraceId] Parsed: root='{root}', parent='{parent}', sampled='{sampled}'")
        return cls(root=root, parent=parent, sampled=sampled)

    def to_root_id(self) -> str:
        """Root ID 部分のみを返す (Request ID として使用)"""
        return self.root

    def __str__(self) -> str:
        """ヘッダー形式の文字列を生成する"""
        s = f"Root={self.root}"
        if self.parent:
            s += f";Parent={self.parent}"
        if self.sampled:
            s += f";Sampled={self.sampled}"
        return s
