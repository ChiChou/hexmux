from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest import mock

from hexmux.paths import prepare_runtime_dir, runtime_dir, socket_path


class PathsTest(unittest.TestCase):
    def test_macos_default_follows_tmux_layout(self):
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch("hexmux.paths.sys.platform", "darwin"):
            expected = Path("/private/tmp") / f"hexmux-{os.getuid()}"
            self.assertEqual(runtime_dir(), expected)
            self.assertEqual(socket_path(), expected / "default")

    def test_other_unix_default_follows_tmux_layout(self):
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch("hexmux.paths.sys.platform", "linux"):
            expected = Path("/tmp") / f"hexmux-{os.getuid()}"
            self.assertEqual(runtime_dir(), expected)
            self.assertEqual(socket_path(), expected / "default")

    def test_explicit_socket_override_is_preserved(self):
        with mock.patch.dict(os.environ, {"HEXMUX_SOCKET": "~/custom.sock"}, clear=True):
            self.assertEqual(socket_path(), Path.home() / "custom.sock")

    def test_runtime_directory_is_private(self):
        with self.subTest("mode"):
            import tempfile

            with tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary) / "runtime"
                with mock.patch.dict(os.environ, {"HEXMUX_RUNTIME_DIR": str(directory)}, clear=True):
                    self.assertEqual(prepare_runtime_dir(), directory)
                    self.assertEqual(directory.stat().st_mode & 0o777, 0o700)
