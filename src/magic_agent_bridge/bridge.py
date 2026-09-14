"""bridge.py — TCP communication layer for magic-agent-bridge.

Host and port are configurable via environment variables:
    MAGIC_BRIDGE_HOST  (default 127.0.0.1)
    MAGIC_BRIDGE_PORT  (default 5566)
"""

import os
import socket

MAGIC_HOST: str = os.environ.get("MAGIC_BRIDGE_HOST", "127.0.0.1")
MAGIC_PORT: int = int(os.environ.get("MAGIC_BRIDGE_PORT", "5566"))


def send(command: str, timeout: float = 15.0) -> str:
    """Send one Tcl command to the running Magic bridge and return the response line.

    Returns a string starting with "OK " on success or "ERR " on failure.
    Never raises — connection errors are returned as ERR strings.
    """
    try:
        with socket.create_connection((MAGIC_HOST, MAGIC_PORT), timeout=timeout) as s:
            s.sendall((command + "\n").encode("utf-8"))
            f = s.makefile("r")
            line = f.readline()
            if not line:
                return "ERR (no response — is magic_bridge.tcl sourced in Magic?)"
            return line.rstrip("\n")
    except (ConnectionRefusedError, OSError) as e:
        return f"ERR connection failed: {e}. Is magic_bridge.tcl sourced inside Magic?"
