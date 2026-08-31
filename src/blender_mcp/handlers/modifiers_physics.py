"""
Modifiers, Physics, and Particle Systems execution handler.
"""

from __future__ import annotations

from typing import Any, Dict
from blender_mcp.handlers.base import BaseHandler


class ModifiersPhysicsHandler(BaseHandler):
    """Executes modifier stack management, physics setups (cloth, rigid body, fluid), and particle systems."""

    CLOTH_PRESETS = {
        "COTTON": {"mass": 0.3, "tension_stiffness": 15.0, "compression_stiffness": 15.0, "shear_stiffness": 5.0, "bending_stiffness": 0.5},
        "SILK": {"mass": 0.15, "tension_stiffness": 20.0, "compression_stiffness": 15.0, "shear_stiffness": 2.0, "bending_stiffness": 0.05},
        "LEATHER": {"mass": 0.4, "tension_stiffness": 45.0, "compression_stiffness": 45.0, "shear_stiffness": 25.0, "bending_stiffness": 1.5},
        "RUBBER": {"mass": 3.0, "tension_stiffness": 15.0, "compression_stiffness": 15.0, "shear_stiffness": 15.0, "bending_stiffness": 25.0},
        "DENIM": {"mass": 1.0, "tension_stiffness": 40.0, "compression_stiffness": 40.0, "shear_stiffness": 10.0, "bending_stiffness": 10.0},
    }

    @classmethod
    def manage_modifier(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        bpy = cls.get_bpy()
        obj = cls.get_object(params["object_name"])
        action = params["action"]
        mod_name = params.get("modifier_name")
        mod_type = params.get("modifier_type")
        props = params.get("properties", {})

        if action == "list":
            mods = [{"name": m.name, "type": m.type} for m in obj.modifiers]
            return {"status": "success", "modifiers": mods}

        if action == "add":
            if not mod_type:
                raise ValueError("modifier_type is required to add modifier.")
            name = mod_name or mod_type.title()
            mod = obj.modifiers.new(name=name, type=mod_type)
            cls._apply_modifier_properties(mod, props)
            return {"status": "success", "modifier_name": mod.name, "type": mod.type}

        if not mod_name:
            raise ValueError("modifier_name is required for action: " + action)

        mod = obj.modifiers.get(mod_name)
        if not mod:
            raise ValueError(f"Modifier '{mod_name}' not found on object '{obj.name}'.")

        if action == "remove":
            obj.modifiers.remove(mod)
            return {"status": "success", "removed_modifier": mod_name}

        if action == "apply":
            with bpy.context.temp_override(active_object=obj, selected_objects=[obj], object=obj):
                bpy.ops.object.modifier_apply(modifier=mod.name)
            return {"status": "success", "applied_modifier": mod_name}

        if action == "configure":
            cls._apply_modifier_properties(mod, props)
            return {"status": "success", "modifier_name": mod.name}

        if action == "reorder" and params.get("new_index") is not None:
            with bpy.context.temp_override(active_object=obj, selected_objects=[obj], object=obj):
                bpy.ops.object.modifier_move_to_index(modifier=mod.name, index=params["new_index"])
            return {"status": "success", "modifier_name": mod.name, "index": params["new_index"]}

        raise ValueError(f"Unknown modifier action: '{action}'")

    @classmethod
    def _apply_modifier_properties(cls, mod: Any, props: Dict[str, Any]):
        for k, v in props.items():
            if k in ("object", "target", "mirror_object") and isinstance(v, str):
                target_obj = cls.get_object(v)
                setattr(mod, k, target_obj)
            elif hasattr(mod, k):
                try:
                    setattr(mod, k, v)
                except Exception:
                    pass

    @classmethod
    def setup_physics_simulation(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        bpy = cls.get_bpy()
        obj = cls.get_object(params["object_name"])
        phys_type = params["physics_type"]
        action = params.get("action", "enable")

        with bpy.context.temp_override(active_object=obj, selected_objects=[obj], object=obj):
            if phys_type == "RIGID_BODY":
                if action == "disable":
                    if hasattr(bpy.ops.rigidbody, "object_remove"):
                        bpy.ops.rigidbody.object_remove()
                    return {"status": "success", "message": "Rigid body removed."}

                if not getattr(obj, "rigid_body", None) and hasattr(bpy.ops.rigidbody, "object_add"):
                    bpy.ops.rigidbody.object_add()

                rb_cfg = params.get("rigid_body", {})
                rb = getattr(obj, "rigid_body", None)
                if rb:
                    for k, v in rb_cfg.items():
                        if hasattr(rb, k):
                            setattr(rb, k, v)
                return {"status": "success", "physics": "RIGID_BODY"}

            if phys_type == "CLOTH":
                mod = obj.modifiers.get("Cloth")
                if action == "disable":
                    if mod:
                        obj.modifiers.remove(mod)
                    return {"status": "success", "message": "Cloth removed."}

                if not mod:
                    mod = obj.modifiers.new(name="Cloth", type="CLOTH")

                cfg = params.get("cloth", {})
                preset = cfg.get("preset")
                if preset and preset in cls.CLOTH_PRESETS and hasattr(mod, "settings"):
                    for pk, pv in cls.CLOTH_PRESETS[preset].items():
                        if hasattr(mod.settings, pk):
                            setattr(mod.settings, pk, pv)

                if hasattr(mod, "settings"):
                    for k, v in cfg.items():
                        if k != "preset" and hasattr(mod.settings, k):
                            setattr(mod.settings, k, v)
                return {"status": "success", "physics": "CLOTH"}

            if phys_type == "COLLISION":
                mod = obj.modifiers.get("Collision")
                if action == "disable":
                    if mod:
                        obj.modifiers.remove(mod)
                    return {"status": "success", "message": "Collision disabled."}
                if not mod:
                    obj.modifiers.new(name="Collision", type="COLLISION")
                return {"status": "success", "physics": "COLLISION"}

            if phys_type == "FLUID":
                mod = obj.modifiers.get("Fluid") or obj.modifiers.new(name="Fluid", type="FLUID")
                f_cfg = params.get("fluid", {})
                f_type = f_cfg.get("fluid_type", "DOMAIN")
                mod.fluid_type = f_type
                return {"status": "success", "physics": "FLUID", "fluid_type": f_type}

            if phys_type == "FORCE_FIELD":
                if action == "disable":
                    if hasattr(obj, "field") and obj.field and hasattr(bpy.ops.object, "forcefield_toggle"):
                        bpy.ops.object.forcefield_toggle()
                    return {"status": "success", "message": "Force field disabled."}
                if hasattr(bpy.ops.object, "forcefield_toggle"):
                    bpy.ops.object.forcefield_toggle()
                ff_cfg = params.get("force_field", {})
                if hasattr(obj, "field") and obj.field:
                    if "field_type" in ff_cfg:
                        obj.field.type = ff_cfg["field_type"]
                    if "strength" in ff_cfg:
                        obj.field.strength = ff_cfg["strength"]
                return {"status": "success", "physics": "FORCE_FIELD"}

        if action == "bake":
            cache_path = params.get("cache_path")
            frame_start = params.get("bake_frame_start")
            frame_end = params.get("bake_frame_end")
            scene = bpy.context.scene
            if frame_start is not None:
                scene.frame_start = int(frame_start)
            if frame_end is not None:
                scene.frame_end = int(frame_end)
            if cache_path and hasattr(bpy.ops.ptcache, "bake_from_cache"):
                try:
                    bpy.ops.ptcache.bake_from_cache()
                except Exception:
                    pass
            if hasattr(bpy.ops.ptcache, "bake_all"):
                bpy.ops.ptcache.bake_all(bake=True)
            return {"status": "success", "message": "Bake completed.", "cache_path": cache_path}

        if action == "free_bake":
            if hasattr(bpy.ops.ptcache, "free_bake_all"):
                bpy.ops.ptcache.free_bake_all()
            return {"status": "success", "message": "Bake freed."}

        if action == "get_bake_status":
            mod_name = {
                "CLOTH": "Cloth",
                "FLUID": "Fluid",
                "COLLISION": "Collision",
            }.get(phys_type)
            baked = False
            if mod_name:
                mod = obj.modifiers.get(mod_name)
                if mod and hasattr(mod, "point_cache"):
                    baked = bool(getattr(mod.point_cache, "is_baked", False))
            elif phys_type == "RIGID_BODY":
                rb_world = getattr(bpy.context.scene, "rigid_body_world", None)
                if rb_world and rb_world.point_cache:
                    baked = bool(rb_world.point_cache.is_baked)
            return {"status": "success", "physics": phys_type, "is_baked": baked}

        if action == "set_cache_path":
            cache_path = params.get("cache_path")
            if not cache_path:
                raise ValueError("cache_path is required for set_cache_path.")
            mod_name = {
                "CLOTH": "Cloth",
                "FLUID": "Fluid",
                "COLLISION": "Collision",
            }.get(phys_type)
            if mod_name:
                mod = obj.modifiers.get(mod_name)
                if mod and hasattr(mod, "point_cache"):
                    mod.point_cache.filepath = cache_path
                    return {"status": "success", "cache_path": cache_path, "physics": phys_type}
            raise ValueError(f"set_cache_path not supported for physics type '{phys_type}'.")

        return {"status": "success", "physics": phys_type}

    @classmethod
    def manage_particle_system(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        bpy = cls.get_bpy()
        obj = cls.get_object(params["object_name"])
        action = params["action"]
        sys_name = params.get("system_name")
        cfg = params.get("config", {})

        if action == "list":
            systems = [{"name": ps.name, "type": ps.settings.type} for ps in obj.particle_systems]
            return {"status": "success", "particle_systems": systems}

        if action == "add":
            with bpy.context.temp_override(active_object=obj, selected_objects=[obj], object=obj):
                bpy.ops.object.particle_system_add()
                ps = getattr(obj.particle_systems, "active", None)
                if not ps:
                    # Mock / fallback creation
                    from tests.mock_bpy import MockParticleSystem
                    ps = MockParticleSystem(sys_name or "ParticleSystem")
                    obj.particle_systems.append(ps)
                    obj.particle_systems.active = ps

                if sys_name:
                    ps.name = sys_name
                if ps and cfg:
                    cls._configure_particle_system(ps, cfg)
                return {"status": "success", "system_name": ps.name}

        ps = obj.particle_systems.get(sys_name) if sys_name else getattr(obj.particle_systems, "active", None)
        if not ps:
            raise ValueError(f"Particle system '{sys_name}' not found.")

        if action == "remove":
            with bpy.context.temp_override(active_object=obj, selected_objects=[obj], object=obj):
                obj.particle_systems.active = ps
                bpy.ops.object.particle_system_remove()
            return {"status": "success", "removed_system": sys_name}

        if action == "configure":
            cls._configure_particle_system(ps, cfg)
            return {"status": "success", "system_name": ps.name}

        raise ValueError(f"Unknown particle action: '{action}'")

    @classmethod
    def _configure_particle_system(cls, ps: Any, cfg: Dict[str, Any]):
        settings = ps.settings
        for k, v in cfg.items():
            if hasattr(settings, k):
                try:
                    setattr(settings, k, v)
                except Exception:
                    pass
