# IDAPython lookup guide

Do not infer API names from memory when local documentation or source is available.

## Documentation locations

Search likely workspace paths first:

```sh
rg -n "function_or_class" ida-pro-mcp/skills/idapython/docs ida-sdk/src/plugins/idapython
```

Prefer Hexmux's version-matched `.pyi` documentation stubs when present; search them with `rg` by symbol or intent. The SDK's `apidoc/*.py` files are useful curated documentation inputs but are not a complete API by themselves. The reference MCP repository may include generated Markdown and RST docs as a temporary fallback.

## High-value modules

- `ida_bytes`: read, patch, flags, comments
- `ida_funcs`: function boundaries and metadata
- `ida_name`: names and renaming
- `ida_xref`: cross-references
- `ida_segment`: segments
- `ida_typeinf`: types
- `ida_hexrays`: decompilation
- `ida_kernwin`: UI/main-thread services
- `ida_auto`: auto-analysis state
- `idautils`: convenient iterators
- `idc`: compatibility helpers and database paths

Check return values for mutation APIs. Account for `idaapi.BADADDR` and absent Hex-Rays support. Keep all IDA API access inside the submitted script; Hexmux schedules that script on IDA's main thread.
