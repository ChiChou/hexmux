---
name: drive-ida-with-hexmux
description: Drive running IDA Pro GUI instances through Hexmux by selecting the correct database, generating focused IDAPython scripts, executing them through the Hexmux CLI, and interpreting structured results. Use for reverse engineering, disassembly, decompilation, database inspection, renaming, comments, type changes, patching, or other IDAPython work when Hexmux is available.
---

# Drive IDA with Hexmux

Use Hexmux as a small execution substrate, not as a catalog of narrow tools. Generate a task-specific script using verified IDAPython APIs and return a compact JSON-compatible `result`.

## Workflow

1. Run `hexmux ps --json`.
2. Select the instance by matching `idb_path`, `binary`, and PID to the user's target. If multiple entries remain plausible, ask the user; never silently use the first instance.
3. Look up uncertain IDAPython APIs in the available local IDAPython documentation. Read [references/idapython.md](references/idapython.md) for search locations and high-value modules.
4. Write one focused Python script. Prefer a saved `.py` file for nontrivial work so the user can inspect and rerun it.
5. Set a JSON-compatible global named `result`. Keep results small by filtering, limiting, and summarizing inside IDA.
6. Execute `hexmux run <instance-id-or-prefix> --json script.py`.
7. Check all of `ok`, `success`, `stderr`, and `traceback`. Correct the script based on actual errors; do not guess API names.

## Script conventions

Import only the modules needed by the script. Hexmux supplies a normal IDAPython execution namespace, not pre-imported convenience globals.

```python
import idautils
import ida_name

result = [
    {"ea": hex(ea), "name": ida_name.get_name(ea)}
    for ea in list(idautils.Functions())[:50]
]
```

Use strings for addresses when returning JSON to avoid ambiguity. For large text such as decompilation, return only the requested functions or write an artifact in the user's workspace when appropriate.

## Safety and retries

- Treat generated scripts as arbitrary code running inside IDA with the user's privileges.
- Inspect before executing mutations. Scope rename, comment, type, patch, debugger, and save operations exactly to the request.
- Do not retry a mutating script after a timeout or disconnect until inspecting IDA state. The client timeout cannot preempt Python already running on IDA's main thread.
- Avoid unbounded database walks. Add limits or incremental queries first, then expand with evidence.
- Prefer IDA APIs over parsing rendered UI text.

## Instance and supervisor behavior

The first CLI command starts the per-user supervisor on demand. IDA plugins reconnect to it through a Unix-domain socket. `hexmux run` requires an explicit instance selector and rejects ambiguous prefixes. If an instance is busy, wait for or investigate the active operation rather than sending competing mutations.
