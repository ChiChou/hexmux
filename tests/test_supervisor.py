from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path

from hexmux.supervisor import Supervisor
from hexmux.wire import async_receive, async_send


class SupervisorTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.supervisor = Supervisor()
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary_directory.name) / "supervisor.sock"
        self.server = await asyncio.start_unix_server(self.supervisor.handle, self.path)

    async def asyncTearDown(self):
        self.server.close()
        await self.server.wait_closed()
        self.temporary_directory.cleanup()

    async def connect(self):
        return await asyncio.open_unix_connection(self.path)

    async def client_request(self, request):
        reader, writer = await self.connect()
        await async_send(writer, {"role": "client"})
        await async_send(writer, request)
        result = await async_receive(reader)
        writer.close()
        await writer.wait_closed()
        return result

    async def test_plugin_registration_listing_and_execution(self):
        plugin_reader, plugin_writer = await self.connect()
        await async_send(
            plugin_writer,
            {
                "role": "plugin",
                "instance_id": "abc123def456",
                "metadata": {"pid": 42, "binary": "fixture", "idb_path": "/tmp/fixture.i64"},
            },
        )
        self.assertTrue((await async_receive(plugin_reader))["ok"])

        listing = await self.client_request({"op": "list"})
        self.assertEqual(listing["instances"][0]["id"], "abc123def456")

        async def fake_ida():
            request = await async_receive(plugin_reader)
            self.assertEqual(request["type"], "exec")
            self.assertEqual(request["code"], "result = 6 * 7")
            await async_send(
                plugin_writer,
                {
                    "type": "result",
                    "request_id": request["request_id"],
                    "success": True,
                    "result": 42,
                    "stdout": "",
                    "stderr": "",
                    "traceback": "",
                },
            )

        ida_task = asyncio.create_task(fake_ida())
        response = await self.client_request(
            {"op": "exec", "instance": "abc123", "code": "result = 6 * 7", "timeout": 2}
        )
        await ida_task
        self.assertTrue(response["ok"])
        self.assertEqual(response["result"], 42)

        plugin_writer.close()
        await plugin_writer.wait_closed()

    async def test_unknown_instance_is_an_error(self):
        response = await self.client_request(
            {"op": "exec", "instance": "missing", "code": "pass", "timeout": 1}
        )
        self.assertFalse(response["ok"])
        self.assertIn("no IDA instance", response["error"])

    async def test_timeout_keeps_instance_busy_until_plugin_finishes(self):
        plugin_reader, plugin_writer = await self.connect()
        await async_send(
            plugin_writer,
            {"role": "plugin", "instance_id": "slow-instance", "metadata": {"pid": 99}},
        )
        await async_receive(plugin_reader)

        first_task = asyncio.create_task(
            self.client_request(
                {"op": "exec", "instance": "slow", "code": "slow()", "timeout": 0.01}
            )
        )
        forwarded = await async_receive(plugin_reader)
        timed_out = await first_task
        self.assertFalse(timed_out["ok"])
        self.assertIn("timed out", timed_out["error"])

        busy = await self.client_request(
            {"op": "exec", "instance": "slow", "code": "second()", "timeout": 1}
        )
        self.assertFalse(busy["ok"])
        self.assertIn("busy", busy["error"])

        await async_send(
            plugin_writer,
            {"type": "result", "request_id": forwarded["request_id"], "success": True},
        )
        await asyncio.sleep(0)
        plugin_writer.close()
        await plugin_writer.wait_closed()


if __name__ == "__main__":
    unittest.main()
