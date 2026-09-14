"""
MCP server that lets Claude Code (or any MCP-speaking agent) drive a live,
already-running Magic VLSI session over the TCP bridge opened by magic_bridge.tcl.

    pip install -e .
    (in Magic's tkcon) source /path/to/magic_bridge.tcl
    claude mcp add magic-bridge -- magic-agent-bridge
"""

import json
import platform
import shutil
import subprocess
import time

from mcp.server.fastmcp import FastMCP

from .bridge import send as _send
from .ext_parser import ExtParseError, parse_ext

mcp = FastMCP("magic-bridge")


def _strip_ok(result: str) -> str:
    """Strip the bridge's 'OK ' wire prefix; leave 'ERR ...' intact so failures stay visible."""
    return result[3:].strip() if result.startswith("OK ") else result


# raw eval / load / extraction pipeline / DRC / screenshot

@mcp.tool()
def magic_eval(command: str) -> str:
    """
    Run a raw Tcl/Magic command in the live Magic tkcon session and return
    the result. Examples: 'load inverter_v3', 'extract all', 'drc why',
    'select top cell', 'box 0 0 10 10'.

    The Magic session must already be running with magic_bridge.tcl sourced.
    This does NOT launch Magic — it talks to a session you already opened.
    """
    return _send(command)


@mcp.tool()
def magic_load(cellname: str) -> str:
    """Load a .mag cell into the live Magic layout window by name (no .mag extension)."""
    return _send(f"load {cellname}")


@mcp.tool()
def magic_extract_pipeline(cellname: str) -> str:
    """
    Run the full extract → patch-ready spice pipeline:
    load, select top cell, extract all, ext2spice lvs/cthresh 0/rthresh 0, ext2spice.
    Returns concatenated per-step output. Stops on first ERR so failures are visible.
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
    Capture a screenshot of the Magic window to save_path (.png).

    macOS: window-scoped via AppleScript bounds + screencapture -R (falls
           back to full-screen if Magic window cannot be located).
    Linux: uses scrot, import (ImageMagick), or grim — whichever is first found.

    Use this sparingly — prefer text-based tools (magic_drc_report,
    magic_parse_ext, magic_query_box) for verifiable state queries.
    """
    time.sleep(delay_seconds)
    try:
        _capture_screenshot(save_path)
        return f"saved screenshot to {save_path}"
    except (subprocess.CalledProcessError, OSError) as e:
        return f"ERR screenshot failed: {e}"
    except (NotImplementedError, RuntimeError) as e:
        return f"ERR {e}"


# structured queries + layout editing

@mcp.tool()
def magic_eval_batch(commands: list[str]) -> str:
    """Run several commands in sequence, stop on first ERR. Beats N separate round-trips."""
    results = []
    for cmd in commands:
        r = _send(cmd)
        results.append({"command": cmd, "result": r})
        if r.startswith("ERR"):
            break
    return json.dumps(results)


@mcp.tool()
def magic_query_box() -> str:
    """Current selection box as JSON — llx/lly/urx/ury/width/height, centilambda units."""
    result = _send("box values")
    if result.startswith("ERR"):
        return result
    payload = _strip_ok(result)
    parts = payload.split()
    if len(parts) >= 4:
        try:
            llx, lly, urx, ury = int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])
            return json.dumps({
                "llx": llx, "lly": lly, "urx": urx, "ury": ury,
                "width": urx - llx, "height": ury - lly,
            })
        except ValueError:
            pass
    return json.dumps({"raw": result})


@mcp.tool()
def magic_query_what() -> str:
    """What's currently selected, as JSON {"raw": ...}."""
    result = _send("what -list")
    return json.dumps({"raw": result})


@mcp.tool()
def magic_query_cells() -> str:
    """All cell names known to the session, as JSON {"cells": [...]}."""
    result = _send("cellname list allcells")
    if result.startswith("ERR"):
        return result
    payload = _strip_ok(result)
    cells = [c for c in payload.split() if c]
    return json.dumps({"cells": cells})


@mcp.tool()
def magic_query_labels() -> str:
    """Select all labels in the cell, then report what was selected."""
    select_r = _send("select labels")
    if select_r.startswith("ERR"):
        # bail here instead of falling through to `what` - otherwise we'd
        # report whatever was selected from a previous call, not labels
        return json.dumps({"error": select_r})
    result = _send("what -list")
    return json.dumps({"raw": result})


@mcp.tool()
def magic_parse_ext(ext_file_path: str) -> str:
    """
    Parse a .ext extraction file into JSON (meta/nodes/caps/subcaps/fets).
    Run magic_extract_pipeline first to generate the file.
    """
    try:
        data = parse_ext(ext_file_path)
        return json.dumps(data)
    except FileNotFoundError:
        return f"ERR file not found: {ext_file_path}"
    except ExtParseError as e:
        return f"ERR parse error: {e}"


@mcp.tool()
def magic_drc_report() -> str:
    """Run full DRC, return {violation_count, check_result, why_result} as JSON."""
    check = _send("drc check")  # forces a full re-scan; result is printed, not returned
    count_r = _send("drc list count total")
    why = _send("drc list why")
    count = 0
    if count_r.startswith("OK "):
        payload = _strip_ok(count_r)
        try:
            count = int(payload.split()[0])
        except (ValueError, IndexError):
            pass
    return json.dumps({
        "violation_count": count,
        "check_result": check,
        "why_result": why,
    })


@mcp.tool()
def magic_paint(layer: str, llx: int, lly: int, urx: int, ury: int) -> str:
    """Set the box to (llx, lly, urx, ury) and paint the given layer."""
    r1 = _send(f"box {llx} {lly} {urx} {ury}")
    if r1.startswith("ERR"):
        # bad box -> don't paint, we'd be hitting whatever region was left over
        return f"box: {r1}\npaint: skipped (box command failed)"
    r2 = _send(f"paint {layer}")
    return f"box: {r1}\npaint: {r2}"


@mcp.tool()
def magic_erase(layer: str, llx: int, lly: int, urx: int, ury: int) -> str:
    """Set the box to (llx, lly, urx, ury) and erase the given layer."""
    r1 = _send(f"box {llx} {lly} {urx} {ury}")
    if r1.startswith("ERR"):
        return f"box: {r1}\nerase: skipped (box command failed)"
    r2 = _send(f"erase {layer}")
    return f"box: {r1}\nerase: {r2}"


@mcp.tool()
def magic_place_label(name: str, layer: str, x: int, y: int) -> str:
    """Drop a point box at (x, y) and label it on the given layer."""
    r1 = _send(f"box {x} {y} {x} {y}")
    if r1.startswith("ERR"):
        return f"box: {r1}\nlabel: skipped (box command failed)"
    r2 = _send(f"label {name} center {layer}")
    return f"box: {r1}\nlabel: {r2}"


@mcp.tool()
def magic_move_to(dx: int, dy: int) -> str:
    """Move the current selection by (dx, dy) in internal units (centilambda)."""
    return _send(f"move {dx} {dy}")


@mcp.tool()
def magic_layout_summary() -> str:
    """
    Return a compact text report of the current layout state:
    current cell name, bounding box, and DRC status.
    Use this to check layout state without taking a screenshot.
    """
    lines = []
    cell_r = _send("cellname list window")
    lines.append(f"cell: {_strip_ok(cell_r)}")
    box_r = _send("box values")
    lines.append(f"box:  {_strip_ok(box_r)}")
    _send("drc check")  # force a full re-scan before reading the count
    drc_r = _send("drc list count total")
    lines.append(f"drc:  {_strip_ok(drc_r)}")
    return "\n".join(lines)


# Screenshot helpers, one per platform.

def _capture_screenshot(save_path: str) -> None:
    system = platform.system()
    if system == "Darwin":
        _capture_macos(save_path)
    elif system == "Linux":
        _capture_linux(save_path)
    else:
        raise NotImplementedError(
            f"Screenshot not supported on {system}. "
            "Use magic_eval / magic_query_box to inspect state as text."
        )


def _capture_macos(save_path: str) -> None:
    # Attempt window-scoped capture: get Magic window bounds via AppleScript,
    # then use screencapture -R x,y,w,h for a smaller image (~4-8x less tokens).
    try:
        script = (
            'tell application "System Events"\n'
            '    if exists process "magic" then\n'
            '        set p to process "magic"\n'
            '    else\n'
            '        set p to (first process whose name contains "magic")\n'
            '    end if\n'
            '    set b to bounds of (first window of p)\n'
            '    return (item 1 of b) & " " & (item 2 of b) & " " '
            '& (item 3 of b) & " " & (item 4 of b)\n'
            'end tell'
        )
        r = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=4,
        )
        if r.returncode == 0:
            parts = r.stdout.strip().split()
            if len(parts) == 4:
                x1, y1, x2, y2 = int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])
                w, h = x2 - x1, y2 - y1
                subprocess.run(
                    ["screencapture", "-x", "-R", f"{x1},{y1},{w},{h}", save_path],
                    check=True,
                )
                return
    except Exception:
        pass
    # Fallback: full screen
    subprocess.run(["screencapture", "-x", save_path], check=True)


def _capture_linux(save_path: str) -> None:
    for tool, args in [
        ("scrot", ["scrot", save_path]),
        ("import", ["import", "-window", "root", save_path]),
        ("grim", ["grim", save_path]),
    ]:
        if shutil.which(tool):
            subprocess.run(args, check=True)
            return
    raise RuntimeError(
        "No screenshot tool found on Linux. Install one: apt install scrot"
    )


# Entry point

def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
