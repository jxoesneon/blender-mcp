"""
Sculpt mode settings and brush data-block management execution handler.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from blender_mcp.handlers.base import BaseHandler


class SculptPaintHandler(BaseHandler):
    """Manages sculpt mode settings and brush data-blocks."""

    @classmethod
    def _sculpt_settings(cls, bpy: Any) -> Any:
        return bpy.context.tool_settings.sculpt

    @classmethod
    def manage_sculpt_settings(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        bpy = cls.get_bpy()
        action = params.get("action")
        object_name = params.get("object_name")
        symmetry_x = params.get("symmetry_x")
        symmetry_y = params.get("symmetry_y")
        symmetry_z = params.get("symmetry_z")
        use_dyntopo = params.get("use_dyntopo")
        detail_size = params.get("detail_size")
        remesh_voxel_size = params.get("remesh_voxel_size")
        remesh_adaptivity = params.get("remesh_adaptivity")

        if action == "enter_sculpt":
            obj = cls.get_object(object_name) if object_name else bpy.context.active_object
            if obj is None:
                raise ValueError("No active object and no object_name provided for enter_sculpt.")
            bpy.context.view_layer.objects.active = obj
            if obj.mode != "SCULPT":
                bpy.ops.object.mode_set(mode="SCULPT")
            return {"status": "success", "object_name": obj.name, "mode": obj.mode}

        if action == "exit_sculpt":
            obj = bpy.context.active_object
            if obj is not None and obj.mode == "SCULPT":
                bpy.ops.object.mode_set(mode="OBJECT")
            return {"status": "success", "mode": obj.mode if obj else None}

        if action == "set_symmetry":
            sculpt = cls._sculpt_settings(bpy)
            updated: Dict[str, Any] = {}
            if symmetry_x is not None:
                sculpt.use_symmetry_x = bool(symmetry_x)
                updated["symmetry_x"] = bool(symmetry_x)
            if symmetry_y is not None:
                sculpt.use_symmetry_y = bool(symmetry_y)
                updated["symmetry_y"] = bool(symmetry_y)
            if symmetry_z is not None:
                sculpt.use_symmetry_z = bool(symmetry_z)
                updated["symmetry_z"] = bool(symmetry_z)
            return {"status": "success", "symmetry": updated}

        if action == "set_dyntopo":
            sculpt = cls._sculpt_settings(bpy)
            if use_dyntopo is not None and hasattr(bpy.ops.sculpt, "dynamic_topology_toggle"):
                current = getattr(sculpt, "use_symmetrize_dyn_topo", False)
                try:
                    is_on = bool(getattr(sculpt, "detail_type", "")) and "DYNTOPO" in str(getattr(sculpt, "detail_type", ""))
                except Exception:
                    is_on = False
                if bool(use_dyntopo) != is_on:
                    try:
                        bpy.ops.sculpt.dynamic_topology_toggle()
                    except Exception:
                        pass
            if detail_size is not None and hasattr(sculpt, "detail_size"):
                sculpt.detail_size = float(detail_size)
            return {
                "status": "success",
                "detail_type": str(getattr(sculpt, "detail_type", None)),
                "detail_size": getattr(sculpt, "detail_size", None),
            }

        if action == "set_remesh":
            obj = bpy.context.active_object
            if obj is None:
                raise ValueError("No active object for voxel remesh.")
            if obj.mode != "SCULPT":
                bpy.context.view_layer.objects.active = obj
                if obj.mode != "OBJECT":
                    bpy.ops.object.mode_set(mode="OBJECT")
                bpy.ops.object.mode_set(mode="SCULPT")
            sculpt = cls._sculpt_settings(bpy)
            if remesh_voxel_size is not None and hasattr(sculpt, "detail_size"):
                sculpt.detail_size = float(remesh_voxel_size)
            if remesh_adaptivity is not None and hasattr(sculpt, "detail_percent"):
                try:
                    sculpt.detail_percent = float(remesh_adaptivity)
                except Exception:
                    pass
            if hasattr(bpy.ops.object, "voxel_remesh"):
                bpy.ops.object.voxel_remesh()
            return {
                "status": "success",
                "remesh_voxel_size": getattr(sculpt, "detail_size", None),
            }

        if action == "get_info":
            obj = bpy.context.active_object
            sculpt = cls._sculpt_settings(bpy)
            info: Dict[str, Any] = {
                "active_object": obj.name if obj else None,
                "mode": obj.mode if obj else None,
                "symmetry_x": getattr(sculpt, "use_symmetry_x", None),
                "symmetry_y": getattr(sculpt, "use_symmetry_y", None),
                "symmetry_z": getattr(sculpt, "use_symmetry_z", None),
                "detail_type": getattr(sculpt, "detail_type", None),
                "detail_size": getattr(sculpt, "detail_size", None),
                "active_brush": sculpt.brush.name if hasattr(sculpt, "brush") and sculpt.brush else None,
            }
            return {"status": "success", "sculpt_settings": info}

        raise ValueError(f"Unknown sculpt settings action: '{action}'")

    @classmethod
    def _resolve_brush(cls, bpy: Any, name: Optional[str]) -> Any:
        if not name:
            return None
        brush = bpy.data.brushes.get(name)
        if brush is None:
            raise ValueError(f"Brush '{name}' not found in bpy.data.brushes.")
        return brush

    @classmethod
    def manage_brushes(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        bpy = cls.get_bpy()
        action = params.get("action")
        brush_name = params.get("brush_name")
        new_name = params.get("new_name")
        brush_type = params.get("brush_type")
        properties = params.get("properties", {}) or {}

        if action == "list":
            brushes: List[Dict[str, Any]] = []
            for b in bpy.data.brushes:
                info: Dict[str, Any] = {
                    "name": b.name,
                    "size": getattr(b, "size", None),
                    "strength": getattr(b, "strength", None),
                    "spacing": getattr(b, "spacing", None),
                    "use_paint_antialiasing": getattr(b, "use_paint_antialiasing", None),
                }
                if hasattr(b, "sculpt_tool"):
                    info["sculpt_tool"] = b.sculpt_tool
                if hasattr(b, "blend_mode"):
                    info["blend_mode"] = b.blend_mode
                brushes.append(info)
            return {"status": "success", "brushes": brushes, "count": len(brushes)}

        if action == "create":
            name = new_name or brush_name or "Brush"
            brush = bpy.data.brushes.new(name=name)
            if brush_type and hasattr(brush, "use_paint_sculpt"):
                if brush_type == "SCULPT":
                    if hasattr(brush, "use_paint_sculpt"):
                        brush.use_paint_sculpt = True
                elif brush_type == "PAINT":
                    if hasattr(brush, "use_paint_image"):
                        brush.use_paint_image = True
                elif brush_type == "WEIGHT":
                    if hasattr(brush, "use_paint_weight"):
                        brush.use_paint_weight = True
                elif brush_type == "TEXTURE":
                    if hasattr(brush, "use_paint_texture"):
                        brush.use_paint_texture = True
                elif brush_type == "GPENCIL":
                    if hasattr(brush, "use_paint_grease_pencil"):
                        brush.use_paint_grease_pencil = True
            return {"status": "success", "brush_name": brush.name}

        if action == "delete":
            brush = cls._resolve_brush(bpy, brush_name)
            bpy.data.brushes.remove(brush)
            return {"status": "success", "deleted_brush": brush_name}

        if action == "configure":
            brush = cls._resolve_brush(bpy, brush_name)
            updated: Dict[str, Any] = {}
            for key, value in properties.items():
                if hasattr(brush, key):
                    try:
                        setattr(brush, key, value)
                        updated[key] = value
                    except Exception:
                        pass
            if new_name and new_name != brush_name:
                brush.name = new_name
                updated["name"] = new_name
            return {"status": "success", "brush_name": brush.name, "updated": updated}

        if action == "set_active":
            brush = cls._resolve_brush(bpy, brush_name)
            mode = bpy.context.mode
            if mode == "SCULPT":
                bpy.context.tool_settings.sculpt.brush = brush
            elif mode in ("PAINT_TEXTURE", "IMAGE_PAINT"):
                if hasattr(bpy.context.tool_settings, "image_paint"):
                    bpy.context.tool_settings.image_paint.brush = brush
            elif mode == "PAINT_WEIGHT":
                if hasattr(bpy.context.tool_settings, "weight_paint"):
                    bpy.context.tool_settings.weight_paint.brush = brush
            elif mode == "PAINT_VERTEX":
                if hasattr(bpy.context.tool_settings, "vertex_paint"):
                    bpy.context.tool_settings.vertex_paint.brush = brush
            elif mode == "PAINT_GPENCIL":
                if hasattr(bpy.context.tool_settings, "gpencil_paint"):
                    bpy.context.tool_settings.gpencil_paint.brush = brush
            else:
                if hasattr(bpy.context.tool_settings, "sculpt"):
                    bpy.context.tool_settings.sculpt.brush = brush
            return {"status": "success", "active_brush": brush.name, "mode": mode}

        raise ValueError(f"Unknown brush action: '{action}'")
