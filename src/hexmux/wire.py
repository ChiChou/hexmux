from __future__ import annotations

import asyncio
import json
import socket
import struct
from typing import Any


HEADER = struct.Struct("!I")
MAX_MESSAGE = 16 * 1024 * 1024


def encode(message: Any) -> bytes:
    payload = json.dumps(message, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    if len(payload) > MAX_MESSAGE:
        raise ValueError(f"message exceeds {MAX_MESSAGE} bytes")
    return HEADER.pack(len(payload)) + payload


async def async_send(writer: asyncio.StreamWriter, message: Any) -> None:
    writer.write(encode(message))
    await writer.drain()


async def async_receive(reader: asyncio.StreamReader) -> Any:
    header = await reader.readexactly(HEADER.size)
    (length,) = HEADER.unpack(header)
    if length > MAX_MESSAGE:
        raise ValueError(f"peer message exceeds {MAX_MESSAGE} bytes")
    return json.loads(await reader.readexactly(length))


def send(sock: socket.socket, message: Any) -> None:
    sock.sendall(encode(message))


def _receive_exact(sock: socket.socket, length: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < length:
        chunk = sock.recv(length - len(chunks))
        if not chunk:
            raise EOFError("peer disconnected")
        chunks.extend(chunk)
    return bytes(chunks)


def receive(sock: socket.socket) -> Any:
    (length,) = HEADER.unpack(_receive_exact(sock, HEADER.size))
    if length > MAX_MESSAGE:
        raise ValueError(f"peer message exceeds {MAX_MESSAGE} bytes")
    return json.loads(_receive_exact(sock, length))
