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

        elif op == "KNIFE":
            pairs = params.get("vertex_pairs") or []
            cuts = 0
            for pair in pairs:
                if len(pair) < 2 or pair[0] >= len(bm.verts) or pair[1] >= len(bm.verts):
                    continue
                v1, v2 = bm.verts[pair[0]], bm.verts[pair[1]]
                try:
                    bmesh.ops.connect_verts(bm, verts=[v1, v2])
                    cuts += 1
                except Exception:
                    pass
            result_info["knife_cuts"] = cuts

        elif op == "LOOP_CUT":
            edge_indices = params.get("edge_indices") or []
            cuts = params.get("cuts") or params.get("segments", 1)
            start_edges = [bm.edges[i] for i in edge_indices if i < len(bm.edges)]
            ring = []
            seen = set()

            def walk_ring(start):
                collected = []
                cur = start
                while cur is not None and id(cur) not in seen:
                    seen.add(id(cur))
                    collected.append(cur)
                    nxt = None
                    for f in cur.link_faces:
                        if len(f.verts) != 4:
                            continue
                        for e in f.edges:
                            if e is cur or id(e) in seen:
                                continue
                            if not (e.verts[0] in cur.verts or e.verts[1] in cur.verts):
                                nxt = e
                                break
                        if nxt is not None:
                            break
                    cur = nxt
                return collected

            for se in start_edges:
                ring.extend(walk_ring(se))
            if ring:
                bmesh.ops.subdivide_edges(bm, edges=ring, cuts=cuts)
            result_info["loop_cut_edges"] = len(ring)
            result_info["cuts"] = cuts

        elif op == "FILL":
            edge_indices = params.get("edge_indices") or []
            edges = [bm.edges[i] for i in edge_indices if i < len(bm.edges)]
            filled = 0
            if edges:
                try:
                    bmesh.ops.edgeloop_fill(bm, edges=edges)
                    filled = len(edges)
                except Exception:
                    bmesh.ops.triangle_fill(bm, edges=edges, use_beauty=True)
                    filled = len(edges)
            result_info["filled_edges"] = filled

        elif op == "GRID_FILL":
            edge_indices = params.get("edge_indices") or []
            edges = [bm.edges[i] for i in edge_indices if i < len(bm.edges)]
            if edges:
                bmesh.ops.grid_fill(bm, edges=edges, sides=params.get("segments", 0))
            result_info["grid_filled_edges"] = len(edges)

        elif op == "POKE":
            face_indices = params.get("face_indices") or list(range(len(bm.faces)))
            target_faces = [bm.faces[i] for i in face_indices if i < len(bm.faces)]
            if target_faces:
                bmesh.ops.poke(bm, faces=target_faces, offset=params.get("offset", 0.0))
            result_info["poked_faces"] = len(target_faces)

        elif op == "EDGE_SPLIT":
            edge_indices = params.get("edge_indices") or []
            edges = [bm.edges[i] for i in edge_indices if i < len(bm.edges)]
            if edges:
                bmesh.ops.split(bm, geom=edges)
            result_info["split_edges"] = len(edges)

        elif op == "SUBDIVIDE_EDGE":
            cuts = params.get("cuts") or params.get("segments", 1)
            edge_indices = params.get("edge_indices") or []
            edges = [bm.edges[i] for i in edge_indices if i < len(bm.edges)]
            if edges:
                bmesh.ops.subdivide_edges(bm, edges=edges, cuts=cuts)
            result_info["subdivided_edges"] = len(edges)
            result_info["cuts"] = cuts

        elif op == "BRIDGE_EDGE_LOOPS":
            edge_indices = params.get("edge_indices") or []
            edges = [bm.edges[i] for i in edge_indices if i < len(bm.edges)]
            if edges:
                bmesh.ops.bridge_loops(bm, edges=edges)
            result_info["bridged_edges"] = len(edges)

        elif op == "BRIDGE_FACES":
            face_indices = params.get("face_indices") or []
            target_faces = [bm.faces[i] for i in face_indices if i < len(bm.faces)]
            loop_edges = []
            for f in target_faces:
                for e in f.edges:
                    shared = sum(1 for ff in e.link_faces if ff in target_faces)
                    if shared == 1:
                        loop_edges.append(e)
            if loop_edges:
                bmesh.ops.bridge_loops(bm, edges=loop_edges)
            result_info["bridged_faces"] = len(target_faces)

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
        action = params.get("action", "build")

        mod = obj.modifiers.get(mod_name)
        if not mod:
            mod = obj.modifiers.new(name=mod_name, type="NODES")

        tree_name = params.get("tree_name") or f"{obj.name}_GeoNodes"
        node_tree = bpy.data.node_groups.get(tree_name) or bpy.data.node_groups.new(tree_name, "GeometryNodeTree")
        mod.node_group = node_tree

        if action == "inspect":
            nodes_info = []
            for n in node_tree.nodes:
                inputs = [{"name": s.name, "identifier": s.identifier, "type": s.type} for s in n.inputs]
                outputs = [{"name": s.name, "identifier": s.identifier, "type": s.type} for s in n.outputs]
                nodes_info.append({
                    "name": n.name,
                    "type": n.type,
                    "bl_idname": n.bl_idname,
                    "location": list(n.location),
                    "inputs": inputs,
                    "outputs": outputs,
                })
            links_info = []
            for l in node_tree.links:
                links_info.append({
                    "from_node": l.from_node.name,
                    "from_socket": l.from_socket.name,
                    "to_node": l.to_node.name,
                    "to_socket": l.to_socket.name,
                })
            group_inputs = [{"name": s.name, "identifier": s.identifier, "type": s.type} for s in node_tree.inputs]
            group_outputs = [{"name": s.name, "identifier": s.identifier, "type": s.type} for s in node_tree.outputs]
            return {
                "status": "success",
                "object": obj.name,
                "node_group": node_tree.name,
                "nodes": nodes_info,
                "links": links_info,
                "group_inputs": group_inputs,
                "group_outputs": group_outputs,
            }

        if action == "set_socket_value":
            node_name = params.get("node_name")
            socket_identifier = params.get("socket_identifier") or params.get("socket_name")
            value = params.get("value")
            direction = params.get("socket_direction", "input")
            node = node_tree.nodes.get(node_name)
            if not node:
                raise ValueError(f"Node '{node_name}' not found in node tree '{node_tree.name}'.")
            sockets = node.inputs if direction == "input" else node.outputs
            sock = None
            for s in sockets:
                if s.identifier == socket_identifier or s.name == socket_identifier:
                    sock = s
                    break
            if not sock:
                sock = sockets.get(socket_identifier)
            if not sock:
                raise ValueError(f"Socket '{socket_identifier}' not found on node '{node_name}'.")
            if hasattr(sock, "default_value") and value is not None:
                sock.default_value = value
            return {"status": "success", "node": node.name, "socket": sock.name, "value": value}

        if action == "add_group_input":
            node = node_tree.nodes.new(type="NodeGroupInput")
            if params.get("location"):
                node.location = params["location"]
            return {"status": "success", "node": node.name, "type": "NodeGroupInput"}

        if action == "add_group_output":
            node = node_tree.nodes.new(type="NodeGroupOutput")
            if params.get("location"):
                node.location = params["location"]
            return {"status": "success", "node": node.name, "type": "NodeGroupOutput"}

        if action == "set_modifier_input":
            input_name = params.get("input_name")
            value = params.get("value")
            if not input_name:
                raise ValueError("input_name is required for set_modifier_input action.")
            if input_name not in mod:
                raise ValueError(f"Modifier '{mod.name}' has no input '{input_name}'.")
            mod[input_name] = value
            return {"status": "success", "modifier": mod.name, "input": input_name, "value": value}

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
