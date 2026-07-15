#!/bin/sh
set -eu

if [ "$(uname -s)" != "Darwin" ]; then
    echo "install-macos.sh must be run on macOS" >&2
    exit 2
fi

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PREFIX=${HEXMUX_PREFIX:-"$HOME/Library/Application Support/Hexmux"}
BUILD=${HEXMUX_BUILD_DIR:-"${TMPDIR:-/tmp}/hexmux-native-build"}
BOOTSTRAP_PYTHON=${PYTHON:-python3}

cmake -S "$ROOT/native" -B "$BUILD" -DCMAKE_BUILD_TYPE=Release
cmake --build "$BUILD" --config Release

mkdir -p "$PREFIX/bin"
cp "$BUILD/hexmux-activate" "$PREFIX/bin/hexmux-activate"
chmod 755 "$PREFIX/bin/hexmux-activate"

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

echo "Hexmux launchd socket activation installed."
