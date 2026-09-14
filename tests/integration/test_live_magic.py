"""
Integration tests — require a live Magic session with magic_bridge.tcl sourced.

Run with:
    MAGIC_RUNNING=1 pytest tests/integration/ -v

These are automatically skipped in CI (no Magic available on cloud runners).
Set MAGIC_RUNNING=1 on a machine where Magic is open and magic_bridge.tcl is active.
"""

import json
import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("MAGIC_RUNNING") != "1",
    reason="Set MAGIC_RUNNING=1 with magic_bridge.tcl sourced inside Magic to run these tests",
)

from magic_agent_bridge.bridge import send
from magic_agent_bridge.server import (
    magic_drc_check,
    magic_drc_report,
    magic_eval,
    magic_query_box,
    magic_query_cells,
    magic_screenshot,
)


def test_ping_via_eval():
    result = magic_eval("expr 1 + 1")
    assert result == "OK 2"


def test_eval_returns_ok_prefix():
    result = magic_eval("puts hello")
    assert result.startswith("OK")


def test_drc_check_returns_ok():
    result = magic_drc_check()
    assert result.startswith("OK")


def test_drc_report_is_valid_json():
    result = magic_drc_report()
    data = json.loads(result)
    assert "violation_count" in data
    assert isinstance(data["violation_count"], int)
    assert "check_result" in data
    assert "why_result" in data


def test_query_box_returns_parseable_response():
    result = magic_query_box()
    # Either valid JSON or raw ERR — should not hard crash
    try:
        data = json.loads(result)
        assert "raw" in data or "llx" in data
    except json.JSONDecodeError:
        pytest.fail(f"magic_query_box returned non-JSON: {result}")


def test_query_cells_returns_list():
    result = magic_query_cells()
    data = json.loads(result)
    assert "cells" in data
    assert isinstance(data["cells"], list)


def test_screenshot_produces_valid_png(tmp_path):
    path = str(tmp_path / "magic_capture.png")
    result = magic_screenshot(path)
    assert "saved screenshot" in result, f"Unexpected result: {result}"
    p = Path(path)
    assert p.exists(), "Screenshot file was not created"
    assert p.stat().st_size > 0, "Screenshot file is empty"
    with open(path, "rb") as f:
        magic_bytes = f.read(8)
    assert magic_bytes == b"\x89PNG\r\n\x1a\n", "File is not a valid PNG"
