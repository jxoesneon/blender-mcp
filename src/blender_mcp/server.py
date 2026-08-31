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
    AssetManageInput,
    CameraManageInput,
    CaptureRenderInput,
    ColorAttributeManageInput,
    ColorManagementInput,
    CompositorManageInput,
    ConstraintManageInput,
    CurvesNewManageInput,
    ExtensionManageInput,
    ExternalDataInput,
    GeometryNodesInput,
    GreasePencilManageInput,
    LatticeManageInput,
    LightManageInput,
    LightprobeManageInput,
    MaterialManageInput,
    MeshManipulateInput,
    MeshPrimitiveInput,
    MetaballManageInput,
    ModifierManageInput,
    ObjectHierarchyInput,
    ObjectInfoInput,
    ParticleSystemInput,
    PhysicsSimulationInput,
    PointcloudManageInput,
    RenderConfigureInput,
    RenderOutputPassesInput,
    SceneManageInput,
    ScriptJSONInput,
    ShaderNodeManageInput,
    ShapeKeyManageInput,
    SculptSettingsInput,
    BrushManageInput,
    SimulateInputInput,
    TimelineKeyframeInput,
    TransformObjectInput,
    UniversalIOInput,
    UndoManageInput,
    UserPreferencesInput,
    UVUnwrapInput,
    UVLayerManageInput,
    VertexGroupManageInput,
    ViewportManageInput,
    VSEStripManageInput,
    WorldManageInput,
    ListPropertiesInput,
    SetupRenderShotInput,
    CreateMaterialPresetInput,
    BakeAnimationToNLAInput,
    RetargetAnimationInput,
    SetupGeoNodesPipelineInput,
    SetupAndBakePhysicsInput,
    AuditAndCleanupInput,
    UVPipelineExportInput,
    BatchMarkAssetsInput,
    AutoRigCharacterInput,
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


@mcp.tool()
def manage_undo(action: str, steps: int = 1) -> Dict[str, Any]:
    """Performs undo/redo control via bpy.ops.ed (undo, redo, undo_history, push_undo_step)."""
    return default_client.send_command("manage_undo", {"action": action, "steps": steps})


@mcp.tool()
def get_object_info(object_name: str) -> Dict[str, Any]:
    """Returns a structured JSON dump of an object's key properties and data."""
    return default_client.send_command("get_object_info", {"object_name": object_name})


@mcp.tool()
def list_properties(path: str, include_readonly: bool = False) -> Dict[str, Any]:
    """Enumerates all settable properties on a data path with types and current values."""
    return default_client.send_command(
        "list_properties",
        {"path": path, "include_readonly": include_readonly},
    )


@mcp.tool()
def simulate_input(
    event_type: str,
    mouse_x: Optional[int] = None,
    mouse_y: Optional[int] = None,
    key: Optional[str] = None,
    value: str = "PRESS",
    region_name: str = "WINDOW",
) -> Dict[str, Any]:
    """Simulates mouse/keyboard events for modal operators (limited in headless Blender)."""
    return default_client.send_command(
        "simulate_input",
        {
            "event_type": event_type,
            "mouse_x": mouse_x,
            "mouse_y": mouse_y,
            "key": key,
            "value": value,
            "region_name": region_name,
        },
    )


@mcp.tool()
def exec_script_json(script: str, use_transaction_rollback: bool = True) -> Dict[str, Any]:
    """Executes a Python script ending with a `result` variable; returns structured JSON instead of stdout."""
    return default_client.send_command(
        "exec_script_json",
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
def manage_view_layers(
    action: Literal["list", "add", "remove", "set_active", "configure"] = "list",
    layer_name: Optional[str] = None,
    new_name: Optional[str] = None,
    settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Manages scene view layers for compositing workflows: list, add, remove, set active, and configure settings."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("manage_view_layers", params)


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


@mcp.tool()
def manage_lightprobes(
    action: Literal["create", "delete", "list", "configure"] = "list",
    lightprobe_name: Optional[str] = None,
    probe_type: Literal["CUBEMAP", "PLANAR", "GRID"] = "CUBEMAP",
    location: Optional[List[float]] = None,
    rotation: Optional[List[float]] = None,
    properties: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Manages EEVEE light probes (reflection cubemaps, planar reflections, irradiance grids) for global illumination."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("manage_lightprobes", params)


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


@mcp.tool()
def manage_vertex_groups(
    object_name: str,
    action: Literal["list", "add", "remove", "assign", "remove_from", "set_active", "rename"],
    group_name: Optional[str] = None,
    new_name: Optional[str] = None,
    vertex_indices: Optional[List[int]] = None,
    weight: float = 1.0,
) -> Dict[str, Any]:
    """Manages vertex groups on an object for rigging and weight painting."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("manage_vertex_groups", params)


@mcp.tool()
def manage_shape_keys(
    object_name: str,
    action: Literal["list", "add", "remove", "set_value", "set_active", "rename"],
    key_name: Optional[str] = None,
    new_name: Optional[str] = None,
    value: Optional[float] = None,
    shape_key_type: Literal["BASIS", "FROM_MIX"] = "BASIS",
) -> Dict[str, Any]:
    """Manages shape keys (morph targets) on mesh objects for facial animation and morphing."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("manage_shape_keys", params)


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
def create_volume(
    name: str = "Volume",
) -> Dict[str, Any]:
    """Creates an empty Volume data-block object for OpenVDB data."""
    return default_client.send_command("create_volume", {"name": name})


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


@mcp.tool()
def manage_grease_pencil(
    action: Literal["create", "list_layers", "add_layer", "remove_layer", "set_active_layer", "configure_layer", "add_stroke", "list_strokes", "set_material"],
    object_name: Optional[str] = None,
    layer_name: Optional[str] = None,
    new_name: Optional[str] = None,
    points: Optional[List[Dict[str, Any]]] = None,
    material_name: Optional[str] = None,
    properties: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Manages Grease Pencil objects: layers, strokes, points, and materials for 2D animation."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("manage_grease_pencil", params)


@mcp.tool()
def manage_curves_new(
    action: Literal["create", "list", "delete", "add_points", "set_attribute", "get_info"] = "list",
    object_name: Optional[str] = None,
    curve_count: Optional[int] = None,
    point_count: Optional[int] = None,
    attribute_name: Optional[str] = None,
    attribute_values: Optional[List[Any]] = None,
    attribute_domain: Optional[Literal["POINT", "CURVE"]] = "POINT",
) -> Dict[str, Any]:
    """Manages Blender 5.x new Curves data type (hair curves, new curve objects)."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("manage_curves_new", params)


@mcp.tool()
def manage_pointclouds(
    action: Literal["create", "list", "delete", "add_points", "set_attribute", "get_info"] = "list",
    object_name: Optional[str] = None,
    point_count: Optional[int] = None,
    attribute_name: Optional[str] = None,
    attribute_values: Optional[List[Any]] = None,
    attribute_domain: Optional[Literal["POINT"]] = "POINT",
) -> Dict[str, Any]:
    """Manages Blender 5.x Point Cloud data type: create, list, delete, add points, set attributes."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("manage_pointclouds", params)


@mcp.tool()
def manage_lattices(
    action: Literal["create", "delete", "list", "set_points", "get_info", "assign_to_object"] = "list",
    lattice_name: Optional[str] = None,
    object_name: Optional[str] = None,
    resolution_u: int = 2,
    resolution_v: int = 2,
    resolution_w: int = 2,
    points: Optional[List[List[float]]] = None,
) -> Dict[str, Any]:
    """Manages lattice data-blocks and lattice modifiers: create, delete, list, set points, get info, and assign to objects."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("manage_lattices", params)


@mcp.tool()
def manage_metaballs(
    action: Literal["create", "delete", "list", "add_element", "set_render_resolution", "set_viewport_resolution", "get_info"] = "list",
    metaball_name: Optional[str] = None,
    element_type: Optional[Literal["BALL", "CAPSULE", "CUBE", "PLANE", "ELLIPSOID"]] = None,
    location: Optional[List[float]] = None,
    rotation: Optional[List[float]] = None,
    scale: Optional[List[float]] = None,
    render_resolution: Optional[float] = None,
    viewport_resolution: Optional[float] = None,
) -> Dict[str, Any]:
    """Manages metaball objects and elements: create, delete, list, add elements, set resolutions, and get info."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("manage_metaballs", params)


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


@mcp.tool()
def manage_color_attributes(
    object_name: str,
    action: Literal["list", "add", "remove", "set_active", "set_values"] = "list",
    attribute_name: Optional[str] = None,
    domain: Optional[Literal["POINT", "CORNER"]] = "POINT",
    data_type: Optional[Literal["FLOAT_COLOR", "BYTE_COLOR"]] = "FLOAT_COLOR",
    vertex_indices: Optional[List[int]] = None,
    color: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """Manages color attributes (vertex colors) on mesh objects: list, add, remove, set active, set values."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("manage_color_attributes", params)


@mcp.tool()
def manage_uv_layers(
    object_name: str,
    action: Literal["list", "add", "remove", "set_active", "rename", "stitch"] = "list",
    uv_name: Optional[str] = None,
    new_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Manages UV layers/maps on mesh objects: list, add, remove, set active, rename, and stitch islands."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("manage_uv_layers", params)


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
    action: Literal["enable", "disable", "configure", "bake", "free_bake", "get_bake_status", "set_cache_path"] = "enable",
    rigid_body: Optional[Dict[str, Any]] = None,
    cloth: Optional[Dict[str, Any]] = None,
    soft_body: Optional[Dict[str, Any]] = None,
    fluid: Optional[Dict[str, Any]] = None,
    force_field: Optional[Dict[str, Any]] = None,
    cache_path: Optional[str] = None,
    bake_frame_start: Optional[int] = None,
    bake_frame_end: Optional[int] = None,
) -> Dict[str, Any]:
    """Configures physics simulations: Rigid Body, Cloth presets, Fluid, Collision, Force Fields, baking, and cache management."""
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
    action: Literal["add_driver", "remove_driver", "add_variable", "remove_variable", "set_expression", "get_info"] = "add_driver",
    target_type: Literal["OBJECT", "MATERIAL", "WORLD", "POSE_BONE", "NODE_TREE"] = "OBJECT",
    array_index: int = -1,
    driver_expression: Optional[str] = None,
    variable_name: Optional[str] = None,
    variable_type: Optional[Literal["SINGLE_PROP", "TRANSFORMS", "ROTATION_DIFF", "AVERAGE"]] = None,
    target_path: Optional[str] = None,
    target_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Adds or removes mathematical expression drivers on animatable channels, manages driver variables and expressions."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("manage_driver", params)


@mcp.tool()
def modify_keyframe(
    target_name: str,
    data_path: str,
    frame: float,
    target_type: Literal["OBJECT", "MATERIAL", "WORLD", "POSE_BONE", "NODE_TREE"] = "OBJECT",
    array_index: int = 0,
    new_frame: Optional[float] = None,
    new_value: Optional[float] = None,
    interpolation: Optional[str] = None,
) -> Dict[str, Any]:
    """Modifies existing keyframes: move frame, change value, or set interpolation."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("modify_keyframe", params)


@mcp.tool()
def manage_nla(
    target_name: str,
    action: Literal["push_nla", "configure_nla"] = "push_nla",
    track_name: Optional[str] = None,
    strip_name: Optional[str] = None,
    nla_properties: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Manages Non-Linear Animation tracks and strips."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("manage_nla", params)


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
    engine: Literal["CYCLES", "BLENDER_EEVEE", "BLENDER_WORKBENCH"] = "CYCLES",
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
    filepath: Optional[str] = None,
    options: Optional[Dict[str, Any]] = None,
    action: Literal["execute", "get_format_options"] = "execute",
) -> Dict[str, Any]:
    """Universal import/export dispatcher for FBX, OBJ, GLTF, USD, Alembic, STL, PLY, SVG, BVH, and DAE. Supports get_format_options to list known valid options per format."""
    params = {
        "format": format.lower(),
        "mode": mode.lower(),
        "filepath": filepath,
        "options": options or {},
        "action": action,
    }
    return default_client.send_command("universal_import_export", params)


# ---------------------------------------------------------------------------
# 10. Video Sequence Editor (VSE) Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def manage_vse_strips(
    action: Literal["add", "remove", "list", "configure", "set_channel", "move"],
    strip_name: Optional[str] = None,
    strip_type: Optional[Literal[
        "MOVIE", "SOUND", "IMAGE", "SCENE", "COLOR", "TEXT",
        "ADJUSTMENT", "SPEED", "TRANSFORM", "GAUSSIAN_BLUR",
        "CROSS", "GAMMA_CROSS", "SINGLE_CROSS", "WIPE",
        "ADD", "SUB", "MUL", "ALPHA_OVER", "ALPHA_UNDER", "OVER_DROP"
    ]] = None,
    filepath: Optional[str] = None,
    scene_name: Optional[str] = None,
    seq1: Optional[str] = None,
    seq2: Optional[str] = None,
    color: Optional[List[float]] = None,
    channel: int = 1,
    frame_start: Optional[int] = None,
    frame_end: Optional[int] = None,
    properties: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Manages Video Sequence Editor strips: add, remove, list, configure, set channel, and move."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("manage_vse_strips", params)


@mcp.tool()
def manage_sculpt_settings(
    action: Literal["enter_sculpt", "exit_sculpt", "set_symmetry", "set_dyntopo", "set_remesh", "get_info"],
    object_name: Optional[str] = None,
    symmetry_x: Optional[bool] = None,
    symmetry_y: Optional[bool] = None,
    symmetry_z: Optional[bool] = None,
    use_dyntopo: Optional[bool] = None,
    detail_size: Optional[float] = None,
    remesh_voxel_size: Optional[float] = None,
    remesh_adaptivity: Optional[float] = None,
) -> Dict[str, Any]:
    """Manages sculpt mode settings: enter/exit sculpt, symmetry axes, dynamic topology, and voxel remesh."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("manage_sculpt_settings", params)


@mcp.tool()
def manage_brushes(
    action: Literal["list", "create", "delete", "configure", "set_active"],
    brush_name: Optional[str] = None,
    new_name: Optional[str] = None,
    brush_type: Optional[Literal["SCULPT", "PAINT", "WEIGHT", "TEXTURE", "GPENCIL"]] = None,
    properties: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Manages brush data-blocks for sculpt/paint modes: list, create, delete, configure, and set active."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("manage_brushes", params)


# ---------------------------------------------------------------------------
# 11. Asset & Extension Management Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def manage_assets(
    action: Literal["mark", "clear", "list", "set_catalog", "create_catalog", "list_catalogs", "save_catalogs"],
    asset_type: Literal["OBJECT", "MATERIAL", "COLLECTION", "NODE_TREE", "WORLD", "SCENE"] = "OBJECT",
    asset_name: Optional[str] = None,
    catalog_name: Optional[str] = None,
    catalog_uuid: Optional[str] = None,
    library_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Marks data-blocks as assets, manages asset catalogs, and lists asset libraries."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("manage_assets", params)


@mcp.tool()
def manage_extensions(
    action: Literal["list", "install", "uninstall", "enable", "disable", "refresh", "sync"],
    package_name: Optional[str] = None,
    filepath: Optional[str] = None,
    repo_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Manages Blender 5.x extension packages: list, install, uninstall, enable, disable, refresh, and sync."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("manage_extensions", params)


# ---------------------------------------------------------------------------
# 11. Timeline Markers, Cache Files & Pose Library Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def manage_markers(
    action: Literal["add", "remove", "list", "set_name", "set_frame", "set_camera"] = "list",
    marker_name: Optional[str] = None,
    frame: Optional[int] = None,
    new_name: Optional[str] = None,
    camera_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Manages timeline markers: add, remove, list, rename, move frame, and bind cameras."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("manage_markers", params)


@mcp.tool()
def manage_cache_files(
    action: Literal["load", "list", "reload", "remove"] = "list",
    filepath: Optional[str] = None,
    cache_name: Optional[str] = None,
    cache_type: Optional[Literal["ALEMBIC", "USD"]] = "ALEMBIC",
) -> Dict[str, Any]:
    """Manages cache files (Alembic/USD): load, list, reload, and remove."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("manage_cache_files", params)


@mcp.tool()
def manage_pose_library(
    action: Literal["create", "add_pose", "list_poses", "apply_pose", "remove_pose"] = "list_poses",
    armature_name: Optional[str] = None,
    pose_name: Optional[str] = None,
    action_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Manages pose libraries: create, add current pose, list, apply, and remove poses."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("manage_pose_library", params)


# ---------------------------------------------------------------------------
# Composite Workflow Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def setup_render_shot(
    target_object: str,
    camera_name: Optional[str] = "ShotCamera",
    camera_location: Optional[List[float]] = None,
    render_engine: Literal["CYCLES", "BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"] = "BLENDER_EEVEE",
    resolution: List[int] = [1920, 1080],
    samples: int = 64,
    output_filepath: str = "/tmp/render_shot_",
    key_light_color: List[float] = [1.0, 1.0, 1.0],
    key_light_energy: float = 1000.0,
    fill_light_color: List[float] = [0.8, 0.85, 1.0],
    fill_light_energy: float = 300.0,
    rim_light_color: List[float] = [1.0, 0.9, 0.8],
    rim_light_energy: float = 500.0,
    dof_focus_distance: Optional[float] = None,
    focal_length: float = 50.0,
    auto_render: bool = False,
) -> Dict[str, Any]:
    """Sets up a complete render shot: camera auto-framing, 3-point lighting, render settings, and optional render."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("setup_render_shot", params)


@mcp.tool()
def create_material_preset(
    preset: Literal["rough_stone", "brushed_metal", "car_paint", "glass", "emissive", "subsurface_skin", "wood", "ice", "lava", "hologram"],
    material_name: Optional[str] = None,
    object_name: Optional[str] = None,
    base_color: Optional[List[float]] = None,
    roughness: Optional[float] = None,
    metallic: Optional[float] = None,
    emission_color: Optional[List[float]] = None,
    emission_strength: Optional[float] = None,
    scale: float = 1.0,
) -> Dict[str, Any]:
    """Creates a procedural material from a named preset with pre-wired shader nodes."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("create_material_preset", params)


@mcp.tool()
def bake_animation_to_nla(
    action_name: str,
    track_name: Optional[str] = None,
    object_name: Optional[str] = None,
    frame_start: int = 1,
    frame_end: int = 250,
    interpolation: Literal["BEZIER", "LINEAR", "CONSTANT"] = "BEZIER",
    clean_keyframes: bool = True,
    blend_mode: Literal["REPLACE", "ADD", "SUBTRACT", "MULTIPLY"] = "REPLACE",
    blend_in: int = 0,
    blend_out: int = 0,
    mute_other_tracks: bool = True,
    use_auto_blend: bool = False,
) -> Dict[str, Any]:
    """Finalizes an animation action into an NLA track with interpolation, cleanup, and blend settings."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("bake_animation_to_nla", params)


@mcp.tool()
def retarget_animation(
    source_armature: str,
    target_armature: str,
    action_name: Optional[str] = None,
    bone_mapping: Optional[Dict[str, str]] = None,
    retarget_mode: Literal["ROTATION_ONLY", "LOCATION_AND_ROTATION"] = "ROTATION_ONLY",
    bake_to_target: bool = True,
    bake_frame_start: int = 1,
    bake_frame_end: int = 250,
    remove_constraints_after_bake: bool = True,
    use_offset_bones: bool = True,
) -> Dict[str, Any]:
    """Retargets animation from a source armature to a target armature with auto bone matching and baking."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("retarget_animation", params)


@mcp.tool()
def setup_geo_nodes_pipeline(
    object_name: str,
    modifier_name: str = "GeoNodesPipeline",
    node_group_name: str = "PipelineGroup",
    pipeline_type: Literal["scatter_instances", "subdivide_displace", "boolean_array", "wave_deform", "point_instance", "custom"] = "scatter_instances",
    instance_object: Optional[str] = None,
    instance_count: int = 100,
    subdivisions: int = 3,
    displace_strength: float = 1.0,
    wave_amplitude: float = 0.5,
    wave_frequency: float = 2.0,
    array_count: int = 5,
    array_offset: List[float] = [2.0, 0.0, 0.0],
    custom_node_count: int = 5,
    set_modifier_inputs: Optional[Dict[str, Any]] = None,
    realize_instances: bool = False,
    output_object: Optional[str] = None,
) -> Dict[str, Any]:
    """Creates a Geometry Nodes modifier pipeline with pre-wired nodes for common procedural patterns."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("setup_geo_nodes_pipeline", params)


@mcp.tool()
def setup_and_bake_physics(
    object_name: str,
    physics_type: Literal["CLOTH", "FLUID", "RIGID_BODY", "SOFT_BODY", "COLLISION", "DYNAMIC_PAINT"] = "CLOTH",
    bake: bool = True,
    frame_start: int = 1,
    frame_end: int = 250,
    cache_directory: Optional[str] = "/tmp/blender_physics_cache",
    substeps: int = 10,
    quality: int = 5,
    preset: Optional[Literal["COTTON", "SILK", "DENIM", "LEATHER", "RUBBER"]] = None,
    mass: float = 1.0,
    collision_shape: Literal["BOX", "SPHERE", "CONVEX_HULL", "MESH"] = "MESH",
    fluid_type: Literal["DOMAIN", "FLOW", "EFFECTOR"] = "DOMAIN",
    poll_interval: float = 2.0,
    poll_timeout: float = 300.0,
) -> Dict[str, Any]:
    """Configures physics simulation on an object and bakes the cache with status polling."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("setup_and_bake_physics", params)


@mcp.tool()
def audit_and_cleanup_scene(
    audit_only: bool = True,
    purge_orphans: bool = False,
    pack_textures: bool = False,
    make_paths_relative: bool = False,
    find_missing_files: bool = False,
    search_directory: Optional[str] = None,
    remove_unused_materials: bool = False,
    remove_unused_meshes: bool = False,
    merge_duplicate_materials: bool = False,
    report_objects: bool = True,
    report_materials: bool = True,
    report_textures: bool = True,
    report_performance: bool = True,
) -> Dict[str, Any]:
    """Audits a Blender scene for orphans, missing files, duplicates, and performance issues, with optional cleanup."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("audit_and_cleanup_scene", params)


@mcp.tool()
def uv_pipeline_export(
    object_name: str,
    uv_method: Literal["SMART", "ANGLE_BASED", "CONFORMAL", "CUBE_PROJECTION"] = "SMART",
    mark_seams_auto: bool = True,
    seam_angle: float = 88.0,
    pack_islands: bool = True,
    pack_margin: float = 0.01,
    export_uv_layout: bool = False,
    uv_layout_path: str = "/tmp/uv_layout.png",
    uv_layout_size: List[int] = [1024, 1024],
    export_format: Optional[Literal["fbx", "obj", "gltf", "glb", "stl", "ply"]] = None,
    export_path: str = "/tmp/exported_mesh",
    export_params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """UV unwraps a mesh and exports it with optional UV layout image in one pipeline."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("uv_pipeline_export", params)


@mcp.tool()
def batch_mark_assets(
    object_filter: Optional[Literal["MESH", "CAMERA", "LIGHT", "ARMATURE", "ALL"]] = "MESH",
    name_pattern: Optional[str] = None,
    catalog_name: Optional[str] = None,
    catalog_path: Optional[str] = None,
    tags: Optional[List[str]] = None,
    generate_previews: bool = True,
    preview_angle: List[float] = [0.6, 0.0, 0.8],
    unmark_first: bool = False,
    only_unmarked: bool = False,
) -> Dict[str, Any]:
    """Batch marks objects as assets with tags, catalog assignment, and preview generation."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("batch_mark_assets", params)


@mcp.tool()
def auto_rig_character(
    mesh_object: str,
    armature_name: str = "AutoRig",
    rig_type: Literal["BIPED", "QUADRUPED", "HUMANOID", "SIMPLE"] = "BIPED",
    bone_count: int = 5,
    auto_weights: bool = True,
    add_ik: bool = True,
    ik_pole_offset: float = 0.5,
    set_bone_rotation_mode: Literal["XYZ", "QUATERNION"] = "XYZ",
    parent_mesh: bool = True,
    add_root_bone: bool = True,
) -> Dict[str, Any]:
    """Automatically rigs a character mesh with an armature, bone placement, IK constraints, and auto weights."""
    params = {k: v for k, v in locals().items() if v is not None}
    return default_client.send_command("auto_rig_character", params)


def main():
    """Main entry point for running the Blender MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
