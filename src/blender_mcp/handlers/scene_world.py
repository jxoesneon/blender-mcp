"""
Scene, World, Viewport, Camera, and Photometric Lighting execution handler.
"""

from __future__ import annotations

import math
import os
from typing import Any, Dict, List, Optional
from blender_mcp.handlers.base import BaseHandler
from blender_mcp.utils.colors import kelvin_to_rgb


class SceneWorldHandler(BaseHandler):
    """Executes scene configuration, lighting, cameras, viewports, and world shading."""

    @classmethod
    def manage_scene(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        bpy = cls.get_bpy()
        action = params.get("action", "list")

        if action == "list":
            return {
                "status": "success",
                "active_scene": bpy.context.scene.name,
                "scenes": [s.name for s in list(bpy.data.scenes)],
            }

        if action == "get_active":
            s = bpy.context.scene
            return {
                "status": "success",
                "name": s.name,
                "unit_system": s.unit_settings.system,
                "scale_length": s.unit_settings.scale_length,
                "gravity": list(s.gravity),
                "active_camera": s.camera.name if s.camera else None,
            }

        if action == "create":
            mode = params.get("create_mode", "NEW")
            name = params.get("scene_name", "Scene")
            if mode == "NEW":
                scene = bpy.data.scenes.new(name)
            elif mode == "EMPTY":
                scene = bpy.data.scenes.new(name)
            elif mode == "FULL_COPY":
                scene = bpy.context.scene.copy()
                scene.name = name
            else:
                scene = bpy.data.scenes.new(name)
            bpy.context.window.scene = scene
            return {"status": "success", "scene_name": scene.name}

        if action == "switch":
            scene = cls.get_scene(params["scene_name"])
            bpy.context.window.scene = scene
            return {"status": "success", "active_scene": scene.name}

        if action == "delete":
            scene = cls.get_scene(params["scene_name"])
            if len(bpy.data.scenes) <= 1:
                raise ValueError("Cannot delete the only scene in the blend file.")
            bpy.data.scenes.remove(scene)
            return {"status": "success", "deleted_scene": params["scene_name"]}

        if action == "configure":
            scene = cls.get_scene(params.get("scene_name"))
            if params.get("unit_system"):
                scene.unit_settings.system = params["unit_system"]
            if params.get("unit_scale_length") is not None:
                scene.unit_settings.scale_length = params["unit_scale_length"]
            if params.get("unit_length"):
                scene.unit_settings.length_unit = params["unit_length"]
            if params.get("unit_rotation"):
                scene.unit_settings.rotation_unit = params["unit_rotation"]
            if params.get("use_gravity") is not None:
                scene.use_gravity = params["use_gravity"]
            if params.get("gravity"):
                scene.gravity = params["gravity"]
            if params.get("active_camera_name"):
                cam = cls.get_object(params["active_camera_name"])
                scene.camera = cam
            return {"status": "success", "configured_scene": scene.name}

        raise ValueError(f"Unknown scene action: '{action}'")

    @classmethod
    def manage_world(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        bpy = cls.get_bpy()
        mode = params.get("mode", "GET_INFO")
        world_name = params.get("world_name")
        world = bpy.data.worlds.get(world_name) if world_name else bpy.context.scene.world

        if not world:
            world = bpy.data.worlds.new(world_name or "World")
            bpy.context.scene.world = world

        world.use_nodes = True
        tree = world.node_tree
        nodes = tree.nodes
        links = tree.links

        if mode == "GET_INFO":
            return {
                "status": "success",
                "world_name": world.name,
                "nodes": [n.name for n in nodes],
                "color": list(world.color) if hasattr(world, "color") else None,
            }

        output_node = next((n for n in nodes if n.type == "OUTPUT_WORLD"), None)
        if not output_node:
            output_node = nodes.new(type="ShaderNodeOutputWorld")
            output_node.location = (400, 0)

        if mode == "COLOR":
            nodes.clear()
            output_node = nodes.new(type="ShaderNodeOutputWorld")
            output_node.location = (400, 0)
            bg_node = nodes.new(type="ShaderNodeBackground")
            bg_node.location = (0, 0)
            if params.get("color"):
                col = params["color"]
                if len(col) == 3:
                    col = list(col) + [1.0]
                bg_node.inputs["Color"].default_value = col
            bg_node.inputs["Strength"].default_value = params.get("strength", 1.0)
            links.new(bg_node.outputs["Background"], output_node.inputs["Surface"])

        elif mode == "SKY_TEXTURE":
            nodes.clear()
            output_node = nodes.new(type="ShaderNodeOutputWorld")
            output_node.location = (400, 0)
            bg_node = nodes.new(type="ShaderNodeBackground")
            bg_node.location = (150, 0)
            bg_node.inputs["Strength"].default_value = params.get("strength", 1.0)

            sky_node = nodes.new(type="ShaderNodeTexSky")
            sky_node.location = (-150, 0)
            sky_node.sky_type = params.get("sky_type", "NISHITA")
            if params.get("sky_sun_intensity") is not None and hasattr(sky_node, "sun_intensity"):
                sky_node.sun_intensity = params["sky_sun_intensity"]
            if params.get("sky_sun_elevation") is not None and hasattr(sky_node, "sun_elevation"):
                sky_node.sun_elevation = math.radians(params["sky_sun_elevation"])
            if params.get("sky_sun_rotation") is not None and hasattr(sky_node, "sun_rotation"):
                sky_node.sun_rotation = math.radians(params["sky_sun_rotation"])

            links.new(sky_node.outputs["Color"], bg_node.inputs["Color"])
            links.new(bg_node.outputs["Background"], output_node.inputs["Surface"])

        elif mode == "HDRI":
            filepath = params.get("hdri_filepath")
            if not filepath or not os.path.exists(filepath):
                pass
            nodes.clear()
            output_node = nodes.new(type="ShaderNodeOutputWorld")
            output_node.location = (600, 0)
            bg_node = nodes.new(type="ShaderNodeBackground")
            bg_node.location = (350, 0)
            bg_node.inputs["Strength"].default_value = params.get("strength", 1.0)

            env_node = nodes.new(type="ShaderNodeTexEnvironment")
            env_node.location = (50, 0)
            if filepath and os.path.exists(filepath):
                env_node.image = bpy.data.images.load(filepath, check_existing=True)

            mapping_node = nodes.new(type="ShaderNodeMapping")
            mapping_node.location = (-200, 0)
            mapping_node.vector_type = "POINT"
            mapping_node.inputs["Rotation"].default_value[2] = math.radians(params.get("hdri_rotation_z", 0.0))

            coord_node = nodes.new(type="ShaderNodeTexCoord")
            coord_node.location = (-400, 0)

            links.new(coord_node.outputs["Generated"], mapping_node.inputs["Vector"])
            links.new(mapping_node.outputs["Vector"], env_node.inputs["Vector"])
            links.new(env_node.outputs["Color"], bg_node.inputs["Color"])
            links.new(bg_node.outputs["Background"], output_node.inputs["Surface"])

        if params.get("volume_type") and params["volume_type"] != "NONE":
            v_type = params["volume_type"]
            v_node = None
            if v_type == "SCATTER":
                v_node = nodes.new(type="ShaderNodeVolumeScatter")
            elif v_type == "ABSORPTION":
                v_node = nodes.new(type="ShaderNodeVolumeAbsorption")
            elif v_type == "PRINCIPLED":
                v_node = nodes.new(type="ShaderNodeVolumePrincipled")

            if v_node:
                v_node.location = (350, -200)
                if "Density" in v_node.inputs:
                    v_node.inputs["Density"].default_value = params.get("volume_density", 0.01)
                if "Color" in v_node.inputs and params.get("volume_color"):
                    col = params["volume_color"]
                    if len(col) == 3:
                        col = list(col) + [1.0]
                    v_node.inputs["Color"].default_value = col
                if "Anisotropy" in v_node.inputs:
                    v_node.inputs["Anisotropy"].default_value = params.get("volume_anisotropy", 0.0)
                links.new(v_node.outputs["Volume"], output_node.inputs["Volume"])

        return {"status": "success", "mode": mode, "world": world.name}

    @classmethod
    def manage_viewport(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        bpy = cls.get_bpy()
        action = params["action"]

        if action == "switch_workspace":
            ws_name = params["workspace_name"]
            ws = bpy.data.workspaces.get(ws_name)
            if not ws:
                raise ValueError(f"Workspace '{ws_name}' not found.")
            bpy.context.window.workspace = ws
            return {"status": "success", "workspace": ws.name}

        space_3d = None
        for area in bpy.context.screen.areas:
            if area.type == "VIEW_3D":
                space_3d = area.spaces.active
                break

        if not space_3d:
            return {"status": "success", "warning": "No active VIEW_3D space found in current context."}

        if action == "set_shading":
            shading = space_3d.shading
            if params.get("shading_type"):
                shading.type = params["shading_type"]
            opts = params.get("shading_options", {})
            for k, v in opts.items():
                if hasattr(shading, k):
                    setattr(shading, k, v)
            return {"status": "success", "shading_type": shading.type}

        if action == "set_overlays":
            overlay = space_3d.overlay
            if params.get("show_overlays") is not None:
                overlay.show_overlays = params["show_overlays"]
            toggles = params.get("overlay_toggles", {})
            for k, v in toggles.items():
                if hasattr(overlay, k):
                    setattr(overlay, k, v)
            return {"status": "success", "show_overlays": overlay.show_overlays}

        if action == "set_clipping_lens":
            if params.get("clip_start") is not None:
                space_3d.clip_start = params["clip_start"]
            if params.get("clip_end") is not None:
                space_3d.clip_end = params["clip_end"]
            if params.get("lens") is not None:
                space_3d.lens = params["lens"]
            return {"status": "success", "clip_start": space_3d.clip_start, "clip_end": space_3d.clip_end}

        if action == "set_cursor":
            cursor = bpy.context.scene.cursor
            if params.get("cursor_location"):
                cursor.location = params["cursor_location"]
            if params.get("cursor_rotation_euler"):
                cursor.rotation_euler = params["cursor_rotation_euler"]
            return {"status": "success", "location": list(cursor.location)}

        if action == "lock_view":
            if params.get("lock_object_name"):
                obj = cls.get_object(params["lock_object_name"])
                space_3d.lock_object = obj
            if params.get("lock_cursor") is not None:
                space_3d.lock_cursor = params["lock_cursor"]
            return {"status": "success"}

        if action == "get_state":
            return {
                "status": "success",
                "shading_type": space_3d.shading.type,
                "show_overlays": space_3d.overlay.show_overlays,
                "clip_start": space_3d.clip_start,
                "clip_end": space_3d.clip_end,
                "lens": space_3d.lens,
            }

        raise ValueError(f"Unknown viewport action: '{action}'")

    @classmethod
    def manage_camera(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        bpy = cls.get_bpy()
        action = params["action"]
        cam_name = params.get("camera_name", "Camera")

        if action == "create":
            cam_data = bpy.data.cameras.new(cam_name)
            cam_obj = bpy.data.objects.new(cam_name, cam_data)
            bpy.context.scene.collection.objects.link(cam_obj)
            cls._apply_camera_properties(cam_data, params)
            return {"status": "success", "camera_name": cam_obj.name}

        cam_obj = cls.get_object(cam_name)
        if cam_obj.type != "CAMERA":
            raise TypeError(f"Object '{cam_name}' is not a Camera.")

        cam_data = cam_obj.data

        if action == "update":
            cls._apply_camera_properties(cam_data, params)
            return {"status": "success", "camera_name": cam_obj.name}

        if action == "set_active":
            bpy.context.scene.camera = cam_obj
            return {"status": "success", "active_camera": cam_obj.name}

        if action == "get_properties":
            dof = cam_data.dof
            return {
                "status": "success",
                "camera_name": cam_obj.name,
                "type": cam_data.type,
                "lens": cam_data.lens,
                "ortho_scale": cam_data.ortho_scale,
                "sensor_width": cam_data.sensor_width,
                "sensor_height": cam_data.sensor_height,
                "clip_start": cam_data.clip_start,
                "clip_end": cam_data.clip_end,
                "dof_enabled": dof.use_dof,
                "focus_distance": dof.focus_distance,
            }

        if action == "delete":
            bpy.data.objects.remove(cam_obj, do_unlink=True)
            return {"status": "success", "deleted_camera": cam_name}

        raise ValueError(f"Unknown camera action: '{action}'")

    @classmethod
    def _apply_camera_properties(cls, cam_data: Any, params: Dict[str, Any]):
        if params.get("type"):
            cam_data.type = params["type"]
        if params.get("focal_length") is not None:
            cam_data.lens = params["focal_length"]
        if params.get("ortho_scale") is not None:
            cam_data.ortho_scale = params["ortho_scale"]
        if params.get("sensor_fit"):
            cam_data.sensor_fit = params["sensor_fit"]
        if params.get("sensor_width") is not None:
            cam_data.sensor_width = params["sensor_width"]
        if params.get("sensor_height") is not None:
            cam_data.sensor_height = params["sensor_height"]
        if params.get("clip_start") is not None:
            cam_data.clip_start = params["clip_start"]
        if params.get("clip_end") is not None:
            cam_data.clip_end = params["clip_end"]
        if params.get("shift_x") is not None:
            cam_data.shift_x = params["shift_x"]
        if params.get("shift_y") is not None:
            cam_data.shift_y = params["shift_y"]

        dof_cfg = params.get("dof", {})
        if dof_cfg:
            dof = cam_data.dof
            if "enabled" in dof_cfg:
                dof.use_dof = dof_cfg["enabled"]
            if "focus_object" in dof_cfg:
                dof.focus_object = cls.get_object(dof_cfg["focus_object"]) if dof_cfg["focus_object"] else None
            if "focus_distance" in dof_cfg:
                dof.focus_distance = dof_cfg["focus_distance"]
            if "fstop" in dof_cfg:
                dof.aperture_fstop = dof_cfg["fstop"]
            if "blades" in dof_cfg:
                dof.aperture_blades = dof_cfg["blades"]
            if "rotation" in dof_cfg:
                dof.aperture_rotation = math.radians(dof_cfg["rotation"])
            if "ratio" in dof_cfg:
                dof.aperture_ratio = dof_cfg["ratio"]

        guides = params.get("composition_guides", {})
        for k, v in guides.items():
            if hasattr(cam_data, k):
                setattr(cam_data, k, v)

    @classmethod
    def manage_light(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        bpy = cls.get_bpy()
        action = params["action"]
        light_name = params.get("light_name", "Light")

        if action == "create":
            light_type = params.get("type", "POINT")
            light_data = bpy.data.lights.new(light_name, type=light_type)
            light_obj = bpy.data.objects.new(light_name, light_data)
            bpy.context.scene.collection.objects.link(light_obj)
            cls._apply_light_properties(light_data, params)
            return {"status": "success", "light_name": light_obj.name, "type": light_type}

        light_obj = cls.get_object(light_name)
        if light_obj.type != "LIGHT":
            raise TypeError(f"Object '{light_name}' is not a Light.")

        light_data = light_obj.data

        if action == "update":
            if params.get("type"):
                light_data.type = params["type"]
            cls._apply_light_properties(light_data, params)
            return {"status": "success", "light_name": light_obj.name}

        if action == "get_properties":
            return {
                "status": "success",
                "light_name": light_obj.name,
                "type": light_data.type,
                "energy": light_data.energy,
                "color": list(light_data.color),
                "shadow_soft_size": getattr(light_data, "shadow_soft_size", None),
            }

        if action == "set_linking":
            ll_cfg = params.get("light_linking", {})
            rec_col_name = ll_cfg.get("receiver_collection_name")
            if hasattr(light_data, "light_linking") and rec_col_name:
                col = bpy.data.collections.get(rec_col_name)
                if col:
                    light_data.light_linking.receiver_collection = col
            return {"status": "success", "light_name": light_obj.name}

        if action == "delete":
            bpy.data.objects.remove(light_obj, do_unlink=True)
            return {"status": "success", "deleted_light": light_name}

        raise ValueError(f"Unknown light action: '{action}'")

    @classmethod
    def _apply_light_properties(cls, light_data: Any, params: Dict[str, Any]):
        if params.get("energy") is not None:
            light_data.energy = params["energy"]

        if params.get("color_type") == "KELVIN" and params.get("color_kelvin") is not None:
            r, g, b = kelvin_to_rgb(params["color_kelvin"])
            light_data.color = (r, g, b)
        elif params.get("color_rgb"):
            rgb = params["color_rgb"]
            light_data.color = (rgb[0], rgb[1], rgb[2])

        if params.get("radius") is not None and hasattr(light_data, "shadow_soft_size"):
            light_data.shadow_soft_size = params["radius"]

        if params.get("area_shape") and hasattr(light_data, "shape"):
            light_data.shape = params["area_shape"]
        if params.get("area_size_x") is not None and hasattr(light_data, "size"):
            light_data.size = params["area_size_x"]
        if params.get("area_size_y") is not None and hasattr(light_data, "size_y"):
            light_data.size_y = params["area_size_y"]

        if params.get("spot_size") is not None and hasattr(light_data, "spot_size"):
            light_data.spot_size = math.radians(params["spot_size"])
        if params.get("spot_blend") is not None and hasattr(light_data, "spot_blend"):
            light_data.spot_blend = params["spot_blend"]
        if params.get("spot_show_cone") is not None and hasattr(light_data, "show_cone"):
            light_data.show_cone = params["spot_show_cone"]

        if params.get("use_shadow") is not None and hasattr(light_data, "use_shadow"):
            light_data.use_shadow = params["use_shadow"]
