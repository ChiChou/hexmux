from __future__ import annotations

from typing import Any


COMMON = """
import ida_bytes
import ida_funcs
import ida_hexrays
import ida_ida
import ida_idaapi
import ida_name
import idautils
import idc

def _hm_ea(value):
    if isinstance(value, int):
        return value
    text = str(value).strip()
    try:
        return int(text, 0)
    except ValueError:
        ea = ida_name.get_name_ea(ida_idaapi.BADADDR, text)
        if ea == ida_idaapi.BADADDR:
            raise ValueError(f"cannot resolve address or name: {value!r}")
        return ea
"""


def _literal(value: Any) -> str:
    return repr(value)


def decompile(arguments: dict[str, Any]) -> str:
    targets = arguments.get("targets")
    if not isinstance(targets, list) or not targets:
        raise ValueError("targets must be a non-empty array")
    return COMMON + f"""
result = []
for _target in {_literal(targets)}:
    try:
        _ea = _hm_ea(_target)
        _func = ida_funcs.get_func(_ea)
        if not _func:
            raise ValueError(f"no function contains {{_ea:#x}}")
        _cfunc = ida_hexrays.decompile(_func.start_ea)
        result.append({{"target": _target, "address": _func.start_ea, "name": ida_funcs.get_func_name(_func.start_ea), "code": str(_cfunc)}})
    except Exception as _exc:
        result.append({{"target": _target, "error": str(_exc)}})
"""


def disass(arguments: dict[str, Any]) -> str:
    if "target" not in arguments:
        raise ValueError("target is required")
    count = min(max(int(arguments.get("count", 64)), 1), 1000)
    return COMMON + f"""
_target = {_literal(arguments['target'])}
_ea = _hm_ea(_target)
_func = ida_funcs.get_func(_ea)
_end = _func.end_ea if _func else ida_idaapi.BADADDR
_lines = []
while _ea != ida_idaapi.BADADDR and len(_lines) < {count} and (not _func or _ea < _end):
    _lines.append({{"address": _ea, "text": idc.generate_disasm_line(_ea, 0) or ""}})
    _next = ida_bytes.next_head(_ea, _end)
    if _next == ida_idaapi.BADADDR or _next <= _ea:
        break
    _ea = _next
result = {{"target": _target, "function": ida_funcs.get_func_name(_func.start_ea) if _func else None, "lines": _lines, "truncated": len(_lines) == {count}}}
"""


def xrefs(arguments: dict[str, Any]) -> str:
    targets = arguments.get("targets")
    if not isinstance(targets, list) or not targets:
        raise ValueError("targets must be a non-empty array")
    direction = arguments.get("direction", "both")
    if direction not in ("to", "from", "both"):
        raise ValueError("direction must be to, from, or both")
    limit = min(max(int(arguments.get("limit", 200)), 1), 5000)
    return COMMON + f"""
result = []
for _target in {_literal(targets)}:
    try:
        _ea = _hm_ea(_target)
        _rows = []
        if {_literal(direction)} in ("to", "both"):
            _rows.extend({{"direction": "to", "from": x.frm, "to": x.to, "type": x.type}} for x in idautils.XrefsTo(_ea))
        if {_literal(direction)} in ("from", "both"):
            _rows.extend({{"direction": "from", "from": x.frm, "to": x.to, "type": x.type}} for x in idautils.XrefsFrom(_ea))
        result.append({{"target": _target, "address": _ea, "xrefs": _rows[:{limit}], "truncated": len(_rows) > {limit}}})
    except Exception as _exc:
        result.append({{"target": _target, "error": str(_exc)}})
"""


def search(arguments: dict[str, Any]) -> str:
    kind = arguments.get("kind")
    if kind not in ("name", "string", "bytes"):
        raise ValueError("kind must be name, string, or bytes")
    query = str(arguments.get("query", ""))
    if not query:
        raise ValueError("query is required")
    limit = min(max(int(arguments.get("limit", 100)), 1), 1000)
    return COMMON + f"""
_kind = {_literal(kind)}
_query = {_literal(query)}
_limit = {limit}
_rows = []
if _kind == "name":
    _needle = _query.casefold()
    for _ea, _name in idautils.Names():
        if _needle in _name.casefold():
            _rows.append({{"address": _ea, "name": _name}})
            if len(_rows) >= _limit:
                break
elif _kind == "string":
    _needle = _query.casefold()
    for _string in idautils.Strings():
        _text = str(_string)
        if _needle in _text.casefold():
            _rows.append({{"address": _string.ea, "text": _text}})
            if len(_rows) >= _limit:
                break
else:
    _start = ida_ida.inf_get_min_ea()
    _end = ida_ida.inf_get_max_ea()
    while len(_rows) < _limit:
        _ea = ida_bytes.find_bytes(_query, _start, range_end=_end)
        if _ea == ida_idaapi.BADADDR:
            break
        _rows.append({{"address": _ea}})
        _start = _ea + 1
result = {{"kind": _kind, "query": _query, "matches": _rows, "truncated": len(_rows) == _limit}}
"""


def annotate(arguments: dict[str, Any]) -> str:
    items = arguments.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("items must be a non-empty array")
    return COMMON + f"""
result = []
for _item in {_literal(items)}:
    try:
        _ea = _hm_ea(_item["target"])
        _changed = []
        if "name" in _item:
            if not ida_name.set_name(_ea, str(_item["name"]), ida_name.SN_CHECK):
                raise RuntimeError("set_name failed")
            _changed.append("name")
        if "comment" in _item:
            if not ida_bytes.set_cmt(_ea, str(_item["comment"]), bool(_item.get("repeatable", False))):
                raise RuntimeError("set_cmt failed")
            _changed.append("comment")
        if "type" in _item:
            if not idc.SetType(_ea, str(_item["type"])):
                raise RuntimeError("SetType failed")
            _changed.append("type")
        result.append({{"target": _item["target"], "address": _ea, "changed": _changed}})
    except Exception as _exc:
        result.append({{"target": _item.get("target"), "error": str(_exc)}})
"""


BUILDERS = {
    "decompile": decompile,
    "disass": disass,
    "xrefs": xrefs,
    "search": search,
    "annotate": annotate,
}
