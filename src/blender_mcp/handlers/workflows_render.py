"""
Composite workflow handlers for render and material automation.

These handlers orchestrate multiple lower-level Blender operations into
higher-level, reusable workflows:

* ``setup_render_shot`` -- frames a target object with a camera, builds a
  classic 3-point lighting rig, configures render settings, and optionally
  triggers a render.
* ``create_material_preset`` -- builds a procedural Principled-BSDF-based
  material from a named preset, wiring texture/shader nodes with version
  tolerant socket access.

Both handlers run inside ``cls.transaction()`` so a failure rolls the scene
back to its prior state via Blender's undo stack.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from blender_mcp.exceptions import BlenderExecutionError
from blender_mcp.handlers.base import BaseHandler


# ---------------------------------------------------------------------------
# Preset definitions
# ---------------------------------------------------------------------------

# Default base colors / roughness / metallic per preset.  These are the
# starting values used unless the caller overrides them.
_PRESET_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "rough_stone": {
        "base_color": [0.35, 0.35, 0.35, 1.0],
        "roughness": 0.9,
        "metallic": 0.0,
    },
    "brushed_metal": {
        "base_color": [0.75, 0.75, 0.78, 1.0],
        "roughness": 0.35,
        "metallic": 1.0,
    },
    "car_paint": {
        "base_color": [0.05, 0.1, 0.6, 1.0],
        "roughness": 0.1,
        "metallic": 0.9,
    },
    "glass": {
        "base_color": [1.0, 1.0, 1.0, 1.0],
        "roughness": 0.0,
        "metallic": 0.0,
    },
    "emissive": {
        "base_color": [0.1, 0.1, 0.1, 1.0],
        "roughness": 0.5,
        "metallic": 0.0,
        "emission_color": [1.0, 0.8, 0.3, 1.0],
        "emission_strength": 5.0,
    },
    "subsurface_skin": {
        "base_color": [0.9, 0.7, 0.6, 1.0],
        "roughness": 0.6,
        "metallic": 0.0,
    },
    "wood": {
        "base_color": [0.35, 0.2, 0.1, 1.0],
        "roughness": 0.7,
        "metallic": 0.0,
    },
    "ice": {
        "base_color": [0.7, 0.85, 1.0, 1.0],
        "roughness": 0.05,
        "metallic": 0.0,
    },
    "lava": {
        "base_color": [0.05, 0.02, 0.0, 1.0],
        "roughness": 0.8,
        "metallic": 0.0,
        "emission_color": [1.0, 0.3, 0.0, 1.0],
        "emission_strength": 8.0,
    },
    "hologram": {
        "base_color": [0.0, 0.6, 0.8, 1.0],
        "roughness": 0.2,
        "metallic": 0.0,
        "emission_color": [0.0, 0.8, 1.0, 1.0],
        "emission_strength": 4.0,
    },
}

_VALID_PRESETS = set(_PRESET_DEFAULTS.keys())


class RenderWorkflowsHandler(BaseHandler):
    """Composite workflow handlers for render-shot and material-preset automation."""

    # ===================================================================
    # setup_render_shot
    # ===================================================================
    @classmethod
    def setup_render_shot(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        """Frame a target object with a camera + 3-point lighting + render setup.

        Builds a camera (auto-framed or manually placed), a key/fill/rim light
        rig, configures the render engine, resolution, samples, output path and
        color management, and optionally triggers a still render.

        Returns a summary dict containing the names of every created object and
        the final render settings applied.
        """
        bpy = cls.get_bpy()

        target_name = params.get("target_object")
        if not target_name:
            raise BlenderExecutionError("'target_object' is required for setup_render_shot.")
        target = cls.get_object(target_name)

        camera_name = params.get("camera_name") or "ShotCamera"
        camera_location: Optional[List[float]] = params.get("camera_location")
        render_engine = params.get("render_engine", "BLENDER_EEVEE")
        resolution = params.get("resolution", [1920, 1080])
        samples = int(params.get("samples", 64))
        output_filepath = params.get("output_filepath", "/tmp/render_shot_")

        key_color = params.get("key_light_color", [1.0, 1.0, 1.0])
        key_energy = float(params.get("key_light_energy", 1000.0))
        fill_color = params.get("fill_light_color", [0.8, 0.85, 1.0])
        fill_energy = float(params.get("fill_light_energy", 300.0))
        rim_color = params.get("rim_light_color", [1.0, 0.9, 0.8])
        rim_energy = float(params.get("rim_light_energy", 500.0))

        dof_focus_distance = params.get("dof_focus_distance")
        focal_length = float(params.get("focal_length", 50.0))
        auto_render = bool(params.get("auto_render", False))

        with cls.transaction("setup_render_shot"):
            # --- 1. Camera -------------------------------------------------
            cam_loc = cls._compute_camera_location(target, camera_location)
            cam_data, cam_obj = cls._create_camera(camera_name, cam_loc, focal_length)

            # Point camera at target
            cls._aim_at(cam_obj, target)

            # Depth of field
            if dof_focus_distance is not None:
                cls._enable_dof(cam_data, float(dof_focus_distance))

            # Make it the active scene camera
            scene = bpy.context.scene
            scene.camera = cam_obj

            # --- 2. 3-point lighting --------------------------------------
            key_light = cls._add_light(
                "KeyLight", "SUN", key_color, key_energy,
                location=cls._offset_from_target(target, [1.0, -1.0, 1.2]),
            )
            fill_light = cls._add_light(
                "FillLight", "AREA", fill_color, fill_energy,
                location=cls._offset_from_target(target, [-1.0, -0.6, 0.5]),
            )
            # Area lights need a size to be useful
            if hasattr(fill_light.data, "size"):
                fill_light.data.size = 3.0
            rim_light = cls._add_light(
                "RimLight", "SPOT", rim_color, rim_energy,
                location=cls._offset_from_target(target, [-0.5, 1.0, 1.0]),
            )
            if hasattr(rim_light.data, "spot_size"):
                rim_light.data.spot_size = math.radians(60.0)

            # Aim fill + rim at the target as well
            cls._aim_at(fill_light, target)
            cls._aim_at(rim_light, target)

            # --- 3. Render settings ---------------------------------------
            rd = scene.render
            rd.engine = render_engine
            rd.resolution_x = int(resolution[0])
            rd.resolution_y = int(resolution[1])
            rd.resolution_percentage = 100
            rd.filepath = output_filepath

            # Samples (Cycles only)
            if render_engine == "CYCLES" and hasattr(scene, "cycles"):
                scene.cycles.samples = samples
            elif render_engine.startswith("BLENDER_EEVEE") and hasattr(scene, "eevee"):
                # EEVEE uses a different sample attribute across versions.
                for attr in ("taa_render_samples", "samples"):
                    if hasattr(scene.eevee, attr):
                        setattr(scene.eevee, attr, samples)
                        break

            # --- 4. Color management (AgX with Filmic fallback) -----------
            cls._set_color_management(scene)

            # --- 5. Optional render ---------------------------------------
            rendered = False
            render_error: Optional[str] = None
            if auto_render:
                try:
                    bpy.ops.render.render(write_still=True)
                    rendered = True
                except Exception as exc:  # pragma: no cover - depends on runtime
                    render_error = str(exc)

        summary = {
            "status": "success",
            "target_object": target.name,
            "camera": {
                "name": cam_obj.name,
                "location": [round(v, 4) for v in cam_obj.location],
                "focal_length": focal_length,
                "dof_enabled": dof_focus_distance is not None,
                "dof_focus_distance": dof_focus_distance,
            },
            "lights": {
                "key": {"name": key_light.name, "type": "SUN", "energy": key_energy},
                "fill": {"name": fill_light.name, "type": "AREA", "energy": fill_energy},
                "rim": {"name": rim_light.name, "type": "SPOT", "energy": rim_energy},
            },
            "render": {
                "engine": render_engine,
                "resolution": [int(resolution[0]), int(resolution[1])],
                "samples": samples,
                "output_filepath": output_filepath,
            },
            "auto_rendered": rendered,
        }
        if render_error:
            summary["render_error"] = render_error
        return summary

    # ===================================================================
    # create_material_preset
    # ===================================================================
    @classmethod
    def create_material_preset(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create a procedural material from a named preset.

        Supported presets: ``rough_stone``, ``brushed_metal``, ``car_paint``,
        ``glass``, ``emissive``, ``subsurface_skin``, ``wood``, ``ice``,
        ``lava``, ``hologram``.

        Each preset wires Principled BSDF (and where appropriate, additional
        shader/texture nodes) using version-tolerant socket lookup so the same
        code works on Blender 4.x and 5.x.
        """
        bpy = cls.get_bpy()

        preset = params.get("preset")
        if not preset:
            raise BlenderExecutionError("'preset' is required for create_material_preset.")
        if preset not in _VALID_PRESETS:
            raise BlenderExecutionError(
                f"Unknown material preset '{preset}'. Valid presets: "
                f"{sorted(_VALID_PRESETS)}"
            )

        material_name = params.get("material_name") or preset
        object_name = params.get("object_name")
        base_color = params.get("base_color")
        roughness = params.get("roughness")
        metallic = params.get("metallic")
        emission_color = params.get("emission_color")
        emission_strength = params.get("emission_strength")
        scale = float(params.get("scale", 1.0))

        defaults = _PRESET_DEFAULTS[preset]
        final_base_color = cls._normalize_color(
            base_color if base_color is not None else defaults["base_color"]
        )
        final_roughness = (
            float(roughness) if roughness is not None else float(defaults["roughness"])
        )
        final_metallic = (
            float(metallic) if metallic is not None else float(defaults["metallic"])
        )
        final_emission_color = (
            cls._normalize_color(emission_color)
            if emission_color is not None
            else cls._normalize_color(defaults.get("emission_color", [1.0, 1.0, 1.0, 1.0]))
        )
        final_emission_strength = (
            float(emission_strength)
            if emission_strength is not None
            else float(defaults.get("emission_strength", 0.0))
        )

        with cls.transaction(f"create_material_preset:{preset}"):
            # Create / reset material
            mat = bpy.data.materials.new(name=material_name)
            mat.use_nodes = True
            tree = mat.node_tree
            tree.nodes.clear()

            output = tree.nodes.new(type="ShaderNodeOutputMaterial")
            output.location = (400, 0)

            principled = tree.nodes.new(type="ShaderNodeBsdfPrincipled")
            principled.location = (100, 0)

            # Apply base properties with version-tolerant socket access.
            cls._set_socket(principled, "Base Color", final_base_color, index=0)
            cls._set_socket(principled, "Roughness", final_roughness, index=7)
            cls._set_socket(principled, "Metallic", final_metallic, index=4)

            # Dispatch to per-preset builder.  Each builder returns a dict of
            # extra info (e.g. node count contributed) for the summary.
            extra = cls._build_preset(
                preset=preset,
                tree=tree,
                principled=principled,
                output=output,
                base_color=final_base_color,
                roughness=final_roughness,
                metallic=final_metallic,
                emission_color=final_emission_color,
                emission_strength=final_emission_strength,
                scale=scale,
            )

            # Connect Principled BSDF -> Material Output (Surface).
            cls._safe_link(tree, principled.outputs[0], output.inputs[0])

            # Assign to object if requested.
            assigned_to: Optional[str] = None
            if object_name:
                obj = cls.get_object(object_name)
                obj.data.materials.append(mat)
                assigned_to = obj.name

        node_count = len(tree.nodes)
        return {
            "status": "success",
            "material_name": mat.name,
            "preset": preset,
            "node_count": node_count,
            "base_color": final_base_color,
            "roughness": final_roughness,
            "metallic": final_metallic,
            "emission_color": final_emission_color,
            "emission_strength": final_emission_strength,
            "scale": scale,
            "assigned_to_object": assigned_to,
            "extra": extra,
        }

    # ===================================================================
    # Internal helpers -- camera / lighting
    # ===================================================================

    @staticmethod
    def _compute_camera_location(target: Any, camera_location: Optional[List[float]]) -> List[float]:
        """Return the camera location, auto-framing when none is supplied."""
        if camera_location is not None:
            return [float(v) for v in camera_location]
        dims = list(target.dimensions) if hasattr(target, "dimensions") else [1.0, 1.0, 1.0]
        max_dim = max(dims) if dims else 1.0
        if max_dim <= 0:
            max_dim = 1.0
        distance = max_dim * 2.5
        return [distance, -distance, distance * 0.8]

    @classmethod
    def _create_camera(cls, name: str, location: List[float], focal_length: float) -> Any:
        """Add a camera object at *location* with the supplied focal length."""
        bpy = cls.get_bpy()
        cam_data = bpy.data.cameras.new(name=f"{name}_Data")
        cam_obj = bpy.data.objects.new(name, cam_data)
        cam_obj.location = location
        # Link to the active scene collection.
        scene = bpy.context.scene
        scene.collection.objects.link(cam_obj)
        if hasattr(cam_data, "lens"):
            cam_data.lens = float(focal_length)
        return cam_data, cam_obj

    @classmethod
    def _aim_at(cls, obj: Any, target: Any) -> None:
        """Orient *obj* so it points at *target* using a Track-To constraint."""
        # Use a Track To constraint for robust aiming that survives transforms.
        if obj.constraints.get("TrackTo_Target"):
            return
        con = obj.constraints.new(type="TRACK_TO")
        con.name = "TrackTo_Target"
        con.target = target
        # Default track/up axes work for cameras and lights alike.
        con.track_axis = "TRACK_NEGATIVE_Z"
        con.up_axis = "UP_Y"

    @classmethod
    def _enable_dof(cls, cam_data: Any, focus_distance: float) -> None:
        """Enable depth-of-field on a camera data-block."""
        if not hasattr(cam_data, "dof"):
            return
        cam_data.dof.use_dof = True
        if hasattr(cam_data.dof, "focus_distance"):
            cam_data.dof.focus_distance = float(focus_distance)

    @classmethod
    def _add_light(
        cls,
        name: str,
        light_type: str,
        color: List[float],
        energy: float,
        location: List[float],
    ) -> Any:
        """Create a light object of the given type/color/energy at *location*."""
        bpy = cls.get_bpy()
        light_data = bpy.data.lights.new(name=f"{name}_Data", type=light_type)
        light_data.energy = energy
        if hasattr(light_data, "color"):
            light_data.color = [float(c) for c in color[:3]]
        light_obj = bpy.data.objects.new(name, light_data)
        light_obj.location = [float(v) for v in location]
        bpy.context.scene.collection.objects.link(light_obj)
        return light_obj

    @staticmethod
    def _offset_from_target(target: Any, offset: List[float]) -> List[float]:
        """Return target world location + scaled *offset* (scaled by max dim)."""
        loc = list(target.location) if hasattr(target, "location") else [0.0, 0.0, 0.0]
        dims = list(target.dimensions) if hasattr(target, "dimensions") else [1.0, 1.0, 1.0]
        max_dim = max(dims) if dims else 1.0
        if max_dim <= 0:
            max_dim = 1.0
        return [
            loc[0] + offset[0] * max_dim,
            loc[1] + offset[1] * max_dim,
            loc[2] + offset[2] * max_dim,
        ]

    @classmethod
    def _set_color_management(cls, scene: Any) -> None:
        """Set AgX view transform, falling back to Filmic for older Blender."""
        vs = getattr(scene, "view_settings", None)
        if not vs:
            return
        # Try AgX first (Blender 4.0+), then Filmic.
        try:
            vs.view_transform = "AgX"
            return
        except Exception:
            pass
        try:
            vs.view_transform = "Filmic"
        except Exception:
            pass

    # ===================================================================
    # Internal helpers -- node graph
    # ===================================================================

    @staticmethod
    def _normalize_color(color: List[float]) -> List[float]:
        """Normalize a color to a 4-element list of floats in 0..1."""
        c = [float(v) for v in color]
        while len(c) < 3:
            c.append(0.0)
        if len(c) < 4:
            c.append(1.0)
        return c[:4]

    @classmethod
    def _set_socket(
        cls,
        node: Any,
        name: str,
        value: Any,
        index: Optional[int] = None,
    ) -> bool:
        """Set a node input socket by name, falling back to *index*.

        Returns True if the socket was found and set.
        """
        inputs = getattr(node, "inputs", None)
        if inputs is None:
            return False
        sock = None
        # Name lookup (case-insensitive for robustness).
        try:
            sock = inputs[name]
        except Exception:
            for s in inputs:
                if s.name.lower() == name.lower():
                    sock = s
                    break
        if sock is None and index is not None and 0 <= index < len(inputs):
            sock = inputs[index]
        if sock is None:
            return False
        try:
            sock.default_value = value
            return True
        except Exception:
            return False

    @classmethod
    def _get_socket(
        cls,
        node: Any,
        name: str,
        index: Optional[int] = None,
        outputs: bool = False,
    ) -> Any:
        """Retrieve an input or output socket by name with index fallback."""
        sockets = getattr(node, "outputs" if outputs else "inputs", None)
        if sockets is None:
            return None
        try:
            return sockets[name]
        except Exception:
            for s in sockets:
                if s.name.lower() == name.lower():
                    return s
        if index is not None and 0 <= index < len(sockets):
            return sockets[index]
        return None

    @classmethod
    def _safe_link(cls, tree: Any, from_sock: Any, to_sock: Any) -> bool:
        """Create a link, swallowing errors from socket-name mismatches."""
        if from_sock is None or to_sock is None:
            return False
        try:
            tree.links.new(from_sock, to_sock)
            return True
        except Exception:
            return False

    @classmethod
    def _add_noise(
        cls,
        tree: Any,
        name: str,
        scale: float,
        detail: float = 2.0,
        location: Optional[List[float]] = None,
    ) -> Any:
        """Helper: add a Noise Texture node with common defaults."""
        node = tree.nodes.new(type="ShaderNodeTexNoise")
        node.name = name
        node.inputs["Scale"].default_value = scale
        if "Detail" in node.inputs:
            node.inputs["Detail"].default_value = detail
        if location:
            node.location = location
        return node

    @classmethod
    def _add_bump(
        cls,
        tree: Any,
        name: str,
        strength: float = 1.0,
        location: Optional[List[float]] = None,
    ) -> Any:
        """Helper: add a Bump node."""
        node = tree.nodes.new(type="ShaderNodeBump")
        node.name = name
        if "Strength" in node.inputs:
            node.inputs["Strength"].default_value = strength
        if location:
            node.location = location
        return node

    @classmethod
    def _add_colorramp(
        cls,
        tree: Any,
        name: str,
        stops: List[List[float]],
        location: Optional[List[float]] = None,
    ) -> Any:
        """Helper: add a ColorRamp node with the given (position, color) stops."""
        node = tree.nodes.new(type="ShaderNodeValToRGB")
        node.name = name
        ramp = node.color_ramp
        # Remove default stops beyond the first two, then configure.
        while len(ramp.elements) > 2:
            ramp.elements.remove(ramp.elements[-1])
        for i, (pos, color) in enumerate(stops):
            if i < len(ramp.elements):
                elem = ramp.elements[i]
            else:
                elem = ramp.elements.new(pos)
            elem.position = float(pos)
            elem.color = [float(c) for c in color[:4]]
        if location:
            node.location = location
        return node

    # ===================================================================
    # Per-preset builders
    # ===================================================================

    @classmethod
    def _build_preset(
        cls,
        preset: str,
        tree: Any,
        principled: Any,
        output: Any,
        base_color: List[float],
        roughness: float,
        metallic: float,
        emission_color: List[float],
        emission_strength: float,
        scale: float,
    ) -> Dict[str, Any]:
        """Dispatch to the appropriate preset builder and return extra info."""
        builder = getattr(cls, f"_preset_{preset}", None)
        if builder is None:
            return {}
        return builder(
            tree=tree,
            principled=principled,
            output=output,
            base_color=base_color,
            roughness=roughness,
            metallic=metallic,
            emission_color=emission_color,
            emission_strength=emission_strength,
            scale=scale,
        )

    # --- rough_stone -----------------------------------------------------
    @classmethod
    def _preset_rough_stone(
        cls, tree, principled, output, base_color, roughness, metallic,
        emission_color, emission_strength, scale,
    ) -> Dict[str, Any]:
        noise = cls._add_noise(tree, "StoneNoise", scale=5.0 * scale, detail=8.0, location=(-600, 200))
        ramp = cls._add_colorramp(
            tree, "StoneRamp",
            stops=[[0.0, [0.2, 0.2, 0.2, 1.0]], [1.0, [0.5, 0.5, 0.5, 1.0]]],
            location=(-400, 200),
        )
        bump = cls._add_bump(tree, "StoneBump", strength=0.8, location=(-200, 200))

        cls._safe_link(tree, cls._get_socket(noise, "Fac", 0, outputs=True), ramp.inputs[0])
        cls._safe_link(tree, cls._get_socket(ramp, "Color", 0, outputs=True), cls._get_socket(principled, "Base Color", 0))
        cls._safe_link(tree, cls._get_socket(noise, "Fac", 0, outputs=True), cls._get_socket(bump, "Height", 2))
        cls._safe_link(tree, cls._get_socket(bump, "Normal", 0, outputs=True), cls._get_socket(principled, "Normal", 20))
        cls._set_socket(principled, "Roughness", max(roughness, 0.9), index=7)
        return {"technique": "noise+bump", "texture": "noise"}

    # --- brushed_metal ---------------------------------------------------
    @classmethod
    def _preset_brushed_metal(
        cls, tree, principled, output, base_color, roughness, metallic,
        emission_color, emission_strength, scale,
    ) -> Dict[str, Any]:
        noise = cls._add_noise(tree, "BrushNoise", scale=50.0 * scale, detail=1.0, location=(-600, 200))
        bump = cls._add_bump(tree, "BrushBump", strength=0.1, location=(-400, 200))

        cls._safe_link(tree, cls._get_socket(noise, "Fac", 0, outputs=True), cls._get_socket(bump, "Height", 2))
        cls._safe_link(tree, cls._get_socket(bump, "Normal", 0, outputs=True), cls._get_socket(principled, "Normal", 20))

        cls._set_socket(principled, "Metallic", 1.0, index=4)
        cls._set_socket(principled, "Roughness", roughness, index=7)
        # Anisotropic (Blender 4+ uses "Anisotropic", some versions "Anisotropy").
        cls._set_socket(principled, "Anisotropic", 0.8, index=12)
        cls._set_socket(principled, "Anisotropy", 0.8, index=12)
        return {"technique": "noise+bump+anisotropic", "metallic": 1.0, "anisotropic": 0.8}

    # --- car_paint -------------------------------------------------------
    @classmethod
    def _preset_car_paint(
        cls, tree, principled, output, base_color, roughness, metallic,
        emission_color, emission_strength, scale,
    ) -> Dict[str, Any]:
        cls._set_socket(principled, "Base Color", base_color, index=0)
        cls._set_socket(principled, "Metallic", metallic, index=4)
        cls._set_socket(principled, "Roughness", roughness, index=7)
        # Clearcoat / Coat Weight (Blender 5.x renamed to "Coat Weight").
        coat_set = cls._set_socket(principled, "Coat Weight", 1.0, index=15)
        if not coat_set:
            cls._set_socket(principled, "Clearcoat", 1.0, index=15)
        # Coat roughness for a glossy clear layer.
        cls._set_socket(principled, "Coat Roughness", 0.05, index=16)
        cls._set_socket(principled, "Clearcoat Roughness", 0.05, index=16)
        return {"technique": "principled+clearcoat", "coat_weight": 1.0}

    # --- glass -----------------------------------------------------------
    @classmethod
    def _preset_glass(
        cls, tree, principled, output, base_color, roughness, metallic,
        emission_color, emission_strength, scale,
    ) -> Dict[str, Any]:
        cls._set_socket(principled, "Base Color", base_color, index=0)
        cls._set_socket(principled, "Roughness", max(roughness, 0.0), index=7)
        # Transmission (Blender 5.x: "Transmission Weight"; older: "Transmission").
        trans_set = cls._set_socket(principled, "Transmission Weight", 1.0, index=17)
        if not trans_set:
            cls._set_socket(principled, "Transmission", 1.0, index=17)
        # IOR
        cls._set_socket(principled, "IOR", 1.45, index=1)
        return {"technique": "principled+transmission", "transmission": 1.0, "ior": 1.45}

    # --- emissive --------------------------------------------------------
    @classmethod
    def _preset_emissive(
        cls, tree, principled, output, base_color, roughness, metallic,
        emission_color, emission_strength, scale,
    ) -> Dict[str, Any]:
        cls._set_socket(principled, "Base Color", base_color, index=0)
        # Emission Color (Blender 5.x: "Emission Color"; older: "Emission").
        em_set = cls._set_socket(principled, "Emission Color", emission_color, index=26)
        if not em_set:
            cls._set_socket(principled, "Emission", emission_color, index=26)
        cls._set_socket(principled, "Emission Strength", emission_strength, index=27)
        return {"technique": "principled+emission", "emission_strength": emission_strength}

    # --- subsurface_skin -------------------------------------------------
    @classmethod
    def _preset_subsurface_skin(
        cls, tree, principled, output, base_color, roughness, metallic,
        emission_color, emission_strength, scale,
    ) -> Dict[str, Any]:
        cls._set_socket(principled, "Base Color", base_color, index=0)
        cls._set_socket(principled, "Roughness", roughness, index=7)
        # Subsurface Weight (Blender 5.x) / Subsurface (older).
        ss_set = cls._set_socket(principled, "Subsurface Weight", 0.5, index=8)
        if not ss_set:
            cls._set_socket(principled, "Subsurface", 0.5, index=8)
        cls._set_socket(principled, "Subsurface Radius", [1.0, 0.2, 0.1], index=10)
        cls._set_socket(principled, "Subsurface Color", base_color, index=11)
        return {"technique": "principled+subsurface", "subsurface_weight": 0.5}

    # --- wood ------------------------------------------------------------
    @classmethod
    def _preset_wood(
        cls, tree, principled, output, base_color, roughness, metallic,
        emission_color, emission_strength, scale,
    ) -> Dict[str, Any]:
        wave = tree.nodes.new(type="ShaderNodeTexWave")
        wave.name = "WoodWave"
        wave.inputs["Scale"].default_value = scale * 5.0
        wave.location = (-800, 200)
        noise = cls._add_noise(tree, "WoodNoise", scale=10.0 * scale, detail=4.0, location=(-800, 0))
        ramp = cls._add_colorramp(
            tree, "WoodRamp",
            stops=[[0.0, [0.2, 0.1, 0.05, 1.0]], [1.0, [0.5, 0.3, 0.15, 1.0]]],
            location=(-400, 100),
        )
        bump = cls._add_bump(tree, "WoodBump", strength=0.3, location=(-200, 100))

        cls._safe_link(tree, cls._get_socket(wave, "Color", 0, outputs=True), ramp.inputs[0])
        cls._safe_link(tree, cls._get_socket(ramp, "Color", 0, outputs=True), cls._get_socket(principled, "Base Color", 0))
        cls._safe_link(tree, cls._get_socket(noise, "Fac", 0, outputs=True), cls._get_socket(bump, "Height", 2))
        cls._safe_link(tree, cls._get_socket(bump, "Normal", 0, outputs=True), cls._get_socket(principled, "Normal", 20))
        cls._set_socket(principled, "Roughness", roughness, index=7)
        return {"technique": "wave+noise+bump", "textures": ["wave", "noise"]}

    # --- ice -------------------------------------------------------------
    @classmethod
    def _preset_ice(
        cls, tree, principled, output, base_color, roughness, metallic,
        emission_color, emission_strength, scale,
    ) -> Dict[str, Any]:
        noise = cls._add_noise(tree, "IceNoise", scale=2.0 * scale, detail=2.0, location=(-600, 200))
        bump = cls._add_bump(tree, "IceBump", strength=0.2, location=(-400, 200))

        cls._safe_link(tree, cls._get_socket(noise, "Fac", 0, outputs=True), cls._get_socket(bump, "Height", 2))
        cls._safe_link(tree, cls._get_socket(bump, "Normal", 0, outputs=True), cls._get_socket(principled, "Normal", 20))

        cls._set_socket(principled, "Base Color", base_color, index=0)
        cls._set_socket(principled, "Roughness", max(roughness, 0.05), index=7)
        trans_set = cls._set_socket(principled, "Transmission Weight", 0.8, index=17)
        if not trans_set:
            cls._set_socket(principled, "Transmission", 0.8, index=17)
        cls._set_socket(principled, "IOR", 1.31, index=1)
        return {"technique": "noise+bump+transmission", "transmission": 0.8, "ior": 1.31}

    # --- lava ------------------------------------------------------------
    @classmethod
    def _preset_lava(
        cls, tree, principled, output, base_color, roughness, metallic,
        emission_color, emission_strength, scale,
    ) -> Dict[str, Any]:
        noise = cls._add_noise(tree, "LavaNoise", scale=3.0 * scale, detail=6.0, location=(-800, 200))
        # Black -> red -> yellow gradient for the glowing cracks.
        ramp = cls._add_colorramp(
            tree, "LavaRamp",
            stops=[
                [0.0, [0.0, 0.0, 0.0, 1.0]],
                [0.5, [1.0, 0.1, 0.0, 1.0]],
                [1.0, [1.0, 0.9, 0.2, 1.0]],
            ],
            location=(-600, 200),
        )
        # Need a 3rd stop; the helper only seeds 2, add the middle.
        ramp.color_ramp.elements.new(0.5).color = [1.0, 0.1, 0.0, 1.0]

        # Mix shader: Principled (rock) + Emission (glow), driven by ramp.
        mix = tree.nodes.new(type="ShaderNodeMixShader")
        mix.location = (250, 0)
        emit = tree.nodes.new(type="ShaderNodeEmission")
        emit.location = (0, -200)
        cls._set_socket(emit, "Color", emission_color, index=0)
        cls._set_socket(emit, "Strength", emission_strength, index=1)

        cls._safe_link(tree, cls._get_socket(noise, "Fac", 0, outputs=True), ramp.inputs[0])
        cls._safe_link(tree, cls._get_socket(ramp, "Color", 0, outputs=True), cls._get_socket(emit, "Color", 0))
        cls._safe_link(tree, cls._get_socket(ramp, "Alpha", 1, outputs=True), mix.inputs[0])
        cls._safe_link(tree, principled.outputs[0], mix.inputs[1])
        cls._safe_link(tree, cls._get_socket(emit, "Emission", 0, outputs=True), mix.inputs[2])
        # Replace the default Principled->Output link with Mix->Output.
        cls._safe_link(tree, cls._get_socket(mix, "Shader", 0, outputs=True), output.inputs[0])

        cls._set_socket(principled, "Base Color", base_color, index=0)
        cls._set_socket(principled, "Roughness", roughness, index=7)
        return {"technique": "noise+ramp+mix+emission", "emission_strength": emission_strength}

    # --- hologram --------------------------------------------------------
    @classmethod
    def _preset_hologram(
        cls, tree, principled, output, base_color, roughness, metallic,
        emission_color, emission_strength, scale,
    ) -> Dict[str, Any]:
        # Scanline noise modulating emission strength.
        noise = cls._add_noise(tree, "HoloNoise", scale=80.0 * scale, detail=1.0, location=(-600, 200))
        ramp = cls._add_colorramp(
            tree, "HoloRamp",
            stops=[[0.0, [0.0, 0.0, 0.0, 1.0]], [1.0, [1.0, 1.0, 1.0, 1.0]]],
            location=(-400, 200),
        )
        # Transparent + Emission mixed for a ghostly look.
        transparent = tree.nodes.new(type="ShaderNodeBsdfTransparent")
        transparent.location = (0, -200)
        emit = tree.nodes.new(type="ShaderNodeEmission")
        emit.location = (0, 100)
        cls._set_socket(emit, "Color", emission_color, index=0)
        cls._set_socket(emit, "Strength", emission_strength, index=1)
        mix = tree.nodes.new(type="ShaderNodeMixShader")
        mix.location = (250, 0)

        cls._safe_link(tree, cls._get_socket(noise, "Fac", 0, outputs=True), ramp.inputs[0])
        cls._safe_link(tree, cls._get_socket(ramp, "Color", 0, outputs=True), cls._get_socket(emit, "Strength", 1))
        cls._safe_link(tree, cls._get_socket(ramp, "Alpha", 1, outputs=True), mix.inputs[0])
        cls._safe_link(tree, cls._get_socket(transparent, "BSDF", 0, outputs=True), mix.inputs[1])
        cls._safe_link(tree, cls._get_socket(emit, "Emission", 0, outputs=True), mix.inputs[2])
        # Replace Principled->Output with Mix->Output.
        cls._safe_link(tree, cls._get_socket(mix, "Shader", 0, outputs=True), output.inputs[0])

        cls._set_socket(principled, "Base Color", base_color, index=0)
        cls._set_socket(principled, "Emission Color", emission_color, index=26)
        cls._set_socket(principled, "Emission", emission_color, index=26)
        cls._set_socket(principled, "Emission Strength", emission_strength, index=27)
        return {"technique": "noise+transparent+emission+mix", "scanlines": True}
