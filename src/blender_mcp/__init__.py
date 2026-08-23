"""
Blender MCP - Enterprise-grade Model Context Protocol integration for Blender 3D.
"""

from blender_mcp.client import BlenderIPCClient, default_client
from blender_mcp.exceptions import (
    BlenderConnectionError,
    BlenderExecutionError,
    BlenderMCPError,
    BlenderTimeoutError,
    BlenderValidationError,
    TransactionFailure,
)
from blender_mcp.handlers import ACTION_REGISTRY, dispatch_blender_command

__version__ = "2.0.0"
__author__ = "Jose Eduardo Rojas Jimenez (jxoesneon)"

__all__ = [
    "BlenderIPCClient",
    "default_client",
    "BlenderMCPError",
    "BlenderConnectionError",
    "BlenderExecutionError",
    "BlenderTimeoutError",
    "BlenderValidationError",
    "TransactionFailure",
    "ACTION_REGISTRY",
    "dispatch_blender_command",
    "__version__",
]
