"""
Rendering, Compositor, Color Management, and Viewport Capture execution handler.
"""

from __future__ import annotations

import base64
import os
import time
from typing import Any, Dict
from blender_mcp.handlers.base import BaseHandler


class RenderingHandler(BaseHandler):
    """Executes render engine configuration, render passes, compositor graphs, and captures."""

    @classmethod
    def configure_render_engine(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        bpy = cls.get_bpy()
        scene = bpy.context.scene
        engine = params.get("engine", "CYCLES")
        scene.render.engine = engine

        if engine == "CYCLES" and hasattr(scene, "cycles"):
            cycles = scene.cycles
            if "device_type" in params:
                cycles.device = params["device_type"]
            if "render_samples" in params:
                cycles.samples = params["render_samples"]
            if "viewport_samples" in params:
                cycles.preview_samples = params["viewport_samples"]
            if "use_noise_threshold" in params:
                cycles.use_adaptive_sampling = params["use_noise_threshold"]
            if "noise_threshold" in params:
                cycles.adaptive_threshold = params["noise_threshold"]

            bounces = params.get("bounces", {})
            for k, v in bounces.items():
                if hasattr(cycles, k):
                    setattr(cycles, k, v)

        return {"status": "success", "engine": scene.render.engine}

    @classmethod
    def configure_output_and_passes(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        bpy = cls.get_bpy()
        scene = bpy.context.scene
        rd = scene.render

        if "resolution_x" in params:
            rd.resolution_x = params["resolution_x"]
        if "resolution_y" in params:
            rd.resolution_y = params["resolution_y"]
        if "resolution_percentage" in params:
            rd.resolution_percentage = params["resolution_percentage"]
        if "fps" in params:
            rd.fps = params["fps"]
        if "fps_base" in params:
            rd.fps_base = params["fps_base"]
        if "output_filepath" in params:
            rd.filepath = params["output_filepath"]
        if "file_format" in params and hasattr(rd, "image_settings"):
            rd.image_settings.file_format = params["file_format"]
        if "color_mode" in params and hasattr(rd, "image_settings"):
            rd.image_settings.color_mode = params["color_mode"]

        # View Layer Passes
        view_layer = getattr(bpy.context, "view_layer", None)
        passes = params.get("passes", {})
        if view_layer and passes:
            pass_map = {
                "z": "use_pass_z",
                "normal": "use_pass_normal",
                "mist": "use_pass_mist",
                "ambient_occlusion": "use_pass_ambient_occlusion",
                "shadow": "use_pass_shadow",
            }
            for k, v in passes.items():
                attr = pass_map.get(k.lower())
                if attr and hasattr(view_layer, attr):
                    setattr(view_layer, attr, bool(v))

        return {
            "status": "success",
            "resolution": [rd.resolution_x, rd.resolution_y],
            "filepath": rd.filepath,
        }

    @classmethod
    def configure_color_management(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        bpy = cls.get_bpy()
        scene = bpy.context.scene
        ds = getattr(scene, "display_settings", None)
        vs = getattr(scene, "view_settings", None)

        if ds and "display_device" in params:
            ds.display_device = params["display_device"]
        if vs:
            if "view_transform" in params:
                vs.view_transform = params["view_transform"]
            if "look" in params:
                vs.look = params["look"]
            if "exposure" in params:
                vs.exposure = float(params["exposure"])
            if "gamma" in params:
                vs.gamma = float(params["gamma"])

        return {
            "status": "success",
            "view_transform": getattr(vs, "view_transform", None),
            "look": getattr(vs, "look", None),
        }

    @classmethod
    def manage_compositor_tree(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        bpy = cls.get_bpy()
        scene = bpy.context.scene
        scene.use_nodes = True
        tree = scene.node_tree
        if not tree:
            raise ValueError("Scene node tree not accessible.")

        action = params.get("action", "inspect")

        if action == "inspect":
            nodes = [{"name": n.name, "type": n.type} for n in tree.nodes]
            links = [{"from": l.from_node.name, "to": l.to_node.name} for l in tree.links]
            return {"status": "success", "nodes": nodes, "links": links}

        if action == "clear":
            tree.nodes.clear()
            return {"status": "success", "cleared": True}

        if action == "add_node":
            node_type = params.get("node_type", "CompositorNodeComposite")
            node = tree.nodes.new(type=node_type)
            if params.get("node_name"):
                node.name = params["node_name"]
            if params.get("location"):
                node.location = params["location"]
            return {"status": "success", "node_name": node.name, "type": node_type}

        if action == "remove_node":
            node = tree.nodes.get(params.get("node_name"))
            if node:
                tree.nodes.remove(node)
            return {"status": "success", "removed_node": params.get("node_name")}

        if action == "link":
            fn = tree.nodes.get(params.get("from_node"))
            tn = tree.nodes.get(params.get("to_node"))
            if fn and tn:
                out_sock = fn.outputs.get(params.get("from_socket", "Image")) or (fn.outputs[0] if fn.outputs else None)
                in_sock = tn.inputs.get(params.get("to_socket", "Image")) or (tn.inputs[0] if tn.inputs else None)
                if out_sock and in_sock:
                    tree.links.new(out_sock, in_sock)
            return {"status": "success", "linked": True}

        if action == "set_socket_value":
            node = tree.nodes.get(params.get("node_name"))
            if node:
                sock_name = params.get("socket_name")
                sock = node.inputs.get(sock_name)
                if sock:
                    sock.default_value = params.get("socket_value")
            return {"status": "success", "set_value": True}

        raise ValueError(f"Unknown compositor action: '{action}'")

    @classmethod
    def execute_capture_or_render(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        bpy = cls.get_bpy()
        scene = bpy.context.scene
        mode = params.get("mode", "STILL")
        t0 = time.time()

        if params.get("camera_name"):
            cam = cls.get_object(params["camera_name"])
            scene.camera = cam

        if mode == "ANIMATION":
            if params.get("frame_start") is not None:
                scene.frame_start = params["frame_start"]
            if params.get("frame_end") is not None:
                scene.frame_end = params["frame_end"]
            if hasattr(bpy.ops.render, "render"):
                bpy.ops.render.render(animation=True)
            return {"status": "success", "mode": "ANIMATION", "duration": round(time.time() - t0, 2)}

        if mode == "STILL":
            target_path = params.get("output_path") or scene.render.filepath
            if hasattr(bpy.path, "abspath"):
                target_path = bpy.path.abspath(target_path)
            os.makedirs(os.path.dirname(os.path.abspath(target_path)) or ".", exist_ok=True)
            scene.render.filepath = target_path

            if hasattr(bpy.ops.render, "render"):
                bpy.ops.render.render(write_still=True)

            res: Dict[str, Any] = {
                "status": "success",
                "mode": "STILL",
                "filepath": target_path,
                "duration": round(time.time() - t0, 2),
            }
            if params.get("return_base64") and os.path.exists(target_path):
                with open(target_path, "rb") as f:
                    res["image_base64"] = base64.b64encode(f.read()).decode("utf-8")
            return res

        if mode == "VIEWPORT_SCREENSHOT":
            temp_path = params.get("output_path") or "/tmp/viewport_cap.png"
            if hasattr(bpy.ops.render, "opengl"):
                orig = scene.render.filepath
                scene.render.filepath = temp_path
                try:
                    bpy.ops.render.opengl(write_still=True)
                finally:
                    scene.render.filepath = orig

            res = {
                "status": "success",
                "mode": "VIEWPORT_SCREENSHOT",
                "filepath": temp_path,
                "duration": round(time.time() - t0, 2),
            }
            if params.get("return_base64") and os.path.exists(temp_path):
                with open(temp_path, "rb") as f:
                    res["image_base64"] = base64.b64encode(f.read()).decode("utf-8")
            return res

        raise ValueError(f"Unknown render mode: '{mode}'")
