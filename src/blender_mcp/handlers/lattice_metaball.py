"""
Lattice and Metaball data-blocks, modifiers, and elements execution handler.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from blender_mcp.handlers.base import BaseHandler


class LatticeMetaballHandler(BaseHandler):
    """Manages lattice data-blocks, lattice modifiers, and metaball objects/elements."""

    # ------------------------------------------------------------------ Lattice

    @classmethod
    def manage_lattices(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        bpy = cls.get_bpy()
        action = params.get("action")
        lattice_name = params.get("lattice_name")
        object_name = params.get("object_name")
        res_u = int(params.get("resolution_u", 2))
        res_v = int(params.get("resolution_v", 2))
        res_w = int(params.get("resolution_w", 2))
        points = params.get("points")

        if action == "list":
            lattices: List[Dict[str, Any]] = []
            for lat in bpy.data.lattices:
                lattices.append({
                    "name": lat.name,
                    "points_u": lat.points_u,
                    "points_v": lat.points_v,
                    "points_w": lat.points_w,
                    "points_count": len(lat.points),
                })
            return {"status": "success", "lattices": lattices}

        if action == "create":
            if not lattice_name:
                raise ValueError("lattice_name is required to create a lattice.")
            if lattice_name in bpy.data.lattices:
                raise ValueError(f"Lattice '{lattice_name}' already exists.")
            lat_data = bpy.data.lattices.new(name=lattice_name)
            lat_data.points_u = max(2, res_u)
            lat_data.points_v = max(2, res_v)
            lat_data.points_w = max(2, res_w)
            lat_obj = bpy.data.objects.new(lattice_name, lat_data)
            bpy.context.scene.collection.objects.link(lat_obj)
            return {
                "status": "success",
                "lattice_name": lat_data.name,
                "object_name": lat_obj.name,
                "resolution": [lat_data.points_u, lat_data.points_v, lat_data.points_w],
            }

        if not lattice_name:
            raise ValueError("lattice_name is required for this action.")
        lat_data = bpy.data.lattices.get(lattice_name)
        if not lat_data:
            raise ValueError(f"Lattice '{lattice_name}' not found in bpy.data.lattices.")

        if action == "delete":
            lat_obj = bpy.data.objects.get(lattice_name)
            if lat_obj:
                bpy.data.objects.remove(lat_obj, do_unlink=True)
            bpy.data.lattices.remove(lat_data, do_unlink=True)
            return {"status": "success", "deleted_lattice": lattice_name}

        if action == "get_info":
            pts: List[Dict[str, Any]] = []
            for i, p in enumerate(lat_data.points):
                pts.append({"index": i, "co_deform": list(p.co_deform)})
            return {
                "status": "success",
                "lattice_name": lat_data.name,
                "resolution": [lat_data.points_u, lat_data.points_v, lat_data.points_w],
                "points_count": len(lat_data.points),
                "points": pts,
            }

        if action == "set_points":
            if not points:
                raise ValueError("points is required for set_points action.")
            if len(points) > len(lat_data.points):
                raise ValueError(
                    f"Provided {len(points)} points but lattice '{lattice_name}' has only "
                    f"{len(lat_data.points)} points."
                )
            for i, co in enumerate(points):
                if len(co) != 3:
                    raise ValueError(f"Point at index {i} must have 3 floats, got {len(co)}.")
                lat_data.points[i].co_deform = tuple(float(v) for v in co)
            return {
                "status": "success",
                "lattice_name": lat_data.name,
                "updated_points": len(points),
            }

        if action == "assign_to_object":
            if not object_name:
                raise ValueError("object_name is required for assign_to_object action.")
            obj = cls.get_object(object_name)
            mod_name = f"Lattice_{lattice_name}"
            lat_obj = bpy.data.objects.get(lattice_name)
            if not lat_obj:
                raise ValueError(
                    f"Lattice object '{lattice_name}' not found in bpy.data.objects. "
                    "Ensure the lattice was created with the 'create' action."
                )
            mod = obj.modifiers.new(name=mod_name, type="LATTICE")
            mod.object = lat_obj
            return {
                "status": "success",
                "object_name": obj.name,
                "modifier_name": mod.name,
                "lattice_object": lat_obj.name,
            }

        raise ValueError(f"Unknown lattice action: '{action}'.")

    # ----------------------------------------------------------------- Metaball

    @classmethod
    def manage_metaballs(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        bpy = cls.get_bpy()
        action = params.get("action")
        metaball_name = params.get("metaball_name")
        element_type = params.get("element_type")
        location = params.get("location")
        rotation = params.get("rotation")
        scale = params.get("scale")
        render_resolution = params.get("render_resolution")
        viewport_resolution = params.get("viewport_resolution")

        if action == "list":
            metaballs: List[Dict[str, Any]] = []
            for mb in bpy.data.metaballs:
                metaballs.append({
                    "name": mb.name,
                    "render_resolution": mb.render_resolution,
                    "viewport_resolution": mb.resolution,
                    "elements_count": len(mb.elements),
                })
            return {"status": "success", "metaballs": metaballs}

        if action == "create":
            if not metaball_name:
                raise ValueError("metaball_name is required to create a metaball.")
            if metaball_name in bpy.data.metaballs:
                raise ValueError(f"Metaball '{metaball_name}' already exists.")
            mb_data = bpy.data.metaballs.new(name=metaball_name)
            mb_obj = bpy.data.objects.new(metaball_name, mb_data)
            bpy.context.scene.collection.objects.link(mb_obj)
            return {
                "status": "success",
                "metaball_name": mb_data.name,
                "object_name": mb_obj.name,
            }

        if not metaball_name:
            raise ValueError("metaball_name is required for this action.")
        mb_data = bpy.data.metaballs.get(metaball_name)
        if not mb_data:
            raise ValueError(f"Metaball '{metaball_name}' not found in bpy.data.metaballs.")

        if action == "delete":
            mb_obj = bpy.data.objects.get(metaball_name)
            if mb_obj:
                bpy.data.objects.remove(mb_obj, do_unlink=True)
            bpy.data.metaballs.remove(mb_data, do_unlink=True)
            return {"status": "success", "deleted_metaball": metaball_name}

        if action == "get_info":
            elements: List[Dict[str, Any]] = []
            for elem in mb_data.elements:
                info: Dict[str, Any] = {
                    "type": elem.type,
                    "co": list(elem.co),
                    "size": elem.size,
                }
                if hasattr(elem, "rotation"):
                    info["rotation"] = list(elem.rotation)
                elements.append(info)
            return {
                "status": "success",
                "metaball_name": mb_data.name,
                "render_resolution": mb_data.render_resolution,
                "viewport_resolution": mb_data.resolution,
                "elements_count": len(mb_data.elements),
                "elements": elements,
            }

        if action == "add_element":
            if not element_type:
                raise ValueError("element_type is required for add_element action.")
            valid_types = ("BALL", "CAPSULE", "CUBE", "PLANE", "ELLIPSOID")
            if element_type not in valid_types:
                raise ValueError(
                    f"Invalid element_type '{element_type}'. Must be one of {valid_types}."
                )
            elem = mb_data.elements.new(type=element_type)
            if location is not None:
                if len(location) != 3:
                    raise ValueError("location must be a list of 3 floats.")
                elem.co = tuple(float(v) for v in location)
            if rotation is not None:
                if len(rotation) != 3:
                    raise ValueError("rotation must be a list of 3 floats.")
                elem.rotation = tuple(float(v) for v in rotation)
            if scale is not None:
                if len(scale) != 3:
                    raise ValueError("scale must be a list of 3 floats.")
                elem.size = tuple(float(v) for v in scale)
            return {
                "status": "success",
                "metaball_name": mb_data.name,
                "element_type": elem.type,
                "co": list(elem.co),
                "size": elem.size,
            }

        if action == "set_render_resolution":
            if render_resolution is None:
                raise ValueError("render_resolution is required for set_render_resolution action.")
            mb_data.render_resolution = float(render_resolution)
            return {
                "status": "success",
                "metaball_name": mb_data.name,
                "render_resolution": mb_data.render_resolution,
            }

        if action == "set_viewport_resolution":
            if viewport_resolution is None:
                raise ValueError("viewport_resolution is required for set_viewport_resolution action.")
            mb_data.resolution = float(viewport_resolution)
            return {
                "status": "success",
                "metaball_name": mb_data.name,
                "viewport_resolution": mb_data.resolution,
            }

        raise ValueError(f"Unknown metaball action: '{action}'.")
