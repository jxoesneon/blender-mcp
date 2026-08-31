"""
Grease Pencil objects, layers, strokes, and materials execution handler.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from blender_mcp.handlers.base import BaseHandler


class GreasePencilHandler(BaseHandler):
    """Manages Grease Pencil objects, layers, strokes, and materials."""

    @classmethod
    def _get_layers(cls, obj: Any) -> Any:
        if hasattr(obj.data, "layers"):
            return obj.data.layers
        return None

    @classmethod
    def _get_active_frame(cls, layer: Any) -> Any:
        if hasattr(layer, "active_frame"):
            return layer.active_frame
        if hasattr(layer, "frames"):
            try:
                return layer.frames[0]
            except Exception:
                return None
        return None

    @classmethod
    def manage_grease_pencil(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        bpy = cls.get_bpy()
        action = params.get("action")
        object_name = params.get("object_name")
        layer_name = params.get("layer_name")
        new_name = params.get("new_name")
        points = params.get("points")
        material_name = params.get("material_name")
        properties = params.get("properties", {})

        if action == "create":
            if hasattr(bpy.ops.object, "grease_pencil_add"):
                bpy.ops.object.grease_pencil_add()
            elif hasattr(bpy.ops.object, "gpencil_add"):
                bpy.ops.object.gpencil_add()
            else:
                gp_data = bpy.data.grease_pencils.new(new_name or "GreasePencil") if hasattr(bpy.data, "grease_pencils") else None
                gp_obj = bpy.data.objects.new(new_name or "GreasePencil", gp_data)
                bpy.context.scene.collection.objects.link(gp_obj)
                bpy.context.view_layer.objects.active = gp_obj
                return {"status": "success", "object_name": gp_obj.name}

            obj = bpy.context.active_object
            if new_name and obj:
                obj.name = new_name
            return {"status": "success", "object_name": obj.name if obj else None}

        if not object_name:
            raise ValueError("object_name is required for this action.")
        obj = cls.get_object(object_name)

        if action == "list_layers":
            layers = cls._get_layers(obj)
            if layers is None:
                return {"status": "success", "layers": []}
            layer_list: List[Dict[str, Any]] = []
            for layer in layers:
                info: Dict[str, Any] = {"name": layer.name}
                for attr in ("opacity", "thickness", "use_lights", "use_onion_skinning", "blend_mode"):
                    if hasattr(layer, attr):
                        info[attr] = getattr(layer, attr)
                layer_list.append(info)
            return {"status": "success", "layers": layer_list}

        if action == "add_layer":
            layers = cls._get_layers(obj)
            if layers is None:
                raise RuntimeError("Grease Pencil layers not accessible on this object.")
            name = new_name or layer_name or "Layer"
            if hasattr(layers, "new"):
                layer = layers.new(name=name)
            else:
                layer = layers.add(name)
            if hasattr(layers, "active"):
                try:
                    layers.active = layer
                except Exception:
                    pass
            return {"status": "success", "layer_name": layer.name}

        if action == "remove_layer":
            layers = cls._get_layers(obj)
            if layers is None:
                raise RuntimeError("Grease Pencil layers not accessible on this object.")
            target = layers.get(layer_name) if hasattr(layers, "get") else None
            if target is None:
                for l in layers:
                    if l.name == layer_name:
                        target = l
                        break
            if target is None:
                raise ValueError(f"Layer '{layer_name}' not found.")
            layers.remove(target)
            return {"status": "success", "removed_layer": layer_name}

        if action == "set_active_layer":
            layers = cls._get_layers(obj)
            if layers is None:
                raise RuntimeError("Grease Pencil layers not accessible on this object.")
            target = layers.get(layer_name) if hasattr(layers, "get") else None
            if target is None:
                for l in layers:
                    if l.name == layer_name:
                        target = l
                        break
            if target is None:
                raise ValueError(f"Layer '{layer_name}' not found.")
            if hasattr(layers, "active"):
                layers.active = target
            return {"status": "success", "active_layer": layer_name}

        if action == "configure_layer":
            layers = cls._get_layers(obj)
            if layers is None:
                raise RuntimeError("Grease Pencil layers not accessible on this object.")
            target = layers.get(layer_name) if hasattr(layers, "get") else None
            if target is None:
                for l in layers:
                    if l.name == layer_name:
                        target = l
                        break
            if target is None:
                raise ValueError(f"Layer '{layer_name}' not found.")
            updated: Dict[str, Any] = {}
            for key, value in properties.items():
                if hasattr(target, key):
                    try:
                        setattr(target, key, value)
                        updated[key] = value
                    except Exception:
                        pass
            return {"status": "success", "layer_name": layer_name, "updated": updated}

        if action == "add_stroke":
            layers = cls._get_layers(obj)
            if layers is None:
                raise RuntimeError("Grease Pencil layers not accessible on this object.")
            target = layers.get(layer_name) if hasattr(layers, "get") else None
            if target is None:
                for l in layers:
                    if l.name == layer_name:
                        target = l
                        break
            if target is None:
                raise ValueError(f"Layer '{layer_name}' not found.")
            frame = cls._get_active_frame(target)
            if frame is None:
                raise RuntimeError(f"No active frame found on layer '{layer_name}'.")
            strokes = frame.strokes if hasattr(frame, "strokes") else None
            if strokes is None:
                raise RuntimeError("Strokes not accessible on frame.")
            stroke = strokes.new() if hasattr(strokes, "new") else strokes.add()
            pts_list = points or []
            if pts_list:
                if hasattr(stroke, "points") and hasattr(stroke.points, "add"):
                    stroke.points.add(len(pts_list))
                    for i, pt_spec in enumerate(pts_list):
                        co = pt_spec.get("co", [0.0, 0.0, 0.0])
                        if hasattr(stroke.points[i], "co"):
                            stroke.points[i].co = co
                        pressure = pt_spec.get("pressure")
                        if pressure is not None and hasattr(stroke.points[i], "pressure"):
                            stroke.points[i].pressure = pressure
                else:
                    for pt_spec in pts_list:
                        co = pt_spec.get("co", [0.0, 0.0, 0.0])
                        if hasattr(stroke, "points"):
                            stroke.points.add(1)
                            idx = len(stroke.points) - 1
                            stroke.points[idx].co = co
            return {"status": "success", "layer_name": layer_name, "point_count": len(pts_list)}

        if action == "list_strokes":
            layers = cls._get_layers(obj)
            if layers is None:
                raise RuntimeError("Grease Pencil layers not accessible on this object.")
            target = layers.get(layer_name) if hasattr(layers, "get") else None
            if target is None:
                for l in layers:
                    if l.name == layer_name:
                        target = l
                        break
            if target is None:
                raise ValueError(f"Layer '{layer_name}' not found.")
            frame = cls._get_active_frame(target)
            if frame is None:
                return {"status": "success", "strokes": []}
            strokes = frame.strokes if hasattr(frame, "strokes") else None
            stroke_list: List[Dict[str, Any]] = []
            if strokes:
                for idx, stroke in enumerate(strokes):
                    info: Dict[str, Any] = {"index": idx}
                    if hasattr(stroke, "points"):
                        info["point_count"] = len(stroke.points)
                    if hasattr(stroke, "material_index"):
                        info["material_index"] = stroke.material_index
                    stroke_list.append(info)
            return {"status": "success", "strokes": stroke_list}

        if action == "set_material":
            layers = cls._get_layers(obj)
            if layers is None:
                raise RuntimeError("Grease Pencil layers not accessible on this object.")
            target = layers.get(layer_name) if hasattr(layers, "get") else None
            if target is None:
                for l in layers:
                    if l.name == layer_name:
                        target = l
                        break
            if target is None:
                raise ValueError(f"Layer '{layer_name}' not found.")
            frame = cls._get_active_frame(target)
            if frame is None:
                raise RuntimeError(f"No active frame found on layer '{layer_name}'.")
            strokes = frame.strokes if hasattr(frame, "strokes") else None
            if not strokes or len(strokes) == 0:
                raise RuntimeError("No strokes available to assign material.")
            mat = cls.get_material(material_name)
            if mat.name not in [m.name for m in obj.data.materials] if hasattr(obj.data, "materials") else True:
                if hasattr(obj.data, "materials"):
                    obj.data.materials.append(mat)
            mat_index = list(obj.data.materials).index(mat) if hasattr(obj.data, "materials") else 0
            for stroke in strokes:
                if hasattr(stroke, "material_index"):
                    stroke.material_index = mat_index
            return {"status": "success", "material_name": material_name, "material_index": mat_index}

        raise ValueError(f"Unknown grease pencil action: '{action}'")
