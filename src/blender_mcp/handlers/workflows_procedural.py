"""
Composite workflow handlers for procedural geometry and physics simulation.
"""

from __future__ import annotations

import math
import os
import time
from typing import Any, Dict, List, Optional, Tuple

from blender_mcp.exceptions import BlenderExecutionError
from blender_mcp.handlers.base import BaseHandler


# Valid pipeline types for ``setup_geo_nodes_pipeline``.
_VALID_PIPELINE_TYPES = (
    "scatter_instances",
    "subdivide_displace",
    "boolean_array",
    "wave_deform",
    "point_instance",
    "custom",
)

# Valid physics types for ``setup_and_bake_physics``.
_VALID_PHYSICS_TYPES = (
    "CLOTH",
    "FLUID",
    "RIGID_BODY",
    "SOFT_BODY",
    "COLLISION",
    "DYNAMIC_PAINT",
)

# Cloth presets reused from ``ModifiersPhysicsHandler`` for consistency.
_CLOTH_PRESETS = {
    "COTTON": {
        "mass": 0.3,
        "tension_stiffness": 15.0,
        "compression_stiffness": 15.0,
        "shear_stiffness": 5.0,
        "bending_stiffness": 0.5,
    },
    "SILK": {
        "mass": 0.15,
        "tension_stiffness": 20.0,
        "compression_stiffness": 15.0,
        "shear_stiffness": 2.0,
        "bending_stiffness": 0.05,
    },
    "DENIM": {
        "mass": 1.0,
        "tension_stiffness": 40.0,
        "compression_stiffness": 40.0,
        "shear_stiffness": 10.0,
        "bending_stiffness": 10.0,
    },
    "LEATHER": {
        "mass": 0.4,
        "tension_stiffness": 45.0,
        "compression_stiffness": 45.0,
        "shear_stiffness": 25.0,
        "bending_stiffness": 1.5,
    },
    "RUBBER": {
        "mass": 3.0,
        "tension_stiffness": 15.0,
        "compression_stiffness": 15.0,
        "shear_stiffness": 15.0,
        "bending_stiffness": 25.0,
    },
}


class ProceduralWorkflowsHandler(BaseHandler):
    """Composite workflow handlers building procedural geometry node pipelines and physics simulations."""

    # ------------------------------------------------------------------
    # Geometry Nodes pipeline
    # ------------------------------------------------------------------
    @classmethod
    def setup_geo_nodes_pipeline(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create and wire a Geometry Nodes modifier pipeline on a target object.

        Builds a node group containing the requested *pipeline_type* graph, assigns it
        to a new Geometry Nodes modifier, optionally sets named modifier inputs, and
        optionally duplicates the object so the modifier can be applied to a copy.

        Returns a dictionary describing the node group, modifier, created nodes,
        and the group's input/output socket names.
        """
        bpy = cls.get_bpy()

        object_name: str = params["object_name"]
        modifier_name: str = params.get("modifier_name", "GeoNodesPipeline")
        node_group_name: str = params.get("node_group_name", "PipelineGroup")
        pipeline_type: str = params.get("pipeline_type", "scatter_instances")
        realize_instances: bool = params.get("realize_instances", False)
        set_modifier_inputs: Optional[Dict[str, Any]] = params.get("set_modifier_inputs")
        output_object: Optional[str] = params.get("output_object")

        if pipeline_type not in _VALID_PIPELINE_TYPES:
            raise BlenderExecutionError(
                f"Invalid pipeline_type '{pipeline_type}'. Expected one of: {', '.join(_VALID_PIPELINE_TYPES)}."
            )

        obj = cls.get_object(object_name)

        with cls.transaction(f"setup_geo_nodes_pipeline:{pipeline_type}"):
            node_group = cls._create_node_group(node_group_name)
            nodes_created, input_sockets, output_sockets = cls._build_pipeline(
                node_group,
                pipeline_type,
                params,
            )

            if realize_instances:
                cls._insert_realize_instances(node_group)

            # Refresh socket metadata after all nodes are wired.
            input_sockets = cls._list_group_inputs(node_group)
            output_sockets = cls._list_group_outputs(node_group)

            target_obj = obj
            if output_object:
                target_obj = cls._duplicate_object(obj, output_object)

            modifier = cls._assign_modifier(target_obj, modifier_name, node_group)

            if set_modifier_inputs:
                cls._set_modifier_inputs(modifier, set_modifier_inputs)

        return {
            "status": "success",
            "node_group": node_group.name,
            "modifier": modifier.name,
            "object": target_obj.name,
            "pipeline_type": pipeline_type,
            "nodes_created": nodes_created,
            "input_sockets": input_sockets,
            "output_sockets": output_sockets,
            "realize_instances": realize_instances,
            "output_object": output_object,
        }

    # ------------------------------------------------------------------
    # Node group helpers
    # ------------------------------------------------------------------
    @classmethod
    def _create_node_group(cls, name: str) -> Any:
        """Create a fresh geometry node group, removing any pre-existing group with the same name."""
        bpy = cls.get_bpy()
        existing = bpy.data.node_groups.get(name)
        if existing:
            bpy.data.node_groups.remove(existing)
        try:
            node_group = bpy.data.node_groups.new(name=name, type="GEOMETRY")
        except TypeError:
            # Older Blender versions use the legacy signature.
            node_group = bpy.data.node_groups.new(name, "GeometryNodeTree")
        return node_group

    @classmethod
    def _add_node(cls, node_group: Any, node_type: str, name: Optional[str] = None, location: Optional[Tuple[float, float]] = None) -> Any:
        """Add a node to *node_group*, returning ``None`` if the type is unavailable."""
        nodes = node_group.nodes
        try:
            node = nodes.new(type=node_type)
        except Exception:
            return None
        if name:
            node.name = name
        if location is not None:
            node.location = location
        return node

    @classmethod
    def _link(cls, node_group: Any, from_socket: Any, to_socket: Any) -> None:
        """Safely link two sockets, ignoring failures."""
        if from_socket is None or to_socket is None:
            return
        try:
            node_group.links.new(from_socket, to_socket)
        except Exception:
            pass

    @classmethod
    def _add_group_socket(cls, node_group: Any, name: str, socket_type: str, in_out: str = "INPUT") -> Any:
        """Add a socket to a node group interface, compatible with Blender 5.x (interface API) and 4.x (inputs/outputs API)."""
        # Blender 5.x: use ng.interface.new_socket()
        if hasattr(node_group, "interface") and hasattr(node_group.interface, "new_socket"):
            try:
                sock = node_group.interface.new_socket(name=name, in_out=in_out, socket_type=socket_type)
                return sock
            except Exception:
                pass
        # Blender 4.x fallback: use ng.inputs.new() / ng.outputs.new()
        try:
            if in_out == "INPUT":
                return node_group.inputs.new(name=name, type=socket_type)
            else:
                return node_group.outputs.new(name=name, type=socket_type)
        except Exception:
            return None

    @classmethod
    def _list_group_inputs(cls, node_group: Any) -> List[str]:
        """List input socket names, compatible with both API versions."""
        if hasattr(node_group, "interface"):
            return [s.name for s in node_group.interface.items_tree if s.in_out == "INPUT" and s.item_type == "SOCKET"]
        if hasattr(node_group, "inputs"):
            return [s.name for s in node_group.inputs]
        return []

    @classmethod
    def _list_group_outputs(cls, node_group: Any) -> List[str]:
        """List output socket names, compatible with both API versions."""
        if hasattr(node_group, "interface"):
            return [s.name for s in node_group.interface.items_tree if s.in_out == "OUTPUT" and s.item_type == "SOCKET"]
        if hasattr(node_group, "outputs"):
            return [s.name for s in node_group.outputs]
        return []

    @classmethod
    def _socket(cls, node: Any, direction: str, name: str, index: int = 0) -> Any:
        """Resolve a socket by name with an index fallback."""
        if node is None:
            return None
        sockets = node.inputs if direction == "input" else node.outputs
        sock = sockets.get(name) if hasattr(sockets, "get") else None
        if sock is not None:
            return sock
        try:
            return sockets[index]
        except Exception:
            return None

    @classmethod
    def _geometry_out(cls, node: Any) -> Any:
        """Return the primary geometry output socket of *node*."""
        if node is None:
            return None
        for name in ("Geometry", "Mesh", "Instances", "Points"):
            sock = node.outputs.get(name) if hasattr(node.outputs, "get") else None
            if sock is not None:
                return sock
        try:
            return node.outputs[0]
        except Exception:
            return None

    @classmethod
    def _geometry_in(cls, node: Any) -> Any:
        """Return the primary geometry input socket of *node*."""
        if node is None:
            return None
        for name in ("Geometry", "Mesh", "Points", "Instances"):
            sock = node.inputs.get(name) if hasattr(node.inputs, "get") else None
            if sock is not None:
                return sock
        try:
            return node.inputs[0]
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Pipeline builders
    # ------------------------------------------------------------------
    @classmethod
    def _build_pipeline(
        cls,
        node_group: Any,
        pipeline_type: str,
        params: Dict[str, Any],
    ) -> Tuple[List[str], List[str], List[str]]:
        """Dispatch to the appropriate pipeline builder and return node/socket metadata."""
        builder = {
            "scatter_instances": cls._build_scatter_instances,
            "subdivide_displace": cls._build_subdivide_displace,
            "boolean_array": cls._build_boolean_array,
            "wave_deform": cls._build_wave_deform,
            "point_instance": cls._build_point_instance,
            "custom": cls._build_custom,
        }[pipeline_type]
        return builder(node_group, params)

    @classmethod
    def _ensure_group_io(cls, node_group: Any) -> Tuple[Any, Any]:
        """Ensure Group Input and Group Output nodes exist, returning them."""
        group_in = None
        group_out = None
        for node in node_group.nodes:
            if node.type == "GROUP_INPUT":
                group_in = node
            elif node.type == "GROUP_OUTPUT":
                group_out = node
        if group_in is None:
            group_in = cls._add_node(node_group, "NodeGroupInput", name="Group Input", location=(-400, 0))
        if group_out is None:
            group_out = cls._add_node(node_group, "NodeGroupOutput", name="Group Output", location=(400, 0))
        # Ensure a geometry socket exists on the group interface.
        existing_inputs = cls._list_group_inputs(node_group)
        if "Geometry" not in existing_inputs:
            cls._add_group_socket(node_group, "Geometry", "NodeSocketGeometry", "INPUT")
        existing_outputs = cls._list_group_outputs(node_group)
        if "Geometry" not in existing_outputs:
            cls._add_group_socket(node_group, "Geometry", "NodeSocketGeometry", "OUTPUT")
        return group_in, group_out

    @classmethod
    def _build_scatter_instances(
        cls,
        node_group: Any,
        params: Dict[str, Any],
    ) -> Tuple[List[str], List[str], List[str]]:
        """Build the scatter_instances pipeline: Mesh to Points -> Instance on Points."""
        instance_object: Optional[str] = params.get("instance_object")
        instance_count: int = int(params.get("instance_count", 100))

        group_in, group_out = cls._ensure_group_io(node_group)

        mesh_to_points = cls._add_node(
            node_group, "GeometryNodeMeshToPoints", name="Mesh to Points", location=(-200, 100)
        )
        instance_on_points = cls._add_node(
            node_group, "GeometryNodeInstanceOnPoints", name="Instance on Points", location=(0, 100)
        )
        object_info = cls._add_node(
            node_group, "GeometryNodeObjectInfo", name="Object Info", location=(-200, -150)
        )

        nodes_created = ["Group Input", "Mesh to Points", "Instance on Points", "Group Output"]
        if object_info:
            nodes_created.append("Object Info")

        # Wire geometry flow.
        cls._link(node_group, cls._geometry_out(group_in), cls._geometry_in(mesh_to_points))
        cls._link(node_group, cls._geometry_out(mesh_to_points), cls._geometry_in(instance_on_points))
        cls._link(node_group, cls._geometry_out(instance_on_points), cls._geometry_in(group_out))

        # Wire instance object.
        if object_info and instance_object:
            try:
                target = cls.get_object(instance_object)
                object_info.inputs["Object"].default_value = target
            except Exception:
                pass
            cls._link(
                node_group,
                cls._socket(object_info, "output", "Instances"),
                cls._socket(instance_on_points, "input", "Instance"),
            )

        # Optionally expose instance count as a group input.
        try:
            count_sock = cls._add_group_socket(node_group, "Instance Count", "NodeSocketInt", "INPUT")
            count_sock.default_value = instance_count
            cls._link(
                node_group,
                cls._socket(group_in, "output", "Instance Count"),
                cls._socket(instance_on_points, "input", "Selection"),
            )
        except Exception:
            pass

        input_sockets = cls._list_group_inputs(node_group)
        output_sockets = cls._list_group_outputs(node_group)
        return nodes_created, input_sockets, output_sockets

    @classmethod
    def _build_subdivide_displace(
        cls,
        node_group: Any,
        params: Dict[str, Any],
    ) -> Tuple[List[str], List[str], List[str]]:
        """Build the subdivide_displace pipeline: Subdivide Mesh -> Set Position (noise offset)."""
        subdivisions: int = int(params.get("subdivisions", 3))
        displace_strength: float = float(params.get("displace_strength", 1.0))

        group_in, group_out = cls._ensure_group_io(node_group)

        subdivide = cls._add_node(
            node_group, "GeometryNodeSubdivideMesh", name="Subdivide Mesh", location=(-200, 100)
        )
        if subdivide is None:
            subdivide = cls._add_node(
                node_group, "GeometryNodeSubdivisionSurface", name="Subdivide Mesh", location=(-200, 100)
            )
        set_position = cls._add_node(
            node_group, "GeometryNodeSetPosition", name="Set Position", location=(100, 100)
        )
        noise_tex = cls._add_node(
            node_group, "ShaderNodeTexNoise", name="Noise Texture", location=(-100, -150)
        )
        separate_xyz = cls._add_node(
            node_group, "ShaderNodeSeparateXYZ", name="Separate XYZ", location=(80, -150)
        )

        nodes_created = ["Group Input", "Subdivide Mesh", "Set Position", "Group Output"]
        if noise_tex:
            nodes_created.append("Noise Texture")
        if separate_xyz:
            nodes_created.append("Separate XYZ")

        # Geometry flow.
        cls._link(node_group, cls._geometry_out(group_in), cls._geometry_in(subdivide))
        cls._link(node_group, cls._geometry_out(subdivide), cls._geometry_in(set_position))
        cls._link(node_group, cls._geometry_out(set_position), cls._geometry_in(group_out))

        # Displacement: Noise -> Separate XYZ -> Set Position offset.
        if noise_tex and separate_xyz and set_position:
            cls._link(
                node_group,
                cls._socket(noise_tex, "output", "Fac"),
                cls._socket(separate_xyz, "input", "Vector"),
            )
            try:
                strength_sock = cls._add_group_socket(node_group, "Displace Strength", "NodeSocketFloat", "INPUT")
                strength_sock.default_value = displace_strength
                multiply = cls._add_node(
                    node_group, "ShaderNodeMath", name="Multiply Strength", location=(280, -150)
                )
                if multiply:
                    multiply.operation = "MULTIPLY"
                    nodes_created.append("Multiply Strength")
                    cls._link(
                        node_group,
                        cls._socket(group_in, "output", "Displace Strength"),
                        cls._socket(multiply, "input", "Value", 0),
                    )
                    cls._link(
                        node_group,
                        cls._socket(separate_xyz, "output", "Z"),
                        cls._socket(multiply, "input", "Value", 1),
                    )
                    cls._link(
                        node_group,
                        cls._socket(multiply, "output", "Value"),
                        cls._socket(set_position, "input", "Offset", 2),
                    )
            except Exception:
                cls._link(
                    node_group,
                    cls._socket(separate_xyz, "output", "Z"),
                    cls._socket(set_position, "input", "Offset", 2),
                )

        # Expose subdivision level.
        if subdivide:
            try:
                level_sock = cls._add_group_socket(node_group, "Subdivisions", "NodeSocketInt", "INPUT")
                level_sock.default_value = subdivisions
                cls._link(
                    node_group,
                    cls._socket(group_in, "output", "Subdivisions"),
                    cls._socket(subdivide, "input", "Level", 0),
                )
            except Exception:
                pass

        input_sockets = cls._list_group_inputs(node_group)
        output_sockets = cls._list_group_outputs(node_group)
        return nodes_created, input_sockets, output_sockets

    @classmethod
    def _build_boolean_array(
        cls,
        node_group: Any,
        params: Dict[str, Any],
    ) -> Tuple[List[str], List[str], List[str]]:
        """Build the boolean_array pipeline: a sequence of Mesh Boolean union nodes with offset copies."""
        array_count: int = max(1, int(params.get("array_count", 5)))
        array_offset: List[float] = list(params.get("array_offset", [2.0, 0.0, 0.0]))

        group_in, group_out = cls._ensure_group_io(node_group)

        nodes_created = ["Group Input", "Group Output"]

        # Expose array parameters on the group interface.
        try:
            count_sock = cls._add_group_socket(node_group, "Array Count", "NodeSocketInt", "INPUT")
            count_sock.default_value = array_count
            offset_sock = cls._add_group_socket(node_group, "Array Offset", "NodeSocketVector", "INPUT")
            offset_sock.default_value = array_offset
        except Exception:
            pass

        prev_geo = cls._geometry_out(group_in)
        cumulative_offset = [0.0, 0.0, 0.0]

        for i in range(array_count):
            cumulative_offset = [
                cumulative_offset[0] + array_offset[0],
                cumulative_offset[1] + array_offset[1],
                cumulative_offset[2] + array_offset[2],
            ]

            transform = cls._add_node(
                node_group, "GeometryNodeTransform", name=f"Transform {i + 1}", location=(-200 + i * 120, -200)
            )
            boolean = cls._add_node(
                node_group, "GeometryNodeMeshBoolean", name=f"Boolean {i + 1}", location=(0 + i * 120, 100)
            )

            if transform:
                nodes_created.append(transform.name)
                try:
                    transform.inputs["Translation"].default_value = cumulative_offset
                except Exception:
                    pass
                cls._link(node_group, cls._geometry_out(group_in), cls._geometry_in(transform))

            if boolean:
                nodes_created.append(boolean.name)
                try:
                    boolean.operation = "UNION"
                except Exception:
                    pass
                cls._link(node_group, prev_geo, cls._socket(boolean, "input", "Mesh 1", 0))
                if transform:
                    cls._link(
                        node_group,
                        cls._geometry_out(transform),
                        cls._socket(boolean, "input", "Mesh 2", 1),
                    )
                prev_geo = cls._geometry_out(boolean)

        cls._link(node_group, prev_geo, cls._geometry_in(group_out))

        input_sockets = cls._list_group_inputs(node_group)
        output_sockets = cls._list_group_outputs(node_group)
        return nodes_created, input_sockets, output_sockets

    @classmethod
    def _build_wave_deform(
        cls,
        node_group: Any,
        params: Dict[str, Any],
    ) -> Tuple[List[str], List[str], List[str]]:
        """Build the wave_deform pipeline: Set Position driven by a sine of the X coordinate."""
        wave_amplitude: float = float(params.get("wave_amplitude", 0.5))
        wave_frequency: float = float(params.get("wave_frequency", 2.0))

        group_in, group_out = cls._ensure_group_io(node_group)

        set_position = cls._add_node(
            node_group, "GeometryNodeSetPosition", name="Set Position", location=(300, 100)
        )
        position = cls._add_node(
            node_group, "GeometryNodeInputPosition", name="Position", location=(-300, -150)
        )
        separate_xyz = cls._add_node(
            node_group, "ShaderNodeSeparateXYZ", name="Separate XYZ", location=(-100, -150)
        )
        math_sine = cls._add_node(
            node_group, "ShaderNodeMath", name="Sine", location=(60, -150)
        )
        math_freq = cls._add_node(
            node_group, "ShaderNodeMath", name="Multiply Frequency", location=(-100, -300)
        )
        math_amp = cls._add_node(
            node_group, "ShaderNodeMath", name="Multiply Amplitude", location=(200, -150)
        )
        combine_xyz = cls._add_node(
            node_group, "ShaderNodeCombineXYZ", name="Combine XYZ", location=(380, -150)
        )

        nodes_created = ["Group Input", "Set Position", "Group Output"]
        for node in (position, separate_xyz, math_sine, math_freq, math_amp, combine_xyz):
            if node:
                nodes_created.append(node.name)

        # Geometry flow.
        cls._link(node_group, cls._geometry_out(group_in), cls._geometry_in(set_position))
        cls._link(node_group, cls._geometry_out(set_position), cls._geometry_in(group_out))

        # Math chain: Position -> Separate XYZ -> (X * frequency) -> sine -> * amplitude -> Combine XYZ -> Offset.
        if position and separate_xyz:
            cls._link(node_group, cls._geometry_out(position), cls._socket(separate_xyz, "input", "Vector"))
        if math_freq:
            math_freq.operation = "MULTIPLY"
            try:
                math_freq.inputs[1].default_value = wave_frequency
            except Exception:
                pass
            cls._link(node_group, cls._socket(separate_xyz, "output", "X"), cls._socket(math_freq, "input", "Value", 0))
        if math_sine:
            math_sine.operation = "SINE"
            src = cls._socket(math_freq, "output", "Value") if math_freq else cls._socket(separate_xyz, "output", "X")
            cls._link(node_group, src, cls._socket(math_sine, "input", "Value", 0))
        if math_amp:
            math_amp.operation = "MULTIPLY"
            try:
                math_amp.inputs[1].default_value = wave_amplitude
            except Exception:
                pass
            cls._link(node_group, cls._socket(math_sine, "output", "Value"), cls._socket(math_amp, "input", "Value", 0))
        if combine_xyz:
            src_z = cls._socket(math_amp, "output", "Value") if math_amp else cls._socket(math_sine, "output", "Value")
            cls._link(node_group, src_z, cls._socket(combine_xyz, "input", "Z"))
            cls._link(node_group, cls._socket(combine_xyz, "output", "Vector"), cls._socket(set_position, "input", "Offset", 2))

        # Expose amplitude/frequency as group inputs.
        try:
            amp_sock = cls._add_group_socket(node_group, "Wave Amplitude", "NodeSocketFloat", "INPUT")
            amp_sock.default_value = wave_amplitude
            freq_sock = cls._add_group_socket(node_group, "Wave Frequency", "NodeSocketFloat", "INPUT")
            freq_sock.default_value = wave_frequency
        except Exception:
            pass

        input_sockets = cls._list_group_inputs(node_group)
        output_sockets = cls._list_group_outputs(node_group)
        return nodes_created, input_sockets, output_sockets

    @classmethod
    def _build_point_instance(
        cls,
        node_group: Any,
        params: Dict[str, Any],
    ) -> Tuple[List[str], List[str], List[str]]:
        """Build the point_instance pipeline: Distribute Points on Faces -> Instance on Points."""
        instance_object: Optional[str] = params.get("instance_object")
        instance_count: int = int(params.get("instance_count", 100))

        group_in, group_out = cls._ensure_group_io(node_group)

        distribute = cls._add_node(
            node_group, "GeometryNodeDistributePointsOnFaces", name="Distribute Points", location=(-200, 100)
        )
        instance_on_points = cls._add_node(
            node_group, "GeometryNodeInstanceOnPoints", name="Instance on Points", location=(50, 100)
        )
        object_info = cls._add_node(
            node_group, "GeometryNodeObjectInfo", name="Object Info", location=(-200, -150)
        )

        nodes_created = ["Group Input", "Distribute Points", "Instance on Points", "Group Output"]
        if object_info:
            nodes_created.append("Object Info")

        cls._link(node_group, cls._geometry_out(group_in), cls._geometry_in(distribute))
        cls._link(node_group, cls._geometry_out(distribute), cls._geometry_in(instance_on_points))
        cls._link(node_group, cls._geometry_out(instance_on_points), cls._geometry_in(group_out))

        if object_info and instance_object:
            try:
                target = cls.get_object(instance_object)
                object_info.inputs["Object"].default_value = target
            except Exception:
                pass
            cls._link(
                node_group,
                cls._socket(object_info, "output", "Instances"),
                cls._socket(instance_on_points, "input", "Instance"),
            )

        try:
            count_sock = cls._add_group_socket(node_group, "Instance Count", "NodeSocketInt", "INPUT")
            count_sock.default_value = instance_count
            density_sock = cls._socket(distribute, "input", "Density Max") or cls._socket(distribute, "input", "Density", 1)
            cls._link(node_group, cls._socket(group_in, "output", "Instance Count"), density_sock)
        except Exception:
            pass

        input_sockets = cls._list_group_inputs(node_group)
        output_sockets = cls._list_group_outputs(node_group)
        return nodes_created, input_sockets, output_sockets

    @classmethod
    def _build_custom(
        cls,
        node_group: Any,
        params: Dict[str, Any],
    ) -> Tuple[List[str], List[str], List[str]]:
        """Build the custom pipeline: Group Input -> N reroute nodes -> Group Output."""
        custom_node_count: int = max(0, int(params.get("custom_node_count", 5)))

        group_in, group_out = cls._ensure_group_io(node_group)

        nodes_created = ["Group Input", "Group Output"]

        prev_geo = cls._geometry_out(group_in)
        for i in range(custom_node_count):
            reroute = cls._add_node(
                node_group, "NodeReroute", name=f"Reroute {i + 1}", location=(-200 + i * 80, 0)
            )
            if reroute:
                nodes_created.append(reroute.name)
                cls._link(node_group, prev_geo, cls._socket(reroute, "input", "Input", 0))
                prev_geo = cls._socket(reroute, "output", "Output", 0)

        cls._link(node_group, prev_geo, cls._geometry_in(group_out))

        input_sockets = cls._list_group_inputs(node_group)
        output_sockets = cls._list_group_outputs(node_group)
        return nodes_created, input_sockets, output_sockets

    # ------------------------------------------------------------------
    # Modifier / object helpers
    # ------------------------------------------------------------------
    @classmethod
    def _insert_realize_instances(cls, node_group: Any) -> None:
        """Insert a Realize Instances node immediately before the Group Output node."""
        group_out = None
        for node in node_group.nodes:
            if node.type == "GROUP_OUTPUT":
                group_out = node
                break
        if group_out is None:
            return

        realize = cls._add_node(
            node_group, "GeometryNodeRealizeInstances", name="Realize Instances", location=(250, 0)
        )
        if realize is None:
            return

        # Re-route any existing links into the group output through the realize node.
        incoming = [link for link in node_group.links if link.to_node == group_out]
        for link in incoming:
            from_socket = link.from_socket
            try:
                node_group.links.remove(link)
            except Exception:
                pass
            cls._link(node_group, from_socket, cls._geometry_in(realize))
        cls._link(node_group, cls._geometry_out(realize), cls._geometry_in(group_out))

    @classmethod
    def _duplicate_object(cls, obj: Any, new_name: str) -> Any:
        """Duplicate *obj* and link the copy to the active scene collection."""
        bpy = cls.get_bpy()
        try:
            new_obj = obj.copy()
            if obj.data:
                new_obj.data = obj.data.copy()
        except Exception as exc:
            raise BlenderExecutionError(f"Failed to duplicate object '{obj.name}': {exc}") from exc
        new_obj.name = new_name
        try:
            bpy.context.scene.collection.objects.link(new_obj)
        except Exception:
            for collection in obj.users_collection:
                collection.objects.link(new_obj)
                break
        return new_obj

    @classmethod
    def _assign_modifier(cls, obj: Any, modifier_name: str, node_group: Any) -> Any:
        """Create a Geometry Nodes modifier on *obj* and assign *node_group* to it."""
        existing = obj.modifiers.get(modifier_name)
        if existing:
            obj.modifiers.remove(existing)
        modifier = obj.modifiers.new(name=modifier_name, type="NODES")
        modifier.node_group = node_group
        return modifier

    @classmethod
    def _set_modifier_inputs(cls, modifier: Any, inputs: Dict[str, Any]) -> None:
        """Set named inputs on a Geometry Nodes modifier, ignoring missing ones."""
        for name, value in inputs.items():
            try:
                if name in modifier:
                    modifier[name] = value
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Physics setup & bake
    # ------------------------------------------------------------------
    @classmethod
    def setup_and_bake_physics(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        """Configure a physics simulation on an object and optionally bake it.

        Adds the requested physics modifier, applies type-specific settings and
        presets, configures the point cache frame range and directory, and (when
        ``bake`` is True) runs the bake while polling for completion.

        Returns a dictionary describing the modifier, cache path, bake status,
        and configured frame range.
        """
        bpy = cls.get_bpy()

        object_name: str = params["object_name"]
        physics_type: str = params["physics_type"]
        bake: bool = params.get("bake", True)
        frame_start: int = int(params.get("frame_start", 1))
        frame_end: int = int(params.get("frame_end", 250))
        cache_directory: Optional[str] = params.get("cache_directory", "/tmp/blender_physics_cache")
        substeps: int = int(params.get("substeps", 10))
        quality: int = int(params.get("quality", 5))
        preset: Optional[str] = params.get("preset")
        mass: float = float(params.get("mass", 1.0))
        collision_shape: str = params.get("collision_shape", "MESH")
        fluid_type: str = params.get("fluid_type", "DOMAIN")
        poll_interval: float = float(params.get("poll_interval", 2.0))
        poll_timeout: float = float(params.get("poll_timeout", 300.0))

        if physics_type not in _VALID_PHYSICS_TYPES:
            raise BlenderExecutionError(
                f"Invalid physics_type '{physics_type}'. Expected one of: {', '.join(_VALID_PHYSICS_TYPES)}."
            )

        obj = cls.get_object(object_name)

        with cls.transaction(f"setup_and_bake_physics:{physics_type}"):
            modifier_name = cls._add_physics_modifier(obj, physics_type, fluid_type)
            cls._configure_physics(
                obj,
                physics_type,
                modifier_name=modifier_name,
                quality=quality,
                preset=preset,
                mass=mass,
                collision_shape=collision_shape,
                fluid_type=fluid_type,
                substeps=substeps,
            )
            cls._configure_cache(
                obj,
                physics_type,
                modifier_name=modifier_name,
                frame_start=frame_start,
                frame_end=frame_end,
                cache_directory=cache_directory,
            )

            bake_status = "skipped"
            if bake:
                bake_status = cls._run_bake(
                    obj,
                    physics_type,
                    modifier_name=modifier_name,
                    poll_interval=poll_interval,
                    poll_timeout=poll_timeout,
                )

        return {
            "status": "success",
            "object": obj.name,
            "physics_type": physics_type,
            "modifier": modifier_name,
            "cache_directory": cache_directory,
            "bake_status": bake_status,
            "frame_start": frame_start,
            "frame_end": frame_end,
        }

    # ------------------------------------------------------------------
    # Physics helpers
    # ------------------------------------------------------------------
    @classmethod
    def _add_physics_modifier(cls, obj: Any, physics_type: str, fluid_type: str) -> str:
        """Add the physics modifier/rigidbody for *physics_type* and return its identifier."""
        bpy = cls.get_bpy()
        with bpy.context.temp_override(active_object=obj, selected_objects=[obj], object=obj):
            if physics_type == "CLOTH":
                mod = obj.modifiers.get("Cloth") or obj.modifiers.new(name="Cloth", type="CLOTH")
                return mod.name

            if physics_type == "SOFT_BODY":
                mod = obj.modifiers.get("Softbody") or obj.modifiers.new(name="Softbody", type="SOFT_BODY")
                return mod.name

            if physics_type == "COLLISION":
                mod = obj.modifiers.get("Collision") or obj.modifiers.new(name="Collision", type="COLLISION")
                return mod.name

            if physics_type == "FLUID":
                mod = obj.modifiers.get("Fluid") or obj.modifiers.new(name="Fluid", type="FLUID")
                try:
                    mod.fluid_type = fluid_type
                except Exception:
                    pass
                # Some Blender versions require the dedicated fluid operator.
                if hasattr(bpy.ops, "fluid") and hasattr(bpy.ops.fluid, "object_add"):
                    try:
                        bpy.ops.fluid.object_add(type=fluid_type)
                    except Exception:
                        pass
                return mod.name

            if physics_type == "RIGID_BODY":
                if not getattr(obj, "rigid_body", None) and hasattr(bpy.ops.rigidbody, "object_add"):
                    try:
                        bpy.ops.rigidbody.object_add()
                    except Exception:
                        pass
                return "Rigid Body"

            if physics_type == "DYNAMIC_PAINT":
                if hasattr(bpy.ops, "dpaint") and hasattr(bpy.ops.dpaint, "type_add"):
                    try:
                        bpy.ops.dpaint.type_add()
                    except Exception:
                        pass
                mod = obj.modifiers.get("Dynamic Paint") or ""
                return mod.name if mod else "Dynamic Paint"

        raise BlenderExecutionError(f"Unsupported physics type '{physics_type}'.")

    @classmethod
    def _configure_physics(
        cls,
        obj: Any,
        physics_type: str,
        *,
        modifier_name: str,
        quality: int,
        preset: Optional[str],
        mass: float,
        collision_shape: str,
        fluid_type: str,
        substeps: int,
    ) -> None:
        """Apply type-specific physics settings to the object/modifier."""
        bpy = cls.get_bpy()

        if physics_type == "CLOTH":
            mod = obj.modifiers.get(modifier_name)
            if not mod or not hasattr(mod, "settings"):
                return
            settings = mod.settings
            if preset and preset in _CLOTH_PRESETS:
                for key, value in _CLOTH_PRESETS[preset].items():
                    if hasattr(settings, key):
                        try:
                            setattr(settings, key, value)
                        except Exception:
                            pass
            for key, value in (("quality", quality), ("mass", mass)):
                if hasattr(settings, key):
                    try:
                        setattr(settings, key, value)
                    except Exception:
                        pass
            return

        if physics_type == "SOFT_BODY":
            mod = obj.modifiers.get(modifier_name)
            if not mod or not hasattr(mod, "settings"):
                return
            settings = mod.settings
            if hasattr(settings, "quality"):
                try:
                    settings.quality = quality
                except Exception:
                    pass
            return

        if physics_type == "RIGID_BODY":
            rb = getattr(obj, "rigid_body", None)
            if not rb:
                return
            if hasattr(rb, "mass"):
                try:
                    rb.mass = mass
                except Exception:
                    pass
            if hasattr(rb, "collision_shape"):
                try:
                    rb.collision_shape = collision_shape
                except Exception:
                    pass
            rb_world = getattr(bpy.context.scene, "rigid_body_world", None)
            if rb_world:
                solver = getattr(rb_world, "solver", None)
                if solver and hasattr(solver, "num_substeps"):
                    try:
                        solver.num_substeps = substeps
                    except Exception:
                        pass
            return

        if physics_type == "FLUID":
            mod = obj.modifiers.get(modifier_name)
            if not mod:
                return
            try:
                mod.fluid_type = fluid_type
            except Exception:
                pass
            domain_settings = getattr(mod, "domain_settings", None)
            if domain_settings:
                if hasattr(domain_settings, "resolution_max"):
                    try:
                        domain_settings.resolution_max = max(32, quality * 16)
                    except Exception:
                        pass
            return

        if physics_type == "COLLISION":
            mod = obj.modifiers.get(modifier_name)
            if not mod or not hasattr(mod, "settings"):
                return
            settings = mod.settings
            if hasattr(settings, "permeability"):
                try:
                    settings.permeability = 0.0
                except Exception:
                    pass
            return

        # DYNAMIC_PAINT has minimal configuration here.
        return

    @classmethod
    def _configure_cache(
        cls,
        obj: Any,
        physics_type: str,
        *,
        modifier_name: str,
        frame_start: int,
        frame_end: int,
        cache_directory: Optional[str],
    ) -> None:
        """Set the point cache frame range and directory for the physics modifier."""
        bpy = cls.get_bpy()

        # Rigid body world uses a shared point cache.
        if physics_type == "RIGID_BODY":
            rb_world = getattr(bpy.context.scene, "rigid_body_world", None)
            if rb_world and rb_world.point_cache:
                cls._apply_cache_settings(
                    rb_world.point_cache,
                    frame_start=frame_start,
                    frame_end=frame_end,
                    cache_directory=cache_directory,
                )
            return

        mod = obj.modifiers.get(modifier_name)
        if not mod:
            return
        point_cache = getattr(mod, "point_cache", None)
        if point_cache:
            cls._apply_cache_settings(
                point_cache,
                frame_start=frame_start,
                frame_end=frame_end,
                cache_directory=cache_directory,
            )

        # Fluid simulations use their own cache settings.
        domain_settings = getattr(mod, "domain_settings", None) if mod else None
        if domain_settings:
            cache = getattr(domain_settings, "cache_directory", None)
            if cache_directory and cache is not None:
                try:
                    domain_settings.cache_directory = cache_directory
                except Exception:
                    pass

    @classmethod
    def _apply_cache_settings(
        cls,
        point_cache: Any,
        *,
        frame_start: int,
        frame_end: int,
        cache_directory: Optional[str],
    ) -> None:
        """Apply frame range and directory settings to a point cache."""
        if hasattr(point_cache, "frame_start"):
            try:
                point_cache.frame_start = frame_start
            except Exception:
                pass
        if hasattr(point_cache, "frame_end"):
            try:
                point_cache.frame_end = frame_end
            except Exception:
                pass
        if cache_directory:
            if hasattr(point_cache, "filepath"):
                try:
                    point_cache.filepath = cache_directory
                except Exception:
                    pass
            try:
                os.makedirs(cache_directory, exist_ok=True)
            except Exception:
                pass

    @classmethod
    def _run_bake(
        cls,
        obj: Any,
        physics_type: str,
        *,
        modifier_name: str,
        poll_interval: float,
        poll_timeout: float,
    ) -> str:
        """Start the physics bake and poll until completion or timeout."""
        bpy = cls.get_bpy()

        with bpy.context.temp_override(active_object=obj, selected_objects=[obj], object=obj):
            baked = False
            # Try the dedicated bake operator first, then fall back to the global one.
            if hasattr(bpy.ops, "ptcache") and hasattr(bpy.ops.ptcache, "bake_all"):
                try:
                    bpy.ops.ptcache.bake_all(bake=True)
                    baked = True
                except Exception:
                    baked = False
            if not baked and hasattr(bpy.ops, "cloth") and hasattr(bpy.ops.cloth, "bake"):
                try:
                    bpy.ops.cloth.bake()
                    baked = True
                except Exception:
                    baked = False

        # Poll for completion.
        deadline = time.monotonic() + poll_timeout
        while time.monotonic() < deadline:
            if cls._is_baked(obj, physics_type, modifier_name=modifier_name):
                return "completed"
            time.sleep(poll_interval)

        # Final check.
        if cls._is_baked(obj, physics_type, modifier_name=modifier_name):
            return "completed"
        return "timeout"

    @classmethod
    def _is_baked(cls, obj: Any, physics_type: str, *, modifier_name: str) -> bool:
        """Return True when the physics cache for *obj* reports as baked."""
        bpy = cls.get_bpy()

        if physics_type == "RIGID_BODY":
            rb_world = getattr(bpy.context.scene, "rigid_body_world", None)
            if rb_world and rb_world.point_cache:
                return bool(getattr(rb_world.point_cache, "is_baked", False))
            return False

        mod = obj.modifiers.get(modifier_name)
        if not mod:
            return False
        point_cache = getattr(mod, "point_cache", None)
        if point_cache:
            return bool(getattr(point_cache, "is_baked", False))
        return False
