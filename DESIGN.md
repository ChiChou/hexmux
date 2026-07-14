# Hexmux design

Hexmux lets an agent drive one of several running IDA Pro GUI processes without opening an IP port and without publishing a large catalog of narrow tools.

## Product interface

The CLI is the primary interface:

```text
hexmux ps
hexmux run <instance> analysis.py
hexmux run <instance> - < analysis.py
hexmux status
hexmux stop
```

An agent should inspect the local IDAPython skill/docs, generate a task-specific Python script, execute it, and use the structured response. This keeps discovery context nearly constant regardless of the size of IDAPython.

An optional MCP adapter can be added later with only two tools:

- `instances()`
- `run_python(instance, code, timeout)`

The adapter should be a thin stdio client of the same supervisor. It must not contain IDA logic or own sessions.

## Processes and trust boundaries

```text
agent -> hexmux CLI/MCP -> /private/tmp/hexmux-<uid>/default <- IDA plugin <- IDA main thread
```

- The on-demand supervisor is a detached per-user daemon, similar to tmux's server.
- At plugin initialization, IDA invokes `hexmux status`. The CLI starts the supervisor if absent.
- Both clients and IDA plugins initiate connections to one Unix-domain socket.
- IDA never listens on TCP/UDP or on a per-instance socket.
- The socket directory is mode `0700`; the socket is mode `0600`.
- Each plugin registers an ephemeral instance ID plus PID, input filename, IDB path, and IDA version.
- Every execution request names an instance explicitly. Unique ID prefixes and exact PIDs are accepted.
- One operation may execute per IDA instance. Additional work receives `busy` rather than silently queueing stale agent actions.

## Protocol

The wire format is a four-byte big-endian length followed by UTF-8 JSON, capped at 16 MiB. The initial frame identifies the peer as `client` or `plugin`. Request IDs are assigned by the supervisor and responses may arrive asynchronously.

The script defines an optional global named `result`. JSON-compatible results are returned directly; other Python objects become `{repr, python_type}`. stdout, stderr, traceback, success, and elapsed time are returned separately.

Scripts execute in a fresh namespace on IDA's main thread via `ida_kernwin.execute_sync(..., MFF_WRITE)`. The transport thread never calls IDA APIs directly.

## Deliberate MVP limits

- Client timeout stops waiting but cannot safely preempt arbitrary Python already running on IDA's main thread.
- The supervisor has no persisted operation journal yet.
- Filesystem permissions authenticate same-user peers; there is not yet a per-install secret or code-signing check.
- Plugin installation is manual in the first slice.
- Headless `idalib` workers are not yet launched by the supervisor.

The Rust reference's bounded worker and structured-error patterns are retained. Its broad tool registry, HTTP sessions, and worker pool are intentionally not part of this GUI-first slice.

## HCLI distribution

HCLI can install the plugin archive, its supporting files, declared Python dependencies, and shared plugin settings. It does not provide a documented arbitrary post-install hook or a mechanism to export persistent environment variables into GUI-launched IDA.

Production release archives should therefore include a standalone `hexmuxd` supervisor helper beside the Python plugin entry point:

```text
hexmux/
├── ida-plugin.json
├── hexmux_plugin.py
└── hexmuxd
```

Publish platform-specific archives for macOS arm64/x86-64 and later Linux/Windows. The plugin resolves `hexmuxd` relative to `__file__`, ensures it is executable where applicable, starts it, and then connects through the Unix socket. This avoids relying on GUI `PATH`, IDA's embedded `sys.executable`, or installer-time environment mutation.

Declare HCLI settings for an optional socket/runtime override and an optional external supervisor path. Read them through `ida-settings`; environment variables remain development and emergency overrides. Do not use `pythonDependencies` as the supervisor installation mechanism: those dependencies are installed for the IDAPython runtime, while the supervisor is deliberately a separate process.

## Versioned IDAPython references

Keep the agent skill small. Do not place the full IDAPython SDK or every generated API page in `SKILL.md`, and do not make the reference MCP repository an authoritative dependency.

Use the official `HexRaysSA/ida-sdk` repository as a pinned development input. A git submodule is acceptable when Hexmux supports one primary IDA release, but it must not be included in the HCLI plugin archive. For multiple supported releases, CI should check out each official `vX.Y.Z-release` or selected `vX.Y.Z-sdk.N` tag and produce separate reference snapshots.

Reuse IDAPython's documentation inputs rather than indexing implementation source code. `apidoc/*.py` already expresses curated Python-facing documentation as modules, classes, functions, signatures, and docstrings. The build then combines those overrides with SWIG signatures and Doxygen documentation from the actual wrapped modules. `api_contents.brief` provides a compact full symbol inventory, while `examples/index.md` provides a categorized entry point to practical examples.

The agent-facing output should remain Python-shaped. Generate `.pyi`-style documentation stubs containing module/class/function structure, signatures, type annotations, constants, and docstrings, with `...` bodies. Do not make HTML the canonical reference format. HTML and its Lunr `index.js` remain useful only as upstream completeness/search inputs when consuming an official documentation build.

Package this shape:

```text
references/
├── manifest.json
├── 9.2/
│   ├── symbols.txt
│   ├── stubs/*.pyi
│   └── examples/*.py
└── 9.3/
    ├── symbols.txt
    ├── stubs/*.pyi
    └── examples/*.py
```

`manifest.json` records the IDA version, exact SDK tag and commit, IDAPython documentation generator version, and generation time. `symbols.txt` is the official qualified-name inventory. Stubs merge the curated `apidoc/*.py` content with the complete runtime-generated signatures and docstrings. Include the generated examples index and selected official example source files.

Expose the reference through `hexmux docs search <query> --ida-version <version>` and `hexmux docs show <qualified-name>`. Search operates over symbol names and stub/docstring text; `docs show` extracts the relevant definition rather than returning an entire module. The agent skill can also use `rg` directly. It first obtains the selected instance's reported `ida_version` and selects the matching snapshot. If no exact snapshot exists, choose the nearest compatible minor version but clearly report the mismatch.

For ambiguous or potentially changed behavior, let the agent run a read-only introspection script inside the selected IDA instance (`hasattr`, `inspect.signature` where supported, `help`, constants, and version fields). Runtime observation wins over bundled documentation.

Update references through a scheduled CI job that detects new official SDK tags, extracts the Python-facing documentation from the matching IDA/IDAPython runtime, emits deterministic stubs, and produces an API diff from `api_contents.brief`. Compare the stub inventory against the official documentation search index when available. Merge and release those updates intentionally; never make released documentation follow the SDK `main` branch implicitly.

The open SDK checkout contains `hrdoc.py`, curated `apidoc/` inputs, the symbol inventory, and examples, but its documented generator expects the matching IDA runtime and pdoc tooling. Treat pre-generated official documentation artifacts as preferred inputs when Hex-Rays publishes them; otherwise run the generator in a licensed CI image for each supported IDA release. Do not expose or bundle the complete SDK source tree to agents.
