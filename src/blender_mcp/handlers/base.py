"""
Base handler defining runtime execution environment, active mode switching, and transaction management.
"""

from __future__ import annotations

import contextlib
from typing import Any, Generator, Optional
from blender_mcp.exceptions import BlenderConnectionError, BlenderExecutionError, TransactionFailure


class BaseHandler:
    """Base class for all domain-specific Blender execution handlers."""

    @classmethod
    def get_bpy(cls) -> Any:
        """Returns the active bpy module or raises an error if not in a Blender runtime."""
        try:
            import bpy
            return bpy
        except ImportError as e:
            raise BlenderConnectionError(
                "bpy module is not available. Ensure this handler is invoked inside Blender runtime."
            ) from e

    @classmethod
    def get_object(cls, name: str) -> Any:
        """Retrieves an object by name from bpy.data.objects or raises BlenderExecutionError."""
        bpy = cls.get_bpy()
        obj = bpy.data.objects.get(name)
        if not obj:
            raise BlenderExecutionError(f"Object '{name}' not found in bpy.data.objects.")
        return obj

    @classmethod
    def get_scene(cls, name: Optional[str] = None) -> Any:
        """Retrieves a scene by name or returns the active context scene."""
        bpy = cls.get_bpy()
        if name:
            scene = bpy.data.scenes.get(name)
            if not scene:
                raise BlenderExecutionError(f"Scene '{name}' not found in bpy.data.scenes.")
            return scene
        return bpy.context.scene

    @classmethod
    def get_material(cls, name: str) -> Any:
        """Retrieves a material by name from bpy.data.materials or raises BlenderExecutionError."""
        bpy = cls.get_bpy()
        mat = bpy.data.materials.get(name)
        if not mat:
            raise BlenderExecutionError(f"Material '{name}' not found in bpy.data.materials.")
        return mat

    @classmethod
    @contextlib.contextmanager
    def active_mode(cls, obj: Any, mode: str = "OBJECT") -> Generator[None, None, None]:
        """Context manager to ensure an object is active and in the requested mode, restoring previous state on exit."""
        bpy = cls.get_bpy()
        prev_active = bpy.context.view_layer.objects.active
        prev_mode = getattr(obj, "mode", "OBJECT")

        bpy.context.view_layer.objects.active = obj
        if hasattr(bpy.ops.object, "mode_set") and obj.mode != mode:
            try:
                bpy.ops.object.mode_set(mode=mode)
            except Exception:
                pass

        try:
            yield
        finally:
            if hasattr(bpy.ops.object, "mode_set") and hasattr(obj, "mode") and obj.mode != prev_mode:
                try:
                    bpy.ops.object.mode_set(mode=prev_mode)
                except Exception:
                    pass
            if prev_active and prev_active.name in bpy.data.objects:
                bpy.context.view_layer.objects.active = prev_active

    @classmethod
    @contextlib.contextmanager
    def transaction(cls, description: str = "MCP Transaction") -> Generator[None, None, None]:
        """Context manager providing transactional undo push and automatic rollback on failure."""
        bpy = cls.get_bpy()
        if hasattr(bpy.ops.ed, "undo_push"):
            bpy.ops.ed.undo_push(message=description)

        try:
            yield
        except Exception as e:
            if hasattr(bpy.ops.ed, "undo"):
                bpy.ops.ed.undo()
            raise TransactionFailure(f"Transaction '{description}' failed and was rolled back: {str(e)}") from e
