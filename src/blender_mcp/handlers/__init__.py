"""
Handler registry and command dispatcher for Blender MCP.
"""

from __future__ import annotations

import traceback
from typing import Any, Callable, Dict

from blender_mcp.handlers.animation_rigging import AnimationRiggingHandler
from blender_mcp.handlers.base import BaseHandler
from blender_mcp.handlers.io_preferences import IOPreferencesHandler
from blender_mcp.handlers.materials_shading import MaterialsShadingHandler
from blender_mcp.handlers.mesh_geometry import MeshGeometryHandler
from blender_mcp.handlers.modifiers_physics import ModifiersPhysicsHandler
from blender_mcp.handlers.objects_hierarchy import ObjectsHierarchyHandler
from blender_mcp.handlers.reflection import ReflectionHandler
from blender_mcp.handlers.rendering import RenderingHandler
from blender_mcp.handlers.scene_world import SceneWorldHandler

# Central routing table mapping action names to handler methods
ACTION_REGISTRY: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
    # Reflection & Scripting
    "inspect_bpy_path": ReflectionHandler.inspect_bpy_path,
    "get_rna_schema": ReflectionHandler.get_rna_schema,
    "execute_operator": ReflectionHandler.execute_operator,
    "get_property": ReflectionHandler.get_property,
    "set_property": ReflectionHandler.set_property,
    "eval_expression": ReflectionHandler.eval_expression,
    "exec_script": ReflectionHandler.exec_script,

    # Scene & World
    "manage_scene": SceneWorldHandler.manage_scene,
    "manage_world": SceneWorldHandler.manage_world,
    "manage_viewport": SceneWorldHandler.manage_viewport,
    "manage_camera": SceneWorldHandler.manage_camera,
    "manage_light": SceneWorldHandler.manage_light,

    # Objects & Hierarchy
    "manage_objects": ObjectsHierarchyHandler.manage_objects,
    "manage_collections": ObjectsHierarchyHandler.manage_collections,
    "transform_object": ObjectsHierarchyHandler.transform_object,
    "manage_constraints": ObjectsHierarchyHandler.manage_constraints,

    # Mesh & Geometry
    "create_primitive": MeshGeometryHandler.create_primitive,
    "manipulate_mesh": MeshGeometryHandler.manipulate_mesh,
    "create_curve": MeshGeometryHandler.create_curve,
    "create_text": MeshGeometryHandler.create_text,
    "create_volume": MeshGeometryHandler.create_volume,
    "manage_geometry_nodes": MeshGeometryHandler.manage_geometry_nodes,

    # Materials & Shading
    "manage_materials": MaterialsShadingHandler.manage_materials,
    "inspect_shader_tree": MaterialsShadingHandler.inspect_shader_tree,
    "manage_shader_node": MaterialsShadingHandler.manage_shader_node,
    "manage_shader_links": MaterialsShadingHandler.manage_shader_links,
    "set_socket_value": MaterialsShadingHandler.set_socket_value,
    "setup_procedural_texture": MaterialsShadingHandler.setup_procedural_texture,
    "assign_image_texture": MaterialsShadingHandler.assign_image_texture,
    "perform_uv_unwrap": MaterialsShadingHandler.perform_uv_unwrap,

    # Modifiers & Physics
    "manage_modifier": ModifiersPhysicsHandler.manage_modifier,
    "setup_physics_simulation": ModifiersPhysicsHandler.setup_physics_simulation,
    "manage_particle_system": ModifiersPhysicsHandler.manage_particle_system,

    # Animation & Rigging
    "timeline_control": AnimationRiggingHandler.timeline_control,
    "insert_keyframe": AnimationRiggingHandler.insert_keyframe,
    "delete_keyframe": AnimationRiggingHandler.delete_keyframe,
    "list_fcurves": AnimationRiggingHandler.list_fcurves,
    "modify_keyframe": AnimationRiggingHandler.modify_keyframe,
    "manage_driver": AnimationRiggingHandler.manage_driver,
    "manage_nla": AnimationRiggingHandler.manage_nla,
    "manage_armature": AnimationRiggingHandler.manage_armature,

    # Rendering & Compositing
    "configure_render_engine": RenderingHandler.configure_render_engine,
    "configure_output_and_passes": RenderingHandler.configure_output_and_passes,
    "configure_color_management": RenderingHandler.configure_color_management,
    "manage_compositor_tree": RenderingHandler.manage_compositor_tree,
    "execute_capture_or_render": RenderingHandler.execute_capture_or_render,

    # Preferences & I/O
    "manage_user_preferences": IOPreferencesHandler.manage_user_preferences,
    "manage_addon": IOPreferencesHandler.manage_addon,
    "manage_external_data": IOPreferencesHandler.manage_external_data,
    "universal_import_export": IOPreferencesHandler.universal_import_export,
}


def dispatch_blender_command(action: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Routes an incoming action string to the appropriate handler with exception capture."""
    handler = ACTION_REGISTRY.get(action)
    if not handler:
        return {
            "success": False,
            "error": f"Unknown Blender MCP action: '{action}'",
        }

    try:
        res = handler(params)
        return {
            "success": True,
            "result": res,
        }
    except Exception as exc:
        return {
            "success": False,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }


__all__ = [
    "BaseHandler",
    "ReflectionHandler",
    "SceneWorldHandler",
    "ObjectsHierarchyHandler",
    "MeshGeometryHandler",
    "MaterialsShadingHandler",
    "ModifiersPhysicsHandler",
    "AnimationRiggingHandler",
    "RenderingHandler",
    "IOPreferencesHandler",
    "ACTION_REGISTRY",
    "dispatch_blender_command",
]
