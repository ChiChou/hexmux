from __future__ import annotations

import importlib.util
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
    def test_plugin_starts_connector_without_spawning_supervisor(self):
        plugin = load_plugin_module()
        fake_connector = mock.Mock()
        with mock.patch.object(plugin, "Connector", return_value=fake_connector):
            result = plugin.HexmuxPlugin().init()
        self.assertEqual(result, plugin.idaapi.PLUGIN_KEEP)
        fake_connector.start.assert_called_once_with()

    def test_python_cell_returns_trailing_expression(self):
        plugin = load_plugin_module()
        response = plugin.execute_code("x = 40\nx + 2")
        self.assertTrue(response["success"])
        self.assertEqual(response["result"], 42)


if __name__ == "__main__":
    unittest.main()
