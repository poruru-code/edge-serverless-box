# Where: tools/cli/compose.py
# What: Compose file selection helpers for CLI commands.
# Why: Switch docker compose invocation based on the runtime mode.
from pathlib import Path

from tools.cli import config as cli_config
from tools.cli import runtime_mode


def resolve_compose_files(mode: str | None = None, target: str = "control") -> list[Path]:
    resolved_mode = mode or runtime_mode.get_mode()

    if target == "control":
        if resolved_mode == cli_config.ESB_MODE_FIRECRACKER:
            if not cli_config.COMPOSE_CONTROL_FILE.exists():
                raise FileNotFoundError(f"Missing compose file: {cli_config.COMPOSE_CONTROL_FILE}")
            return [cli_config.COMPOSE_CONTROL_FILE]
        missing = [
            path
            for path in (
                cli_config.COMPOSE_BASE_FILE,
                cli_config.COMPOSE_COMPUTE_FILE,
                cli_config.COMPOSE_ADAPTER_FILE,
            )
            if not path.exists()
        ]
        if missing:
            raise FileNotFoundError(f"Missing compose file: {missing[0]}")
        return [
            cli_config.COMPOSE_BASE_FILE,
            cli_config.COMPOSE_COMPUTE_FILE,
            cli_config.COMPOSE_ADAPTER_FILE,
        ]

    if target == "compute":
        if not cli_config.COMPOSE_COMPUTE_FILE.exists():
            raise FileNotFoundError(f"Missing compose file: {cli_config.COMPOSE_COMPUTE_FILE}")
        return [cli_config.COMPOSE_COMPUTE_FILE]

    raise ValueError(f"Unsupported compose target: {target}")


def build_compose_command(
    args: list[str],
    mode: str | None = None,
    target: str = "control",
) -> list[str]:
    cmd = ["docker", "compose"]
    for path in resolve_compose_files(mode, target=target):
        cmd.extend(["-f", str(path)])
    cmd.extend(args)
    return cmd
