# Where: tools/cli/build_service_images.py
# What: Build and push service images needed by compute nodes.
# Why: Provide registry images for firecracker-mode node compose.
from __future__ import annotations

from pathlib import Path
import os

import docker

from tools.cli import config as cli_config
from tools.cli.core import logging

SERVICE_IMAGES: dict[str, Path] = {
    "esb-runtime-node": cli_config.PROJECT_ROOT / "services" / "runtime-node",
    "esb-agent": cli_config.PROJECT_ROOT / "services" / "agent",
}


def build_and_push(no_cache: bool = False) -> bool:
    client = docker.from_env()
    registry = os.getenv("CONTAINER_REGISTRY", "localhost:5010")

    for name, context in SERVICE_IMAGES.items():
        if not context.exists():
            logging.warning(f"Service build context not found: {context}")
            return False

        image_tag = f"{registry}/{name}:latest"
        logging.step(f"Building service image: {name}")
        print(f"  • Building {logging.highlight(image_tag)} ...", end="", flush=True)
        try:
            client.images.build(
                path=str(context),
                dockerfile="Dockerfile",
                tag=image_tag,
                nocache=no_cache,
                rm=True,
            )
            print(f" {logging.Color.GREEN}✅{logging.Color.END}")
        except Exception as exc:
            print(f" {logging.Color.RED}❌{logging.Color.END}")
            logging.error(f"Service image build failed ({name}): {exc}")
            return False

        print(f"  • Pushing {logging.highlight(image_tag)} ...", end="", flush=True)
        try:
            for line in client.images.push(image_tag, stream=True, decode=True):
                if "error" in line:
                    raise Exception(line["error"])
            print(f" {logging.Color.GREEN}✅{logging.Color.END}")
        except Exception as exc:
            print(f" {logging.Color.RED}❌{logging.Color.END}")
            logging.error(f"Push failed ({name}): {exc}")
            return False

    return True
