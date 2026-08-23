"""
High-performance IPC client communicating with Blender background socket server.
"""

from __future__ import annotations

import os
import socket
from typing import Any, Dict, Optional

from blender_mcp.exceptions import (
    BlenderConnectionError,
    BlenderExecutionError,
    BlenderTimeoutError,
)
from blender_mcp.utils.framing import encode_frame, read_frame


class BlenderIPCClient:
    """Manages length-prefixed TCP socket connections to the Blender MCP addon."""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        timeout: float = 30.0,
    ):
        self.host = host or os.environ.get("BLENDER_HOST", "127.0.0.1")
        self.port = int(port or os.environ.get("BLENDER_PORT", 9876))
        self.timeout = timeout

    def send_command(self, action: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Sends an action request to Blender and awaits framed JSON response."""
        payload = {"action": action, "params": params or {}}
        frame_bytes = encode_frame(payload)

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)

        try:
            sock.connect((self.host, self.port))
            sock.sendall(frame_bytes)
            response = read_frame(sock)
        except socket.timeout as e:
            raise BlenderTimeoutError(
                f"Command '{action}' timed out after {self.timeout}s waiting for Blender."
            ) from e
        except (ConnectionRefusedError, socket.error) as e:
            raise BlenderConnectionError(
                f"Could not connect to Blender MCP server at {self.host}:{self.port}. "
                "Ensure Blender is running and the Blender MCP addon server is started."
            ) from e
        finally:
            sock.close()

        if not isinstance(response, dict):
            raise BlenderExecutionError(f"Malformed response from Blender: {response}")

        if not response.get("success", False):
            err_msg = response.get("error", "Unknown error during Blender execution.")
            tb = response.get("traceback")
            raise BlenderExecutionError(err_msg, tb)

        return response.get("result", {})


default_client = BlenderIPCClient()
