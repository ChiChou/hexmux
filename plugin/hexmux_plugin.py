"""IDA Pro plugin endpoint for Hexmux.

Install this file in ~/.idapro/plugins/. It intentionally depends only on
IDAPython and the Python standard library.
"""

from __future__ import annotations

import contextlib
import ast
import io
import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import threading
import time
import traceback
import uuid
from pathlib import Path

import ida_kernwin
import ida_nalt
import idaapi
import idc


HEADER = struct.Struct("!I")
MAX_MESSAGE = 16 * 1024 * 1024
MAX_CAPTURE = 4 * 1024 * 1024


def socket_path() -> Path:
    override = os.environ.get("HEXMUX_SOCKET")
    if override:
        return Path(override).expanduser()
    if sys.platform == "darwin":
        return Path("/private/tmp") / f"hexmux-{os.getuid()}" / "default"
    return Path("/tmp") / f"hexmux-{os.getuid()}" / "default"


def find_hexmux_executable() -> str | None:
    override = os.environ.get("HEXMUX_EXECUTABLE")
    if override:
        return str(Path(override).expanduser())
    discovered = shutil.which("hexmux")
    if discovered:
        return discovered
    candidates = (
        Path.home() / ".local" / "bin" / "hexmux",
        Path("/opt/homebrew/bin/hexmux"),
        Path("/usr/local/bin/hexmux"),
    )
    return next((str(path) for path in candidates if path.is_file() and os.access(path, os.X_OK)), None)


def ensure_supervisor_running() -> str:
    """Ask the CLI to start its daemon before connecting."""
    executable = find_hexmux_executable()
    if executable is None:
        return "executable-not-found"
    try:
        completed = subprocess.run(
            [executable, "status"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"start-failed: {exc}"
    return "running" if completed.returncode == 0 else f"start-failed: exit {completed.returncode}"


def send(sock: socket.socket, message: object) -> None:
    payload = json.dumps(message, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    if len(payload) > MAX_MESSAGE:
        raise ValueError("response too large")
    sock.sendall(HEADER.pack(len(payload)) + payload)


def receive_exact(sock: socket.socket, length: int) -> bytes:
    result = bytearray()
    while len(result) < length:
        chunk = sock.recv(length - len(result))
        if not chunk:
            raise EOFError("supervisor disconnected")
        result.extend(chunk)
    return bytes(result)


def receive(sock: socket.socket) -> dict:
    (length,) = HEADER.unpack(receive_exact(sock, HEADER.size))
    if length > MAX_MESSAGE:
        raise ValueError("request too large")
    return json.loads(receive_exact(sock, length))


def json_result(value):
    try:
        json.dumps(value)
    except (TypeError, ValueError, OverflowError):
        return {"repr": repr(value), "python_type": type(value).__name__}
    return value


def execute_code(code: str) -> dict:
    response: dict = {}

    def on_main_thread():
        stdout = io.StringIO()
        stderr = io.StringIO()
        namespace = {"__name__": "__hexmux__", "__builtins__": __builtins__}
        started = time.monotonic()
        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                tree = ast.parse(code, "<hexmux>", "exec")
                if tree.body and isinstance(tree.body[-1], ast.Expr):
                    tree.body[-1] = ast.Assign(
                        targets=[ast.Name(id="result", ctx=ast.Store())],
                        value=tree.body[-1].value,
                    )
                    ast.fix_missing_locations(tree)
                exec(compile(tree, "<hexmux>", "exec"), namespace, namespace)
            response.update(success=True, result=json_result(namespace.get("result")), traceback="")
        except BaseException:
            response.update(success=False, result=None, traceback=traceback.format_exc())
        finally:
            response.update(
                stdout=stdout.getvalue()[:MAX_CAPTURE],
                stderr=stderr.getvalue()[:MAX_CAPTURE],
                elapsed_ms=round((time.monotonic() - started) * 1000, 3),
            )
        return 1

    ida_kernwin.execute_sync(on_main_thread, ida_kernwin.MFF_WRITE)
    return response


class Connector(threading.Thread):
    def __init__(self):
        super().__init__(name="hexmux-connector", daemon=True)
        self.instance_id = uuid.uuid4().hex
        self.stopping = threading.Event()
        self.current_socket = None

    def metadata(self) -> dict:
        return {
            "pid": os.getpid(),
            "binary": ida_nalt.get_root_filename() or "",
            "idb_path": idc.get_idb_path() or "",
            "ida_version": idaapi.get_kernel_version(),
        }

    def run(self):
        while not self.stopping.is_set():
            try:
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                    self.current_socket = sock
                    sock.connect(str(socket_path()))
                    send(sock, {"role": "plugin", "instance_id": self.instance_id, "metadata": self.metadata()})
                    reply = receive(sock)
                    if not reply.get("ok"):
                        raise RuntimeError(reply.get("error", "registration rejected"))
                    print(f"[Hexmux] Connected as {self.instance_id[:12]}")
                    while not self.stopping.is_set():
                        request = receive(sock)
                        if request.get("type") != "exec":
                            continue
                        response = execute_code(request.get("code", ""))
                        send(sock, {"type": "result", "request_id": request.get("request_id"), **response})
            except (OSError, EOFError, ValueError, RuntimeError):
                if not self.stopping.is_set():
                    time.sleep(1.0)
            finally:
                self.current_socket = None

    def stop(self):
        self.stopping.set()
        if self.current_socket is not None:
            with contextlib.suppress(OSError):
                self.current_socket.shutdown(socket.SHUT_RDWR)


class HexmuxPlugin(idaapi.plugin_t):
    flags = idaapi.PLUGIN_FIX | idaapi.PLUGIN_KEEP
    comment = "Agent script bridge over a local Unix socket"
    help = "Hexmux"
    wanted_name = "Hexmux"
    wanted_hotkey = ""

    def init(self):
        supervisor_status = ensure_supervisor_running()
        print(f"[Hexmux] Supervisor: {supervisor_status}")
        self.connector = Connector()
        self.connector.start()
        return idaapi.PLUGIN_KEEP

    def run(self, arg):
        print(f"[Hexmux] Instance {self.connector.instance_id}; supervisor {socket_path()}")

    def term(self):
        self.connector.stop()
        self.connector.join(timeout=2.0)


def PLUGIN_ENTRY():
    return HexmuxPlugin()
