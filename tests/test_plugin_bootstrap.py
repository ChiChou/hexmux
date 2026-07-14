from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import types
import unittest
from pathlib import Path
from unittest import mock


class PluginBase:
    pass


def fake_module(name: str, **attributes: object) -> types.ModuleType:
    module = types.ModuleType(name)
    for key, value in attributes.items():
        setattr(module, key, value)
    return module


def load_plugin_module():
    modules = {
        "idaapi": fake_module(
            "idaapi",
            plugin_t=PluginBase,
            PLUGIN_FIX=1,
            PLUGIN_KEEP=2,
            PLUGIN_SKIP=0,
            get_kernel_version=lambda: "test",
        ),
        "ida_kernwin": fake_module("ida_kernwin", MFF_WRITE=2, execute_sync=lambda callback, flags: callback()),
        "ida_nalt": fake_module("ida_nalt", get_root_filename=lambda: "fixture"),
        "idc": fake_module("idc", get_idb_path=lambda: "/tmp/fixture.i64"),
    }
    path = Path(__file__).parents[1] / "plugin" / "hexmux_plugin.py"
    spec = importlib.util.spec_from_file_location("hexmux_plugin_under_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    with mock.patch.dict(sys.modules, modules):
        spec.loader.exec_module(module)
    return module


class PluginBootstrapTest(unittest.TestCase):
    def test_environment_override_starts_supervisor_through_cli(self):
        plugin = load_plugin_module()
        completed = subprocess.CompletedProcess([], 0)
        with mock.patch.dict(os.environ, {"HEXMUX_EXECUTABLE": "/custom/bin/hexmux"}), mock.patch.object(
            plugin.subprocess, "run", return_value=completed
        ) as run:
            self.assertEqual(plugin.ensure_supervisor_running(), "running")
        self.assertEqual(run.call_args.args[0], ["/custom/bin/hexmux", "status"])

    def test_plugin_starts_supervisor_and_connector(self):
        plugin = load_plugin_module()
        fake_connector = mock.Mock()
        with mock.patch.object(plugin, "ensure_supervisor_running", return_value="running") as start, mock.patch.object(
            plugin, "Connector", return_value=fake_connector
        ):
            result = plugin.HexmuxPlugin().init()
        self.assertEqual(result, plugin.idaapi.PLUGIN_KEEP)
        start.assert_called_once_with()
        fake_connector.start.assert_called_once_with()

    def test_python_cell_returns_trailing_expression(self):
        plugin = load_plugin_module()
        response = plugin.execute_code("x = 40\nx + 2")
        self.assertTrue(response["success"])
        self.assertEqual(response["result"], 42)


if __name__ == "__main__":
    unittest.main()
