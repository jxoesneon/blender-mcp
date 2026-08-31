"""
Composite workflow handlers for scene management, UV export, asset batching, and auto-rigging.

These handlers orchestrate multiple lower-level Blender operations into
higher-level, reusable, transactional workflows:

* ``audit_and_cleanup_scene`` -- diagnoses a scene (orphans, missing files,
  duplicate materials, heavy geometry, performance hints) and optionally
  performs cleanup actions.
* ``uv_pipeline_export`` -- runs a full UV unwrap + island packing + optional
  UV-layout export + mesh export pipeline on a single mesh object.
* ``batch_mark_assets`` -- marks (or unmarks) a filtered set of objects as
  Blender assets, assigns tags/catalogs, and optionally generates previews.
* ``auto_rig_character`` -- generates an armature approximating a character
  mesh from its bounding box, parents the mesh with automatic weights, and
  optionally adds IK constraints.

All handlers run inside ``cls.transaction()`` so a failure rolls the scene
back to its prior state via Blender's undo stack. Operator calls that may
have context requirements are wrapped in ``try/except`` and use
``bpy.context.temp_override`` where appropriate, so the same code works
across Blender 4.x and 5.x.
"""

from __future__ import annotations

import math
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from blender_mcp.exceptions import BlenderExecutionError
from blender_mcp.handlers.base import BaseHandler


class SceneWorkflowsHandler(BaseHandler):
    """Composite workflow handlers for scene, UV, asset, and rigging automation."""

    # ===================================================================
    # Workflow 1: audit_and_cleanup_scene
    # ===================================================================
    @classmethod
    def audit_and_cleanup_scene(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        """Diagnose and optionally clean up a Blender scene.

        Performs a comprehensive audit of the current scene -- counting
        objects by type, locating orphan data-blocks, finding missing
        external files, detecting duplicate material names, reporting
        polygon/vertex/draw-call statistics, and flagging heavy or
        potentially-unused objects. When ``audit_only`` is False, selected
        cleanup actions (purge orphans, pack textures, make paths relative,
        find missing files, remove unused materials/meshes, merge duplicate
        materials) are executed.

        Returns a dict containing the full audit report plus a list of
        cleanup actions that were performed.
        """
        bpy = cls.get_bpy()

        # --- Parameter extraction ---
        audit_only: bool = bool(params.get("audit_only", True))
        purge_orphans: bool = bool(params.get("purge_orphans", False))
        pack_textures: bool = bool(params.get("pack_textures", False))
        make_paths_relative: bool = bool(params.get("make_paths_relative", False))
        find_missing_files: bool = bool(params.get("find_missing_files", False))
        search_directory: Optional[str] = params.get("search_directory")
        remove_unused_materials: bool = bool(params.get("remove_unused_materials", False))
        remove_unused_meshes: bool = bool(params.get("remove_unused_meshes", False))
        merge_duplicate_materials: bool = bool(params.get("merge_duplicate_materials", False))
        report_objects: bool = bool(params.get("report_objects", True))
        report_materials: bool = bool(params.get("report_materials", True))
        report_textures: bool = bool(params.get("report_textures", True))
        report_performance: bool = bool(params.get("report_performance", True))

        with cls.transaction("audit_and_cleanup_scene"):
            # -----------------------------------------------------------
            # AUDIT PHASE
            # -----------------------------------------------------------
            report: Dict[str, Any] = {}

            # (a) Count all objects by type
            object_counts: Dict[str, int] = {}
            for obj in bpy.data.objects:
                object_counts[obj.type] = object_counts.get(obj.type, 0) + 1
            report["object_counts"] = object_counts
            report["total_objects"] = len(bpy.data.objects)

            # (b) Find orphan data blocks (users == 0)
            orphan_types = [
                "meshes", "materials", "images", "textures",
                "armatures", "actions", "node_groups",
            ]
            orphans: Dict[str, List[str]] = {}
            for attr in orphan_types:
                coll = getattr(bpy.data, attr, None)
                if coll is None:
                    continue
                orphans[attr] = [
                    item.name for item in coll
                    if getattr(item, "users", 1) == 0
                ]
            report["orphans"] = orphans

            # (c) Find missing external files
            missing_files: List[Dict[str, str]] = []
            # Images
            for img in bpy.data.images:
                filepath = getattr(img, "filepath", "")
                if filepath and not img.packed_file:
                    abs_path = bpy.path.abspath(filepath)
                    if not os.path.exists(abs_path):
                        missing_files.append({
                            "type": "image",
                            "name": img.name,
                            "filepath": filepath,
                        })
            # Fonts
            for font in bpy.data.fonts:
                filepath = getattr(font, "filepath", "")
                if filepath:
                    abs_path = bpy.path.abspath(filepath)
                    if not os.path.exists(abs_path):
                        missing_files.append({
                            "type": "font",
                            "name": font.name,
                            "filepath": filepath,
                        })
            # Cache files
            if hasattr(bpy.data, "cache_files"):
                for cf in bpy.data.cache_files:
                    filepath = getattr(cf, "filepath", "")
                    if filepath:
                        abs_path = bpy.path.abspath(filepath)
                        if not os.path.exists(abs_path):
                            missing_files.append({
                                "type": "cache_file",
                                "name": cf.name,
                                "filepath": filepath,
                            })
            report["missing_files"] = missing_files

            # (d) Find mesh objects with no material assigned
            no_material_objects: List[str] = []
            for obj in bpy.data.objects:
                if obj.type != "MESH":
                    continue
                mesh = obj.data
                if mesh is None or len(mesh.materials) == 0:
                    no_material_objects.append(obj.name)
                elif all(m is None for m in mesh.materials):
                    no_material_objects.append(obj.name)
            report["objects_without_materials"] = no_material_objects

            # (e) Find duplicate material names (case-insensitive)
            mat_lower_map: Dict[str, List[str]] = {}
            for mat in bpy.data.materials:
                key = mat.name.lower()
                mat_lower_map.setdefault(key, []).append(mat.name)
            duplicate_materials: Dict[str, List[str]] = {
                k: v for k, v in mat_lower_map.items() if len(v) > 1
            }
            report["duplicate_materials"] = duplicate_materials

            # (f) Count total polygons, vertices, draw calls
            total_polys = 0
            total_verts = 0
            draw_calls = 0
            for obj in bpy.data.objects:
                if obj.type != "MESH":
                    continue
                mesh = obj.data
                if mesh is None:
                    continue
                total_polys += len(mesh.polygons)
                total_verts += len(mesh.vertices)
                # Draw calls ~= number of materials on the object
                mat_count = len([m for m in mesh.materials if m is not None])
                draw_calls += max(mat_count, 1)
            report["performance"] = {
                "total_polygons": total_polys,
                "total_vertices": total_verts,
                "estimated_draw_calls": draw_calls,
            }

            # (g) Check for heavy objects (poly count > 100000)
            heavy_threshold = 100000
            heavy_objects: List[Dict[str, Any]] = []
            for obj in bpy.data.objects:
                if obj.type != "MESH":
                    continue
                mesh = obj.data
                if mesh is None:
                    continue
                poly_count = len(mesh.polygons)
                if poly_count > heavy_threshold:
                    heavy_objects.append({
                        "name": obj.name,
                        "polygon_count": poly_count,
                    })
            report["heavy_objects"] = heavy_objects

            # (h) Check for objects at origin with no transforms (potential unused)
            origin_objects: List[str] = []
            for obj in bpy.data.objects:
                loc = list(obj.location)
                scale = list(obj.scale)
                rot_zero = (
                    list(obj.rotation_euler) == [0.0, 0.0, 0.0]
                )
                at_origin = (
                    loc == [0.0, 0.0, 0.0]
                    and scale == [1.0, 1.0, 1.0]
                    and rot_zero
                )
                if at_origin:
                    origin_objects.append(obj.name)
            report["objects_at_origin"] = origin_objects

            # -----------------------------------------------------------
            # CLEANUP PHASE
            # -----------------------------------------------------------
            cleanup_actions: List[str] = []

            if not audit_only:
                # (a) Purge orphans
                if purge_orphans:
                    purged = 0
                    try:
                        if hasattr(bpy.ops, "outliner") and hasattr(bpy.ops.outliner, "orphans_purge"):
                            # Try the recursive purge available in newer Blender versions.
                            try:
                                bpy.ops.outliner.orphans_purge(do_local_ids=True, do_recursive=True)
                            except TypeError:
                                bpy.ops.outliner.orphans_purge()
                        else:
                            # Manual removal of zero-user data blocks
                            for attr in orphan_types:
                                coll = getattr(bpy.data, attr, None)
                                if coll is None:
                                    continue
                                to_remove = [
                                    item for item in list(coll)
                                    if getattr(item, "users", 1) == 0
                                ]
                                for item in to_remove:
                                    coll.remove(item)
                                    purged += 1
                        cleanup_actions.append("purge_orphans")
                    except Exception as exc:
                        cleanup_actions.append(f"purge_orphans (failed: {exc})")

                # (b) Pack textures
                if pack_textures:
                    try:
                        if hasattr(bpy.ops.file, "pack_all"):
                            bpy.ops.file.pack_all()
                            cleanup_actions.append("pack_textures")
                    except Exception as exc:
                        cleanup_actions.append(f"pack_textures (failed: {exc})")

                # (c) Make paths relative
                if make_paths_relative:
                    try:
                        if hasattr(bpy.ops.file, "make_paths_relative"):
                            bpy.ops.file.make_paths_relative()
                            cleanup_actions.append("make_paths_relative")
                    except Exception as exc:
                        cleanup_actions.append(f"make_paths_relative (failed: {exc})")

                # (d) Find missing files
                if find_missing_files:
                    try:
                        if hasattr(bpy.ops.file, "find_missing_files"):
                            kwargs: Dict[str, Any] = {}
                            if search_directory:
                                kwargs["directory"] = search_directory
                            bpy.ops.file.find_missing_files(**kwargs)
                            cleanup_actions.append("find_missing_files")
                    except Exception as exc:
                        cleanup_actions.append(f"find_missing_files (failed: {exc})")

                # (e) Remove unused materials
                if remove_unused_materials:
                    removed = 0
                    for mat in list(bpy.data.materials):
                        if getattr(mat, "users", 1) == 0:
                            bpy.data.materials.remove(mat)
                            removed += 1
                    cleanup_actions.append(f"remove_unused_materials ({removed} removed)")

                # (f) Remove unused meshes
                if remove_unused_meshes:
                    removed = 0
                    for mesh in list(bpy.data.meshes):
                        if getattr(mesh, "users", 1) == 0:
                            bpy.data.meshes.remove(mesh)
                            removed += 1
                    cleanup_actions.append(f"remove_unused_meshes ({removed} removed)")

                # (g) Merge duplicate materials
                if merge_duplicate_materials:
                    merged = 0
                    for key, names in duplicate_materials.items():
                        if len(names) < 2:
                            continue
                        # Keep the first, reassign users of the rest, then remove
                        keeper = bpy.data.materials.get(names[0])
                        if keeper is None:
                            continue
                        for dup_name in names[1:]:
                            dup = bpy.data.materials.get(dup_name)
                            if dup is None:
                                continue
                            # Reassign all object material slots referencing the duplicate
                            for obj in bpy.data.objects:
                                if obj.type != "MESH":
                                    continue
                                mesh = obj.data
                                if mesh is None:
                                    continue
                                for i, slot_mat in enumerate(mesh.materials):
                                    if slot_mat == dup:
                                        mesh.materials[i] = keeper
                            # Remove the duplicate if it now has no users
                            if getattr(dup, "users", 1) == 0:
                                bpy.data.materials.remove(dup)
                                merged += 1
                    cleanup_actions.append(f"merge_duplicate_materials ({merged} merged)")

            # -----------------------------------------------------------
            # Build filtered report sections
            # -----------------------------------------------------------
            final_report: Dict[str, Any] = {
                "object_counts": report["object_counts"],
                "total_objects": report["total_objects"],
                "orphans": report["orphans"],
                "missing_files": report["missing_files"],
                "objects_without_materials": report["objects_without_materials"],
                "duplicate_materials": report["duplicate_materials"],
                "heavy_objects": report["heavy_objects"],
                "objects_at_origin": report["objects_at_origin"],
            }
            if report_performance:
                final_report["performance"] = report["performance"]
            # report_objects / report_materials / report_textures gate
            # the inclusion of the corresponding detailed sections.
            if not report_objects:
                final_report.pop("object_counts", None)
                final_report.pop("total_objects", None)
                final_report.pop("objects_at_origin", None)
            if not report_materials:
                final_report.pop("objects_without_materials", None)
                final_report.pop("duplicate_materials", None)
            if not report_textures:
                final_report.pop("missing_files", None)

            return {
                "status": "success",
                "audit_only": audit_only,
                "report": final_report,
                "cleanup_actions": cleanup_actions,
            }

    # ===================================================================
    # Workflow 2: uv_pipeline_export
    # ===================================================================
    @classmethod
    def uv_pipeline_export(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        """Run a UV unwrap and mesh export pipeline on a single mesh object.

        Enters edit mode, optionally auto-marks seams, creates/activates a
        UV map layer, unwraps using the requested method (smart,
        angle-based, conformal, or cube projection), optionally packs UV
        islands, optionally exports the UV layout as an image, and finally
        exports the mesh in the requested format (fbx, obj, gltf, glb, stl,
        ply). Operator name variations across Blender versions are handled
        with fallback lookups and ``try/except``.
        """
        bpy = cls.get_bpy()

        # --- Parameter extraction ---
        object_name: str = params["object_name"]
        uv_method: str = params.get("uv_method", "SMART")
        mark_seams_auto: bool = bool(params.get("mark_seams_auto", True))
        seam_angle: float = float(params.get("seam_angle", 88.0))
        pack_islands: bool = bool(params.get("pack_islands", True))
        pack_margin: float = float(params.get("pack_margin", 0.01))
        export_uv_layout: bool = bool(params.get("export_uv_layout", False))
        uv_layout_path: str = params.get("uv_layout_path", "/tmp/uv_layout.png")
        uv_layout_size: List[int] = list(params.get("uv_layout_size", [1024, 1024]))
        export_format: str = params.get("export_format", "fbx")
        export_path: str = params.get("export_path", "/tmp/exported_mesh.fbx")
        export_params: Optional[Dict[str, Any]] = params.get("export_params")

        valid_methods = {"SMART", "ANGLE_BASED", "CONFORMAL", "CUBE_PROJECTION"}
        if uv_method not in valid_methods:
            raise BlenderExecutionError(
                f"Invalid uv_method '{uv_method}'. Must be one of {sorted(valid_methods)}."
            )

        valid_formats = {"fbx", "obj", "gltf", "glb", "stl", "ply"}
        if export_format not in valid_formats:
            raise BlenderExecutionError(
                f"Invalid export_format '{export_format}'. Must be one of {sorted(valid_formats)}."
            )

        with cls.transaction(f"uv_pipeline_export('{object_name}')"):
            # 1. Verify object exists and is a mesh
            obj = cls.get_object(object_name)
            if obj.type != "MESH":
                raise BlenderExecutionError(
                    f"Object '{object_name}' is not a MESH (type={obj.type})."
                )
            mesh = obj.data

            # 5. Create or get UV map layer (done before entering edit mode
            # so the layer exists regardless of unwrap method).
            uv_layers = mesh.uv_layers
            uv_layer = uv_layers.get("UVMap")
            if uv_layer is None:
                uv_layer = uv_layers.new(name="UVMap")
            uv_layers.active = uv_layer
            uv_map_name = uv_layer.name

            island_count = 0

            # 2-7. Edit-mode UV operations
            with cls.active_mode(obj, "EDIT"):
                # 3. Select all faces
                if hasattr(bpy.ops.mesh, "select_all"):
                    try:
                        bpy.ops.mesh.select_all(action="SELECT")
                    except Exception:
                        pass

                # 4. Auto mark seams
                if mark_seams_auto:
                    cls._auto_mark_seams(bpy, seam_angle)

                # 6. Unwrap based on uv_method
                if uv_method == "SMART":
                    # smart_project handles seams internally
                    try:
                        bpy.ops.uv.smart_project(
                            angle_limit=math.radians(seam_angle),
                            island_margin=pack_margin,
                        )
                    except Exception:
                        # Fallback: unwrap without angle limit
                        try:
                            bpy.ops.uv.smart_project()
                        except Exception:
                            pass
                elif uv_method == "ANGLE_BASED":
                    try:
                        bpy.ops.uv.unwrap(method="ANGLE_BASED")
                    except Exception:
                        try:
                            bpy.ops.uv.unwrap()
                        except Exception:
                            pass
                elif uv_method == "CONFORMAL":
                    try:
                        bpy.ops.uv.unwrap(method="CONFORMAL")
                    except Exception:
                        try:
                            bpy.ops.uv.unwrap()
                        except Exception:
                            pass
                elif uv_method == "CUBE_PROJECTION":
                    try:
                        bpy.ops.uv.cube_project()
                    except Exception:
                        pass

                # 7. Pack islands
                if pack_islands and uv_method != "SMART":
                    # smart_project already packs with island_margin
                    try:
                        bpy.ops.uv.pack_islands(margin=pack_margin)
                    except Exception:
                        try:
                            bpy.ops.uv.pack_islands()
                        except Exception:
                            pass

                # Estimate island count from UV islands is non-trivial via
                # the API; we approximate by counting UV islands after the
                # fact using a simple connectivity heuristic on the active
                # UV layer. Fall back to 0 if unavailable.
                island_count = cls._count_uv_islands(mesh, uv_map_name)

            # 8. Exit edit mode handled by active_mode context manager.

            # 9. Export UV layout
            uv_layout_exported = False
            uv_layout_size_bytes: Optional[int] = None
            if export_uv_layout:
                try:
                    # Ensure the output directory exists
                    out_dir = os.path.dirname(os.path.abspath(uv_layout_path))
                    if out_dir:
                        os.makedirs(out_dir, exist_ok=True)
                    if hasattr(bpy.ops.uv, "export_layout"):
                        bpy.ops.uv.export_layout(
                            filepath=uv_layout_path,
                            size=uv_layout_size,
                        )
                        uv_layout_exported = True
                        if os.path.exists(uv_layout_path):
                            uv_layout_size_bytes = os.path.getsize(uv_layout_path)
                except Exception:
                    uv_layout_exported = False

            # 10. Export mesh
            export_result: Dict[str, Any] = {}
            if export_format:
                # Resolve the export path extension if the default placeholder
                # contains the {ext} token.
                resolved_export_path = export_path.replace("{ext}", export_format)
                # Ensure the path ends with the correct extension.
                if not resolved_export_path.lower().endswith(f".{export_format}"):
                    resolved_export_path = f"{resolved_export_path}.{export_format}"

                export_result = cls._export_mesh(
                    bpy=bpy,
                    fmt=export_format,
                    filepath=resolved_export_path,
                    extra_params=export_params or {},
                    obj=obj,
                )

            return {
                "status": "success",
                "object": obj.name,
                "uv_map": uv_map_name,
                "uv_method": uv_method,
                "island_count": island_count,
                "uv_layout_exported": uv_layout_exported,
                "uv_layout_path": uv_layout_path if uv_layout_exported else None,
                "uv_layout_size_bytes": uv_layout_size_bytes,
                "export": export_result,
            }

    # ===================================================================
    # Workflow 3: batch_mark_assets
    # ===================================================================
    @classmethod
    def batch_mark_assets(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        """Batch mark objects as Blender assets.

        Filters objects by type and/or a regex name pattern, optionally
        unmarks existing assets first, marks each matching object as an
        asset, assigns tags and a catalog, and optionally generates preview
        renders for each marked object.
        """
        bpy = cls.get_bpy()

        # --- Parameter extraction ---
        object_filter: Optional[str] = params.get("object_filter", "MESH")
        name_pattern: Optional[str] = params.get("name_pattern")
        catalog_name: Optional[str] = params.get("catalog_name")
        catalog_path: Optional[str] = params.get("catalog_path")
        tags: Optional[List[str]] = params.get("tags")
        generate_previews: bool = bool(params.get("generate_previews", True))
        preview_angle: List[float] = list(params.get("preview_angle", [0.6, 0.0, 0.8]))
        unmark_first: bool = bool(params.get("unmark_first", False))
        only_unmarked: bool = bool(params.get("only_unmarked", False))

        # Compile name pattern if provided
        name_regex: Optional[re.Pattern] = None
        if name_pattern:
            try:
                name_regex = re.compile(name_pattern)
            except re.error as exc:
                raise BlenderExecutionError(
                    f"Invalid name_pattern regex '{name_pattern}': {exc}"
                )

        with cls.transaction("batch_mark_assets"):
            # 1. Get all objects matching object_filter and name_pattern
            matching: List[Any] = []
            for obj in bpy.data.objects:
                if object_filter and object_filter.upper() != "ALL":
                    if obj.type != object_filter.upper():
                        continue
                if name_regex and not name_regex.search(obj.name):
                    continue
                matching.append(obj)

            if not matching:
                return {
                    "status": "success",
                    "marked_objects": [],
                    "count": 0,
                    "message": "No objects matched the filter criteria.",
                }

            # 2. Optionally unmark all matching objects first
            unmarked_count = 0
            if unmark_first:
                for obj in matching:
                    if getattr(obj, "asset_data", None) and hasattr(obj, "asset_clear"):
                        try:
                            obj.asset_clear()
                            unmarked_count += 1
                        except Exception:
                            pass

            # Resolve catalog UUID if requested
            catalog_uuid: Optional[str] = None
            if catalog_name or catalog_path:
                catalog_uuid = cls._resolve_or_create_catalog(
                    bpy, catalog_name, catalog_path
                )

            # 3. Mark each matching object as an asset
            marked_objects: List[Dict[str, Any]] = []
            skipped_already_marked = 0
            for obj in matching:
                # (a) Skip if only_unmarked and already an asset
                if only_unmarked and getattr(obj, "asset_data", None):
                    skipped_already_marked += 1
                    continue

                # (b) Mark as asset
                if not getattr(obj, "asset_data", None):
                    if hasattr(obj, "asset_mark"):
                        try:
                            obj.asset_mark()
                        except Exception as exc:
                            raise BlenderExecutionError(
                                f"Failed to mark '{obj.name}' as asset: {exc}"
                            )
                    else:
                        raise BlenderExecutionError(
                            f"Object '{obj.name}' does not support asset marking."
                        )

                # (c) Add tags
                added_tags: List[str] = []
                if tags and obj.asset_data and hasattr(obj.asset_data, "tags"):
                    existing_tag_names = {t.name for t in obj.asset_data.tags}
                    for tag in tags:
                        if tag in existing_tag_names:
                            continue
                        try:
                            obj.asset_data.tags.new(name=tag)
                            added_tags.append(tag)
                        except Exception:
                            pass

                # (d) Assign catalog
                if catalog_uuid and obj.asset_data:
                    try:
                        obj.asset_data.catalog_id = catalog_uuid
                    except Exception:
                        pass

                marked_objects.append({
                    "name": obj.name,
                    "type": obj.type,
                    "tags": added_tags,
                    "catalog_id": catalog_uuid,
                })

            # 4. Generate previews
            preview_status: List[Dict[str, Any]] = []
            if generate_previews and marked_objects:
                preview_status = cls._generate_asset_previews(
                    bpy, [bpy.data.objects[m["name"]] for m in marked_objects],
                    preview_angle,
                )

            return {
                "status": "success",
                "marked_objects": marked_objects,
                "count": len(marked_objects),
                "unmarked_first": unmarked_count,
                "skipped_already_marked": skipped_already_marked,
                "catalog": {
                    "name": catalog_name,
                    "path": catalog_path,
                    "uuid": catalog_uuid,
                },
                "previews": preview_status,
            }

    # ===================================================================
    # Workflow 4: auto_rig_character
    # ===================================================================
    @classmethod
    def auto_rig_character(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        """Automatically rig a mesh with an armature.

        Computes approximate proportions from the mesh's bounding box,
        creates an armature with bones laid out according to the chosen rig
        type (biped/humanoid, quadruped, or a simple chain), sets bone
        parenting, optionally parents the mesh to the armature with
        automatic weights, and optionally adds IK constraints to limbs with
        pole targets.
        """
        bpy = cls.get_bpy()

        # --- Parameter extraction ---
        mesh_object_name: str = params["mesh_object"]
        armature_name: str = params.get("armature_name", "AutoRig")
        rig_type: str = params.get("rig_type", "BIPED")
        bone_count: int = int(params.get("bone_count", 5))
        auto_weights: bool = bool(params.get("auto_weights", True))
        add_ik: bool = bool(params.get("add_ik", True))
        ik_pole_offset: float = float(params.get("ik_pole_offset", 0.5))
        set_bone_rotation_mode: str = params.get("set_bone_rotation_mode", "XYZ")
        parent_mesh: bool = bool(params.get("parent_mesh", True))
        add_root_bone: bool = bool(params.get("add_root_bone", True))

        valid_rig_types = {"BIPED", "QUADRUPED", "HUMANOID", "SIMPLE"}
        if rig_type not in valid_rig_types:
            raise BlenderExecutionError(
                f"Invalid rig_type '{rig_type}'. Must be one of {sorted(valid_rig_types)}."
            )

        valid_rot_modes = {"XYZ", "QUATERNION"}
        if set_bone_rotation_mode not in valid_rot_modes:
            raise BlenderExecutionError(
                f"Invalid set_bone_rotation_mode '{set_bone_rotation_mode}'. "
                f"Must be one of {sorted(valid_rot_modes)}."
            )

        with cls.transaction(f"auto_rig_character('{mesh_object_name}')"):
            # 1. Get mesh object, compute bounding box
            mesh_obj = cls.get_object(mesh_object_name)
            if mesh_obj.type != "MESH":
                raise BlenderExecutionError(
                    f"Object '{mesh_object_name}' is not a MESH (type={mesh_obj.type})."
                )

            # 2. Compute approximate proportions from bounding box
            dims = list(mesh_obj.dimensions)
            height = dims[2] if dims[2] > 0 else 1.0
            width = dims[0] if dims[0] > 0 else 1.0
            depth = dims[1] if dims[1] > 0 else 1.0
            center = list(mesh_obj.location)
            # Bottom of the mesh (feet level)
            z_min = center[2] - height / 2.0
            z_max = center[2] + height / 2.0

            # 3. Create armature at object center
            arm_data = bpy.data.armatures.new(armature_name)
            arm_obj = bpy.data.objects.new(armature_name, arm_data)
            arm_obj.location = [center[0], center[1], z_min]
            bpy.context.scene.collection.objects.link(arm_obj)

            # 4. Enter edit mode, create bones based on rig_type
            bone_specs: List[Dict[str, Any]] = []
            if rig_type in ("BIPED", "HUMANOID"):
                bone_specs = cls._build_biped_bones(
                    center, height, width, depth, z_min, add_root_bone
                )
            elif rig_type == "QUADRUPED":
                bone_specs = cls._build_quadruped_bones(
                    center, height, width, depth, z_min, add_root_bone
                )
            elif rig_type == "SIMPLE":
                bone_specs = cls._build_simple_bones(
                    center, height, bone_count
                )

            with cls.active_mode(arm_obj, "EDIT"):
                # Create all bones first
                created_bones: Dict[str, Any] = {}
                for spec in bone_specs:
                    b = arm_data.edit_bones.new(spec["name"])
                    b.head = spec["head"]
                    b.tail = spec["tail"]
                    created_bones[spec["name"]] = b

                # 5. Set bone parenting
                for spec in bone_specs:
                    parent_name = spec.get("parent")
                    if parent_name and parent_name in created_bones:
                        child = created_bones[spec["name"]]
                        parent = created_bones[parent_name]
                        child.parent = parent
                        # Connect to parent if the tail/head align
                        try:
                            child.use_connect = (
                                abs(child.head[2] - parent.tail[2]) < 1e-4
                                and abs(child.head[0] - parent.tail[0]) < 1e-4
                                and abs(child.head[1] - parent.tail[1]) < 1e-4
                            )
                        except Exception:
                            pass

            # 6. Exit edit mode (handled by active_mode)

            bone_list = [spec["name"] for spec in bone_specs]

            # 7. Parent mesh to armature with automatic weights
            weight_status = "not_parented"
            if parent_mesh:
                weight_status = cls._parent_mesh_to_armature(
                    bpy, mesh_obj, arm_obj, auto_weights
                )

            # 8. Add IK constraints
            ik_targets: List[Dict[str, Any]] = []
            if add_ik and rig_type in ("BIPED", "HUMANOID", "QUADRUPED"):
                ik_targets = cls._add_ik_constraints(
                    bpy, arm_obj, bone_specs, ik_pole_offset, rig_type
                )

            # 9. Set bone rotation mode on all pose bones
            rot_mode_set = 0
            if hasattr(arm_obj, "pose") and arm_obj.pose:
                for pbone in arm_obj.pose.bones:
                    try:
                        if set_bone_rotation_mode == "QUATERNION":
                            pbone.rotation_mode = "QUATERNION"
                        else:
                            pbone.rotation_mode = "XYZ"
                        rot_mode_set += 1
                    except Exception:
                        pass

            return {
                "status": "success",
                "mesh_object": mesh_obj.name,
                "armature": arm_obj.name,
                "rig_type": rig_type,
                "bone_count": len(bone_list),
                "bones": bone_list,
                "ik_targets": ik_targets,
                "weight_paint_status": weight_status,
                "rotation_mode_set": rot_mode_set,
                "rotation_mode": set_bone_rotation_mode,
            }

    # ===================================================================
    # Internal helpers -- UV pipeline
    # ===================================================================

    @classmethod
    def _auto_mark_seams(cls, bpy: Any, seam_angle: float) -> None:
        """Auto-mark seams on the active mesh in edit mode.

        Clears existing seams, switches to edge selection mode, selects
        edges whose adjacent-face angle exceeds the threshold, and marks
        them as seams. Falls back gracefully when the operator API is not
        available.
        """
        try:
            # Clear existing seams
            if hasattr(bpy.ops.mesh, "mark_seam"):
                try:
                    bpy.ops.mesh.mark_seam(clear=True)
                except TypeError:
                    bpy.ops.mesh.mark_seam(clear_seams=True)
        except Exception:
            pass

        try:
            # Switch to edge selection mode
            if hasattr(bpy.ops.mesh, "select_mode"):
                bpy.ops.mesh.select_mode(type="EDGE")
        except Exception:
            pass

        # Select sharp edges and mark as seams. The select_sharp_edges
        # operator (Blender 4.2+) is the cleanest way; otherwise we iterate
        # manually over bmesh edges.
        try:
            if hasattr(bpy.ops.mesh, "select_sharp_edges"):
                bpy.ops.mesh.select_sharp_edges(sharp_angle=math.radians(seam_angle))
                if hasattr(bpy.ops.mesh, "mark_seam"):
                    bpy.ops.mesh.mark_seam()
                return
        except Exception:
            pass

        # Manual fallback via bmesh
        try:
            import bmesh
            me = bpy.context.edit_object.data
            bm = bmesh.from_edit_mesh(me)
            bm.edges.ensure_lookup_table()
            threshold = math.radians(seam_angle)
            for edge in bm.edges:
                if len(edge.link_faces) < 2:
                    edge.select = True
                    continue
                angle = edge.calc_face_angle(0.0)
                if angle > threshold:
                    edge.select = True
                else:
                    edge.select = False
            bmesh.update_edit_mesh(me)
            if hasattr(bpy.ops.mesh, "mark_seam"):
                bpy.ops.mesh.mark_seam()
        except Exception:
            pass

    @classmethod
    def _count_uv_islands(cls, mesh: Any, uv_map_name: str) -> int:
        """Approximate the number of UV islands on a mesh's UV layer.

        Uses a union-find over polygon adjacency in UV space. Returns 0 if
        the UV layer or mesh data is unavailable.
        """
        try:
            uv_layer = mesh.uv_layers.get(uv_map_name)
            if uv_layer is None:
                return 0
            polys = mesh.polygons
            if len(polys) == 0:
                return 0

            # Build adjacency: two polygons are in the same island if they
            # share a UV-loop vertex position (approximately).
            parent = list(range(len(polys)))

            def find(x: int) -> int:
                while parent[x] != x:
                    parent[x] = parent[parent[x]]
                    x = parent[x]
                return x

            def union(a: int, b: int) -> None:
                ra, rb = find(a), find(b)
                if ra != rb:
                    parent[ra] = rb

            # Map from rounded UV coordinate -> list of polygon indices
            uv_to_polys: Dict[Tuple[int, int], List[int]] = {}
            uv_data = uv_layer.data
            for pi, poly in enumerate(polys):
                for loop_idx in poly.loop_indices:
                    uv = uv_data[loop_idx].uv
                    key = (round(uv.x, 5), round(uv.y, 5))
                    uv_to_polys.setdefault(key, []).append(pi)

            for poly_list in uv_to_polys.values():
                for i in range(1, len(poly_list)):
                    union(poly_list[0], poly_list[i])

            roots = {find(i) for i in range(len(polys))}
            return len(roots)
        except Exception:
            return 0

    @classmethod
    def _export_mesh(
        cls,
        bpy: Any,
        fmt: str,
        filepath: str,
        extra_params: Dict[str, Any],
        obj: Any,
    ) -> Dict[str, Any]:
        """Export the given object in the requested format.

        Resolves the appropriate export operator with fallbacks for name
        variations across Blender versions, selects only the target object
        for the export, and returns a summary dict including file size.
        """
        # Ensure the output directory exists
        out_dir = os.path.dirname(os.path.abspath(filepath))
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        # Save current selection, then select only the target object
        prev_selection = {o.name for o in bpy.context.selected_objects}
        try:
            bpy.ops.object.select_all(action="DESELECT")
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
        except Exception:
            pass

        # Build operator lookup with fallbacks for version variations
        op: Optional[Any] = None
        if fmt == "fbx":
            op = getattr(bpy.ops.export_scene, "fbx", None)
        elif fmt == "obj":
            op = (
                getattr(bpy.ops.wm, "obj_export", None)
                or getattr(bpy.ops.export_scene, "obj", None)
            )
        elif fmt in ("gltf", "glb"):
            op = getattr(bpy.ops.export_scene, "gltf", None)
        elif fmt == "stl":
            op = (
                getattr(bpy.ops.export_mesh, "stl", None)
                or getattr(bpy.ops.wm, "stl_export", None)
            )
        elif fmt == "ply":
            op = (
                getattr(bpy.ops.export_mesh, "ply", None)
                or getattr(bpy.ops.wm, "ply_export", None)
            )

        exported = False
        error: Optional[str] = None
        kwargs = dict(extra_params)

        if op is None:
            error = f"Export operator for '{fmt}' is not available in this Blender version."
        else:
            try:
                if fmt in ("gltf", "glb"):
                    # glTF exporter uses export_format='GLB'/'GLTF_SEPARATE'
                    gltf_format = "GLB" if fmt == "glb" else "GLTF_SEPARATE"
                    op(filepath=filepath, export_format=gltf_format, **kwargs)
                else:
                    op(filepath=filepath, **kwargs)
                exported = True
            except Exception as exc:
                error = str(exc)

        # Restore selection
        try:
            bpy.ops.object.select_all(action="DESELECT")
            for name in prev_selection:
                o = bpy.data.objects.get(name)
                if o:
                    o.select_set(True)
        except Exception:
            pass

        file_size: Optional[int] = None
        if exported and os.path.exists(filepath):
            file_size = os.path.getsize(filepath)

        return {
            "format": fmt,
            "filepath": filepath,
            "exported": exported,
            "file_size_bytes": file_size,
            "error": error,
        }

    # ===================================================================
    # Internal helpers -- batch_mark_assets
    # ===================================================================

    @classmethod
    def _resolve_or_create_catalog(
        cls,
        bpy: Any,
        catalog_name: Optional[str],
        catalog_path: Optional[str],
    ) -> Optional[str]:
        """Resolve an existing catalog UUID by name/path, or create a new one.

        Returns the catalog UUID string, or None if catalogs are not
        available in the current Blender version.
        """
        # Try to find an existing catalog by name or path
        try:
            # Blender 5.x: bpy.assets.catalogs
            catalogs = None
            if hasattr(bpy, "assets") and hasattr(bpy.assets, "catalogs"):
                catalogs = bpy.assets.catalogs
            elif hasattr(bpy.context, "asset_library_catalogs"):
                catalogs = bpy.context.asset_library_catalogs

            if catalogs is not None:
                for cat in catalogs:
                    cat_path_attr = getattr(cat, "path", "") or getattr(cat, "name", "")
                    cat_name_attr = getattr(cat, "name", "") or getattr(cat, "path", "")
                    if catalog_name and cat_name_attr == catalog_name:
                        return getattr(cat, "uuid", None) or getattr(cat, "id", None)
                    if catalog_path and cat_path_attr == catalog_path:
                        return getattr(cat, "uuid", None) or getattr(cat, "id", None)

                # Create a new catalog if not found
                if hasattr(bpy.ops.asset, "catalog_new"):
                    new_name = catalog_name or (catalog_path or "NewCatalog")
                    try:
                        bpy.ops.asset.catalog_new(catalog_name=new_name)
                    except Exception:
                        pass
                    # Re-scan for the newly created catalog
                    for cat in catalogs:
                        cat_name_attr = getattr(cat, "name", "")
                        if cat_name_attr == new_name:
                            return getattr(cat, "uuid", None) or getattr(cat, "id", None)
        except Exception:
            pass

        # Fallback: parse the blender_assets.cats.txt file in asset libraries
        try:
            asset_libs = bpy.context.preferences.asset_libraries
            search_name = catalog_name or (catalog_path and catalog_path.split("/")[-1])
            for lib in asset_libs:
                lib_path = getattr(lib, "path", "")
                if not lib_path:
                    continue
                cat_file = os.path.join(lib_path, "blender_assets.cats.txt")
                if not os.path.exists(cat_file):
                    continue
                with open(cat_file, "r") as fh:
                    for line in fh:
                        line = line.strip()
                        if not line or line.startswith("#") or ":" not in line:
                            continue
                        parts = line.split(":", 2)
                        if len(parts) < 3:
                            continue
                        uuid, path_str, name_str = (
                            parts[0].strip(),
                            parts[1].strip(),
                            parts[2].strip(),
                        )
                        if (catalog_name and name_str == catalog_name) or (
                            catalog_path and path_str == catalog_path
                        ):
                            return uuid
        except Exception:
            pass

        return None

    @classmethod
    def _generate_asset_previews(
        cls,
        bpy: Any,
        objects: List[Any],
        preview_angle: List[float],
    ) -> List[Dict[str, Any]]:
        """Generate asset preview renders for a list of objects.

        For each object, saves the current selection/rotation, selects only
        that object, applies the preview rotation, renders a preview, and
        restores the original state.
        """
        results: List[Dict[str, Any]] = []
        # Normalize preview angle to 3 floats
        angle = list(preview_angle)
        while len(angle) < 3:
            angle.append(0.0)
        angle = [float(v) for v in angle[:3]]

        prev_active = bpy.context.view_layer.objects.active
        prev_selection = {o.name for o in bpy.context.selected_objects}

        for obj in objects:
            status: Dict[str, Any] = {"name": obj.name, "generated": False}
            try:
                # Save original rotation
                orig_rot = list(obj.rotation_euler)

                # Select only this object
                bpy.ops.object.select_all(action="DESELECT")
                obj.select_set(True)
                bpy.context.view_layer.objects.active = obj

                # Set preview rotation
                obj.rotation_euler = angle

                # Try the dedicated asset preview operator first
                generated = False
                try:
                    if hasattr(bpy.ops.ed, "asset_preview_render"):
                        bpy.ops.ed.asset_preview_render()
                        generated = True
                except Exception:
                    pass

                # Fallback: viewport render
                if not generated:
                    try:
                        if hasattr(bpy.ops.render, "opengl"):
                            bpy.ops.render.opengl()
                            generated = True
                    except Exception:
                        pass

                # Restore rotation
                obj.rotation_euler = orig_rot
                status["generated"] = generated
            except Exception as exc:
                status["error"] = str(exc)
            results.append(status)

        # Restore selection
        try:
            bpy.ops.object.select_all(action="DESELECT")
            for name in prev_selection:
                o = bpy.data.objects.get(name)
                if o:
                    o.select_set(True)
            if prev_active and prev_active.name in bpy.data.objects:
                bpy.context.view_layer.objects.active = prev_active
        except Exception:
            pass

        return results

    # ===================================================================
    # Internal helpers -- auto_rig_character
    # ===================================================================

    @classmethod
    def _build_biped_bones(
        cls,
        center: List[float],
        height: float,
        width: float,
        depth: float,
        z_min: float,
        add_root: bool,
    ) -> List[Dict[str, Any]]:
        """Build the bone specification list for a biped/humanoid rig.

        Bone positions are approximated from the bounding-box proportions,
        expressed as fractions of the total height. The armature origin is
        at the feet (z_min), so all Z coordinates are relative to z_min.
        """
        cx, cy = center[0], center[1]
        h = height
        w = width
        # Helper to produce a vertical bone spec
        def vbone(
            name: str,
            z_head_frac: float,
            z_tail_frac: float,
            x_offset: float = 0.0,
            parent: Optional[str] = None,
            length: Optional[float] = None,
        ) -> Dict[str, Any]:
            z_head = z_min + h * z_head_frac
            z_tail = z_min + h * z_tail_frac
            if length is not None:
                z_tail = z_head + length
            return {
                "name": name,
                "head": [cx + x_offset, cy, z_head],
                "tail": [cx + x_offset, cy, z_tail],
                "parent": parent,
            }

        bones: List[Dict[str, Any]] = []

        if add_root:
            bones.append(vbone("Root", 0.0, 0.02, parent=None))

        # Spine chain
        bones.append(vbone("Hips", 0.45, 0.60, parent="Root" if add_root else None))
        bones.append(vbone("Spine", 0.60, 0.75, parent="Hips"))
        bones.append(vbone("Chest", 0.75, 0.78, parent="Spine"))
        bones.append(vbone("Neck", 0.85, 0.88, parent="Chest"))
        bones.append(vbone("Head", 0.88, 0.92, parent="Neck"))

        # Arms (left = +x, right = -x)
        shoulder_x = w / 3.0
        arm_x = w / 2.5
        bones.append(vbone("Shoulder.L", 0.78, 0.78, x_offset=shoulder_x, parent="Chest", length=h * 0.05))
        bones.append(vbone("Shoulder.R", 0.78, 0.78, x_offset=-shoulder_x, parent="Chest", length=h * 0.05))
        bones.append(vbone("UpperArm.L", 0.70, 0.55, x_offset=arm_x, parent="Shoulder.L"))
        bones.append(vbone("UpperArm.R", 0.70, 0.55, x_offset=-arm_x, parent="Shoulder.R"))
        bones.append(vbone("LowerArm.L", 0.55, 0.45, x_offset=arm_x, parent="UpperArm.L"))
        bones.append(vbone("LowerArm.R", 0.55, 0.45, x_offset=-arm_x, parent="UpperArm.R"))
        bones.append(vbone("Hand.L", 0.45, 0.43, x_offset=arm_x, parent="LowerArm.L"))
        bones.append(vbone("Hand.R", 0.45, 0.43, x_offset=-arm_x, parent="LowerArm.R"))

        # Legs
        leg_x = w / 4.0
        bones.append(vbone("UpperLeg.L", 0.40, 0.20, x_offset=leg_x, parent="Hips"))
        bones.append(vbone("UpperLeg.R", 0.40, 0.20, x_offset=-leg_x, parent="Hips"))
        bones.append(vbone("LowerLeg.L", 0.20, 0.02, x_offset=leg_x, parent="UpperLeg.L"))
        bones.append(vbone("LowerLeg.R", 0.20, 0.02, x_offset=-leg_x, parent="UpperLeg.R"))
        bones.append(vbone("Foot.L", 0.02, 0.0, x_offset=leg_x, parent="LowerLeg.L", length=h * 0.04))
        bones.append(vbone("Foot.R", 0.02, 0.0, x_offset=-leg_x, parent="LowerLeg.R", length=h * 0.04))

        return bones

    @classmethod
    def _build_quadruped_bones(
        cls,
        center: List[float],
        height: float,
        width: float,
        depth: float,
        z_min: float,
        add_root: bool,
    ) -> List[Dict[str, Any]]:
        """Build the bone specification list for a quadruped rig.

        The quadruped layout is horizontal: the spine runs along the Y axis
        (depth), with legs dropping down at the front and rear.
        """
        cx, cy, cz = center[0], center[1], center[2]
        h = height
        w = width
        d = depth
        # Spine runs along Y from rear (y_min) to head (y_max)
        y_min = cy - d / 2.0
        y_max = cy + d / 2.0
        leg_z = z_min + h * 0.5  # legs attach at mid-height

        def hbone(
            name: str,
            y_head: float,
            y_tail: float,
            z: float,
            x_offset: float = 0.0,
            parent: Optional[str] = None,
        ) -> Dict[str, Any]:
            return {
                "name": name,
                "head": [cx + x_offset, y_head, z],
                "tail": [cx + x_offset, y_tail, z],
                "parent": parent,
            }

        def vbone(
            name: str,
            z_head: float,
            z_tail: float,
            x_offset: float,
            y: float,
            parent: Optional[str] = None,
        ) -> Dict[str, Any]:
            return {
                "name": name,
                "head": [cx + x_offset, y, z_head],
                "tail": [cx + x_offset, y, z_tail],
                "parent": parent,
            }

        bones: List[Dict[str, Any]] = []

        if add_root:
            bones.append({
                "name": "Root",
                "head": [cx, y_min, z_min],
                "tail": [cx, y_min, z_min + h * 0.02],
                "parent": None,
            })

        # Spine chain along Y
        bones.append(hbone("Hips", y_min, y_min + d * 0.15, leg_z, parent="Root" if add_root else None))
        bones.append(hbone("Spine", y_min + d * 0.15, y_min + d * 0.45, leg_z, parent="Hips"))
        bones.append(hbone("Chest", y_min + d * 0.45, y_min + d * 0.70, leg_z, parent="Spine"))
        bones.append(hbone("Neck", y_min + d * 0.70, y_min + d * 0.85, leg_z, parent="Chest"))
        bones.append(hbone("Head", y_min + d * 0.85, y_max, leg_z, parent="Neck"))

        # Front legs (at chest) and rear legs (at hips)
        leg_x = w / 4.0
        front_y = y_min + d * 0.65
        rear_y = y_min + d * 0.10

        for side, sign in (("L", 1), ("R", -1)):
            x_off = sign * leg_x
            # Front legs
            bones.append(vbone(f"FrontUpperLeg.{side}", leg_z, z_min + h * 0.25, x_off, front_y, parent="Chest"))
            bones.append(vbone(f"FrontLowerLeg.{side}", z_min + h * 0.25, z_min + h * 0.05, x_off, front_y, parent=f"FrontUpperLeg.{side}"))
            bones.append(vbone(f"FrontFoot.{side}", z_min + h * 0.05, z_min, x_off, front_y, parent=f"FrontLowerLeg.{side}"))
            # Rear legs
            bones.append(vbone(f"RearUpperLeg.{side}", leg_z, z_min + h * 0.25, x_off, rear_y, parent="Hips"))
            bones.append(vbone(f"RearLowerLeg.{side}", z_min + h * 0.25, z_min + h * 0.05, x_off, rear_y, parent=f"RearUpperLeg.{side}"))
            bones.append(vbone(f"RearFoot.{side}", z_min + h * 0.05, z_min, x_off, rear_y, parent=f"RearLowerLeg.{side}"))

        return bones

    @classmethod
    def _build_simple_bones(
        cls,
        center: List[float],
        height: float,
        bone_count: int,
    ) -> List[Dict[str, Any]]:
        """Build a simple vertical chain of *bone_count* bones from bottom to top."""
        cx, cy = center[0], center[1]
        z_min = center[2] - height / 2.0
        segment = height / max(bone_count, 1)
        bones: List[Dict[str, Any]] = []
        for i in range(bone_count):
            name = f"Bone{i + 1:02d}"
            z_head = z_min + i * segment
            z_tail = z_head + segment
            parent = f"Bone{i:02d}" if i > 0 else None
            bones.append({
                "name": name,
                "head": [cx, cy, z_head],
                "tail": [cx, cy, z_tail],
                "parent": parent,
            })
        return bones

    @classmethod
    def _parent_mesh_to_armature(
        cls,
        bpy: Any,
        mesh_obj: Any,
        arm_obj: Any,
        auto_weights: bool,
    ) -> str:
        """Parent a mesh object to an armature, optionally with automatic weights.

        Returns a status string describing the parenting method used.
        """
        try:
            # Select mesh first, then armature (armature must be active)
            bpy.ops.object.select_all(action="DESELECT")
            mesh_obj.select_set(True)
            arm_obj.select_set(True)
            bpy.context.view_layer.objects.active = arm_obj

            if auto_weights:
                try:
                    bpy.ops.object.parent_set(type="ARMATURE_AUTO")
                    return "parented_with_automatic_weights"
                except Exception:
                    # Fallback: parent with envelope weights or plain parent
                    try:
                        bpy.ops.object.parent_set(type="ARMATURE")
                        return "parented_with_envelope_weights"
                    except Exception:
                        mesh_obj.parent = arm_obj
                        return "parented_no_weights"
            else:
                try:
                    bpy.ops.object.parent_set(type="OBJECT")
                    return "parented_object"
                except Exception:
                    mesh_obj.parent = arm_obj
                    return "parented_object_manual"
        except Exception as exc:
            return f"parenting_failed: {exc}"

    @classmethod
    def _add_ik_constraints(
        cls,
        bpy: Any,
        arm_obj: Any,
        bone_specs: List[Dict[str, Any]],
        pole_offset: float,
        rig_type: str,
    ) -> List[Dict[str, Any]]:
        """Add IK constraints to limb bones of an armature.

        For each limb (arms and legs in biped; front/rear legs in
        quadruped), adds an IK constraint on the foot/hand bone targeting a
        newly created IK target bone, plus a pole target for the
        knee/elbow. Returns a list of IK target descriptors.
        """
        ik_targets: List[Dict[str, Any]] = []

        if not hasattr(arm_obj, "pose") or not arm_obj.pose:
            return ik_targets

        # Determine limb groups based on rig type
        limbs: List[Tuple[str, str, str, str]] = []  # (chain_root, mid, tip, side)
        if rig_type in ("BIPED", "HUMANOID"):
            for side in ("L", "R"):
                limbs.append(("UpperArm", "LowerArm", "Hand", side))
                limbs.append(("UpperLeg", "LowerLeg", "Foot", side))
        elif rig_type == "QUADRUPED":
            for side in ("L", "R"):
                limbs.append(("FrontUpperLeg", "FrontLowerLeg", "FrontFoot", side))
                limbs.append(("RearUpperLeg", "RearLowerLeg", "RearFoot", side))

        # We need to add IK target bones in edit mode, then add constraints
        # in pose mode. Collect target bone specs first.
        ik_target_specs: List[Tuple[str, str, List[float]]] = []
        for upper_name, mid_name, tip_name, side in limbs:
            tip_full = f"{tip_name}.{side}"
            # Find the tip bone spec to get its tail position
            tip_spec = next(
                (s for s in bone_specs if s["name"] == tip_full), None
            )
            if tip_spec is None:
                continue
            tail = tip_spec["tail"]
            # IK target bone placed slightly beyond the tip
            target_name = f"IK_{tip_full}"
            target_head = list(tail)
            target_tail = [target_head[0], target_head[1], target_head[2] + 0.05]
            ik_target_specs.append((target_name, tip_full, target_head, target_tail))

        # Add IK target bones in edit mode
        if ik_target_specs:
            with cls.active_mode(arm_obj, "EDIT"):
                arm_data = arm_obj.data
                for target_name, tip_full, target_head, target_tail in ik_target_specs:
                    if arm_data.edit_bones.get(target_name) is None:
                        b = arm_data.edit_bones.new(target_name)
                        b.head = target_head
                        b.tail = target_tail

        # Add IK constraints in pose mode
        for upper_name, mid_name, tip_name, side in limbs:
            tip_full = f"{tip_name}.{side}"
            mid_full = f"{mid_name}.{side}"
            target_name = f"IK_{tip_full}"
            pole_name = f"Pole_{mid_full}"

            pbone = arm_obj.pose.bones.get(tip_full)
            if pbone is None:
                continue

            # Add IK constraint
            try:
                ik_con = pbone.constraints.new(type="IK")
                ik_con.target = arm_obj
                ik_con.subtarget = target_name
                # Chain length: 2 bones (upper + lower)
                ik_con.chain_count = 2

                # Add pole target bone in edit mode
                mid_spec = next(
                    (s for s in bone_specs if s["name"] == mid_full), None
                )
                if mid_spec is not None:
                    mid_head = mid_spec["head"]
                    # Pole target placed offset from the elbow/knee
                    pole_head = [
                        mid_head[0] + pole_offset,
                        mid_head[1],
                        mid_head[2],
                    ]
                    pole_tail = [
                        pole_head[0],
                        pole_head[1],
                        pole_head[2] + 0.05,
                    ]
                    with cls.active_mode(arm_obj, "EDIT"):
                        arm_data = arm_obj.data
                        if arm_data.edit_bones.get(pole_name) is None:
                            pb = arm_data.edit_bones.new(pole_name)
                            pb.head = pole_head
                            pb.tail = pole_tail

                    # Configure pole target on the IK constraint
                    pole_pbone = arm_obj.pose.bones.get(pole_name)
                    if pole_pbone is not None:
                        ik_con.pole_target = arm_obj
                        ik_con.pole_subtarget = pole_name
                        # Pole angle defaults; can be tuned per rig
                        if hasattr(ik_con, "pole_angle"):
                            ik_con.pole_angle = math.radians(90.0)

                ik_targets.append({
                    "tip_bone": tip_full,
                    "ik_target_bone": target_name,
                    "pole_bone": pole_name,
                    "chain_count": 2,
                })
            except Exception:
                continue

        return ik_targets
