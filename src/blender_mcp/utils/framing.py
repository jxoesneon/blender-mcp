"""
Binary framing protocol utilities for TCP socket IPC with Blender.
Uses 4-byte big-endian length prefix framing (>I) to prevent truncation.
"""

from __future__ import annotations

import json
import socket
import struct
from typing import Any


def encode_frame(payload: Any) -> bytes:
    """Encodes a Python object into JSON and prefixes it with a 4-byte big-endian length header."""
    data = json.dumps(payload).encode("utf-8")
    header = struct.pack(">I", len(data))
    return header + data


def read_exact(sock: socket.socket, num_bytes: int) -> bytes:
    """Reads exactly num_bytes from the socket, accumulating chunks until complete."""
    chunks = []
    bytes_read = 0
    while bytes_read < num_bytes:
        chunk = sock.recv(min(num_bytes - bytes_read, 65536))
        if not chunk:
            raise ConnectionError("Socket connection closed before receiving expected bytes.")
        chunks.append(chunk)
        bytes_read += len(chunk)
    return b"".join(chunks)


def read_frame(sock: socket.socket) -> Any:
    """Reads a length-prefixed frame from the socket and parses the JSON payload."""
    header = read_exact(sock, 4)
    frame_len = struct.unpack(">I", header)[0]
    payload_bytes = read_exact(sock, frame_len)
    return json.loads(payload_bytes.decode("utf-8"))
