"""
magic_mcp_server.py

MCP server that lets Claude Code (or any MCP-speaking agent) drive a live,
already-running Magic session over the TCP bridge opened by magic_bridge.tcl.

Setup:
    pip install "mcp[cli]"

Usage:
    1. In Magic's tkcon:  source /path/to/magic_bridge.tcl
    2. Register this server with Claude Code:
           claude mcp add magic-bridge -- python3 /path/to/magic_mcp_server.py
    3. In a Claude Code session, tools magic_eval / magic_screenshot /
       magic_load / magic_extract_pipeline are now available.

This is v0: a raw command-eval bridge plus a whole-screen screenshot.
Known rough edges (fine for solo dev use, worth fixing before wider release):
    - magic_screenshot captures the WHOLE screen, not just Magic's window
      (targeting a specific window by id needs a small AppleScript/
      Quartz helper - v1 item, not done here).
    - No reconnect/retry logic - if Magic bridge isn't running, calls fail
      fast with a clear error rather than hanging.
    - One command per call - no batching/transactions.
"""

import socket
import subprocess
import time

from mcp.server.fastmcp import FastMCP

MAGIC_HOST = "127.0.0.1"
MAGIC_PORT = 5566

mcp = FastMCP("magic-bridge")


def _send(command: str, timeout: float = 15.0) -> str:
    try:
        with socket.create_connection((MAGIC_HOST, MAGIC_PORT), timeout=timeout) as s:
            s.sendall((command + "\n").encode("utf-8"))
            f = s.makefile("r")
            line = f.readline()
            if not line:
                return "ERR (no response - is magic_bridge.tcl sourced in Magic?)"
            return line.rstrip("\n")
    except (ConnectionRefusedError, OSError) as e:
        return f"ERR connection failed: {e}. Is magic_bridge.tcl sourced inside Magic?"


@mcp.tool()
def magic_eval(command: str) -> str:
    """
    Run a raw Tcl/Magic command in the live Magic tkcon session and return
    the result. Examples: 'load inverter_v3', 'extract all', 'drc why',
    'select top cell', 'box 0 0 10 10'.

    The Magic session must already be running with magic_bridge.tcl sourced
    into it (see project README). This does NOT launch Magic - it talks to
    a session you already opened yourself.
    """
    return _send(command)


@mcp.tool()
def magic_load(cellname: str) -> str:
    """Load a .mag cell into the live Magic layout window by name (no .mag extension)."""
    return _send(f"load {cellname}")


@mcp.tool()
def magic_extract_pipeline(cellname: str) -> str:
    """
    Run the full extract -> patch-ready spice pipeline used in this project:
    load, select top cell, extract all, ext2spice lvs/cthresh 0/rthresh 0,
    then ext2spice. Returns the concatenated result of each step so errors
    are visible per-step rather than only at the end.
    """
    steps = [
        f"load {cellname}",
        "select top cell",
        "extract all",
        "ext2spice lvs",
        "ext2spice cthresh 0",
        "ext2spice rthresh 0",
        "ext2spice",
    ]
    results = []
    for step in steps:
        r = _send(step)
        results.append(f"$ {step}\n{r}")
        if r.startswith("ERR"):
            results.append("-- stopped: step failed --")
            break
    return "\n".join(results)


@mcp.tool()
def magic_drc_check() -> str:
    """Force a full DRC re-scan of the currently loaded cell and report violation count/status."""
    return _send("drc check")


@mcp.tool()
def magic_screenshot(save_path: str, delay_seconds: float = 0.3) -> str:
    """
    Capture a screenshot to save_path (macOS only, uses `screencapture`).
    v0 limitation: captures the WHOLE screen, not just the Magic window -
    bring Magic to the front before calling this. save_path should end in
    .png.
    """
    time.sleep(delay_seconds)
    try:
        subprocess.run(["screencapture", "-x", save_path], check=True)
        return f"saved screenshot to {save_path}"
    except subprocess.CalledProcessError as e:
        return f"ERR screencapture failed: {e}"


if __name__ == "__main__":
    mcp.run()
