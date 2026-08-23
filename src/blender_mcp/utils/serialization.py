"""
Serialization utilities for Blender RNA properties, mathutils, and IDProperty types.
"""

from __future__ import annotations

import math
from typing import Any


def serialize_bpy_value(val: Any, depth: int = 0, max_depth: int = 3) -> Any:
    """Converts Blender data structures and mathutils objects to JSON-serializable types."""
    if val is None or isinstance(val, (bool, int, str)):
        return val

    if isinstance(val, float):
        if math.isnan(val) or math.isinf(val):
            return str(val)
        return val

    # Mathutils types
    type_name = type(val).__name__
    if type_name in ("Euler", "MockEuler") or hasattr(val, "order"):
        return {"angles": list(val), "order": getattr(val, "order", "XYZ")}

    if type_name in ("Quaternion", "MockQuaternion") or hasattr(val, "w"):
        return {"w": float(val.w), "x": float(val.x), "y": float(val.y), "z": float(val.z)}

    if type_name in ("Matrix", "MockMatrix"):
        return [list(row) for row in val]

    if type_name in ("Vector", "Color", "MockVector", "MockColor") or hasattr(val, "to_tuple"):
        return list(val)

    if isinstance(val, (list, tuple)):
        return [serialize_bpy_value(v, depth + 1, max_depth) for v in val]

    if isinstance(val, (set, frozenset)):
        return [serialize_bpy_value(v, depth + 1, max_depth) for v in sorted(val, key=str)]

    if isinstance(val, dict):
        return {str(k): serialize_bpy_value(v, depth + 1, max_depth) for k, v in val.items()}

    # IDProperty and array types
    if hasattr(val, "to_list"):
        return [serialize_bpy_value(v, depth + 1, max_depth) for v in val.to_list()]

    if hasattr(val, "to_dict"):
        return {str(k): serialize_bpy_value(v, depth + 1, max_depth) for k, v in val.to_dict().items()}

    # bpy_struct / RNA types
    if hasattr(val, "rna_type"):
        if depth >= max_depth:
            name = getattr(val, "name", "unnamed")
            return f"<{val.rna_type.name}: {name}>"
        res: dict[str, Any] = {"_rna_type": val.rna_type.name}
        if hasattr(val, "name"):
            res["name"] = val.name
        return res

    # Object fallback
    if hasattr(val, "__iter__") and not isinstance(val, (str, bytes)):
        try:
            return [serialize_bpy_value(v, depth + 1, max_depth) for v in val]
        except Exception:
            pass

    return str(val)
