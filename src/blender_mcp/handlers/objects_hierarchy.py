"""
Objects, Collections, Transforms, Hierarchy, and Constraints execution handler.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional
from blender_mcp.handlers.base import BaseHandler


class ObjectsHierarchyHandler(BaseHandler):
    """Handles object lifecycle, hierarchy parenting, collections, transforms, and constraints."""

    @classmethod
    def manage_objects(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        bpy = cls.get_bpy()
        action = params["action"]

        if action == "create":
            prim = params.get("primitive_type", "MESH_CUBE")
            name = params.get("name") or "Object"
            loc = params.get("location", [0.0, 0.0, 0.0])
            rot = params.get("rotation", [0.0, 0.0, 0.0])
            scl = params.get("scale", [1.0, 1.0, 1.0])

            if prim == "MESH_CUBE":
                bpy.ops.mesh.primitive_cube_add(location=loc, rotation=rot, scale=scl)
            elif prim == "MESH_SPHERE":
                bpy.ops.mesh.primitive_uv_sphere_add(location=loc, rotation=rot, scale=scl)
            elif prim == "MESH_CYLINDER":
                bpy.ops.mesh.primitive_cylinder_add(location=loc, rotation=rot, scale=scl)
            elif prim == "MESH_PLANE":
                bpy.ops.mesh.primitive_plane_add(location=loc, rotation=rot, scale=scl)
            elif prim.startswith("EMPTY"):
                bpy.ops.object.empty_add(location=loc, rotation=rot, scale=scl)
            elif prim == "CAMERA":
                bpy.ops.object.camera_add(location=loc, rotation=rot)
            elif prim == "ARMATURE":
                bpy.ops.object.armature_add(location=loc, rotation=rot, scale=scl)
            else:
                bpy.ops.mesh.primitive_cube_add(location=loc, rotation=rot, scale=scl)

            obj = bpy.context.active_object or bpy.data.objects.new(name)
            if name:
                obj.name = name
            return {"status": "success", "name": obj.name if obj else None}

        if action == "delete":
            names = params.get("names", [])
            if params.get("name") and params["name"] not in names:
                names.append(params["name"])
            deleted = []
            for n in names:
                obj = bpy.data.objects.get(n)
                if obj:
                    if params.get("delete_hierarchy") and hasattr(obj, "children_recursive"):
                        for child in obj.children_recursive:
                            bpy.data.objects.remove(child, do_unlink=True)
                    bpy.data.objects.remove(obj, do_unlink=True)
                    deleted.append(n)
            return {"status": "success", "deleted_objects": deleted}

        if action == "duplicate":
            names = params.get("names", [])
            linked = params.get("linked", False)
            if hasattr(bpy.ops.object, "select_all"):
                bpy.ops.object.select_all(action="DESELECT")
            for n in names:
                obj = bpy.data.objects.get(n)
                if obj:
                    obj.select_set(True)
                    bpy.context.view_layer.objects.active = obj
            bpy.ops.object.duplicate(linked=linked)
            duplicates = [o.name for o in bpy.context.selected_objects]
            return {"status": "success", "duplicates": duplicates}

        if action == "rename":
            obj = cls.get_object(params["name"])
            old = obj.name
            new_n = params["new_name"]
            obj.name = new_n
            return {"status": "success", "old_name": old, "name": obj.name}

        if action == "set_parent":
            parent = cls.get_object(params["parent_name"])
            child_names = params.get("child_names", [])
            for cn in child_names:
                child = cls.get_object(cn)
                child.parent = parent
                if params.get("keep_transform", True) and hasattr(parent, "matrix_world") and hasattr(parent.matrix_world, "inverted"):
                    child.matrix_parent_inverse = parent.matrix_world.inverted()
            return {"status": "success", "parent": parent.name, "children": child_names}

        if action == "clear_parent":
            child_names = params.get("child_names", [])
            for cn in child_names:
                child = cls.get_object(cn)
                child.parent = None
            return {"status": "success", "children": child_names}

        if action == "manipulate_parent_inverse":
            obj = cls.get_object(params["name"])
            mat = params.get("matrix_parent_inverse")
            if mat and hasattr(obj, "matrix_parent_inverse"):
                try:
                    import mathutils
                    obj.matrix_parent_inverse = mathutils.Matrix(mat)
                except Exception:
                    pass
            return {"status": "success", "name": obj.name}

        raise ValueError(f"Unknown object action: '{action}'")

    @classmethod
    def manage_collections(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        bpy = cls.get_bpy()
        action = params["action"]
        name = params["name"]

        if action == "create":
            col = bpy.data.collections.get(name) or bpy.data.collections.new(name)
            p_name = params.get("parent_collection")
            parent = bpy.data.collections.get(p_name) if p_name else bpy.context.scene.collection
            if col.name not in parent.children:
                parent.children.link(col)
            return {"status": "success", "collection": col.name}

        col = bpy.data.collections.get(name)
        if not col and action != "create":
            raise ValueError(f"Collection '{name}' not found.")

        if action == "delete":
            bpy.data.collections.remove(col)
            return {"status": "success", "deleted_collection": name}

        if action == "rename":
            new_n = params["new_name"]
            col.name = new_n
            return {"status": "success", "name": col.name}

        if action == "move":
            p_name = params.get("parent_collection")
            new_parent = bpy.data.collections.get(p_name) if p_name else bpy.context.scene.collection
            for p in list(bpy.data.collections):
                if col.name in p.children:
                    p.children.unlink(col)
            if col.name in bpy.context.scene.collection.children:
                bpy.context.scene.collection.children.unlink(col)
            new_parent.children.link(col)
            return {"status": "success", "collection": col.name, "parent": new_parent.name}

        if action in ("link_objects", "unlink_objects"):
            obj_names = params.get("object_names", [])
            for on in obj_names:
                obj = cls.get_object(on)
                if action == "link_objects":
                    if params.get("unlink_from_all_others"):
                        for uc in list(obj.users_collection):
                            uc.unlink(obj)
                    if obj.name not in col.objects:
                        col.objects.link(obj)
                else:
                    if obj.name in col.objects:
                        col.objects.unlink(obj)
            return {"status": "success", "collection": col.name, "objects": obj_names}

        if action == "set_visibility":
            if params.get("hide_viewport") is not None:
                col.hide_viewport = params["hide_viewport"]
            if params.get("hide_render") is not None:
                col.hide_render = params["hide_render"]
            if params.get("hide_select") is not None:
                col.hide_select = params["hide_select"]
            if params.get("color_tag") is not None and hasattr(col, "color_tag"):
                col.color_tag = params["color_tag"]
            return {"status": "success", "collection": col.name}

        raise ValueError(f"Unknown collection action: '{action}'")

    @classmethod
    def transform_object(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        obj = cls.get_object(params["name"])
        try:
            import mathutils
        except ImportError:
            mathutils = None

        target_prop = "delta_location" if params.get("delta") else "location"
        target_rot_prop = "delta_rotation_euler" if params.get("delta") else "rotation_euler"
        target_scale_prop = "delta_scale" if params.get("delta") else "scale"

        # Location
        if params.get("location") is not None:
            loc = params["location"]
            if params.get("relative_location"):
                curr = getattr(obj, target_prop)
                setattr(obj, target_prop, [c + l for c, l in zip(curr, loc)])
            else:
                setattr(obj, target_prop, loc)

        # Rotation
        if params.get("rotation") is not None:
            rot = params["rotation"]
            if params.get("rotation_in_degrees"):
                rot = [math.radians(r) for r in rot]
            if params.get("relative_rotation"):
                curr_rot = getattr(obj, target_rot_prop)
                setattr(obj, target_rot_prop, [c + r for c, r in zip(curr_rot, rot)])
            else:
                setattr(obj, target_rot_prop, rot)

        # Scale
        if params.get("scale") is not None:
            scl = params["scale"]
            if params.get("relative_scale"):
                curr_scl = getattr(obj, target_scale_prop)
                setattr(obj, target_scale_prop, [c * s for c, s in zip(curr_scl, scl)])
            else:
                setattr(obj, target_scale_prop, scl)

        return {
            "status": "success",
            "name": obj.name,
            "location": list(obj.location),
            "rotation_euler": list(obj.rotation_euler),
            "scale": list(obj.scale),
        }

    @classmethod
    def manage_constraints(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        obj = cls.get_object(params["object_name"])
        action = params["action"]
        c_name = params.get("constraint_name")
        c_type = params.get("constraint_type")
        config = params.get("config", {})

        bone_name = params.get("bone_name")
        if bone_name and hasattr(obj, "pose") and obj.pose:
            pbone = obj.pose.bones.get(bone_name)
            if not pbone:
                raise ValueError(f"Bone '{bone_name}' not found on armature '{obj.name}'.")
            constraints = pbone.constraints
        else:
            constraints = obj.constraints

        if action == "add":
            if not c_type:
                raise ValueError("constraint_type required to add constraint.")
            c = constraints.new(type=c_type)
            if c_name:
                c.name = c_name
            cls._apply_constraint_config(c, config)
            return {"status": "success", "constraint_name": c.name, "type": c.type}

        if action == "get":
            clist = [{"name": c.name, "type": c.type, "influence": c.influence} for c in constraints]
            return {"status": "success", "constraints": clist}

        if not c_name:
            raise ValueError("constraint_name required for action: " + action)

        c = constraints.get(c_name)
        if not c:
            raise ValueError(f"Constraint '{c_name}' not found.")

        if action == "remove":
            constraints.remove(c)
            return {"status": "success", "removed": c_name}

        if action == "update":
            cls._apply_constraint_config(c, config)
            return {"status": "success", "constraint_name": c.name}

        if action == "reorder" and params.get("new_index") is not None:
            idx = params["new_index"]
            c.name = c_name
            return {"status": "success", "reordered": c_name, "index": idx}

        raise ValueError(f"Unknown constraint action: '{action}'")

    @classmethod
    def manage_shape_keys(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        bpy = cls.get_bpy()
        obj = cls.get_object(params["object_name"])
        action = params["action"]

        if not hasattr(obj, "data") or not hasattr(obj.data, "shape_keys"):
            raise ValueError(f"Object '{obj.name}' has no mesh data supporting shape keys.")

        if action == "list":
            sk = obj.data.shape_keys
            if not sk:
                return {"status": "success", "object": obj.name, "shape_keys": []}
            blocks = [
                {"name": kb.name, "value": kb.value, "active": idx == obj.active_shape_key_index}
                for idx, kb in enumerate(sk.key_blocks)
            ]
            return {"status": "success", "object": obj.name, "shape_keys": blocks}

        if action == "add":
            key_name = params.get("key_name")
            shape_key_type = params.get("shape_key_type", "BASIS")
            from_mix = shape_key_type == "FROM_MIX"
            kb = obj.shape_key_add(name=key_name, from_mix=from_mix)
            return {"status": "success", "object": obj.name, "shape_key": kb.name, "value": kb.value}

        if action == "set_value":
            key_name = params["key_name"]
            value = params.get("value", 0.0)
            sk = obj.data.shape_keys
            if not sk or key_name not in sk.key_blocks:
                raise ValueError(f"Shape key '{key_name}' not found on object '{obj.name}'.")
            sk.key_blocks[key_name].value = float(value)
            return {"status": "success", "object": obj.name, "shape_key": key_name, "value": sk.key_blocks[key_name].value}

        if action == "set_active":
            key_name = params["key_name"]
            sk = obj.data.shape_keys
            if not sk or key_name not in sk.key_blocks:
                raise ValueError(f"Shape key '{key_name}' not found on object '{obj.name}'.")
            idx = list(sk.key_blocks.keys()).index(key_name)
            obj.active_shape_key_index = idx
            return {"status": "success", "object": obj.name, "active_shape_key": key_name, "index": idx}

        if action == "rename":
            key_name = params["key_name"]
            new_name = params["new_name"]
            sk = obj.data.shape_keys
            if not sk or key_name not in sk.key_blocks:
                raise ValueError(f"Shape key '{key_name}' not found on object '{obj.name}'.")
            kb = sk.key_blocks[key_name]
            kb.name = new_name
            return {"status": "success", "object": obj.name, "old_name": key_name, "shape_key": kb.name}

        if action == "remove":
            key_name = params["key_name"]
            sk = obj.data.shape_keys
            if not sk or key_name not in sk.key_blocks:
                raise ValueError(f"Shape key '{key_name}' not found on object '{obj.name}'.")
            kb = sk.key_blocks[key_name]
            obj.shape_key_remove(kb)
            return {"status": "success", "object": obj.name, "removed": key_name}

        raise ValueError(f"Unknown shape key action: '{action}'")

    @classmethod
    def manage_vertex_groups(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        obj = cls.get_object(params["object_name"])
        if not hasattr(obj, "vertex_groups"):
            raise ValueError(f"Object '{obj.name}' has no vertex groups (not a mesh).")
        action = params["action"]
        vgs = obj.vertex_groups

        if action == "list":
            groups = []
            for vg in vgs:
                count = 0
                if hasattr(obj.data, "vertices"):
                    for v in obj.data.vertices:
                        for g in v.groups:
                            if g.group == vg.index:
                                count += 1
                                break
                groups.append({"name": vg.name, "index": vg.index, "vertex_count": count})
            return {"status": "success", "object": obj.name, "vertex_groups": groups}

        if action == "add":
            name = params.get("group_name") or "Group"
            vg = vgs.new(name=name)
            return {"status": "success", "vertex_group": vg.name, "index": vg.index}

        if action == "remove":
            name = params.get("group_name")
            vg = vgs.get(name) if name else None
            if not vg:
                raise ValueError(f"Vertex group '{name}' not found.")
            vgs.remove(vg)
            return {"status": "success", "removed": name}

        if action == "assign":
            name = params.get("group_name")
            vg = vgs.get(name) if name else None
            if not vg:
                raise ValueError(f"Vertex group '{name}' not found.")
            indices = params.get("vertex_indices", [])
            weight = params.get("weight", 1.0)
            vg.add(indices, weight, "REPLACE")
            return {"status": "success", "vertex_group": vg.name, "assigned": len(indices), "weight": weight}

        if action == "remove_from":
            name = params.get("group_name")
            vg = vgs.get(name) if name else None
            if not vg:
                raise ValueError(f"Vertex group '{name}' not found.")
            indices = params.get("vertex_indices", [])
            vg.remove(indices)
            return {"status": "success", "vertex_group": vg.name, "removed_from": len(indices)}

        if action == "set_active":
            name = params.get("group_name")
            vg = vgs.get(name) if name else None
            if not vg:
                raise ValueError(f"Vertex group '{name}' not found.")
            obj.vertex_groups.active_index = vg.index
            return {"status": "success", "active": vg.name, "index": vg.index}

        if action == "rename":
            name = params.get("group_name")
            vg = vgs.get(name) if name else None
            if not vg:
                raise ValueError(f"Vertex group '{name}' not found.")
            old = vg.name
            vg.name = params["new_name"]
            return {"status": "success", "old_name": old, "name": vg.name}

        raise ValueError(f"Unknown vertex group action: '{action}'")

    @classmethod
    def _apply_constraint_config(cls, c: Any, config: Dict[str, Any]):
        for k, v in config.items():
            if k == "target" and isinstance(v, str):
                c.target = cls.get_object(v)
            elif k == "subtarget" and hasattr(c, "subtarget"):
                c.subtarget = v
            elif hasattr(c, k):
                try:
                    setattr(c, k, v)
                except Exception:
                    pass
