from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from .paths import prepare_runtime_dir, socket_path
from .wire import receive, send


def connect() -> socket.socket:
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(str(socket_path()))
    send(sock, {"role": "client"})
    return sock


def request(message: dict[str, Any]) -> dict[str, Any]:
    with connect() as sock:
        send(sock, message)
        return receive(sock)


def is_running() -> bool:
    try:
        return bool(request({"op": "ping"}).get("ok"))
    except (OSError, EOFError, ValueError):
        return False


def ensure_supervisor() -> None:
    if is_running():
        return
    prepare_runtime_dir()
    subprocess.Popen(
        [sys.executable, "-m", "hexmux.supervisor"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        close_fds=True,
    )
    for _ in range(100):
        if is_running():
            return
        time.sleep(0.05)
    raise SystemExit(f"Hexmux supervisor failed to start at {socket_path()}")


def print_instances(instances: list[dict[str, Any]]) -> None:
    if not instances:
        print("No IDA instances connected.")
        return
    headings = ("ID", "PID", "BINARY", "IDB")
    rows = [
        (
            str(item.get("id", ""))[:12],
            str(item.get("pid", "")),
            str(item.get("binary", "")),
            str(item.get("idb_path", "")),
        )
        for item in instances
    ]
    widths = [max(len(headings[index]), *(len(row[index]) for row in rows)) for index in range(4)]
    print("  ".join(headings[index].ljust(widths[index]) for index in range(4)))
    for row in rows:
        print("  ".join(row[index].ljust(widths[index]) for index in range(4)))


def run_command(args: argparse.Namespace) -> int:
    ensure_supervisor()
    if args.command == "mcp":
        from .mcp import serve

        serve()
        return 0
    if args.command == "status":
        response = request({"op": "ping"})
        if args.json:
            print(json.dumps(response, indent=2))
        else:
            print(f"supervisor pid={response['pid']}, instances={response['instances']}, socket={socket_path()}")
        return 0
    if args.command in ("ps", "list"):
        response = request({"op": "list"})
        if args.json:
            print(json.dumps(response["instances"], indent=2))
        else:
            print_instances(response["instances"])
        return 0
    if args.command == "stop":
        response = request({"op": "stop"})
        return 0 if response.get("ok") else 1
    if args.command == "run":
        code = sys.stdin.read() if args.script == "-" else Path(args.script).read_text(encoding="utf-8")
        response = request({"op": "exec", "instance": args.instance, "code": code, "timeout": args.timeout})
        if args.json:
            print(json.dumps(response, indent=2, ensure_ascii=False))
        elif not response.get("ok"):
            print(response.get("error", "execution failed"), file=sys.stderr)
        else:
            if response.get("stdout"):
                print(response["stdout"], end="")
            if response.get("stderr"):
                print(response["stderr"], end="", file=sys.stderr)
            if response.get("traceback"):
                print(response["traceback"], end="", file=sys.stderr)
            if response.get("result") is not None:
                print(json.dumps(response["result"], indent=2, ensure_ascii=False))
        return 0 if response.get("ok") and response.get("success") else 1
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hexmux", description="Drive IDA through a local Unix-socket supervisor")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("ps", "list"):
        child = subparsers.add_parser(name, help="list connected IDA instances")
        child.add_argument("--json", action="store_true")
    status = subparsers.add_parser("status", help="show supervisor status")
    status.add_argument("--json", action="store_true")
    subparsers.add_parser("stop", help="stop the background supervisor")
    subparsers.add_parser("mcp", help="serve MCP over stdio")
    run = subparsers.add_parser("run", help="run an IDAPython script in one IDA instance")
    run.add_argument("instance", help="instance ID/prefix, or PID")
    run.add_argument("script", nargs="?", default="-", help="script path (default: stdin)")
    run.add_argument("--timeout", type=float, default=60.0)
    run.add_argument("--json", action="store_true", help="print the complete response envelope")
    return parser


def main() -> None:
    raise SystemExit(run_command(build_parser().parse_args()))


if __name__ == "__main__":
    main()
