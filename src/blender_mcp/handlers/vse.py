"""
Video Sequence Editor (VSE) strips execution handler.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
from blender_mcp.handlers.base import BaseHandler


class VSEHandler(BaseHandler):
    """Executes Video Sequence Editor strip management operations."""

    EFFECT_TYPES = {
        "ADJUSTMENT", "SPEED", "TRANSFORM", "GAUSSIAN_BLUR",
        "CROSS", "GAMMA_CROSS", "SINGLE_CROSS", "WIPE",
        "ADD", "SUB", "MUL", "ALPHA_OVER", "ALPHA_UNDER", "OVER_DROP",
    }

    @classmethod
    def _get_sequence_editor(cls, create: bool = True) -> Any:
        bpy = cls.get_bpy()
        scene = bpy.context.scene
        seq = scene.sequence_editor
        if seq is None and create:
            seq = scene.sequence_editor_create()
        if seq is None:
            raise RuntimeError("Scene has no Sequence Editor and creation was not requested.")
        return seq

    @classmethod
    def _strip_info(cls, strip: Any) -> Dict[str, Any]:
        info = {
            "name": strip.name,
            "type": strip.type,
            "channel": strip.channel,
            "frame_start": strip.frame_start,
            "frame_final_start": strip.frame_final_start,
            "frame_final_end": strip.frame_final_end,
            "frame_final_duration": strip.frame_final_duration,
            "blend_alpha": getattr(strip, "blend_alpha", None),
            "mute": strip.mute,
            "lock": strip.lock,
            "select": strip.select,
        }
        return info

    @classmethod
    def manage_vse_strips(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        bpy = cls.get_bpy()
        action = params.get("action")

        if action == "list":
            return cls._list_strips()

        if action == "add":
            return cls._add_strip(params)

        if action == "remove":
            return cls._remove_strip(params)

        if action == "configure":
            return cls._configure_strip(params)

        if action == "set_channel":
            return cls._set_channel(params)

        if action == "move":
            return cls._move_strip(params)

        raise ValueError(f"Unknown VSE action: '{action}'")

    @classmethod
    def _list_strips(cls) -> Dict[str, Any]:
        bpy = cls.get_bpy()
        seq = bpy.context.scene.sequence_editor
        if seq is None:
            return {"status": "success", "strips": [], "count": 0}
        strips = [cls._strip_info(s) for s in seq.strips]
        return {"status": "success", "strips": strips, "count": len(strips)}

    @classmethod
    def _add_strip(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        bpy = cls.get_bpy()
        seq = cls._get_sequence_editor(create=True)

        strip_type = params.get("strip_type")
        name = params.get("strip_name")
        if not name:
            name = f"{strip_type or 'Strip'}"
        channel = int(params.get("channel", 1))
        frame_start = int(params.get("frame_start", bpy.context.scene.frame_start))
        frame_end = params.get("frame_end")
        filepath = params.get("filepath")

        if strip_type == "MOVIE":
            if not filepath:
                raise ValueError("'filepath' is required for MOVIE strips.")
            strip = seq.strips.new_movie(name, filepath, channel, frame_start)
        elif strip_type == "SOUND":
            if not filepath:
                raise ValueError("'filepath' is required for SOUND strips.")
            strip = seq.strips.new_sound(name, filepath, channel, frame_start)
        elif strip_type == "IMAGE":
            if not filepath:
                raise ValueError("'filepath' is required for IMAGE strips.")
            strip = seq.strips.new_image(name, filepath, channel, frame_start)
        elif strip_type == "SCENE":
            scene_name = params.get("scene_name") or params.get("filepath")
            if not scene_name:
                raise ValueError("'scene_name' (or 'filepath') is required for SCENE strips.")
            target_scene = bpy.data.scenes.get(scene_name)
            if target_scene is None:
                raise ValueError(f"Scene '{scene_name}' not found.")
            strip = seq.strips.new_scene(name, target_scene, channel, frame_start)
        elif strip_type in cls.EFFECT_TYPES:
            kwargs = {}
            seq1_name = params.get("seq1")
            seq2_name = params.get("seq2")
            if seq1_name:
                seq1 = seq.strips.get(seq1_name)
                if seq1 is None:
                    raise ValueError(f"Reference strip '{seq1_name}' not found.")
                kwargs["seq1"] = seq1
            if seq2_name:
                seq2 = seq.strips.get(seq2_name)
                if seq2 is None:
                    raise ValueError(f"Reference strip '{seq2_name}' not found.")
                kwargs["seq2"] = seq2
            end = int(frame_end) if frame_end is not None else (frame_start + 1)
            strip = seq.strips.new_effect(
                name, strip_type, channel, frame_start, frame_end=end, **kwargs
            )
        elif strip_type == "COLOR":
            color = params.get("color", [0.0, 0.0, 0.0, 1.0])
            end = int(frame_end) if frame_end is not None else (frame_start + 1)
            strip = seq.strips.new_effect(name, "COLOR", channel, frame_start, frame_end=end)
            if hasattr(strip, "color"):
                strip.color = color
        elif strip_type == "TEXT":
            end = int(frame_end) if frame_end is not None else (frame_start + 1)
            strip = seq.strips.new_effect(name, "TEXT", channel, frame_start, frame_end=end)
        else:
            raise ValueError(f"Unsupported strip type: '{strip_type}'")

        properties = params.get("properties") or {}
        cls._apply_properties(strip, properties)

        return {"status": "success", "strip": cls._strip_info(strip)}

    @classmethod
    def _remove_strip(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        bpy = cls.get_bpy()
        seq = cls._get_sequence_editor(create=False)
        name = params.get("strip_name")
        if not name:
            raise ValueError("'strip_name' is required to remove a strip.")
        strip = seq.strips.get(name)
        if strip is None:
            raise ValueError(f"Strip '{name}' not found.")
        seq.strips.remove(strip)
        return {"status": "success", "removed_strip": name}

    @classmethod
    def _configure_strip(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        bpy = cls.get_bpy()
        seq = cls._get_sequence_editor(create=False)
        name = params.get("strip_name")
        if not name:
            raise ValueError("'strip_name' is required to configure a strip.")
        strip = seq.strips.get(name)
        if strip is None:
            raise ValueError(f"Strip '{name}' not found.")

        simple_keys = {
            "channel", "frame_start", "frame_final_start", "frame_final_end",
            "blend_alpha", "mute", "lock", "select",
        }
        applied = {}
        for key, value in params.items():
            if key in simple_keys and value is not None:
                setattr(strip, key, value)
                applied[key] = value

        properties = params.get("properties") or {}
        cls._apply_properties(strip, properties)
        applied.update(properties)

        return {"status": "success", "strip": cls._strip_info(strip), "applied": applied}

    @classmethod
    def _set_channel(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        bpy = cls.get_bpy()
        seq = cls._get_sequence_editor(create=False)
        name = params.get("strip_name")
        if not name:
            raise ValueError("'strip_name' is required to set channel.")
        strip = seq.strips.get(name)
        if strip is None:
            raise ValueError(f"Strip '{name}' not found.")
        channel = int(params.get("channel", 1))
        strip.channel = channel
        return {"status": "success", "strip": cls._strip_info(strip)}

    @classmethod
    def _move_strip(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        bpy = cls.get_bpy()
        seq = cls._get_sequence_editor(create=False)
        name = params.get("strip_name")
        if not name:
            raise ValueError("'strip_name' is required to move a strip.")
        strip = seq.strips.get(name)
        if strip is None:
            raise ValueError(f"Strip '{name}' not found.")
        frame_start = params.get("frame_start")
        if frame_start is None:
            raise ValueError("'frame_start' is required to move a strip.")
        strip.frame_start = int(frame_start)
        return {"status": "success", "strip": cls._strip_info(strip)}

    @classmethod
    def _apply_properties(cls, strip: Any, properties: Dict[str, Any]) -> None:
        for key, value in (properties or {}).items():
            if hasattr(strip, key):
                try:
                    setattr(strip, key, value)
                except Exception:
                    pass
