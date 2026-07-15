# Hexmux

![Badge](https://img.shields.io/badge/AI_Slop-Yes-red)

Hexmux is a small local control plane for agent-driven IDA Pro. Agents send task-specific IDAPython scripts through a per-user Unix-socket supervisor; IDA connects outward to that supervisor and never opens a network port.

## Development setup

```sh
cd hexmux
python3 -m pip install -e .
mkdir -p ~/.idapro/plugins
cp plugin/hexmux_plugin.py ~/.idapro/plugins/
```

Restart IDA. The plugin connects to the system-owned activation socket in the
background. It does not locate executables or spawn the supervisor itself.

## Use

The first connection starts the supervisor through launchd or systemd:

```sh
hexmux status
hexmux ps
```

## Native socket activation

The C++ activator lets launchd or systemd own the Unix socket and start the
Python supervisor only when a client connects. Install it before loading the
IDA plugin or using the CLI:

macOS:

```sh
./scripts/install-macos.sh
```

Linux with a systemd user manager:

```sh
./scripts/install-linux.sh
```

Set `HEXMUX_NO_LOAD=1` to build and generate the service definition without
loading or enabling it.

The generated launchd/systemd job invokes the same Python environment used by
the installer. The supervisor adopts the inherited listening descriptor and
exits after 30 idle seconds. It does not remove the service-manager-owned
socket. Use `--no-load` to inspect the generated job without registering it.

The current native implementation supports launchd and systemd. A Windows SCM
named-pipe backend requires the corresponding Python multiplexed-stream adapter
and is not provided yet.

Generate a script:

```python
import idautils
import ida_name

result = [
    {"ea": hex(ea), "name": ida_name.get_name(ea)}
    for ea in list(idautils.Functions())[:20]
]
```

Then run it using the ID or unique prefix printed by `hexmux ps`:

```sh
hexmux run 7c91a42b functions.py
hexmux run 7c91a42b --json < functions.py
```

`result` should normally be JSON-compatible. Printed output and exceptions are captured separately. Use `--json` when another program or agent will consume the response.

## MCP

Configure an MCP client to launch:

```sh
hexmux mcp
```

The stdio server exposes seven tools: `instances`, `python`, `decompile`, `disass`, `xrefs`, `search`, and `annotate`. Every IDA-facing tool requires an explicit instance selector. `python` is the general interface and returns the value of a trailing expression; the remaining tools are compact conveniences implemented as generated IDAPython scripts over the same execution protocol.

See [DESIGN.md](DESIGN.md) for protocol and MCP adapter decisions.

## Fetch IDAPython reference stubs

Fetch a pinned, source-form documentation snapshot without retaining the SDK checkout:

```sh
python3 scripts/fetch_idapython_reference.py \
  --ref v9.3.0-release \
  --output references/9.3
```

This copies the curated `apidoc/*.py` files as `.pyi` documentation stubs, plus the qualified symbol inventory and examples index. These curated stubs are useful but not a complete substitute for runtime-generated IDAPython documentation.
