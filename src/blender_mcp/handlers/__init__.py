"""
Handler registry and command dispatcher for Blender MCP.
"""

from __future__ import annotations

import traceback
from typing import Any, Callable, Dict

from blender_mcp.handlers.animation_rigging import AnimationRiggingHandler
from blender_mcp.handlers.assets_extensions import AssetsExtensionsHandler
from blender_mcp.handlers.base import BaseHandler
from blender_mcp.handlers.grease_pencil import GreasePencilHandler
from blender_mcp.handlers.io_preferences import IOPreferencesHandler
from blender_mcp.handlers.lattice_metaball import LatticeMetaballHandler
from blender_mcp.handlers.materials_shading import MaterialsShadingHandler
from blender_mcp.handlers.mesh_geometry import MeshGeometryHandler
from blender_mcp.handlers.modifiers_physics import ModifiersPhysicsHandler
from blender_mcp.handlers.new_data_types import NewDataTypesHandler
from blender_mcp.handlers.objects_hierarchy import ObjectsHierarchyHandler
from blender_mcp.handlers.reflection import ReflectionHandler
from blender_mcp.handlers.rendering import RenderingHandler
from blender_mcp.handlers.sculpt_paint import SculptPaintHandler
from blender_mcp.handlers.scene_world import SceneWorldHandler
from blender_mcp.handlers.timeline_data import TimelineDataHandler
from blender_mcp.handlers.vse import VSEHandler
from blender_mcp.handlers.workflows_render import RenderWorkflowsHandler
from blender_mcp.handlers.workflows_animation import AnimationWorkflowsHandler
from blender_mcp.handlers.workflows_procedural import ProceduralWorkflowsHandler
from blender_mcp.handlers.workflows_scene import SceneWorkflowsHandler

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
    "manage_undo": ReflectionHandler.manage_undo,
    "get_object_info": ReflectionHandler.get_object_info,
    "list_properties": ReflectionHandler.list_properties,
    "simulate_input": ReflectionHandler.simulate_input,
    "exec_script_json": ReflectionHandler.exec_script_json,

    # Scene & World
    "manage_scene": SceneWorldHandler.manage_scene,
    "manage_world": SceneWorldHandler.manage_world,
    "manage_viewport": SceneWorldHandler.manage_viewport,
    "manage_view_layers": SceneWorldHandler.manage_view_layers,
    "manage_camera": SceneWorldHandler.manage_camera,
    "manage_light": SceneWorldHandler.manage_light,
    "manage_lightprobes": SceneWorldHandler.manage_lightprobes,

    # Objects & Hierarchy
    "manage_objects": ObjectsHierarchyHandler.manage_objects,
    "manage_collections": ObjectsHierarchyHandler.manage_collections,
    "transform_object": ObjectsHierarchyHandler.transform_object,
    "manage_constraints": ObjectsHierarchyHandler.manage_constraints,
    "manage_vertex_groups": ObjectsHierarchyHandler.manage_vertex_groups,
    "manage_shape_keys": ObjectsHierarchyHandler.manage_shape_keys,

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
    "manage_uv_layers": MaterialsShadingHandler.manage_uv_layers,
    "manage_color_attributes": MaterialsShadingHandler.manage_color_attributes,

    # Modifiers & Physics
    "manage_modifier": ModifiersPhysicsHandler.manage_modifier,
    "setup_physics_simulation": ModifiersPhysicsHandler.setup_physics_simulation,
    "manage_particle_system": ModifiersPhysicsHandler.manage_particle_system,

    # Lattices & Metaballs
    "manage_lattices": LatticeMetaballHandler.manage_lattices,
    "manage_metaballs": LatticeMetaballHandler.manage_metaballs,

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

    # Grease Pencil
    "manage_grease_pencil": GreasePencilHandler.manage_grease_pencil,

    # New Data Types (Blender 5.x)
    "manage_curves_new": NewDataTypesHandler.manage_curves_new,
    "manage_pointclouds": NewDataTypesHandler.manage_pointclouds,

    # Preferences & I/O
    "manage_user_preferences": IOPreferencesHandler.manage_user_preferences,
    "manage_addon": IOPreferencesHandler.manage_addon,
    "manage_external_data": IOPreferencesHandler.manage_external_data,
    "universal_import_export": IOPreferencesHandler.universal_import_export,

    # Video Sequence Editor
    "manage_vse_strips": VSEHandler.manage_vse_strips,

    # Sculpt & Paint
    "manage_sculpt_settings": SculptPaintHandler.manage_sculpt_settings,
    "manage_brushes": SculptPaintHandler.manage_brushes,

    # Timeline Data (Markers, Cache Files, Pose Library)
    "manage_markers": TimelineDataHandler.manage_markers,
    "manage_cache_files": TimelineDataHandler.manage_cache_files,
    "manage_pose_library": TimelineDataHandler.manage_pose_library,

    # Assets & Extensions
    "manage_assets": AssetsExtensionsHandler.manage_assets,
    "manage_extensions": AssetsExtensionsHandler.manage_extensions,

    # Composite Workflows
    "setup_render_shot": RenderWorkflowsHandler.setup_render_shot,
    "create_material_preset": RenderWorkflowsHandler.create_material_preset,
    "bake_animation_to_nla": AnimationWorkflowsHandler.bake_animation_to_nla,
    "retarget_animation": AnimationWorkflowsHandler.retarget_animation,
    "setup_geo_nodes_pipeline": ProceduralWorkflowsHandler.setup_geo_nodes_pipeline,
    "setup_and_bake_physics": ProceduralWorkflowsHandler.setup_and_bake_physics,
    "audit_and_cleanup_scene": SceneWorkflowsHandler.audit_and_cleanup_scene,
    "uv_pipeline_export": SceneWorkflowsHandler.uv_pipeline_export,
    "batch_mark_assets": SceneWorkflowsHandler.batch_mark_assets,
    "auto_rig_character": SceneWorkflowsHandler.auto_rig_character,
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
    "GreasePencilHandler",
    "RenderingHandler",
    "SculptPaintHandler",
    "IOPreferencesHandler",
    "VSEHandler",
    "NewDataTypesHandler",
    "TimelineDataHandler",
    "LatticeMetaballHandler",
    "AssetsExtensionsHandler",
    "RenderWorkflowsHandler",
    "AnimationWorkflowsHandler",
    "ProceduralWorkflowsHandler",
    "SceneWorkflowsHandler",
    "ACTION_REGISTRY",
    "dispatch_blender_command",
]
