"""
Unit tests for the IPC Client.
"""

import socket
import unittest
from unittest.mock import MagicMock, patch

from blender_mcp.client import BlenderIPCClient
from blender_mcp.exceptions import (
    BlenderConnectionError,
    BlenderExecutionError,
    BlenderTimeoutError,
)
from blender_mcp.utils.framing import encode_frame


class TestBlenderIPCClient(unittest.TestCase):
    def setUp(self):
        self.client = BlenderIPCClient(host="127.0.0.1", port=9876, timeout=2.0)

    @patch("socket.socket")
    def test_send_command_success(self, mock_socket_cls):
        mock_sock = MagicMock()
        mock_socket_cls.return_value = mock_sock

        success_response = {"success": True, "result": {"active_scene": "Scene"}}
        encoded = encode_frame(success_response)
        mock_sock.recv.side_effect = [encoded[:4], encoded[4:]]

        result = self.client.send_command("manage_scene", {"action": "get_active"})
        self.assertEqual(result, {"active_scene": "Scene"})
        mock_sock.connect.assert_called_with(("127.0.0.1", 9876))

    @patch("socket.socket")
    def test_send_command_execution_error(self, mock_socket_cls):
        mock_sock = MagicMock()
        mock_socket_cls.return_value = mock_sock

        error_response = {"success": False, "error": "Object not found", "traceback": "Traceback..."}
        encoded = encode_frame(error_response)
        mock_sock.recv.side_effect = [encoded[:4], encoded[4:]]

        with self.assertRaises(BlenderExecutionError) as ctx:
            self.client.send_command("inspect_bpy_path", {"path": "invalid"})
        self.assertIn("Object not found", str(ctx.exception))

    @patch("socket.socket")
    def test_send_command_malformed_response(self, mock_socket_cls):
        mock_sock = MagicMock()
        mock_socket_cls.return_value = mock_sock

        encoded = encode_frame(["not", "a", "dict"])
        mock_sock.recv.side_effect = [encoded[:4], encoded[4:]]

        with self.assertRaises(BlenderExecutionError):
            self.client.send_command("test")

    @patch("socket.socket")
    def test_send_command_timeout(self, mock_socket_cls):
        mock_sock = MagicMock()
        mock_socket_cls.return_value = mock_sock
        mock_sock.connect.side_effect = socket.timeout()

        with self.assertRaises(BlenderTimeoutError):
            self.client.send_command("test")

    @patch("socket.socket")
    def test_send_command_connection_refused(self, mock_socket_cls):
        mock_sock = MagicMock()
        mock_socket_cls.return_value = mock_sock
        mock_sock.connect.side_effect = ConnectionRefusedError()

        with self.assertRaises(BlenderConnectionError):
            self.client.send_command("test")


if __name__ == "__main__":
    unittest.main()
