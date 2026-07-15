#!/usr/bin/env python3
"""Install Hexmux socket activation files for the current desktop user."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def render(source: Path, destination: Path, values: dict[str, str]) -> None:
    content = source.read_text(encoding="utf-8")
    for key, value in values.items():
        content = content.replace(f"@{key}@", value)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8")


def install_macos(activator: Path, python: Path, *, load: bool) -> Path:
    runtime = Path("/private/tmp") / f"hexmux-{os.getuid()}"
    runtime.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(runtime, 0o700)
    destination = Path.home() / "Library/LaunchAgents/io.hexmux.supervisor.plist"
    render(
        ROOT / "native/launchd/io.hexmux.supervisor.plist.in",
        destination,
        {
            "HEXMUX_ACTIVATE": str(activator),
            "PYTHON": str(python),
            "SOCKET_PATH": str(runtime / "default"),
        },
    )
    if load:
        domain = f"gui/{os.getuid()}"
        subprocess.run(["launchctl", "bootout", domain, str(destination)], check=False)
        subprocess.run(["launchctl", "bootstrap", domain, str(destination)], check=True)
    return destination


def install_linux(activator: Path, python: Path, *, load: bool) -> Path:
    destination = Path.home() / ".config/systemd/user"
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "native/systemd/hexmux.socket", destination / "hexmux.socket")
    render(
        ROOT / "native/systemd/hexmux.service.in",
        destination / "hexmux.service",
        {"HEXMUX_ACTIVATE": str(activator), "PYTHON": str(python)},
    )
    if load:
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
        subprocess.run(["systemctl", "--user", "enable", "--now", "hexmux.socket"], check=True)
    return destination


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--activator", type=Path, default=ROOT / "native/build/hexmux-activate")
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--no-load", action="store_true", help="write files without loading/enabling them")
    args = parser.parse_args()
    activator = args.activator.expanduser().resolve()
    python = args.python.expanduser().resolve()
    if not activator.is_file():
        parser.error(f"activator does not exist: {activator}")
    if sys.platform == "darwin":
        installed = install_macos(activator, python, load=not args.no_load)
    elif sys.platform.startswith("linux"):
        installed = install_linux(activator, python, load=not args.no_load)
    else:
        parser.error("socket-activation installation currently supports macOS and Linux")
    print(installed)


if __name__ == "__main__":
    main()
