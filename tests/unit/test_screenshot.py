"""Unit tests for magic_screenshot — mocked subprocess and platform, no Magic required."""

import subprocess
from unittest.mock import MagicMock, call, patch

import pytest

from magic_agent_bridge.server import magic_screenshot


class TestMacOSScreenshot:
    def test_window_scoped_when_bounds_available(self, tmp_path):
        save_path = str(tmp_path / "test.png")
        osascript_ok = MagicMock(returncode=0, stdout="100 200 900 700")

        with patch("magic_agent_bridge.server.platform.system", return_value="Darwin"), \
             patch("magic_agent_bridge.server.subprocess.run",
                   side_effect=[osascript_ok, None]) as mock_run:
            result = magic_screenshot(save_path, delay_seconds=0)

        assert "saved screenshot" in result
        region_call = mock_run.call_args_list[-1]
        assert "-R" in region_call[0][0]
        assert "100,200,800,500" in region_call[0][0]

    def test_fallback_to_fullscreen_when_osascript_fails(self, tmp_path):
        save_path = str(tmp_path / "test.png")
        osascript_fail = MagicMock(returncode=1, stdout="")

        with patch("magic_agent_bridge.server.platform.system", return_value="Darwin"), \
             patch("magic_agent_bridge.server.subprocess.run",
                   side_effect=[osascript_fail, None]) as mock_run:
            result = magic_screenshot(save_path, delay_seconds=0)

        assert "saved screenshot" in result
        fallback_call = mock_run.call_args_list[-1]
        assert "screencapture" in fallback_call[0][0]
        assert "-x" in fallback_call[0][0]
        assert "-R" not in fallback_call[0][0]

    def test_screencapture_failure_returns_err(self, tmp_path):
        save_path = str(tmp_path / "test.png")
        osascript_fail = MagicMock(returncode=1, stdout="")

        with patch("magic_agent_bridge.server.platform.system", return_value="Darwin"), \
             patch("magic_agent_bridge.server.subprocess.run",
                   side_effect=[osascript_fail,
                                 subprocess.CalledProcessError(1, "screencapture")]):
            result = magic_screenshot(save_path, delay_seconds=0)

        assert result.startswith("ERR")


class TestLinuxScreenshot:
    def test_scrot_used_when_available(self, tmp_path):
        save_path = str(tmp_path / "test.png")

        with patch("magic_agent_bridge.server.platform.system", return_value="Linux"), \
             patch("magic_agent_bridge.server.shutil.which",
                   side_effect=lambda cmd: "/usr/bin/scrot" if cmd == "scrot" else None), \
             patch("magic_agent_bridge.server.subprocess.run") as mock_run:
            result = magic_screenshot(save_path, delay_seconds=0)

        assert "saved screenshot" in result
        mock_run.assert_called_once()
        assert "scrot" in mock_run.call_args[0][0]

    def test_import_used_when_scrot_absent(self, tmp_path):
        save_path = str(tmp_path / "test.png")

        def which_side(cmd):
            return "/usr/bin/import" if cmd == "import" else None

        with patch("magic_agent_bridge.server.platform.system", return_value="Linux"), \
             patch("magic_agent_bridge.server.shutil.which", side_effect=which_side), \
             patch("magic_agent_bridge.server.subprocess.run") as mock_run:
            result = magic_screenshot(save_path, delay_seconds=0)

        assert "saved screenshot" in result
        assert "import" in mock_run.call_args[0][0]

    def test_no_tool_returns_err(self, tmp_path):
        save_path = str(tmp_path / "test.png")

        with patch("magic_agent_bridge.server.platform.system", return_value="Linux"), \
             patch("magic_agent_bridge.server.shutil.which", return_value=None):
            result = magic_screenshot(save_path, delay_seconds=0)

        assert result.startswith("ERR")
        assert "scrot" in result.lower() or "screenshot" in result.lower()


class TestUnsupportedPlatform:
    def test_windows_returns_err(self, tmp_path):
        save_path = str(tmp_path / "test.png")

        with patch("magic_agent_bridge.server.platform.system", return_value="Windows"):
            result = magic_screenshot(save_path, delay_seconds=0)

        assert result.startswith("ERR")
