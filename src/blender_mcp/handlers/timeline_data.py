"""
Timeline markers, cache files (Alembic/USD), and pose library execution handler.
"""

from __future__ import annotations

from typing import Any, Dict
from blender_mcp.handlers.base import BaseHandler


class TimelineDataHandler(BaseHandler):
    """Executes timeline marker, cache file, and pose library operations."""

    @classmethod
    def manage_markers(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        bpy = cls.get_bpy()
        scene = bpy.context.scene
        action = params.get("action", "list")

        if action == "list":
            markers = []
            for m in scene.timeline_markers:
                markers.append({
                    "name": m.name,
                    "frame": m.frame,
                    "camera": m.camera.name if m.camera else None,
                })
            return {"status": "success", "markers": markers}

        if action == "add":
            name = params.get("marker_name")
            if not name:
                raise ValueError("marker_name is required for add action.")
            frame = int(params.get("frame", scene.frame_current))
            marker = scene.timeline_markers.new(name=name, frame=frame)
            cam_name = params.get("camera_name")
            if cam_name:
                cam_obj = cls.get_object(cam_name)
                marker.camera = cam_obj
            return {"status": "success", "marker": marker.name, "frame": marker.frame}

        if action == "remove":
            name = params.get("marker_name")
            if not name:
                raise ValueError("marker_name is required for remove action.")
            marker = scene.timeline_markers.get(name)
            if not marker:
                raise ValueError(f"Marker '{name}' not found.")
            scene.timeline_markers.remove(marker)
            return {"status": "success", "removed": name}

        if action == "set_name":
            name = params.get("marker_name")
            new_name = params.get("new_name")
            if not name or not new_name:
                raise ValueError("marker_name and new_name are required for set_name action.")
            marker = scene.timeline_markers.get(name)
            if not marker:
                raise ValueError(f"Marker '{name}' not found.")
            marker.name = new_name
            return {"status": "success", "marker": marker.name}

        if action == "set_frame":
            name = params.get("marker_name")
            frame = params.get("frame")
            if not name or frame is None:
                raise ValueError("marker_name and frame are required for set_frame action.")
            marker = scene.timeline_markers.get(name)
            if not marker:
                raise ValueError(f"Marker '{name}' not found.")
            marker.frame = int(frame)
            return {"status": "success", "marker": marker.name, "frame": marker.frame}

        if action == "set_camera":
            name = params.get("marker_name")
            cam_name = params.get("camera_name")
            if not name or not cam_name:
                raise ValueError("marker_name and camera_name are required for set_camera action.")
            marker = scene.timeline_markers.get(name)
            if not marker:
                raise ValueError(f"Marker '{name}' not found.")
            cam_obj = cls.get_object(cam_name)
            marker.camera = cam_obj
            return {"status": "success", "marker": marker.name, "camera": cam_obj.name}

        raise ValueError(f"Unknown marker action: '{action}'")

    @classmethod
    def manage_cache_files(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        bpy = cls.get_bpy()
        action = params.get("action", "list")

        if action == "list":
            caches = []
            for cf in bpy.data.cache_files:
                caches.append({
                    "name": cf.name,
                    "filepath": cf.filepath,
                    "is_read_only": getattr(cf, "is_read_only", False),
                })
            return {"status": "success", "cache_files": caches}

        if action == "load":
            filepath = params.get("filepath")
            if not filepath:
                raise ValueError("filepath is required for load action.")
            cache_name = params.get("cache_name", "CacheFile")
            cache_type = params.get("cache_type", "ALEMBIC")
            cf = bpy.data.cache_files.new(name=cache_name)
            cf.filepath = filepath
            if hasattr(cf, "add_layer"):
                pass
            return {
                "status": "success",
                "cache_file": cf.name,
                "filepath": cf.filepath,
                "cache_type": cache_type,
            }

        if action == "reload":
            cache_name = params.get("cache_name")
            if not cache_name:
                raise ValueError("cache_name is required for reload action.")
            cf = bpy.data.cache_files.get(cache_name)
            if not cf:
                raise ValueError(f"Cache file '{cache_name}' not found.")
            if hasattr(cf, "reload"):
                cf.reload()
            return {"status": "success", "cache_file": cf.name}

        if action == "remove":
            cache_name = params.get("cache_name")
            if not cache_name:
                raise ValueError("cache_name is required for remove action.")
            cf = bpy.data.cache_files.get(cache_name)
            if not cf:
                raise ValueError(f"Cache file '{cache_name}' not found.")
            bpy.data.cache_files.remove(cf)
            return {"status": "success", "removed": cache_name}

        raise ValueError(f"Unknown cache file action: '{action}'")

    @classmethod
    def manage_pose_library(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        bpy = cls.get_bpy()
        action = params.get("action", "list_poses")

        if action == "create":
            armature_name = params.get("armature_name")
            if not armature_name:
                raise ValueError("armature_name is required for create action.")
            arm_obj = cls.get_object(armature_name)
            if arm_obj.type != "ARMATURE":
                raise TypeError(f"Object '{armature_name}' is not an Armature.")
            action_name = params.get("action_name", f"{armature_name}_PoseLibrary")
            pose_action = bpy.data.actions.new(name=action_name)
            if hasattr(pose_action, "use_asset"):
                pose_action.use_asset = True
            if not arm_obj.animation_data:
                arm_obj.animation_data_create()
            arm_obj.animation_data.action = pose_action
            return {"status": "success", "action": pose_action.name, "armature": arm_obj.name}

        armature_name = params.get("armature_name")
        if not armature_name:
            raise ValueError("armature_name is required for pose library actions.")
        arm_obj = cls.get_object(armature_name)
        if arm_obj.type != "ARMATURE":
            raise TypeError(f"Object '{armature_name}' is not an Armature.")

        pose_action = None
        if hasattr(arm_obj, "pose_library") and arm_obj.pose_library:
            pose_action = arm_obj.pose_library
        elif arm_obj.animation_data and arm_obj.animation_data.action:
            pose_action = arm_obj.animation_data.action
        if not pose_action:
            raise ValueError(f"No pose library action found on armature '{armature_name}'.")

        if action == "add_pose":
            pose_name = params.get("pose_name", "Pose")
            with cls.active_mode(arm_obj, "POSE"):
                if hasattr(bpy.ops.poselib, "pose_add"):
                    try:
                        bpy.ops.poselib.pose_add(pose_index=-1)
                    except Exception:
                        pass
            return {"status": "success", "pose": pose_name, "action": pose_action.name}

        if action == "list_poses":
            poses = []
            if hasattr(pose_action, "pose_markers"):
                for pm in pose_action.pose_markers:
                    poses.append({
                        "name": pm.name,
                        "frame": pm.frame,
                    })
            return {"status": "success", "poses": poses, "action": pose_action.name}

        if action == "apply_pose":
            pose_name = params.get("pose_name")
            if not pose_name:
                raise ValueError("pose_name is required for apply_pose action.")
            pm = None
            if hasattr(pose_action, "pose_markers"):
                pm = pose_action.pose_markers.get(pose_name)
            if not pm:
                raise ValueError(f"Pose '{pose_name}' not found in action '{pose_action.name}'.")
            with cls.active_mode(arm_obj, "POSE"):
                if hasattr(bpy.ops.poselib, "apply_pose"):
                    try:
                        bpy.ops.poselib.apply_pose(pose_index=pm.frame)
                    except Exception:
                        scene = bpy.context.scene
                        prev_frame = scene.frame_current
                        scene.frame_set(pm.frame)
                        scene.frame_set(prev_frame)
            return {"status": "success", "pose": pose_name, "frame": pm.frame}

        if action == "remove_pose":
            pose_name = params.get("pose_name")
            if not pose_name:
                raise ValueError("pose_name is required for remove_pose action.")
            pm = None
            if hasattr(pose_action, "pose_markers"):
                pm = pose_action.pose_markers.get(pose_name)
            if not pm:
                raise ValueError(f"Pose '{pose_name}' not found in action '{pose_action.name}'.")
            pose_action.pose_markers.remove(pm)
            return {"status": "success", "removed": pose_name}

        raise ValueError(f"Unknown pose library action: '{action}'")
