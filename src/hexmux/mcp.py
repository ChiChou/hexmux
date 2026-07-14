from __future__ import annotations

import json
import sys
from typing import Any, BinaryIO

from .cli import ensure_supervisor, request
from .tools import BUILDERS


INSTANCE = {"type": "string", "description": "IDA instance ID, unique prefix, or PID"}
TOOLS = [
    {"name": "instances", "description": "List connected IDA instances (hexmux ps)", "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "python", "description": "Run an ad-hoc IDAPython cell; a trailing expression is returned", "inputSchema": {"type": "object", "properties": {"instance": INSTANCE, "code": {"type": "string"}, "timeout": {"type": "number", "minimum": 0.1, "maximum": 3600}}, "required": ["instance", "code"], "additionalProperties": False}},
    {"name": "decompile", "description": "Decompile functions", "inputSchema": {"type": "object", "properties": {"instance": INSTANCE, "targets": {"type": "array", "items": {"type": ["string", "integer"]}, "minItems": 1}}, "required": ["instance", "targets"], "additionalProperties": False}},
    {"name": "disass", "description": "Disassemble from an address or function", "inputSchema": {"type": "object", "properties": {"instance": INSTANCE, "target": {"type": ["string", "integer"]}, "count": {"type": "integer", "minimum": 1, "maximum": 1000}}, "required": ["instance", "target"], "additionalProperties": False}},
    {"name": "xrefs", "description": "Find cross-references to or from targets", "inputSchema": {"type": "object", "properties": {"instance": INSTANCE, "targets": {"type": "array", "items": {"type": ["string", "integer"]}, "minItems": 1}, "direction": {"type": "string", "enum": ["to", "from", "both"]}, "limit": {"type": "integer", "minimum": 1, "maximum": 5000}}, "required": ["instance", "targets"], "additionalProperties": False}},
    {"name": "search", "description": "Search names, strings, or byte patterns", "inputSchema": {"type": "object", "properties": {"instance": INSTANCE, "kind": {"type": "string", "enum": ["name", "string", "bytes"]}, "query": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 1000}}, "required": ["instance", "kind", "query"], "additionalProperties": False}},
    {"name": "annotate", "description": "Batch rename, comment, or apply types", "inputSchema": {"type": "object", "properties": {"instance": INSTANCE, "items": {"type": "array", "minItems": 1, "items": {"type": "object", "properties": {"target": {"type": ["string", "integer"]}, "name": {"type": "string"}, "comment": {"type": "string"}, "repeatable": {"type": "boolean"}, "type": {"type": "string"}}, "required": ["target"], "additionalProperties": False}}}, "required": ["instance", "items"], "additionalProperties": False}},
]


def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    ensure_supervisor()
    if name == "instances":
        response = request({"op": "list"})
    else:
        instance = str(arguments.get("instance", "")).strip()
        if not instance:
            raise ValueError("instance is required")
        if name == "python":
            code = arguments.get("code")
            if not isinstance(code, str):
                raise ValueError("code must be a string")
        elif name in BUILDERS:
            code = BUILDERS[name](arguments)
        else:
            raise ValueError(f"unknown tool: {name}")
        response = request({"op": "exec", "instance": instance, "code": code, "timeout": arguments.get("timeout", 60)})
    text = json.dumps(response, ensure_ascii=False, separators=(",", ":"))
    failed = not response.get("ok") or response.get("success") is False
    return {"content": [{"type": "text", "text": text}], "structuredContent": response, "isError": failed}


def dispatch(message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    request_id = message.get("id")
    if request_id is None:
        return None
    try:
        if method == "initialize":
            params = message.get("params") or {}
            result = {"protocolVersion": params.get("protocolVersion", "2025-03-26"), "capabilities": {"tools": {}}, "serverInfo": {"name": "hexmux", "version": "0.1.0"}}
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            params = message.get("params") or {}
            result = call_tool(str(params.get("name", "")), dict(params.get("arguments") or {}))
        else:
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": f"method not found: {method}"}}
        return {"jsonrpc": "2.0", "id": request_id, "result": result}
    except Exception as exc:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32000, "message": str(exc)}}


def serve(stdin: BinaryIO | None = None, stdout: BinaryIO | None = None) -> None:
    source = stdin or sys.stdin.buffer
    sink = stdout or sys.stdout.buffer
    for line in source:
        if not line.strip():
            continue
        try:
            response = dispatch(json.loads(line))
        except Exception as exc:
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": str(exc)}}
        if response is not None:
            sink.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")).encode() + b"\n")
            sink.flush()


def main() -> None:
    serve()


if __name__ == "__main__":
    main()
