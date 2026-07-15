from __future__ import annotations

import argparse
import asyncio
import contextlib
import os
import signal
import socket
import stat
import time
from dataclasses import dataclass, field
from typing import Any

from .paths import prepare_runtime_dir, socket_path
from .wire import async_receive, async_send


@dataclass
class Instance:
    instance_id: str
    metadata: dict[str, Any]
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter
    connected_at: float = field(default_factory=time.time)
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    busy_request_id: str | None = None

    def public(self) -> dict[str, Any]:
        return {
            "id": self.instance_id,
            **self.metadata,
            "connected_at": self.connected_at,
        }


class Supervisor:
    def __init__(self) -> None:
        self.instances: dict[str, Instance] = {}
        self.pending: dict[str, asyncio.Future] = {}
        self.request_number = 0
        self.stop_event = asyncio.Event()
        self.active_connections = 0
        self.activity_event = asyncio.Event()

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self.active_connections += 1
        self.activity_event.set()
        try:
            hello = await async_receive(reader)
            role = hello.get("role")
            if role == "plugin":
                await self.handle_plugin(hello, reader, writer)
            elif role == "client":
                await self.handle_client(reader, writer)
            else:
                await async_send(writer, {"ok": False, "error": "invalid peer role"})
        except (EOFError, asyncio.IncompleteReadError, ConnectionError):
            pass
        except Exception as exc:
            with contextlib.suppress(Exception):
                await async_send(writer, {"ok": False, "error": f"supervisor error: {exc}"})
        finally:
            self.active_connections -= 1
            self.activity_event.set()
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()

    async def handle_plugin(
        self,
        hello: dict[str, Any],
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        instance_id = str(hello.get("instance_id", "")).strip()
        if not instance_id or len(instance_id) > 128:
            await async_send(writer, {"ok": False, "error": "invalid instance_id"})
            return
        old = self.instances.get(instance_id)
        if old:
            old.writer.close()
        instance = Instance(instance_id, dict(hello.get("metadata") or {}), reader, writer)
        self.instances[instance_id] = instance
        await async_send(writer, {"ok": True, "type": "registered", "instance_id": instance_id})
        try:
            while True:
                message = await async_receive(reader)
                if message.get("type") != "result":
                    continue
                request_id = message.get("request_id")
                if instance.busy_request_id == request_id:
                    instance.busy_request_id = None
                future = self.pending.pop(request_id, None)
                if future and not future.done():
                    future.set_result(message)
        finally:
            if self.instances.get(instance_id) is instance:
                del self.instances[instance_id]
            for request_id, future in list(self.pending.items()):
                if request_id.startswith(instance_id + ":") and not future.done():
                    future.set_exception(ConnectionError(f"IDA instance {instance_id} disconnected"))
                    del self.pending[request_id]

    def resolve_instance(self, selector: str) -> Instance:
        if selector in self.instances:
            return self.instances[selector]
        matches = [item for key, item in self.instances.items() if key.startswith(selector)]
        if not matches and selector.isdigit():
            matches = [item for item in self.instances.values() if str(item.metadata.get("pid")) == selector]
        if len(matches) == 1:
            return matches[0]
        if not matches:
            raise LookupError(f"no IDA instance matches {selector!r}")
        raise LookupError(f"ambiguous IDA instance selector {selector!r}")

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        request = await async_receive(reader)
        operation = request.get("op")
        if operation == "ping":
            await async_send(writer, {"ok": True, "pid": os.getpid(), "instances": len(self.instances)})
        elif operation == "list":
            instances = sorted((item.public() for item in self.instances.values()), key=lambda item: item["connected_at"])
            await async_send(writer, {"ok": True, "instances": instances})
        elif operation == "stop":
            await async_send(writer, {"ok": True})
            self.stop_event.set()
        elif operation == "exec":
            await self.execute(request, writer)
        else:
            await async_send(writer, {"ok": False, "error": f"unknown operation: {operation}"})

    async def execute(self, request: dict[str, Any], writer: asyncio.StreamWriter) -> None:
        timeout = 60.0
        request_id: str | None = None
        try:
            instance = self.resolve_instance(str(request.get("instance", "")))
            code = request.get("code")
            if not isinstance(code, str):
                raise ValueError("code must be a string")
            timeout = min(max(float(request.get("timeout", 60)), 0.1), 3600.0)
            if instance.busy_request_id is not None:
                raise RuntimeError(f"IDA instance {instance.instance_id} is busy")
            self.request_number += 1
            request_id = f"{instance.instance_id}:{self.request_number}"
            instance.busy_request_id = request_id
            future = asyncio.get_running_loop().create_future()
            self.pending[request_id] = future
            try:
                async with instance.send_lock:
                    await async_send(instance.writer, {"type": "exec", "request_id": request_id, "code": code})
            except Exception:
                instance.busy_request_id = None
                raise
            result = await asyncio.wait_for(future, timeout)
            await async_send(writer, {"ok": True, **result})
        except TimeoutError:
            await async_send(
                writer,
                {
                    "ok": False,
                    "error": (
                        f"operation timed out after {timeout:g}s; IDA may still be "
                        "running and this instance remains busy until it responds"
                    ),
                },
            )
        except Exception as exc:
            await async_send(writer, {"ok": False, "error": str(exc)})
        finally:
            if request_id is not None:
                self.pending.pop(request_id, None)


async def stop_when_idle(supervisor: Supervisor, timeout: float) -> None:
    while not supervisor.stop_event.is_set():
        if supervisor.active_connections:
            supervisor.activity_event.clear()
            await supervisor.activity_event.wait()
            continue
        supervisor.activity_event.clear()
        try:
            await asyncio.wait_for(supervisor.activity_event.wait(), timeout)
        except TimeoutError:
            if not supervisor.active_connections:
                supervisor.stop_event.set()


async def run(*, listen_fd: int | None = None, idle_timeout: float | None = None) -> None:
    if not hasattr(asyncio, "start_unix_server"):
        raise SystemExit("hexmux currently requires Unix-domain socket support")
    supervisor = Supervisor()
    path = None
    if listen_fd is not None:
        listener = socket.socket(fileno=listen_fd)
        listener.setblocking(False)
        server = await asyncio.start_unix_server(supervisor.handle, sock=listener)
    else:
        prepare_runtime_dir()
        path = socket_path()
        if path.exists():
            try:
                _reader, writer = await asyncio.open_unix_connection(path)
            except OSError:
                path.unlink()
            else:
                writer.close()
                await writer.wait_closed()
                raise SystemExit(f"supervisor already running at {path}")
        server = await asyncio.start_unix_server(supervisor.handle, path=path)
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, supervisor.stop_event.set)
    idle_task = None
    try:
        async with server:
            idle_task = (
                asyncio.create_task(stop_when_idle(supervisor, idle_timeout)) if idle_timeout is not None else None
            )
            await supervisor.stop_event.wait()
    finally:
        if idle_task is not None:
            idle_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await idle_task
        server.close()
        await server.wait_closed()
        if path is not None:
            with contextlib.suppress(FileNotFoundError):
                path.unlink()


def main() -> None:
    parser = argparse.ArgumentParser(description="Hexmux background supervisor")
    parser.add_argument("--listen-fd", type=int, default=None)
    parser.add_argument("--idle-timeout", type=float, default=None)
    args = parser.parse_args()
    if args.listen_fd is not None and args.listen_fd < 0:
        parser.error("--listen-fd must be non-negative")
    if args.idle_timeout is not None and args.idle_timeout <= 0:
        parser.error("--idle-timeout must be positive")
    asyncio.run(run(listen_fd=args.listen_fd, idle_timeout=args.idle_timeout))


if __name__ == "__main__":
    main()
