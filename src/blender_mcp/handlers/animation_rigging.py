"""
Animation, Timeline, F-Curves, Drivers, NLA, Armatures, and Rigging execution handler.
"""

from __future__ import annotations

from typing import Any, Dict
from blender_mcp.handlers.base import BaseHandler


class AnimationRiggingHandler(BaseHandler):
    """Executes keyframing, timeline range, graph editing, drivers, NLA strips, and armature posing."""

    @classmethod
    def _resolve_target(cls, target_type: str, target_name: str) -> Any:
        bpy = cls.get_bpy()
        if target_type == "OBJECT":
            return cls.get_object(target_name)
        if target_type == "MATERIAL":
            return cls.get_material(target_name)
        if target_type == "WORLD":
            return bpy.data.worlds.get(target_name) or bpy.context.scene.world
        return cls.get_object(target_name)

    @classmethod
    def timeline_control(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        bpy = cls.get_bpy()
        scene = bpy.context.scene
        if params.get("frame_start") is not None:
            scene.frame_start = int(params["frame_start"])
        if params.get("frame_end") is not None:
            scene.frame_end = int(params["frame_end"])
        if params.get("current_frame") is not None:
            scene.frame_set(int(params["current_frame"]))
        if params.get("fps") is not None and hasattr(scene, "render"):
            scene.render.fps = int(params["fps"])
        if params.get("fps_base") is not None and hasattr(scene, "render"):
            scene.render.fps_base = float(params["fps_base"])
        return {
            "status": "success",
            "frame_current": scene.frame_current,
            "frame_start": scene.frame_start,
            "frame_end": scene.frame_end,
        }

    @classmethod
    def insert_keyframe(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        bpy = cls.get_bpy()
        target = cls._resolve_target(params.get("target_type", "OBJECT"), params["target_name"])
        data_path = params["data_path"]
        array_index = params.get("array_index", -1)
        frame = params.get("frame")
        if frame is None:
            frame = bpy.context.scene.frame_current

        if params.get("value") is not None:
            if array_index >= 0:
                getattr(target, data_path)[array_index] = params["value"]
            else:
                setattr(target, data_path, params["value"])

        kwargs: Dict[str, Any] = {"data_path": data_path, "frame": frame}
        if array_index >= 0:
            kwargs["index"] = array_index
        if params.get("group"):
            kwargs["group"] = params["group"]

        success = target.keyframe_insert(**kwargs) if hasattr(target, "keyframe_insert") else True
        return {"status": "success" if success else "failed", "data_path": data_path, "frame": frame}

    @classmethod
    def delete_keyframe(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        bpy = cls.get_bpy()
        target = cls._resolve_target(params.get("target_type", "OBJECT"), params["target_name"])
        data_path = params["data_path"]
        array_index = params.get("array_index", -1)
        frame = float(params.get("frame", bpy.context.scene.frame_current))

        kwargs: Dict[str, Any] = {"data_path": data_path, "frame": frame}
        if array_index >= 0:
            kwargs["index"] = array_index

        success = target.keyframe_delete(**kwargs) if hasattr(target, "keyframe_delete") else True
        return {"status": "success" if success else "failed", "frame": frame}

    @classmethod
    def list_fcurves(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        target = cls._resolve_target(params.get("target_type", "OBJECT"), params["target_name"])
        if not getattr(target, "animation_data", None) or not target.animation_data.action:
            return {"status": "success", "fcurves": []}

        action = target.animation_data.action
        curves = []

        # Blender 5.x layered action API: fcurves live inside channelbags
        if not hasattr(action, "fcurves") and hasattr(action, "layers"):
            for layer in action.layers:
                for strip in layer.strips:
                    for cb in strip.channelbags:
                        for fc in cb.fcurves:
                            curves.append({
                                "data_path": fc.data_path,
                                "array_index": fc.array_index,
                                "keyframe_count": len(fc.keyframe_points),
                            })
            return {"status": "success", "fcurves": curves}

        # Legacy Blender 4.x API
        for fc in action.fcurves:
            curves.append({
                "data_path": fc.data_path,
                "array_index": fc.array_index,
                "keyframe_count": len(fc.keyframe_points),
            })
        return {"status": "success", "fcurves": curves}

    @classmethod
    def modify_keyframe(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        target = cls._resolve_target(params.get("target_type", "OBJECT"), params["target_name"])
        if not getattr(target, "animation_data", None) or not target.animation_data.action:
            raise ValueError("Target object has no action.")

        data_path = params["data_path"]
        idx = params.get("array_index", 0)
        frame = float(params["frame"])
        action = target.animation_data.action

        # Blender 5.x layered action API: fcurves live inside channelbags
        fcurve = None
        if not hasattr(action, "fcurves") and hasattr(action, "layers"):
            for layer in action.layers:
                for strip in layer.strips:
                    for cb in strip.channelbags:
                        for fc in cb.fcurves:
                            if fc.data_path == data_path and fc.array_index == idx:
                                fcurve = fc
                                break
        else:
            # Legacy Blender 4.x API
            fcurve = next((fc for fc in action.fcurves if fc.data_path == data_path and fc.array_index == idx), None)

        if not fcurve:
            raise ValueError(f"F-Curve '{data_path}[{idx}]' not found.")

        kp = next((p for p in fcurve.keyframe_points if abs(p.co[0] - frame) < 0.001), None)
        if not kp:
            raise ValueError(f"Keyframe at frame {frame} not found.")

        if params.get("new_frame") is not None:
            kp.co[0] = float(params["new_frame"])
        if params.get("new_value") is not None:
            kp.co[1] = float(params["new_value"])
        if params.get("interpolation"):
            kp.interpolation = params["interpolation"]

        if hasattr(fcurve, "update"):
            fcurve.update()

        return {"status": "success", "frame": kp.co[0], "value": kp.co[1]}

    @classmethod
    def manage_driver(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        bpy = cls.get_bpy()
        target = cls._resolve_target(params.get("target_type", "OBJECT"), params["target_name"])
        action = params.get("action", "add_driver")
        data_path = params["data_path"]
        array_index = params.get("array_index", -1)

        if action == "remove_driver":
            if array_index >= 0 and hasattr(target, "driver_remove"):
                target.driver_remove(data_path, array_index)
            elif hasattr(target, "driver_remove"):
                target.driver_remove(data_path)
            return {"status": "success", "removed_driver": data_path}

        if action == "add_driver":
            if hasattr(target, "driver_add"):
                fc = target.driver_add(data_path, array_index) if array_index >= 0 else target.driver_add(data_path)
                fcurves = fc if isinstance(fc, list) else [fc]
                if params.get("driver_expression"):
                    for fcurve in fcurves:
                        fcurve.driver.expression = params["driver_expression"]
            return {"status": "success", "driver": data_path}

        fcurve = cls._get_driver_fcurve(target, data_path, array_index)
        if not fcurve:
            raise ValueError(f"No driver found for '{data_path}[{array_index}]'.")
        driver = fcurve.driver

        if action == "add_variable":
            var_name = params.get("variable_name")
            if not var_name:
                raise ValueError("variable_name is required for add_variable.")
            var_type = params.get("variable_type", "SINGLE_PROP")
            var = driver.variables.new()
            var.name = var_name
            var.type = var_type
            target_path = params.get("target_path")
            target_id_name = params.get("target_id")
            if var_type == "SINGLE_PROP" and target_path:
                tgt = var.targets[0]
                tgt.data_path = target_path
                if target_id_name:
                    tgt.id = cls._resolve_target_id(target_id_name)
            return {"status": "success", "variable": var.name, "driver": data_path}

        if action == "remove_variable":
            var_name = params.get("variable_name")
            if not var_name:
                raise ValueError("variable_name is required for remove_variable.")
            var = driver.variables.get(var_name)
            if not var:
                raise ValueError(f"Driver variable '{var_name}' not found.")
            driver.variables.remove(var)
            return {"status": "success", "removed_variable": var_name, "driver": data_path}

        if action == "set_expression":
            expr = params.get("driver_expression")
            if expr is None:
                raise ValueError("driver_expression is required for set_expression.")
            driver.expression = expr
            return {"status": "success", "expression": driver.expression, "driver": data_path}

        if action == "get_info":
            variables = []
            for var in driver.variables:
                var_info = {"name": var.name, "type": var.type}
                if var.type == "SINGLE_PROP" and var.targets:
                    tgt = var.targets[0]
                    var_info["data_path"] = getattr(tgt, "data_path", "")
                    var_info["target_id"] = getattr(getattr(tgt, "id", None), "name", None)
                variables.append(var_info)
            return {
                "status": "success",
                "driver": data_path,
                "expression": driver.expression,
                "type": driver.type,
                "variables": variables,
            }

        raise ValueError(f"Unknown driver action: '{action}'")

    @classmethod
    def _get_driver_fcurve(cls, target: Any, data_path: str, array_index: int) -> Any:
        anim_data = getattr(target, "animation_data", None)
        if not anim_data or not anim_data.drivers:
            return None
        for fc in anim_data.drivers:
            if fc.data_path == data_path and (array_index < 0 or fc.array_index == array_index):
                return fc
        return None

    @classmethod
    def _resolve_target_id(cls, name: str) -> Any:
        bpy = cls.get_bpy()
        for collection in (bpy.data.objects, bpy.data.materials, bpy.data.worlds, bpy.data.node_groups, bpy.data.scenes):
            item = collection.get(name)
            if item:
                return item
        return None

    @classmethod
    def manage_nla(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        bpy = cls.get_bpy()
        obj = cls.get_object(params["target_name"])
        action = params.get("action", "push_nla")

        if not obj.animation_data:
            obj.animation_data_create()

        if action == "push_nla":
            act = obj.animation_data.action
            if not act:
                raise ValueError("No active action to push down.")
            track = obj.animation_data.nla_tracks.new()
            track.name = params.get("track_name") or f"NlaTrack_{act.name}"
            strip = track.strips.new(name=act.name, start=int(act.frame_range[0]), action=act)
            obj.animation_data.action = None
            return {"status": "success", "track": track.name, "strip": strip.name}

        if action == "configure_nla":
            track = obj.animation_data.nla_tracks.get(params.get("track_name"))
            if not track:
                raise ValueError(f"NLA track '{params.get('track_name')}' not found.")
            strip = track.strips.get(params.get("strip_name"))
            if not strip:
                raise ValueError(f"NLA strip '{params.get('strip_name')}' not found.")
            props = params.get("nla_properties", {})
            for k, v in props.items():
                if hasattr(strip, k):
                    setattr(strip, k, v)
            return {"status": "success", "strip": strip.name}

        raise ValueError(f"Unknown NLA action: '{action}'")

    @classmethod
    def manage_armature(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        bpy = cls.get_bpy()
        action = params.get("action", "create_armature")
        arm_name = params["armature_name"]

        if action == "create_armature":
            arm_data = bpy.data.armatures.new(arm_name)
            arm_obj = bpy.data.objects.new(arm_name, arm_data)
            bpy.context.scene.collection.objects.link(arm_obj)

            bones = params.get("bones", [])
            if bones:
                with cls.active_mode(arm_obj, "EDIT"):
                    for b_spec in bones:
                        b = arm_data.edit_bones.new(b_spec["bone_name"])
                        b.head = b_spec.get("head", [0, 0, 0])
                        b.tail = b_spec.get("tail", [0, 0, 1])
                    for b_spec in bones:
                        if b_spec.get("parent_name"):
                            child = arm_data.edit_bones.get(b_spec["bone_name"])
                            parent = arm_data.edit_bones.get(b_spec["parent_name"])
                            if child and parent:
                                child.parent = parent

            return {"status": "success", "armature_name": arm_obj.name, "bones": len(bones)}

        arm_obj = cls.get_object(arm_name)
        if arm_obj.type != "ARMATURE":
            raise TypeError(f"Object '{arm_name}' is not an Armature.")

        if action == "pose_bone":
            bone_name = params["bone_name"]
            pbone = arm_obj.pose.bones.get(bone_name) if hasattr(arm_obj, "pose") and arm_obj.pose else None
            if not pbone:
                raise ValueError(f"Pose bone '{bone_name}' not found.")
            transforms = params.get("bone_transforms", {})
            if "location" in transforms:
                pbone.location = transforms["location"]
            if "rotation_euler" in transforms:
                pbone.rotation_euler = transforms["rotation_euler"]
            if "scale" in transforms:
                pbone.scale = transforms["scale"]
            return {"status": "success", "bone": bone_name}

        if action == "add_constraint":
            bone_name = params["bone_name"]
            pbone = arm_obj.pose.bones.get(bone_name) if hasattr(arm_obj, "pose") and arm_obj.pose else None
            if not pbone:
                raise ValueError(f"Pose bone '{bone_name}' not found.")
            c_type = params.get("constraint_type", "IK")
            c = pbone.constraints.new(type=c_type)
            cfg = params.get("constraint_config", {})
            for k, v in cfg.items():
                if k == "target" and isinstance(v, str):
                    c.target = cls.get_object(v)
                elif hasattr(c, k):
                    setattr(c, k, v)
            return {"status": "success", "bone": bone_name, "constraint": c.name}

        return {"status": "success", "armature": arm_obj.name}
