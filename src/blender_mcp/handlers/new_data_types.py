"""
Blender 5.x new Curves and Point Cloud data type handlers.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from blender_mcp.handlers.base import BaseHandler


class NewDataTypesHandler(BaseHandler):
    """Manages Blender 5.x new Curves and Point Cloud data types."""

    # ------------------------------------------------------------------
    # New Curves (hair curves / new curve objects)
    # ------------------------------------------------------------------

    @classmethod
    def manage_curves_new(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        bpy = cls.get_bpy()
        action = params.get("action")
        object_name = params.get("object_name")
        curve_count = params.get("curve_count")
        point_count = params.get("point_count")
        attribute_name = params.get("attribute_name")
        attribute_values = params.get("attribute_values")
        attribute_domain = params.get("attribute_domain", "POINT")

        if not hasattr(bpy.data, "curves"):
            raise RuntimeError("bpy.data.curves (new Curves type) is not available in this Blender version.")

        if action == "create":
            name = object_name or "Curves"
            curves_data = bpy.data.curves.new(name=name)
            obj = bpy.data.objects.new(name, curves_data)
            bpy.context.scene.collection.objects.link(obj)
            return {"status": "success", "object_name": obj.name, "data_name": curves_data.name}

        if action == "list":
            result: List[Dict[str, Any]] = []
            for cd in bpy.data.curves:
                info: Dict[str, Any] = {"name": cd.name}
                if hasattr(cd, "curve_count"):
                    info["curve_count"] = cd.curve_count
                if hasattr(cd, "point_count"):
                    info["point_count"] = cd.point_count
                result.append(info)
            return {"status": "success", "curves": result}

        if not object_name:
            raise ValueError("object_name is required for this action.")
        obj = cls.get_object(object_name)
        curves_data = obj.data

        if action == "delete":
            bpy.data.objects.remove(obj)
            if curves_data and curves_data.name in bpy.data.curves:
                bpy.data.curves.remove(curves_data)
            return {"status": "success", "deleted": object_name}

        if action == "add_points":
            if curve_count is not None and hasattr(curves_data, "curve_count"):
                try:
                    curves_data.curve_count = curve_count
                except Exception:
                    pass
            if point_count is not None and hasattr(curves_data, "point_count"):
                try:
                    curves_data.point_count = point_count
                except Exception:
                    pass
            return {
                "status": "success",
                "object_name": object_name,
                "curve_count": getattr(curves_data, "curve_count", 0),
                "point_count": getattr(curves_data, "point_count", 0),
            }

        if action == "set_attribute":
            if not attribute_name:
                raise ValueError("attribute_name is required for set_attribute.")
            if not attribute_values:
                raise ValueError("attribute_values is required for set_attribute.")
            attrs = curves_data.attributes if hasattr(curves_data, "attributes") else None
            if attrs is None:
                raise RuntimeError("Curves data-block has no attributes collection.")
            attr = attrs.get(attribute_name) if hasattr(attrs, "get") else None
            if attr is None:
                data_type = cls._infer_attribute_type(attribute_values)
                attr = attrs.new(attribute_name, data_type, attribute_domain)
            cls._set_attribute_values(attr, attribute_values)
            return {
                "status": "success",
                "object_name": object_name,
                "attribute_name": attribute_name,
                "domain": attribute_domain,
            }

        if action == "get_info":
            info = {"name": curves_data.name, "object_name": object_name}
            if hasattr(curves_data, "curve_count"):
                info["curve_count"] = curves_data.curve_count
            if hasattr(curves_data, "point_count"):
                info["point_count"] = curves_data.point_count
            if hasattr(curves_data, "attributes"):
                info["attributes"] = [a.name for a in curves_data.attributes]
            return {"status": "success", "info": info}

        raise ValueError(f"Unknown curves action: '{action}'")

    # ------------------------------------------------------------------
    # Point Clouds
    # ------------------------------------------------------------------

    @classmethod
    def manage_pointclouds(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        bpy = cls.get_bpy()
        action = params.get("action")
        object_name = params.get("object_name")
        point_count = params.get("point_count")
        attribute_name = params.get("attribute_name")
        attribute_values = params.get("attribute_values")
        attribute_domain = params.get("attribute_domain", "POINT")

        if not hasattr(bpy.data, "pointclouds"):
            raise RuntimeError("bpy.data.pointclouds is not available in this Blender version.")

        if action == "create":
            name = object_name or "PointCloud"
            pc_data = bpy.data.pointclouds.new(name=name)
            obj = bpy.data.objects.new(name, pc_data)
            bpy.context.scene.collection.objects.link(obj)
            return {"status": "success", "object_name": obj.name, "data_name": pc_data.name}

        if action == "list":
            result: List[Dict[str, Any]] = []
            for pc in bpy.data.pointclouds:
                info: Dict[str, Any] = {"name": pc.name}
                if hasattr(pc, "point_count"):
                    info["point_count"] = pc.point_count
                result.append(info)
            return {"status": "success", "pointclouds": result}

        if not object_name:
            raise ValueError("object_name is required for this action.")
        obj = cls.get_object(object_name)
        pc_data = obj.data

        if action == "delete":
            bpy.data.objects.remove(obj)
            if pc_data and pc_data.name in bpy.data.pointclouds:
                bpy.data.pointclouds.remove(pc_data)
            return {"status": "success", "deleted": object_name}

        if action == "add_points":
            if point_count is not None and hasattr(pc_data, "point_count"):
                try:
                    pc_data.point_count = point_count
                except Exception:
                    pass
            return {
                "status": "success",
                "object_name": object_name,
                "point_count": getattr(pc_data, "point_count", 0),
            }

        if action == "set_attribute":
            if not attribute_name:
                raise ValueError("attribute_name is required for set_attribute.")
            if not attribute_values:
                raise ValueError("attribute_values is required for set_attribute.")
            attrs = pc_data.attributes if hasattr(pc_data, "attributes") else None
            if attrs is None:
                raise RuntimeError("Point cloud data-block has no attributes collection.")
            attr = attrs.get(attribute_name) if hasattr(attrs, "get") else None
            if attr is None:
                data_type = cls._infer_attribute_type(attribute_values)
                attr = attrs.new(attribute_name, data_type, attribute_domain)
            cls._set_attribute_values(attr, attribute_values)
            return {
                "status": "success",
                "object_name": object_name,
                "attribute_name": attribute_name,
                "domain": attribute_domain,
            }

        if action == "get_info":
            info = {"name": pc_data.name, "object_name": object_name}
            if hasattr(pc_data, "point_count"):
                info["point_count"] = pc_data.point_count
            if hasattr(pc_data, "attributes"):
                info["attributes"] = [a.name for a in pc_data.attributes]
            return {"status": "success", "info": info}

        raise ValueError(f"Unknown pointcloud action: '{action}'")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @classmethod
    def _infer_attribute_type(cls, values: List[Any]) -> str:
        if not values:
            return "FLOAT"
        first = values[0]
        if isinstance(first, (list, tuple)):
            if len(first) == 4:
                return "FLOAT_COLOR"
            if len(first) == 3:
                return "FLOAT_VECTOR"
            return "FLOAT_VECTOR"
        if isinstance(first, bool):
            return "BOOLEAN"
        if isinstance(first, int):
            return "INT"
        return "FLOAT"

    @classmethod
    def _set_attribute_values(cls, attr: Any, values: List[Any]) -> None:
        data = attr.data if hasattr(attr, "data") else None
        if data is None:
            return
        n = min(len(values), len(data))
        for i in range(n):
            item = data[i]
            val = values[i]
            if hasattr(item, "value"):
                item.value = val
            elif hasattr(item, "vector") and isinstance(val, (list, tuple)):
                item.vector = val
            elif hasattr(item, "color") and isinstance(val, (list, tuple)):
                item.color = val
            else:
                try:
                    item.value = val
                except Exception:
                    pass
