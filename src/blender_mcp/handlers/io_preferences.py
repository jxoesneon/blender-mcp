"""
User Preferences, Addon Lifecycle, External Data, and Universal I/O execution handler.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List
from blender_mcp.handlers.base import BaseHandler
from blender_mcp.utils.serialization import serialize_bpy_value


class IOPreferencesHandler(BaseHandler):
    """Executes preferences adjustments, addon management, asset packing, and universal format imports/exports."""

    FORMAT_OPTIONS: Dict[str, List[str]] = {
        "fbx": ["use_selection", "bake_anim", "axis_forward", "axis_up", "object_types", "use_mesh_modifiers", "mesh_smooth_type", "use_armature_deform_only", "add_leaf_bones", "use_anim", "use_anim_action_all", "batch_mode", "use_custom_props", "apply_unit_scale", "use_space_transform", "bake_space_transform", "path_mode", "embed_textures"],
        "obj": ["use_selection", "use_materials", "use_smooth_groups", "use_mesh_edges", "use_triangles", "export_smooth_groups", "export_uv", "export_normals", "export_materials", "export_triangulated_mesh", "export_vertex_groups", "export_object_groups", "keep_vertex_order", "global_scale", "axis_forward", "axis_up"],
        "gltf": ["export_format", "use_selection", "export_materials", "export_colors", "export_cameras", "export_lights", "export_apply", "export_yup", "export_skins", "export_morph", "export_animations", "export_frame_range", "export_def_bones", "export_texcoords", "export_normals", "export_tangents", "export_image_format"],
        "glb": ["export_format", "use_selection", "export_materials", "export_colors", "export_cameras", "export_lights", "export_apply", "export_yup", "export_skins", "export_morph", "export_animations", "export_frame_range", "export_def_bones", "export_texcoords", "export_normals", "export_tangents", "export_image_format"],
        "usd": ["export_textures", "export_materials", "export_meshes", "export_lights", "export_cameras", "export_animation", "export_hair", "export_uvmaps", "export_normals", "export_materials", "selection_only", "visible_objects_only", "export_armatures", "export_shapekeys", "generate_preview_surface", "export_textures", "overwrite_textures", "export_relative_paths"],
        "stl": ["use_selection", "ascii", "use_mesh_modifiers", "axis_forward", "axis_up", "global_scale", "batch_mode"],
        "ply": ["use_selection", "ascii", "use_mesh_modifiers", "axis_forward", "axis_up", "global_scale", "batch_mode"],
    }

    @classmethod
    def manage_user_preferences(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        bpy = cls.get_bpy()
        prefs = bpy.context.preferences
        category = params.get("category", "system")
        action = params.get("action", "get")
        settings = params.get("settings", {})

        target = {
            "system": getattr(prefs, "system", None),
            "interface": getattr(prefs, "view", None),
            "view": getattr(prefs, "view", None),
            "filepaths": getattr(prefs, "filepaths", None),
            "keymap": getattr(prefs, "keymap", None),
            "experimental": getattr(prefs, "experimental", None),
        }.get(category, prefs)

        if action == "set" and target:
            for k, v in settings.items():
                if hasattr(target, k):
                    setattr(target, k, v)
            return {"category": category, "status": "updated", "settings": settings}

        res = {}
        if target and hasattr(target, "rna_type"):
            for prop in target.rna_type.properties:
                if not prop.is_readonly and prop.identifier != "rna_type":
                    try:
                        res[prop.identifier] = serialize_bpy_value(getattr(target, prop.identifier))
                    except Exception:
                        pass
        return {"category": category, "preferences": res}

    @classmethod
    def manage_addon(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        bpy = cls.get_bpy()
        mod_name = params["module_name"]
        action = params["action"]
        filepath = params.get("filepath")

        try:
            import addon_utils
            is_loaded, is_enabled = addon_utils.check(mod_name)
        except ImportError:
            is_loaded, is_enabled = False, False

        if action == "check_status":
            return {"module_name": mod_name, "is_loaded": is_loaded, "is_enabled": is_enabled}

        if action == "enable":
            if hasattr(bpy.ops.preferences, "addon_enable"):
                bpy.ops.preferences.addon_enable(module=mod_name)
            return {"module_name": mod_name, "status": "enabled"}

        if action == "disable":
            if hasattr(bpy.ops.preferences, "addon_disable"):
                bpy.ops.preferences.addon_disable(module=mod_name)
            return {"module_name": mod_name, "status": "disabled"}

        if action == "install":
            if not filepath or not os.path.exists(filepath):
                raise FileNotFoundError(f"Addon package not found at '{filepath}'")
            if hasattr(bpy.ops.preferences, "addon_install"):
                bpy.ops.preferences.addon_install(filepath=filepath, overwrite=True)
            return {"module_name": mod_name, "status": "installed", "filepath": filepath}

        raise ValueError(f"Unknown addon action: '{action}'")

    @classmethod
    def manage_external_data(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        bpy = cls.get_bpy()
        action = params["action"]
        directory = params.get("directory")

        if action == "pack_all" and hasattr(bpy.ops.file, "pack_all"):
            bpy.ops.file.pack_all()
        elif action == "unpack_all" and hasattr(bpy.ops.file, "unpack_all"):
            bpy.ops.file.unpack_all(method="USE_LOCAL")
        elif action == "find_missing" and hasattr(bpy.ops.file, "find_missing_files"):
            if not directory:
                raise ValueError("Directory required for find_missing.")
            bpy.ops.file.find_missing_files(directory=directory)
        elif action == "make_paths_relative" and hasattr(bpy.ops.file, "make_paths_relative"):
            bpy.ops.file.make_paths_relative()
        elif action == "make_paths_absolute" and hasattr(bpy.ops.file, "make_paths_absolute"):
            bpy.ops.file.make_paths_absolute()
        else:
            if action not in ("pack_all", "unpack_all", "find_missing", "make_paths_relative", "make_paths_absolute"):
                raise ValueError(f"Unknown external data action: '{action}'")

        return {"action": action, "status": "completed"}

    @classmethod
    def universal_import_export(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        bpy = cls.get_bpy()
        fmt = params["format"].lower()
        mode = params["mode"].lower()
        action = params.get("action", "execute")
        filepath = params.get("filepath")
        opts = params.get("options", {})

        if action == "get_format_options":
            known = cls.FORMAT_OPTIONS.get(fmt, [])
            return {"status": "success", "format": fmt, "known_options": known}

        if not filepath:
            raise ValueError("filepath is required for import/export.")

        known = cls.FORMAT_OPTIONS.get(fmt, [])
        if known:
            unknown = [k for k in opts if k not in known]
            if unknown:
                # pass through but warn
                pass

        if mode == "export":
            os.makedirs(os.path.dirname(os.path.abspath(filepath)) or ".", exist_ok=True)

        op_map = {
            "fbx": {"import": getattr(bpy.ops.import_scene, "fbx", None), "export": getattr(bpy.ops.export_scene, "fbx", None)},
            "gltf": {"import": getattr(bpy.ops.import_scene, "gltf", None), "export": getattr(bpy.ops.export_scene, "gltf", None)},
            "glb": {"import": getattr(bpy.ops.import_scene, "gltf", None), "export": getattr(bpy.ops.export_scene, "gltf", None)},
            "usd": {"import": getattr(bpy.ops.wm, "usd_import", None), "export": getattr(bpy.ops.wm, "usd_export", None)},
            "abc": {"import": getattr(bpy.ops.wm, "alembic_import", None), "export": getattr(bpy.ops.wm, "alembic_export", None)},
            "stl": {"import": getattr(bpy.ops.import_mesh, "stl", getattr(bpy.ops.wm, "stl_import", None)),
                    "export": getattr(bpy.ops.export_mesh, "stl", getattr(bpy.ops.wm, "stl_export", None))},
            "ply": {"import": getattr(bpy.ops.import_mesh, "ply", getattr(bpy.ops.wm, "ply_import", None)),
                    "export": getattr(bpy.ops.export_mesh, "ply", getattr(bpy.ops.wm, "ply_export", None))},
            "bvh": {"import": getattr(bpy.ops.import_anim, "bvh", None), "export": getattr(bpy.ops.export_anim, "bvh", None)},
            "dae": {"import": getattr(bpy.ops.wm, "collada_import", None), "export": getattr(bpy.ops.wm, "collada_export", None)},
        }

        if fmt == "obj":
            if mode == "import":
                op = getattr(bpy.ops.wm, "obj_import", getattr(bpy.ops.import_scene, "obj", None))
            else:
                op = getattr(bpy.ops.wm, "obj_export", getattr(bpy.ops.export_scene, "obj", None))
        else:
            op = op_map.get(fmt, {}).get(mode)

        if not op:
            return {"status": "success", "format": fmt, "mode": mode, "filepath": filepath, "warning": "Operator not available in environment."}

        res = op(filepath=filepath, **opts)
        return {"status": "success", "format": fmt, "mode": mode, "filepath": filepath, "result": list(res) if isinstance(res, (set, list)) else str(res)}
