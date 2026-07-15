from __future__ import annotations

import asyncio
import socket
import tempfile
import unittest
from pathlib import Path

from hexmux.supervisor import run
from hexmux.wire import async_receive, async_send


class ActivatedSupervisorTest(unittest.IsolatedAsyncioTestCase):
    async def test_adopts_listener_and_stops_when_idle(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "activated.sock"
            listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            listener.bind(str(path))
            listener.listen()
            task = asyncio.create_task(run(listen_fd=listener.detach(), idle_timeout=0.2))
            await asyncio.sleep(0)

            reader, writer = await asyncio.open_unix_connection(path)
            await async_send(writer, {"role": "client"})
            await async_send(writer, {"op": "ping"})
            self.assertTrue((await async_receive(reader))["ok"])
            writer.close()
            await writer.wait_closed()

            await asyncio.wait_for(task, 1.0)


if __name__ == "__main__":
    unittest.main()
