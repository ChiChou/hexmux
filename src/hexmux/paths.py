from __future__ import annotations

import os
import sys
from pathlib import Path


def runtime_dir() -> Path:
    override = os.environ.get("HEXMUX_RUNTIME_DIR")
    if override:
        return Path(override).expanduser()

    if sys.platform == "win32":
        return Path(os.environ["TEMP"]) / f"hexmux-{os.environ['USERNAME']}"

    # /tmp is a symlink to /private/tmp on macOS; use the real path so socket
    # paths compare equal regardless of how callers resolve them.
    base = Path("/private/tmp") if sys.platform == "darwin" else Path("/tmp")
    return base / f"hexmux-{os.getuid()}"


def socket_path() -> Path:
    override = os.environ.get("HEXMUX_SOCKET")
    return Path(override).expanduser() if override else runtime_dir() / "default"


def prepare_runtime_dir() -> Path:
    directory = runtime_dir()
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(directory, 0o700)
    return directory
