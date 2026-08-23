"""
Unit tests for socket binary framing utilities.
"""

import socket
import struct
import unittest
from unittest.mock import MagicMock

from blender_mcp.utils.framing import encode_frame, read_exact, read_frame


class TestFraming(unittest.TestCase):
    def test_encode_frame(self):
        payload = {"action": "test", "params": {"x": 42}}
        encoded = encode_frame(payload)
        self.assertTrue(len(encoded) > 4)
        length = struct.unpack(">I", encoded[:4])[0]
        self.assertEqual(length, len(encoded) - 4)

    def test_read_exact_success(self):
        mock_sock = MagicMock()
        mock_sock.recv.side_effect = [b"he", b"llo"]
        data = read_exact(mock_sock, 5)
        self.assertEqual(data, b"hello")

    def test_read_exact_socket_closed(self):
        mock_sock = MagicMock()
        mock_sock.recv.return_value = b""
        with self.assertRaises(ConnectionError):
            read_exact(mock_sock, 10)

    def test_read_frame(self):
        payload = {"result": "success", "data": [1, 2, 3]}
        encoded = encode_frame(payload)

        mock_sock = MagicMock()
        mock_sock.recv.side_effect = [encoded[:4], encoded[4:]]
        decoded = read_frame(mock_sock)
        self.assertEqual(decoded, payload)


if __name__ == "__main__":
    unittest.main()
