#!/usr/bin/env python3
"""Install Hexmux into the current interpreter without invoking pip."""

from __future__ import annotations

import shutil
import stat
import sys
import sysconfig
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
source = ROOT / "src/hexmux"
destination = Path(sysconfig.get_path("purelib")) / "hexmux"
shutil.copytree(source, destination, dirs_exist_ok=True)

launcher = Path(sys.executable).parent / "hexmux"
launcher.write_text(
    f"#!{sys.executable}\nfrom hexmux.cli import main\nmain()\n",
    encoding="utf-8",
)
launcher.chmod(launcher.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
print(destination)
