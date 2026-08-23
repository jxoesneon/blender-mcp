"""
Domain-specific exceptions for Blender MCP.
"""

from __future__ import annotations


class BlenderMCPError(Exception):
    """Base exception for all Blender MCP errors."""
    pass


class BlenderConnectionError(BlenderMCPError):
    """Raised when communication with Blender's background socket server fails."""
    pass


class BlenderExecutionError(BlenderMCPError):
    """Raised when an operation or script execution inside Blender raises an unhandled exception."""
    def __init__(self, message: str, traceback_str: str | None = None):
        super().__init__(message)
        self.traceback_str = traceback_str


class BlenderTimeoutError(BlenderMCPError):
    """Raised when a command times out waiting for Blender's main thread to complete."""
    pass


class BlenderValidationError(BlenderMCPError):
    """Raised when incoming parameters fail validation checks."""
    pass


class TransactionFailure(BlenderMCPError):
    """Raised when an atomic multi-step operation fails and triggers an undo rollback."""
    pass
