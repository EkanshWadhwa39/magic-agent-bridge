# magic-agent-bridge

Let an agentic AI (Claude Code, or anything else that speaks MCP) drive a
**live, already-open** Magic VLSI layout session - running real Tcl/Magic
commands and reading results back - instead of you manually retyping tkcon
commands and pasting screenshots back into a chat.

## Why this exists

Magic's tkcon console is a Tcl interpreter with its own event loop, already
running as part of the GUI process. That means we don't need to build a
plugin, patch Magic's source, or use anything exotic - we just open a plain
TCP socket *inside* that already-running interpreter. Anything sent to that
socket executes exactly as if typed at tkcon, and the result comes back over
the same connection.

Deliberately NOT using Tk's built-in `send` command (X11 interp registration)
- that mechanism depends on the same X11 selection subsystem that's known to
segfault on setups with two X11 stacks loaded simultaneously (e.g. Homebrew
cairo + XQuartz on macOS). A bare socket sidesteps that entirely.

## Architecture

```
Claude Code / any MCP client
        |  MCP tool call, e.g. magic_eval("extract all")
        v
magic-agent-bridge   --TCP, 127.0.0.1:5566-->  magic_bridge.tcl
   (stdio MCP server)                        (sourced into your
                                               already-running Magic)
        ^                                          |
        +---------------- result text -------------+
```

- `magic_bridge.tcl` - source this ONCE inside a Magic session you already
  have open. Opens a localhost-only socket server.
- `src/magic_agent_bridge/server.py` - the MCP-facing side. Register this
  with Claude Code (or any MCP client) via the `magic-agent-bridge` console
  script; it forwards tool calls to the socket above.

## Setup

```bash
pip install -e .
```

1. Launch Magic as normal:
   ```bash
   magic -T <techfile> &
   ```
2. In the tkcon console, source the bridge:
   ```
   source /path/to/magic-agent-bridge/magic_bridge.tcl
   ```
   You should see: `magic_bridge: listening on 127.0.0.1:5566`
3. Register the MCP server with Claude Code:
   ```bash
   claude mcp add magic-bridge -- magic-agent-bridge
   ```
4. In a Claude Code session, tools like `magic_eval`, `magic_load`,
   `magic_extract_pipeline`, `magic_drc_report`, `magic_paint`,
   `magic_query_box`, and `magic_screenshot` are now available. Claude can
   now, e.g., load a cell, run the extraction pipeline, check DRC, paint
   geometry, and verify layout state as text - all without you typing
   anything into tkcon yourself.

## What this does NOT do (yet)

- **Doesn't draw for you from scratch via natural language.** `magic_eval`
  can run any Magic command including `paint`/`box`, so in principle an
  agent could construct geometry rectangle by rectangle - but there's no
  higher-level "draw an inverter with W=1.8um" primitive yet. A natural next
  step is a small library of parametric-cell generators (inverter, chain,
  ring-oscillator-of-N) that emit the right sequence of `box`/`paint`
  commands from a spec.
- **No auth beyond localhost binding.** Fine for a solo dev machine. Do not
  run this where other local users/processes are untrusted.
- **One Magic session per MCP server.** No multi-session or port-negotiation
  support - if you need to talk to two Magic instances at once, set
  `magic_bridge_port` to a different value in one of them, then point a
  second MCP server at it via the `MAGIC_BRIDGE_PORT` env var.
- **Windows screenshot support is missing.** The screenshot tool supports
  macOS (window-scoped) and Linux (`scrot`/`import`/`grim`); on Windows it
  returns an explicit error rather than a screenshot. All other tools work
  fine on Windows if Magic itself is reachable (e.g. running under WSL).

## Status

v2 - structured query tools, `.ext` file parsing, DRC reporting, layout
painting/erasing/labeling, window-scoped screenshots on macOS, and
env-var-configurable host/port, on top of the original raw command bridge.
Built for solo/small-team use; contributions and issues welcome.
