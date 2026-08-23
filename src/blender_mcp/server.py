"""
Blender Model Context Protocol (MCP) Server.
Exposes strictly typed tool endpoints for AI hosts.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Literal, Optional, Tuple, Union

from blender_mcp.client import default_client
from blender_mcp.schemas import (
    AddonManageInput,
    ArmatureRiggingInput,
    CameraManageInput,
    CaptureRenderInput,
    ColorManagementInput,
    CompositorManageInput,
    ConstraintManageInput,
    ExternalDataInput,
    GeometryNodesInput,
    LightManageInput,
    MaterialManageInput,
    MeshManipulateInput,
    MeshPrimitiveInput,
    ModifierManageInput,
    ObjectHierarchyInput,
    ParticleSystemInput,
    PhysicsSimulationInput,
    RenderConfigureInput,
    RenderOutputPassesInput,
    SceneManageInput,
    ShaderNodeManageInput,
    TimelineKeyframeInput,
    TransformObjectInput,
    UniversalIOInput,
    UserPreferencesInput,
    UVUnwrapInput,
    ViewportManageInput,
    WorldManageInput,
)

# Optional FastMCP import with fallback
try:
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("blender-mcp")
except ImportError:
    class DummyMCP:
        def __init__(self, name: str):
            self.name = name
            self._tools = {}

        def tool(self):
            def decorator(func):
                self._tools[func.__name__] = func
                return func
            return decorator

        def run(self):
            print(f"[{self.name}] Server initialized.")

    mcp = DummyMCP("blender-mcp")


# ---------------------------------------------------------------------------
# 1. Dynamic Reflection & Operator Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def inspect_bpy_path(path: str) -> Dict[str, Any]:
    """Introspects any arbitrary Blender RNA data path."""
    return default_client.send_command("inspect_bpy_path", {"path": path})


@mcp.tool()
def get_rna_schema(rna_type_name: str) -> Dict[str, Any]:
    """Queries RNA struct definitions dynamically for any Blender type."""
    return default_client.send_command("get_rna_schema", {"rna_type_name": rna_type_name})


@mcp.tool()
def execute_operator(
    operator: str,
    execution_context: Literal[
        "EXEC_DEFAULT", "INVOKE_DEFAULT", "EXEC_REGION_WIN", "EXEC_SCREEN", "INVOKE_REGION_WIN"
    ] = "EXEC_DEFAULT",
    kwargs: Optional[Dict[str, Any]] = None,
    context_override: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Executes ANY arbitrary Blender operator with optional kwargs and context overrides."""
    return default_client.send_command(
        "execute_operator",
        {
            "operator": operator,
            "execution_context": execution_context,
            "kwargs": kwargs or {},
            "context_override": context_override or {},
        },
    )


@mcp.tool()
def get_property(path: str) -> Dict[str, Any]:
    """Retrieves the value of any data path on any Blender entity."""
    return default_client.send_command("get_property", {"path": path})


@mcp.tool()
def set_property(path: str, value: Any) -> Dict[str, Any]:
    """Sets the value of any Blender RNA data path with dynamic type coercion."""
    return default_client.send_command("set_property", {"path": path, "value": value})


@mcp.tool()
def eval_expression(expression: str) -> Dict[str, Any]:
    """Evaluates a single-line Python expression within Blender's global namespace."""
    return default_client.send_command("eval_expression", {"expression": expression})


@mcp.tool()
def exec_script(script: str, use_transaction_rollback: bool = True) -> Dict[str, Any]:
    """Executes an arbitrary multi-line Python script within Blender with stdout capture and undo rollback."""
    return default_client.send_command(
        "exec_script",
        {"script": script, "use_transaction_rollback": use_transaction_rollback},
    )


# ---------------------------------------------------------------------------
# 2. Scene, World & Viewport Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def manage_scene(
    action: Literal["create", "switch", "delete", "configure", "list", "get_active"] = "list",
    scene_name: Optional[str] = None,
    new_name: Optional[str] = None,
    create_mode: Literal["NEW", "EMPTY", "LINK_COPY", "FULL_COPY", "LINK_OBJECT_DATA"] = "NEW",
    unit_system: Optional[Literal["METRIC", "IMPERIAL", "NONE"]] = None,
    unit_length: Optional[str] = None,
    unit_rotation: Optional[Literal["DEGREES", "RADIANS"]] = None,
    unit_scale_length: Optional[float] = None,
    gravity: Optional[List[float]] = None,
    use_gravity: Optional[bool] = None,
    active_camera_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Manages scene graph, unit systems, gravity vectors, and active camera assignments."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("manage_scene", params)


@mcp.tool()
def manage_world(
    mode: Literal["HDRI", "SKY_TEXTURE", "COLOR", "VOLUMETRICS_ONLY", "GET_INFO"] = "GET_INFO",
    world_name: Optional[str] = None,
    color: Optional[List[float]] = None,
    strength: float = 1.0,
    hdri_filepath: Optional[str] = None,
    hdri_rotation_z: float = 0.0,
    sky_type: Literal["NISHITA", "HOSEK_WILKIE", "PREETHAM"] = "NISHITA",
    sky_sun_intensity: float = 1.0,
    sky_sun_elevation: Optional[float] = None,
    sky_sun_rotation: Optional[float] = None,
    volume_type: Literal["NONE", "SCATTER", "ABSORPTION", "PRINCIPLED"] = "NONE",
    volume_density: float = 0.01,
    volume_color: Optional[List[float]] = None,
    volume_anisotropy: float = 0.0,
) -> Dict[str, Any]:
    """Configures World background lighting, HDRIs, Nishita procedural skies, and volumetric fog."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("manage_world", params)


@mcp.tool()
def manage_viewport(
    action: Literal["switch_workspace", "set_shading", "set_overlays", "set_clipping_lens", "set_cursor", "lock_view", "get_state"],
    workspace_name: Optional[str] = None,
    shading_type: Optional[Literal["WIREFRAME", "SOLID", "MATERIAL", "RENDERED"]] = None,
    shading_options: Optional[Dict[str, Any]] = None,
    show_overlays: Optional[bool] = None,
    overlay_toggles: Optional[Dict[str, bool]] = None,
    clip_start: Optional[float] = None,
    clip_end: Optional[float] = None,
    lens: Optional[float] = None,
    cursor_location: Optional[List[float]] = None,
    cursor_rotation_euler: Optional[List[float]] = None,
    lock_object_name: Optional[str] = None,
    lock_cursor: Optional[bool] = None,
) -> Dict[str, Any]:
    """Controls 3D Viewport workspaces, shading modes, overlays, clipping planes, and 3D cursor."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("manage_viewport", params)


@mcp.tool()
def manage_camera(
    action: Literal["create", "update", "set_active", "get_properties", "delete"],
    camera_name: Optional[str] = None,
    type: Literal["PERSP", "ORTHO", "PANO"] = "PERSP",
    focal_length: Optional[float] = None,
    ortho_scale: Optional[float] = None,
    sensor_fit: Optional[Literal["AUTO", "HORIZONTAL", "VERTICAL"]] = None,
    sensor_width: Optional[float] = None,
    sensor_height: Optional[float] = None,
    clip_start: Optional[float] = None,
    clip_end: Optional[float] = None,
    shift_x: Optional[float] = None,
    shift_y: Optional[float] = None,
    dof: Optional[Dict[str, Any]] = None,
    composition_guides: Optional[Dict[str, bool]] = None,
) -> Dict[str, Any]:
    """Creates, configures, or inspects Camera objects with depth of field and guides."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("manage_camera", params)


@mcp.tool()
def manage_light(
    action: Literal["create", "update", "delete", "get_properties", "set_linking"],
    light_name: Optional[str] = None,
    type: Literal["POINT", "SUN", "SPOT", "AREA"] = "POINT",
    energy: Optional[float] = None,
    color_type: Literal["RGB", "KELVIN"] = "RGB",
    color_rgb: Optional[List[float]] = None,
    color_kelvin: Optional[float] = None,
    radius: Optional[float] = None,
    area_shape: Optional[Literal["SQUARE", "RECTANGLE", "DISK", "ELLIPSE"]] = None,
    area_size_x: Optional[float] = None,
    area_size_y: Optional[float] = None,
    spot_size: Optional[float] = None,
    spot_blend: Optional[float] = None,
    spot_show_cone: Optional[bool] = None,
    use_shadow: Optional[bool] = None,
    light_linking: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Manipulates Point, Sun, Spot, and Area light emitters and light linking collections."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("manage_light", params)


# ---------------------------------------------------------------------------
# 3. Objects, Collections & Constraints Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def manage_objects(
    action: Literal["create", "delete", "duplicate", "rename", "set_parent", "clear_parent", "manipulate_parent_inverse"],
    names: Optional[List[str]] = None,
    name: Optional[str] = None,
    new_name: Optional[str] = None,
    primitive_type: Optional[str] = None,
    location: Optional[List[float]] = None,
    rotation: Optional[List[float]] = None,
    scale: Optional[List[float]] = None,
    linked: bool = False,
    delete_hierarchy: bool = False,
    child_names: Optional[List[str]] = None,
    parent_name: Optional[str] = None,
    keep_transform: bool = True,
    matrix_parent_inverse: Optional[List[List[float]]] = None,
) -> Dict[str, Any]:
    """Creates, duplicates, deletes, renames, and parents objects."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("manage_objects", params)


@mcp.tool()
def manage_collections(
    action: Literal["create", "delete", "move", "rename", "link_objects", "unlink_objects", "set_visibility"],
    name: str,
    new_name: Optional[str] = None,
    parent_collection: Optional[str] = None,
    object_names: Optional[List[str]] = None,
    unlink_from_all_others: bool = False,
    hide_viewport: Optional[bool] = None,
    hide_render: Optional[bool] = None,
    hide_select: Optional[bool] = None,
    color_tag: Optional[str] = None,
) -> Dict[str, Any]:
    """Manages scene collections, organization, object links, and visibility."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("manage_collections", params)


@mcp.tool()
def transform_object(
    name: str,
    space: Literal["GLOBAL", "LOCAL", "PARENT"] = "GLOBAL",
    location: Optional[List[float]] = None,
    relative_location: bool = False,
    rotation_mode: Literal["XYZ", "XZY", "YXZ", "YZX", "ZXY", "ZYX", "QUATERNION", "AXIS_ANGLE"] = "XYZ",
    rotation: Optional[List[float]] = None,
    rotation_in_degrees: bool = False,
    relative_rotation: bool = False,
    scale: Optional[List[float]] = None,
    relative_scale: bool = False,
    delta: bool = False,
) -> Dict[str, Any]:
    """Transforms objects in global, local, or parent coordinate spaces."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("transform_object", params)


@mcp.tool()
def manage_constraints(
    action: Literal["add", "update", "remove", "get", "reorder"],
    object_name: str,
    bone_name: Optional[str] = None,
    constraint_name: Optional[str] = None,
    constraint_type: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
    new_index: Optional[int] = None,
) -> Dict[str, Any]:
    """Adds, updates, removes, or reorders object and bone constraints."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("manage_constraints", params)


# ---------------------------------------------------------------------------
# 4. Mesh, BMesh & Geometry Nodes Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def create_primitive(
    primitive_type: Literal[
        "CUBE", "UV_SPHERE", "ICO_SPHERE", "CYLINDER", "CONE", "TORUS", "GRID", "PLANE", "CIRCLE", "MONKEY", "EMPTY"
    ] = "CUBE",
    name: Optional[str] = None,
    location: Optional[List[float]] = None,
    rotation: Optional[List[float]] = None,
    scale: Optional[List[float]] = None,
    size: float = 2.0,
    radius: float = 1.0,
    depth: float = 2.0,
    segments: int = 32,
    ring_count: int = 16,
    subdivisions: int = 3,
) -> Dict[str, Any]:
    """Generates parametric mesh primitives (Cube, Sphere, Cylinder, Torus, Monkey, etc.)."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("create_primitive", params)


@mcp.tool()
def manipulate_mesh(
    object_name: str,
    operation: Literal[
        "EXTRUDE_FACES", "BEVEL", "INSET_FACES", "SUBDIVIDE", "MERGE_VERTICES",
        "BRIDGE_EDGE_LOOPS", "DISSOLVE", "BOOLEAN", "RECALCULATE_NORMALS",
        "SET_SHADING", "CREATE_ELEMENTS", "DELETE_ELEMENTS"
    ],
    vertex_indices: Optional[List[int]] = None,
    edge_indices: Optional[List[int]] = None,
    face_indices: Optional[List[int]] = None,
    translation: Optional[List[float]] = None,
    offset: float = 0.2,
    thickness: float = 0.0,
    segments: int = 2,
    profile: float = 0.5,
    merge_type: Literal["DISTANCE", "CENTER", "COLLAPSE"] = "DISTANCE",
    boolean_target: Optional[str] = None,
    boolean_operation: Literal["DIFFERENCE", "UNION", "INTERSECT"] = "DIFFERENCE",
    shading_mode: Optional[Literal["SMOOTH", "FLAT", "AUTO_SMOOTH"]] = None,
) -> Dict[str, Any]:
    """Executes high-precision bmesh modeling operations, extrusions, insets, and booleans."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("manipulate_mesh", params)


@mcp.tool()
def create_curve(
    name: str = "Curve",
    curve_type: Literal["BEZIER", "NURBS_CURVE", "PATH"] = "BEZIER",
    points: Optional[List[Dict[str, Any]]] = None,
    is_cyclic: bool = False,
    bevel_depth: float = 0.0,
    extrude: float = 0.0,
) -> Dict[str, Any]:
    """Generates Bezier, NURBS, or Path curves with programmable control points and bevels."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("create_curve", params)


@mcp.tool()
def create_text_3d(
    body: str,
    name: str = "Text3D",
    location: Optional[List[float]] = None,
    size: float = 1.0,
    extrude: float = 0.05,
    bevel_depth: float = 0.01,
) -> Dict[str, Any]:
    """Creates 3D extruded and bevelled typography."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("create_text", params)


@mcp.tool()
def manage_geometry_nodes(
    object_name: str,
    modifier_name: str = "GeometryNodes",
    tree_name: Optional[str] = None,
    nodes: Optional[List[Dict[str, Any]]] = None,
    links: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Constructs or modifies procedural Geometry Nodes graphs on target objects."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("manage_geometry_nodes", params)


# ---------------------------------------------------------------------------
# 5. Materials, Shading & UV Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def manage_materials(
    action: Literal["create", "delete", "duplicate", "assign", "set_use_nodes"],
    material_name: Optional[str] = None,
    new_name: Optional[str] = None,
    object_name: Optional[str] = None,
    slot_index: Optional[int] = None,
    face_indices: Optional[List[int]] = None,
    use_nodes: bool = True,
) -> Dict[str, Any]:
    """Creates, assigns, duplicates, and manages material slots on objects."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("manage_materials", params)


@mcp.tool()
def inspect_shader_tree(material_name: str, group_name: Optional[str] = None) -> Dict[str, Any]:
    """Inspects all nodes, sockets, and connections within a material's shader tree."""
    return default_client.send_command("inspect_shader_tree", {"material_name": material_name, "group_name": group_name})


@mcp.tool()
def manage_shader_node(
    action: Literal["create", "delete", "move"],
    material_name: str,
    node_type: Optional[str] = None,
    node_name: Optional[str] = None,
    location: Optional[List[float]] = None,
    group_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Creates, moves, or deletes shader nodes in a material."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("manage_shader_node", params)


@mcp.tool()
def manage_shader_links(
    material_name: str,
    from_node: str,
    from_socket: Union[str, int],
    to_node: str,
    to_socket: Union[str, int],
    action: Literal["link", "unlink"] = "link",
    group_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Wires or removes socket connections between shader nodes."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("manage_shader_links", params)


@mcp.tool()
def set_socket_value(
    material_name: str,
    node_name: str,
    socket_identifier: Union[str, int],
    value: Any,
    group_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Sets the default value of an input socket on a shader node (Colors, Vectors, Floats)."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("set_socket_value", params)


@mcp.tool()
def setup_procedural_texture(
    material_name: str,
    texture_type: Literal["noise", "voronoi", "wave", "brick", "checker", "gradient", "magic"] = "noise",
    coord_type: Literal["Generated", "UV", "Object", "Camera", "Window", "Reflection"] = "UV",
    location: Optional[List[float]] = None,
    rotation: Optional[List[float]] = None,
    scale: Optional[List[float]] = None,
    connect_to_principled: bool = True,
) -> Dict[str, Any]:
    """Constructs an automated TexCoord + Mapping + Procedural Texture shader pipeline."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("setup_procedural_texture", params)


@mcp.tool()
def assign_image_texture(
    material_name: str,
    image_path: str,
    pack_image: bool = False,
    target_socket: str = "Base Color",
) -> Dict[str, Any]:
    """Loads an external image asset, assigns to an Image Texture node, and links to Principled BSDF."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("assign_image_texture", params)


@mcp.tool()
def perform_uv_unwrap(
    object_name: str,
    method: Literal["smart_project", "unwrap", "cube_project", "cylinder_project", "sphere_project", "lightmap_pack"] = "smart_project",
    angle_limit: float = 66.0,
    island_margin: float = 0.02,
) -> Dict[str, Any]:
    """Executes UV unwrapping algorithms (Smart UV Project, Seam-based Unwrap, Projections)."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("perform_uv_unwrap", params)


# ---------------------------------------------------------------------------
# 6. Modifiers, Physics & Particle Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def manage_modifier(
    object_name: str,
    action: Literal["add", "remove", "apply", "reorder", "configure", "list"],
    modifier_name: Optional[str] = None,
    modifier_type: Optional[str] = None,
    new_index: Optional[int] = None,
    properties: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Manages all Blender modifiers across Generate, Deform, and Modify categories."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("manage_modifier", params)


@mcp.tool()
def setup_physics_simulation(
    object_name: str,
    physics_type: Literal["RIGID_BODY", "CLOTH", "COLLISION", "SOFT_BODY", "DYNAMIC_PAINT", "FLUID", "FORCE_FIELD"],
    action: Literal["enable", "disable", "configure", "bake"] = "enable",
    rigid_body: Optional[Dict[str, Any]] = None,
    cloth: Optional[Dict[str, Any]] = None,
    soft_body: Optional[Dict[str, Any]] = None,
    fluid: Optional[Dict[str, Any]] = None,
    force_field: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Configures physics simulations: Rigid Body, Cloth presets, Fluid, Collision, and Force Fields."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("setup_physics_simulation", params)


@mcp.tool()
def manage_particle_system(
    object_name: str,
    action: Literal["add", "remove", "configure", "list"],
    system_name: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Creates and parameterizes Emitter and Hair particle systems."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("manage_particle_system", params)


# ---------------------------------------------------------------------------
# 7. Animation, Timeline & Rigging Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def timeline_control(
    frame_start: Optional[int] = None,
    frame_end: Optional[int] = None,
    current_frame: Optional[int] = None,
    fps: Optional[int] = None,
    fps_base: Optional[float] = None,
) -> Dict[str, Any]:
    """Controls playback range, frame rates, and active playhead frame."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("timeline_control", params)


@mcp.tool()
def insert_keyframe(
    target_name: str,
    data_path: str,
    target_type: Literal["OBJECT", "MATERIAL", "WORLD", "POSE_BONE", "NODE_TREE"] = "OBJECT",
    array_index: int = -1,
    frame: Optional[float] = None,
    value: Optional[Any] = None,
    group: Optional[str] = None,
    interpolation: Optional[str] = None,
) -> Dict[str, Any]:
    """Inserts keyframes across any data path with optional values and interpolation."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("insert_keyframe", params)


@mcp.tool()
def delete_keyframe(
    target_name: str,
    data_path: str,
    target_type: Literal["OBJECT", "MATERIAL", "WORLD", "POSE_BONE", "NODE_TREE"] = "OBJECT",
    array_index: int = -1,
    frame: Optional[float] = None,
) -> Dict[str, Any]:
    """Deletes keyframes on target properties."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("delete_keyframe", params)


@mcp.tool()
def list_fcurves(target_name: str, target_type: Literal["OBJECT", "MATERIAL", "WORLD", "POSE_BONE"] = "OBJECT") -> Dict[str, Any]:
    """Lists animated F-Curves and keyframe counts on an entity."""
    return default_client.send_command("list_fcurves", {"target_name": target_name, "target_type": target_type})


@mcp.tool()
def manage_driver(
    target_name: str,
    data_path: str,
    action: Literal["add_driver", "remove_driver"] = "add_driver",
    target_type: Literal["OBJECT", "MATERIAL", "WORLD", "POSE_BONE", "NODE_TREE"] = "OBJECT",
    array_index: int = -1,
    driver_expression: Optional[str] = None,
) -> Dict[str, Any]:
    """Adds or removes mathematical expression drivers on animatable channels."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("manage_driver", params)


@mcp.tool()
def manage_armature(
    armature_name: str,
    action: Literal["create_armature", "pose_bone", "add_constraint"] = "create_armature",
    location: Optional[List[float]] = None,
    rotation_euler: Optional[List[float]] = None,
    bones: Optional[List[Dict[str, Any]]] = None,
    bone_name: Optional[str] = None,
    bone_transforms: Optional[Dict[str, Any]] = None,
    constraint_type: Optional[str] = None,
    constraint_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Builds armature bone hierarchies, adjusts pose bone transforms, and configures IK."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("manage_armature", params)


# ---------------------------------------------------------------------------
# 8. Render Engine, Compositor & Capture Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def configure_render_engine(
    engine: Literal["CYCLES", "BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "BLENDER_WORKBENCH"] = "CYCLES",
    device_type: Literal["CPU", "GPU"] = "GPU",
    render_samples: int = 128,
    viewport_samples: int = 32,
    use_noise_threshold: bool = True,
    noise_threshold: float = 0.01,
    bounces: Optional[Dict[str, int]] = None,
) -> Dict[str, Any]:
    """Configures render engine (Cycles/EEVEE/Workbench), GPU compute device, and sampling limits."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("configure_render_engine", params)


@mcp.tool()
def configure_output_and_passes(
    resolution_x: int = 1920,
    resolution_y: int = 1080,
    resolution_percentage: int = 100,
    fps: int = 24,
    output_filepath: str = "//render_output/render_",
    file_format: str = "PNG",
    passes: Optional[Dict[str, bool]] = None,
) -> Dict[str, Any]:
    """Sets image dimensions, framerate, file formats, and View Layer passes."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("configure_output_and_passes", params)


@mcp.tool()
def configure_color_management(
    display_device: str = "sRGB",
    view_transform: str = "AgX",
    look: str = "None",
    exposure: float = 0.0,
    gamma: float = 1.0,
) -> Dict[str, Any]:
    """Configures OCIO Color Management, View Transforms (AgX/Filmic), looks, and exposures."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("configure_color_management", params)


@mcp.tool()
def manage_compositor_tree(
    action: Literal["inspect", "enable", "clear", "add_node", "remove_node", "link", "set_socket_value"],
    node_type: Optional[str] = None,
    node_name: Optional[str] = None,
    location: Optional[List[float]] = None,
    from_node: Optional[str] = None,
    from_socket: Optional[str] = None,
    to_node: Optional[str] = None,
    to_socket: Optional[str] = None,
) -> Dict[str, Any]:
    """Constructs and manages the Compositor node graph."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("manage_compositor_tree", params)


@mcp.tool()
def execute_capture_or_render(
    mode: Literal["STILL", "ANIMATION", "VIEWPORT_SCREENSHOT"] = "STILL",
    camera_name: Optional[str] = None,
    frame_start: Optional[int] = None,
    frame_end: Optional[int] = None,
    shading_mode: Literal["WIREFRAME", "SOLID", "MATERIAL", "RENDERED"] = "RENDERED",
    show_overlays: bool = False,
    output_path: Optional[str] = None,
    return_base64: bool = True,
) -> Dict[str, Any]:
    """Triggers offline frame renders, multi-frame animations, or instant OpenGL viewport captures."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("execute_capture_or_render", params)


# ---------------------------------------------------------------------------
# 9. Preferences, Addons & Universal I/O Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def manage_user_preferences(
    category: Literal["system", "interface", "view", "filepaths", "keymap", "experimental", "all"] = "system",
    action: Literal["get", "set"] = "get",
    settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Inspects or modifies Blender User Preferences across all categories."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("manage_user_preferences", params)


@mcp.tool()
def manage_addon(
    module_name: str,
    action: Literal["enable", "disable", "install", "check_status"],
    filepath: Optional[str] = None,
) -> Dict[str, Any]:
    """Checks, enables, disables, or installs Blender addons."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("manage_addon", params)


@mcp.tool()
def manage_external_data(
    action: Literal["pack_all", "unpack_all", "find_missing", "make_paths_relative", "make_paths_absolute"],
    directory: Optional[str] = None,
) -> Dict[str, Any]:
    """Packs or unpacks external files, locates missing assets, and manages path relations."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("manage_external_data", params)


@mcp.tool()
def universal_import_export(
    format: Literal["fbx", "obj", "gltf", "glb", "usd", "abc", "stl", "ply", "svg", "bvh", "dae"],
    mode: Literal["import", "export"],
    filepath: str,
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Universal import/export dispatcher for FBX, OBJ, GLTF, USD, Alembic, STL, PLY, SVG, BVH, and DAE."""
    params = {
        "format": format.lower(),
        "mode": mode.lower(),
        "filepath": filepath,
        "options": options or {},
    }
    return default_client.send_command("universal_import_export", params)


def main():
    """Main entry point for running the Blender MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
