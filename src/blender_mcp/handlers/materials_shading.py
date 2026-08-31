"""
Materials, Shader Nodes, Textures, and UV Unwrapping execution handler.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
from blender_mcp.handlers.base import BaseHandler


class MaterialsShadingHandler(BaseHandler):
    """Executes material lifecycle, shader node graph construction, image textures, and UV unwrapping."""

    @classmethod
    def _get_node_tree(cls, material: Any, group_name: Optional[str] = None) -> Any:
        material.use_nodes = True
        if group_name:
            group = material.node_tree.nodes.get(group_name)
            if not group or not hasattr(group, "node_tree") or not group.node_tree:
                raise ValueError(f"Node group '{group_name}' not found.")
            return group.node_tree
        return material.node_tree

    @classmethod
    def manage_materials(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        bpy = cls.get_bpy()
        action = params["action"]
        mat_name = params.get("material_name")
        new_name = params.get("new_name")
        obj_name = params.get("object_name")

        if action == "create":
            name = new_name or mat_name or "Material"
            mat = bpy.data.materials.new(name=name)
            mat.use_nodes = params.get("use_nodes", True)
            return {"status": "success", "material_name": mat.name}

        if action == "delete":
            mat = cls.get_material(mat_name)
            bpy.data.materials.remove(mat)
            return {"status": "success", "deleted_material": mat_name}

        if action == "duplicate":
            mat = cls.get_material(mat_name)
            dup = mat.copy()
            if new_name:
                dup.name = new_name
            return {"status": "success", "material_name": dup.name}

        if action == "set_use_nodes":
            mat = cls.get_material(mat_name)
            mat.use_nodes = params.get("use_nodes", True)
            return {"status": "success", "material_name": mat.name, "use_nodes": mat.use_nodes}

        if action == "assign":
            obj = cls.get_object(obj_name)
            mat = cls.get_material(mat_name)
            slot_idx = params.get("slot_index")

            if slot_idx is not None:
                while len(obj.material_slots) <= slot_idx:
                    obj.data.materials.append(None)
                obj.material_slots[slot_idx].material = mat
                target_slot = slot_idx
            else:
                obj.data.materials.append(mat)
                target_slot = len(obj.material_slots) - 1

            face_indices = params.get("face_indices")
            if face_indices and hasattr(obj.data, "polygons"):
                for fi in face_indices:
                    if 0 <= fi < len(obj.data.polygons):
                        obj.data.polygons[fi].material_index = target_slot
                obj.data.update()

            return {"status": "success", "object": obj.name, "material": mat.name, "slot_index": target_slot}

        raise ValueError(f"Unknown material action: '{action}'")

    @classmethod
    def inspect_shader_tree(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        mat = cls.get_material(params["material_name"])
        tree = cls._get_node_tree(mat, params.get("group_name"))

        nodes = []
        for n in tree.nodes:
            nodes.append({
                "name": n.name,
                "type": n.bl_idname if hasattr(n, "bl_idname") else n.type,
                "location": [n.location.x, n.location.y] if hasattr(n.location, "x") else list(n.location),
                "inputs": [i.name for i in n.inputs],
                "outputs": [o.name for o in n.outputs],
            })

        links = []
        for l in tree.links:
            links.append({
                "from_node": l.from_node.name,
                "from_socket": l.from_socket.name,
                "to_node": l.to_node.name,
                "to_socket": l.to_socket.name,
            })

        return {"status": "success", "material": mat.name, "nodes": nodes, "links": links}

    @classmethod
    def manage_shader_node(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        action = params.get("action", "create")
        mat = cls.get_material(params["material_name"])
        tree = cls._get_node_tree(mat, params.get("group_name"))

        if action == "create":
            node_type = params["node_type"]
            node = tree.nodes.new(type=node_type)
            if params.get("node_name"):
                node.name = params["node_name"]
            if params.get("location"):
                node.location = params["location"]
            return {"status": "success", "node_name": node.name, "type": node_type}

        node_name = params.get("node_name")
        node = tree.nodes.get(node_name)
        if not node:
            raise ValueError(f"Node '{node_name}' not found.")

        if action == "delete":
            tree.nodes.remove(node)
            return {"status": "success", "deleted_node": node_name}

        if action == "move":
            if params.get("location"):
                node.location = params["location"]
            return {"status": "success", "node_name": node.name, "location": list(node.location)}

        raise ValueError(f"Unknown node action: '{action}'")

    @classmethod
    def manage_shader_links(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        action = params.get("action", "link")
        mat = cls.get_material(params["material_name"])
        tree = cls._get_node_tree(mat, params.get("group_name"))

        fn = tree.nodes.get(params["from_node"])
        tn = tree.nodes.get(params["to_node"])
        if not fn or not tn:
            raise ValueError("Source or destination node not found.")

        from_sock_id = params["from_socket"]
        to_sock_id = params["to_socket"]

        out_sock = fn.outputs[from_sock_id] if isinstance(from_sock_id, int) else fn.outputs.get(from_sock_id)
        in_sock = tn.inputs[to_sock_id] if isinstance(to_sock_id, int) else tn.inputs.get(to_sock_id)

        if not out_sock or not in_sock:
            raise ValueError("Output or input socket could not be resolved.")

        if action == "link":
            tree.links.new(out_sock, in_sock)
            return {"status": "success", "from": fn.name, "to": tn.name}

        if action == "unlink":
            for l in list(tree.links):
                if l.from_socket == out_sock and l.to_socket == in_sock:
                    tree.links.remove(l)
            return {"status": "success", "unlinked": True}

        raise ValueError(f"Unknown link action: '{action}'")

    @classmethod
    def set_socket_value(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        mat = cls.get_material(params["material_name"])
        tree = cls._get_node_tree(mat, params.get("group_name"))
        node = tree.nodes.get(params["node_name"])
        if not node:
            raise ValueError(f"Node '{params['node_name']}' not found.")

        sock_id = params["socket_identifier"]
        sock = node.inputs[sock_id] if isinstance(sock_id, int) else node.inputs.get(sock_id)
        if not sock:
            raise ValueError(f"Input socket '{sock_id}' not found.")

        val = params["value"]
        sock.default_value = val
        return {"status": "success", "node": node.name, "socket": sock.name, "value": str(val)}

    @classmethod
    def setup_procedural_texture(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        mat = cls.get_material(params["material_name"])
        tree = cls._get_node_tree(mat)

        tex_type = params.get("texture_type", "noise")
        coord_type = params.get("coord_type", "UV")

        coord_node = tree.nodes.new(type="ShaderNodeTexCoord")
        coord_node.location = (-600, 0)

        mapping_node = tree.nodes.new(type="ShaderNodeMapping")
        mapping_node.location = (-400, 0)
        if params.get("location") and "Location" in mapping_node.inputs:
            mapping_node.inputs["Location"].default_value = params["location"]
        if params.get("rotation") and "Rotation" in mapping_node.inputs:
            mapping_node.inputs["Rotation"].default_value = params["rotation"]
        if params.get("scale") and "Scale" in mapping_node.inputs:
            mapping_node.inputs["Scale"].default_value = params["scale"]

        tex_node_map = {
            "noise": "ShaderNodeTexNoise",
            "voronoi": "ShaderNodeTexVoronoi",
            "wave": "ShaderNodeTexWave",
            "brick": "ShaderNodeTexBrick",
            "checker": "ShaderNodeTexChecker",
            "gradient": "ShaderNodeTexGradient",
            "magic": "ShaderNodeTexMagic",
        }
        tex_node_type = tex_node_map.get(tex_type.lower(), "ShaderNodeTexNoise")
        tex_node = tree.nodes.new(type=tex_node_type)
        tex_node.location = (-200, 0)

        if coord_type in coord_node.outputs:
            tree.links.new(coord_node.outputs[coord_type], mapping_node.inputs["Vector"])
        tree.links.new(mapping_node.outputs["Vector"], tex_node.inputs["Vector"])

        if params.get("connect_to_principled", True):
            principled = next((n for n in tree.nodes if getattr(n, "type", "") == "BSDF_PRINCIPLED"), None)
            if principled:
                out_sock = tex_node.outputs.get("Color") or tex_node.outputs.get("Fac")
                if out_sock and "Base Color" in principled.inputs:
                    tree.links.new(out_sock, principled.inputs["Base Color"])

        return {"status": "success", "texture_type": tex_type}

    @classmethod
    def assign_image_texture(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        bpy = cls.get_bpy()
        mat = cls.get_material(params["material_name"])
        tree = cls._get_node_tree(mat)
        img_path = params["image_path"]

        if not os.path.exists(img_path):
            raise FileNotFoundError(f"Image not found at path: {img_path}")

        img = bpy.data.images.load(img_path, check_existing=True)
        if params.get("pack_image"):
            img.pack()

        tex_node = tree.nodes.new(type="ShaderNodeTexImage")
        tex_node.image = img
        tex_node.location = (-300, 200)

        target_sock = params.get("target_socket", "Base Color")
        principled = next((n for n in tree.nodes if getattr(n, "type", "") == "BSDF_PRINCIPLED"), None)
        if principled and target_sock in principled.inputs:
            tree.links.new(tex_node.outputs["Color"], principled.inputs[target_sock])

        return {"status": "success", "image_name": img.name}

    @classmethod
    def perform_uv_unwrap(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        bpy = cls.get_bpy()
        obj = cls.get_object(params["object_name"])
        method = params.get("method", "smart_project")

        with cls.active_mode(obj, "EDIT"):
            if hasattr(bpy.ops.mesh, "select_all"):
                bpy.ops.mesh.select_all(action="SELECT")

            if method == "smart_project":
                bpy.ops.uv.smart_project(
                    angle_limit=params.get("angle_limit", 66.0),
                    island_margin=params.get("island_margin", 0.02),
                )
            elif method == "cube_project":
                bpy.ops.uv.cube_project()
            elif method == "cylinder_project":
                bpy.ops.uv.cylinder_project()
            elif method == "sphere_project":
                bpy.ops.uv.sphere_project()
            elif method == "lightmap_pack":
                bpy.ops.uv.lightmap_pack()
            else:
                bpy.ops.uv.unwrap(margin=params.get("island_margin", 0.02))

        return {"status": "success", "object": obj.name, "method": method}

    @classmethod
    def manage_color_attributes(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        obj = cls.get_object(params["object_name"])
        action = params["action"]
        attrs = obj.data.color_attributes

        if action == "list":
            out = []
            for i, attr in enumerate(attrs):
                out.append({
                    "name": attr.name,
                    "domain": attr.domain,
                    "data_type": attr.data_type,
                    "active": i == attrs.active_index,
                })
            return {"status": "success", "object": obj.name, "color_attributes": out}

        if action == "add":
            name = params.get("attribute_name", "Color")
            data_type = params.get("data_type", "FLOAT_COLOR")
            domain = params.get("domain", "POINT")
            attr = attrs.new(name=name, type=data_type, domain=domain)
            return {"status": "success", "object": obj.name, "attribute_name": attr.name, "domain": attr.domain, "data_type": attr.data_type}

        if action == "remove":
            attr_name = params.get("attribute_name")
            attr = attrs.get(attr_name) if attr_name else None
            if not attr:
                raise ValueError(f"Color attribute '{attr_name}' not found.")
            attrs.remove(attr)
            return {"status": "success", "object": obj.name, "removed_attribute": attr_name}

        if action == "set_active":
            attr_name = params.get("attribute_name")
            for i, attr in enumerate(attrs):
                if attr.name == attr_name:
                    attrs.active_index = i
                    return {"status": "success", "object": obj.name, "active_attribute": attr_name, "active_index": i}
            raise ValueError(f"Color attribute '{attr_name}' not found.")

        if action == "set_values":
            attr_name = params.get("attribute_name")
            attr = attrs.get(attr_name) if attr_name else None
            if not attr:
                raise ValueError(f"Color attribute '{attr_name}' not found.")
            vertex_indices = params.get("vertex_indices", [])
            color = params.get("color", [1.0, 1.0, 1.0, 1.0])
            for idx in vertex_indices:
                if 0 <= idx < len(attr.data):
                    attr.data[idx].color = color
            return {"status": "success", "object": obj.name, "attribute_name": attr_name, "updated_indices": vertex_indices}

        raise ValueError(f"Unknown color attribute action: '{action}'")

    @classmethod
    def manage_uv_layers(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        bpy = cls.get_bpy()
        obj = cls.get_object(params["object_name"])
        action = params.get("action", "list")
        uv_name = params.get("uv_name")
        new_name = params.get("new_name")

        if not hasattr(obj.data, "uv_layers"):
            raise ValueError(f"Object '{obj.name}' has no UV layers (not a mesh).")

        uv_layers = obj.data.uv_layers

        if action == "list":
            layers = [{"name": l.name, "active": l.active_render} for l in uv_layers]
            return {"status": "success", "object": obj.name, "uv_layers": layers}

        if action == "add":
            name = uv_name or "UVMap"
            layer = uv_layers.new(name=name)
            return {"status": "success", "object": obj.name, "uv_layer": layer.name}

        if action == "remove":
            layer = uv_layers.get(uv_name)
            if not layer:
                raise ValueError(f"UV layer '{uv_name}' not found on '{obj.name}'.")
            uv_layers.remove(layer)
            return {"status": "success", "object": obj.name, "removed": uv_name}

        if action == "set_active":
            layer = uv_layers.get(uv_name)
            if not layer:
                raise ValueError(f"UV layer '{uv_name}' not found on '{obj.name}'.")
            uv_layers.active = layer
            return {"status": "success", "object": obj.name, "active": layer.name}

        if action == "rename":
            layer = uv_layers.get(uv_name)
            if not layer:
                raise ValueError(f"UV layer '{uv_name}' not found on '{obj.name}'.")
            layer.name = new_name or uv_name
            return {"status": "success", "object": obj.name, "uv_layer": layer.name}

        if action == "stitch":
            with cls.active_mode(obj, "EDIT"):
                if hasattr(bpy.ops.mesh, "select_all"):
                    bpy.ops.mesh.select_all(action="SELECT")
                if hasattr(bpy.ops.uv, "stitch"):
                    bpy.ops.uv.stitch()
                    return {"status": "success", "object": obj.name, "stitched": True}
                raise ValueError("bpy.ops.uv.stitch is not available in this context.")

        raise ValueError(f"Unknown UV layer action: '{action}'")
