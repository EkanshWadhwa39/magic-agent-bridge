"""ext_parser.py — Parse Magic .ext extraction files into JSON-serialisable dicts.

Usage:
    from magic_agent_bridge.ext_parser import parse_ext, ExtParseError

    data = parse_ext("/path/to/cell.ext")
    # data keys: meta, nodes, caps, subcaps, fets

The .ext format is line-oriented with keyword-prefixed records:
    timestamp, version, tech, style, scale, resistclasses
    node, cap, subcap, fet
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


class ExtParseError(ValueError):
    """Raised when a .ext file line cannot be parsed."""


def _tokenize(line: str) -> list[str]:
    """Split a .ext line into tokens, respecting double-quoted strings (quotes stripped)."""
    tokens: list[str] = []
    for m in re.finditer(r'"[^"]*"|[^\s]+', line):
        tok = m.group()
        if tok.startswith('"') and tok.endswith('"'):
            tok = tok[1:-1]
        tokens.append(tok)
    return tokens


def parse_ext(path: str | Path) -> dict[str, Any]:
    """Parse a Magic .ext file from disk into a structured dict.

    Returns a dict with keys:
        meta       — header fields (timestamp, version, tech, style, scale, resistclasses)
        nodes      — list of node records
        caps       — list of inter-node capacitor records (value_ff in femtofarads)
        subcaps    — list of substrate capacitor records (can be negative)
        fets       — list of transistor records

    Raises:
        FileNotFoundError  if the file does not exist.
        ExtParseError      if a data line is malformed.
    """
    text = Path(path).read_text()
    return _parse(text, source=str(path))


def parse_ext_text(text: str, source: str = "<string>") -> dict[str, Any]:
    """Parse .ext content from a string (useful for testing without a file)."""
    return _parse(text, source=source)


def _parse(text: str, source: str) -> dict[str, Any]:
    meta: dict[str, Any] = {}
    nodes: list[dict] = []
    caps: list[dict] = []
    subcaps: list[dict] = []
    fets: list[dict] = []

    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            toks = _tokenize(line)
            kw = toks[0]

            if kw == "timestamp":
                meta["timestamp"] = int(toks[1])

            elif kw == "version":
                meta["version"] = toks[1]

            elif kw == "tech":
                meta["tech"] = toks[1]

            elif kw == "style":
                meta["style"] = " ".join(toks[1:])

            elif kw == "scale":
                if len(toks) < 4:
                    raise ExtParseError("scale line needs 3 integer fields")
                meta["scale"] = {
                    "int_scale": int(toks[1]),
                    "res_scale": int(toks[2]),
                    "cap_scale": int(toks[3]),
                }

            elif kw == "resistclasses":
                meta["resistclasses"] = [int(t) for t in toks[1:]]

            elif kw == "node":
                # node "<name>" <res_class> <cap_ff> <x> <y> <layer> <int...>
                if len(toks) < 7:
                    raise ExtParseError(
                        f"node line has {len(toks)} fields, expected at least 7"
                    )
                nodes.append({
                    "name": toks[1],
                    "res_class": int(toks[2]),
                    "cap_ff": float(toks[3]),
                    "x": int(toks[4]),
                    "y": int(toks[5]),
                    "layer": toks[6],
                    "layer_geometry": [int(t) for t in toks[7:]],
                })

            elif kw == "cap":
                # cap "<node_a>" "<node_b>" <value_ff>
                caps.append({
                    "node_a": toks[1],
                    "node_b": toks[2],
                    "value_ff": float(toks[3]),
                })

            elif kw == "subcap":
                # subcap "<node>" <value_ff>  (value can be negative)
                subcaps.append({
                    "node": toks[1],
                    "value_ff": float(toks[2]),
                })

            elif kw == "fet":
                # fet <type> <x1> <y1> <x2> <y2> <width> <length> "<substrate>"
                #     "<gate>" <gw> <ga>
                #     "<source>" <sw> <sa>
                #     "<drain>" <dw> <da>
                # ga/sa/da may be "0" or "area,perimeter" — stored as strings
                if len(toks) < 9:
                    raise ExtParseError(
                        f"fet line has {len(toks)} fields, expected at least 9"
                    )
                fet: dict[str, Any] = {
                    "type": toks[1],
                    "x1": int(toks[2]),
                    "y1": int(toks[3]),
                    "x2": int(toks[4]),
                    "y2": int(toks[5]),
                    "width": int(toks[6]),
                    "length": int(toks[7]),
                    "substrate": toks[8],
                }
                i = 9
                if i < len(toks): fet["gate"] = toks[i]; i += 1
                if i < len(toks): fet["gate_width"] = int(toks[i]); i += 1
                if i < len(toks): fet["gate_area"] = toks[i]; i += 1
                if i < len(toks): fet["source"] = toks[i]; i += 1
                if i < len(toks): fet["source_width"] = int(toks[i]); i += 1
                if i < len(toks): fet["source_area"] = toks[i]; i += 1
                if i < len(toks): fet["drain"] = toks[i]; i += 1
                if i < len(toks): fet["drain_width"] = int(toks[i]); i += 1
                if i < len(toks): fet["drain_area"] = toks[i]; i += 1
                fets.append(fet)

            # Unknown keywords (e.g. use/transform/end in hierarchical .ext) — silently skip

        except ExtParseError:
            raise
        except Exception as exc:
            raise ExtParseError(
                f"{source}:{lineno}: failed to parse '{line}': {exc}"
            ) from exc

    return {
        "meta": meta,
        "nodes": nodes,
        "caps": caps,
        "subcaps": subcaps,
        "fets": fets,
    }
