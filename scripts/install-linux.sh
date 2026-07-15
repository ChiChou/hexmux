#!/bin/sh
set -eu

if [ "$(uname -s)" != "Linux" ]; then
    echo "install-linux.sh must be run on Linux" >&2
    exit 2
fi

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PREFIX=${HEXMUX_PREFIX:-"$HOME/.local/lib/hexmux"}
BUILD=${HEXMUX_BUILD_DIR:-"${TMPDIR:-/tmp}/hexmux-native-build"}
BOOTSTRAP_PYTHON=${PYTHON:-python3}

cmake -S "$ROOT/native" -B "$BUILD" -DCMAKE_BUILD_TYPE=Release
cmake --build "$BUILD" --config Release

install -d -m 755 "$PREFIX/bin"
install -m 755 "$BUILD/hexmux-activate" "$PREFIX/bin/hexmux-activate"

if [ ! -x "$PREFIX/venv/bin/python" ]; then
    "$BOOTSTRAP_PYTHON" -m venv "$PREFIX/venv"
fi
"$PREFIX/venv/bin/python" "$ROOT/scripts/install_runtime.py"
if [ "${HEXMUX_NO_LOAD:-0}" = "1" ]; then
    "$PREFIX/venv/bin/python" "$ROOT/scripts/install_activation.py" --no-load \
        --activator "$PREFIX/bin/hexmux-activate" --python "$PREFIX/venv/bin/python"
else
    "$PREFIX/venv/bin/python" "$ROOT/scripts/install_activation.py" \
        --activator "$PREFIX/bin/hexmux-activate" --python "$PREFIX/venv/bin/python"
fi

echo "Hexmux systemd user socket activation installed."
