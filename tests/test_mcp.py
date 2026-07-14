from __future__ import annotations

import io
import json
import unittest
from unittest import mock

from hexmux import mcp
from hexmux.tools import BUILDERS


class McpTest(unittest.TestCase):
    def test_tools_list_is_small_and_uses_disass_name(self):
        response = mcp.dispatch({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        assert response is not None
        names = [tool["name"] for tool in response["result"]["tools"]]
        self.assertEqual(names, ["instances", "python", "decompile", "disass", "xrefs", "search", "annotate"])

    def test_instances_projects_supervisor_list(self):
        listing = {"ok": True, "instances": [{"id": "abc", "pid": 42}]}
        with mock.patch.object(mcp, "ensure_supervisor"), mock.patch.object(mcp, "request", return_value=listing) as request:
            result = mcp.call_tool("instances", {})
        request.assert_called_once_with({"op": "list"})
        self.assertEqual(result["structuredContent"], listing)

    def test_python_projects_supervisor_exec(self):
        response = {"ok": True, "success": True, "result": 42}
        with mock.patch.object(mcp, "ensure_supervisor"), mock.patch.object(mcp, "request", return_value=response) as request:
            result = mcp.call_tool("python", {"instance": "abc", "code": "6 * 7", "timeout": 2})
        request.assert_called_once_with({"op": "exec", "instance": "abc", "code": "6 * 7", "timeout": 2})
        self.assertFalse(result["isError"])

    def test_generated_tools_produce_valid_python(self):
        cases = {
            "decompile": {"targets": ["main"]},
            "disass": {"target": "main", "count": 10},
            "xrefs": {"targets": ["main"], "direction": "both"},
            "search": {"kind": "string", "query": "hello"},
            "annotate": {"items": [{"target": "main", "comment": "entry"}]},
        }
        for name, arguments in cases.items():
            with self.subTest(name):
                compile(BUILDERS[name](arguments), f"<{name}>", "exec")

    def test_stdio_round_trip(self):
        source = io.BytesIO((json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "test"}}) + "\n").encode())
        sink = io.BytesIO()
        mcp.serve(source, sink)
        response = json.loads(sink.getvalue())
        self.assertEqual(response["result"]["protocolVersion"], "test")


if __name__ == "__main__":
    unittest.main()
