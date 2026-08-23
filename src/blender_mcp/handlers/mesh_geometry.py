"""
Mesh Geometry, BMesh Operations, Curves, Typography, Volumes, and Geometry Nodes execution handler.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional
from blender_mcp.handlers.base import BaseHandler


class MeshGeometryHandler(BaseHandler):
    """Executes parametric primitive creation, BMesh sub-element manipulations, and geometry nodes."""

    @classmethod
    def create_primitive(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        bpy = cls.get_bpy()
        ptype = params.get("primitive_type", "CUBE").upper()
        name = params.get("name")
        loc = params.get("location", [0.0, 0.0, 0.0])
        rot = params.get("rotation", [0.0, 0.0, 0.0])
        scale = params.get("scale", [1.0, 1.0, 1.0])

        size = params.get("size", 2.0)
        radius = params.get("radius", 1.0)
        depth = params.get("depth", 2.0)
        segments = params.get("segments", 32)
        ring_count = params.get("ring_count", 16)
        subdivisions = params.get("subdivisions", 3)

        if ptype == "CUBE":
            bpy.ops.mesh.primitive_cube_add(size=size, location=loc, rotation=rot, scale=scale)
        elif ptype == "UV_SPHERE":
            bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=ring_count, radius=radius, location=loc, rotation=rot, scale=scale)
        elif ptype == "ICO_SPHERE":
            bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=subdivisions, radius=radius, location=loc, rotation=rot, scale=scale)
        elif ptype == "CYLINDER":
            bpy.ops.mesh.primitive_cylinder_add(vertices=segments, radius=radius, depth=depth, location=loc, rotation=rot, scale=scale)
        elif ptype == "CONE":
            bpy.ops.mesh.primitive_cone_add(vertices=segments, radius1=radius, depth=depth, location=loc, rotation=rot, scale=scale)
        elif ptype == "TORUS":
            bpy.ops.mesh.primitive_torus_add(major_radius=radius, minor_radius=radius * 0.25, major_segments=segments, minor_segments=ring_count, location=loc, rotation=rot)
        elif ptype == "GRID":
            bpy.ops.mesh.primitive_grid_add(x_subdivisions=segments, y_subdivisions=segments, size=size, location=loc, rotation=rot, scale=scale)
        elif ptype == "PLANE":
            bpy.ops.mesh.primitive_plane_add(size=size, location=loc, rotation=rot, scale=scale)
        elif ptype == "CIRCLE":
            bpy.ops.mesh.primitive_circle_add(vertices=segments, radius=radius, location=loc, rotation=rot, scale=scale)
        elif ptype == "MONKEY":
            bpy.ops.mesh.primitive_monkey_add(size=size, location=loc, rotation=rot, scale=scale)
        elif ptype == "EMPTY":
            bpy.ops.object.empty_add(type="PLAIN_AXES", location=loc, rotation=rot, scale=scale)
        else:
            bpy.ops.mesh.primitive_cube_add(size=size, location=loc, rotation=rot, scale=scale)

        obj = bpy.context.active_object
        if name and obj:
            obj.name = name

        return {
            "status": "success",
            "primitive_type": ptype,
            "name": obj.name if obj else None,
        }

    @classmethod
    def manipulate_mesh(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        bpy = cls.get_bpy()
        obj = cls.get_object(params["object_name"])
        op = params["operation"]

        if op == "SET_SHADING":
            mode = params.get("shading_mode", "SMOOTH")
            with cls.active_mode(obj, "OBJECT"):
                if mode == "SMOOTH":
                    bpy.ops.object.shade_smooth()
                elif mode == "AUTO_SMOOTH":
                    bpy.ops.object.shade_auto_smooth()
                else:
                    bpy.ops.object.shade_flat()
            return {"status": "success", "shading": mode}

        if op == "BOOLEAN":
            target_name = params.get("boolean_target")
            target_obj = cls.get_object(target_name)
            bool_op = params.get("boolean_operation", "DIFFERENCE")

            mod = obj.modifiers.new(name="MCP_Boolean", type="BOOLEAN")
            mod.object = target_obj
            mod.operation = bool_op

            with bpy.context.temp_override(active_object=obj, selected_objects=[obj], object=obj):
                bpy.ops.object.modifier_apply(modifier=mod.name)

            return {"status": "success", "boolean_operation": bool_op, "target": target_name}

        # BMesh operations in edit/direct mode
        try:
            import bmesh
            import mathutils
        except ImportError:
            bmesh = None
            mathutils = None

        if not bmesh:
            raise RuntimeError("bmesh module is not accessible.")

        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        result_info: Dict[str, Any] = {"operation": op}

        if op == "EXTRUDE_FACES":
            face_indices = params.get("face_indices") or list(range(len(bm.faces)))
            target_faces = [bm.faces[i] for i in face_indices if i < len(bm.faces)]
            res = bmesh.ops.extrude_face_region(bm, geom=target_faces)
            trans = params.get("translation", [0.0, 0.0, 1.0])
            verts = [e for e in res["geom"] if isinstance(e, bmesh.types.BMVert)]
            bmesh.ops.translate(bm, vec=mathutils.Vector(trans) if mathutils else trans, verts=verts)
            result_info["extruded_faces"] = len(target_faces)

        elif op == "INSET_FACES":
            face_indices = params.get("face_indices") or list(range(len(bm.faces)))
            target_faces = [bm.faces[i] for i in face_indices if i < len(bm.faces)]
            thickness = params.get("thickness", 0.1)
            depth = params.get("offset", 0.0)
            bmesh.ops.inset_individual(bm, faces=target_faces, thickness=thickness, depth=depth)
            result_info["inset_faces"] = len(target_faces)

        elif op == "BEVEL":
            offset = params.get("offset", 0.1)
            segments = params.get("segments", 2)
            profile = params.get("profile", 0.5)
            edge_indices = params.get("edge_indices")
            if edge_indices:
                geom = [bm.edges[i] for i in edge_indices if i < len(bm.edges)]
                affect = "EDGES"
            else:
                geom = list(bm.edges)
                affect = "EDGES"
            bmesh.ops.bevel(bm, geom=geom, offset=offset, segments=segments, profile=profile, affect=affect)
            result_info["beveled_edges"] = len(geom)

        elif op == "SUBDIVIDE":
            cuts = params.get("segments", 1)
            edge_indices = params.get("edge_indices")
            edges = [bm.edges[i] for i in edge_indices if i < len(bm.edges)] if edge_indices else list(bm.edges)
            bmesh.ops.subdivide_edges(bm, edges=edges, cuts=cuts)
            result_info["subdivided_edges"] = len(edges)

        elif op == "MERGE_VERTICES":
            dist = params.get("offset", 0.0001)
            vert_indices = params.get("vertex_indices")
            verts = [bm.verts[i] for i in vert_indices if i < len(bm.verts)] if vert_indices else list(bm.verts)
            if params.get("merge_type") == "COLLAPSE":
                bmesh.ops.collapse(bm, edges=list(bm.edges))
            else:
                bmesh.ops.remove_doubles(bm, verts=verts, dist=dist)
            result_info["merged_verts"] = len(verts)

        elif op == "RECALCULATE_NORMALS":
            bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
            result_info["recalculated"] = True

        elif op == "DELETE_ELEMENTS":
            if params.get("face_indices"):
                geom = [bm.faces[i] for i in params["face_indices"] if i < len(bm.faces)]
                bmesh.ops.delete(bm, geom=geom, context="FACES")
            elif params.get("edge_indices"):
                geom = [bm.edges[i] for i in params["edge_indices"] if i < len(bm.edges)]
                bmesh.ops.delete(bm, geom=geom, context="EDGES")
            elif params.get("vertex_indices"):
                geom = [bm.verts[i] for i in params["vertex_indices"] if i < len(bm.verts)]
                bmesh.ops.delete(bm, geom=geom, context="VERTS")

        bm.to_mesh(obj.data)
        bm.free()
        obj.data.update()

        return {"status": "success", "info": result_info}

    @classmethod
    def create_curve(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        bpy = cls.get_bpy()
        name = params.get("name", "Curve")
        ctype = params.get("curve_type", "BEZIER")

        curve_data = bpy.data.curves.new(name, type="CURVE")
        curve_data.dimensions = "3D"
        curve_data.bevel_depth = params.get("bevel_depth", 0.0)
        curve_data.extrude = params.get("extrude", 0.0)

        spline = curve_data.splines.new(ctype)
        spline.use_cyclic_u = params.get("is_cyclic", False)

        points = params.get("points", [])
        if points:
            if ctype == "BEZIER":
                spline.bezier_points.add(len(points) - 1)
                for i, pt in enumerate(points):
                    bp = spline.bezier_points[i]
                    bp.co = pt.get("co", [0, 0, 0])
                    if "handle_left" in pt:
                        bp.handle_left = pt["handle_left"]
                    if "handle_right" in pt:
                        bp.handle_right = pt["handle_right"]
            else:
                spline.points.add(len(points) - 1)
                for i, pt in enumerate(points):
                    co = pt.get("co", [0, 0, 0])
                    spline.points[i].co = (co[0], co[1], co[2], 1.0)

        curve_obj = bpy.data.objects.new(name, curve_data)
        bpy.context.scene.collection.objects.link(curve_obj)
        return {"status": "success", "curve_name": curve_obj.name}

    @classmethod
    def create_text(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        bpy = cls.get_bpy()
        name = params.get("name", "Text3D")
        body = params.get("body", "Hello World")
        loc = params.get("location", [0, 0, 0])

        curve_data = bpy.data.curves.new(name, type="FONT")
        curve_data.body = body
        curve_data.size = params.get("size", 1.0)
        curve_data.extrude = params.get("extrude", 0.05)
        curve_data.bevel_depth = params.get("bevel_depth", 0.01)

        text_obj = bpy.data.objects.new(name, curve_data)
        text_obj.location = loc
        bpy.context.scene.collection.objects.link(text_obj)
        return {"status": "success", "text_name": text_obj.name, "body": body}

    @classmethod
    def create_volume(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        bpy = cls.get_bpy()
        name = params.get("name", "Volume")
        vol_data = bpy.data.volumes.new(name=name) if hasattr(bpy.data, "volumes") else None
        vol_obj = bpy.data.objects.new(name, vol_data)
        bpy.context.scene.collection.objects.link(vol_obj)
        return {"status": "success", "volume_name": vol_obj.name}

    @classmethod
    def manage_geometry_nodes(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        bpy = cls.get_bpy()
        obj = cls.get_object(params["object_name"])
        mod_name = params.get("modifier_name", "GeometryNodes")

        mod = obj.modifiers.get(mod_name)
        if not mod:
            mod = obj.modifiers.new(name=mod_name, type="NODES")

        tree_name = params.get("tree_name") or f"{obj.name}_GeoNodes"
        node_tree = bpy.data.node_groups.get(tree_name) or bpy.data.node_groups.new(tree_name, "GeometryNodeTree")
        mod.node_group = node_tree

        nodes_spec = params.get("nodes", [])
        for n_spec in nodes_spec:
            node = node_tree.nodes.new(type=n_spec["type_name"])
            if "name" in n_spec:
                node.name = n_spec["name"]
            if "location" in n_spec:
                node.location = n_spec["location"]

        links_spec = params.get("links", [])
        for l_spec in links_spec:
            from_node = node_tree.nodes.get(l_spec["from_node"])
            to_node = node_tree.nodes.get(l_spec["to_node"])
            if from_node and to_node:
                from_sock = from_node.outputs.get(l_spec.get("from_socket", "Geometry")) or from_node.outputs[0]
                to_sock = to_node.inputs.get(l_spec.get("to_socket", "Geometry")) or to_node.inputs[0]
                node_tree.links.new(from_sock, to_sock)

        return {"status": "success", "object": obj.name, "node_group": node_tree.name}
