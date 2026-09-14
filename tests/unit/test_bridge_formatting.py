"""Unit tests for bridge.py — mocked TCP socket, no Magic session required."""

import socket
from unittest.mock import MagicMock, patch

import pytest

from magic_agent_bridge.bridge import send


def _mock_conn(response: str) -> MagicMock:
    """Build a mock socket context manager returning the given response line."""
    mock_sock = MagicMock()
    mock_file = MagicMock()
    mock_file.readline.return_value = response
    mock_sock.__enter__ = lambda s: s
    mock_sock.__exit__ = MagicMock(return_value=False)
    mock_sock.makefile.return_value = mock_file
    return mock_sock


class TestResponseParsing:
    def test_ok_response_returned_verbatim(self):
        with patch("magic_agent_bridge.bridge.socket.create_connection",
                   return_value=_mock_conn("OK some result\n")):
            assert send("puts hello") == "OK some result"

    def test_err_response_returned_verbatim(self):
        with patch("magic_agent_bridge.bridge.socket.create_connection",
                   return_value=_mock_conn("ERR cell not loaded\n")):
            assert send("extract all") == "ERR cell not loaded"

    def test_trailing_newline_stripped(self):
        with patch("magic_agent_bridge.bridge.socket.create_connection",
                   return_value=_mock_conn("OK 2\n")):
            assert send("expr 1+1") == "OK 2"

    def test_empty_response_returns_err_string(self):
        with patch("magic_agent_bridge.bridge.socket.create_connection",
                   return_value=_mock_conn("")):
            result = send("drc check")
            assert result.startswith("ERR")
            assert "no response" in result.lower() or "ERR" in result

    def test_ok_with_embedded_content(self):
        with patch("magic_agent_bridge.bridge.socket.create_connection",
                   return_value=_mock_conn("OK 5 errors remain\n")):
            result = send("drc check")
            assert result == "OK 5 errors remain"


class TestConnectionErrors:
    def test_connection_refused_returns_err_string(self):
        with patch("magic_agent_bridge.bridge.socket.create_connection",
                   side_effect=ConnectionRefusedError("connection refused")):
            result = send("load foo")
        assert result.startswith("ERR connection failed")

    def test_os_error_returns_err_string(self):
        with patch("magic_agent_bridge.bridge.socket.create_connection",
                   side_effect=OSError("network unreachable")):
            result = send("load foo")
        assert result.startswith("ERR connection failed")

    def test_err_message_mentions_bridge(self):
        with patch("magic_agent_bridge.bridge.socket.create_connection",
                   side_effect=ConnectionRefusedError()):
            result = send("load foo")
        assert "magic_bridge" in result or "bridge" in result.lower()


class TestCommandSending:
    def test_command_sent_with_trailing_newline(self):
        mock_sock = _mock_conn("OK\n")
        with patch("magic_agent_bridge.bridge.socket.create_connection",
                   return_value=mock_sock):
            send("paint ndiff")
        mock_sock.sendall.assert_called_once_with(b"paint ndiff\n")

    def test_utf8_encoding_used(self):
        mock_sock = _mock_conn("OK\n")
        with patch("magic_agent_bridge.bridge.socket.create_connection",
                   return_value=mock_sock):
            send("puts hello")
        call_arg = mock_sock.sendall.call_args[0][0]
        assert isinstance(call_arg, bytes)

    def test_multiword_command_sent_intact(self):
        mock_sock = _mock_conn("OK\n")
        with patch("magic_agent_bridge.bridge.socket.create_connection",
                   return_value=mock_sock):
            send("box 0 0 100 100")
        mock_sock.sendall.assert_called_once_with(b"box 0 0 100 100\n")
