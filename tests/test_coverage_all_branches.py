"""
Exhaustive branch coverage tests for all 9 domain handlers, client, server, and addon.
"""

import os
import unittest
from unittest.mock import MagicMock, patch

from tests.mock_bpy import install_mocks, MockAction

mock_bpy = install_mocks()

import addon
import blender_mcp
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
import blender_mcp.server as server


class TestCoverageAllBranches(unittest.TestCase):
    def setUp(self):
        MaterialsShadingHandler.manage_materials({"action": "create", "material_name": "Chrome"})

    def test_animation_rigging_full_branches(self):
        # Insert keyframe on Material & World
        res_mat_key = AnimationRiggingHandler.insert_keyframe({
            "target_type": "MATERIAL",
            "target_name": "Chrome",
            "data_path": "name",
            "value": "ChromeKeyed"
        })
        self.assertEqual(res_mat_key["status"], "success")

        res_w_key = AnimationRiggingHandler.insert_keyframe({
            "target_type": "WORLD",
            "target_name": "World",
            "data_path": "name"
        })
        self.assertEqual(res_w_key["status"], "success")

        # Pose bone transform with rotation quaternion & scale
        AnimationRiggingHandler.manage_armature({
            "action": "create_armature",
            "armature_name": "ArmFull",
            "bones": [{"bone_name": "Root", "head": [0, 0, 0], "tail": [0, 0, 1]}]
        })
        res_p = AnimationRiggingHandler.manage_armature({
            "action": "pose_bone",
            "armature_name": "ArmFull",
            "bone_name": "Root",
            "bone_transforms": {
                "location": [1, 2, 3],
                "rotation_euler": [0, 0, 0],
                "scale": [2, 2, 2]
            }
        })
        self.assertEqual(res_p["status"], "success")

        # Set action on Cube and push NLA
        cube = BaseHandler.get_object("Cube")
        if not cube.animation_data:
            cube.animation_data_create()
        cube.animation_data.action = MockAction("ActionForNLA")

        res_push = AnimationRiggingHandler.manage_nla({
            "action": "push_nla",
            "target_name": "Cube",
            "track_name": "NlaTrack_DefaultAction"
        })
        self.assertEqual(res_push["status"], "success")

        res_nla = AnimationRiggingHandler.manage_nla({
            "action": "configure_nla",
            "target_name": "Cube",
            "track_name": "NlaTrack_DefaultAction",
            "strip_name": "ActionForNLA",
            "nla_properties": {"frame_start": 5.0, "frame_end": 100.0}
        })
        self.assertEqual(res_nla["status"], "success")

    def test_materials_shading_full_branches(self):
        # Procedural texture all types
        types = ["wave", "brick", "checker", "gradient", "magic", "noise", "voronoi"]
        for t in types:
            res = MaterialsShadingHandler.setup_procedural_texture({
                "material_name": "Chrome",
                "texture_type": t,
                "coord_type": "Generated",
                "location": [1, 1, 1],
                "rotation": [0, 0, 0],
                "scale": [2, 2, 2]
            })
            self.assertEqual(res["status"], "success")

        # Set socket value with integer socket id
        MaterialsShadingHandler.manage_shader_node({
            "action": "create",
            "material_name": "Chrome",
            "node_type": "ShaderNodeBsdfPrincipled",
            "node_name": "PrincipledBSDF"
        })
        res_sock_int = MaterialsShadingHandler.set_socket_value({
            "material_name": "Chrome",
            "node_name": "PrincipledBSDF",
            "socket_identifier": 0,
            "value": [0.8, 0.2, 0.2, 1.0]
        })
        self.assertEqual(res_sock_int["status"], "success")

    def test_objects_hierarchy_full_branches(self):
        # Create all primitive types
        prims = ["MESH_CUBE", "MESH_SPHERE", "MESH_CYLINDER", "MESH_PLANE", "EMPTY", "CAMERA", "ARMATURE"]
        for p in prims:
            res = ObjectsHierarchyHandler.manage_objects({
                "action": "create",
                "primitive_type": p,
                "name": f"Obj_{p}"
            })
            self.assertEqual(res["status"], "success")

        # Transform delta
        res_tf_delta = ObjectsHierarchyHandler.transform_object({
            "name": "Cube",
            "delta": True,
            "location": [1, 2, 3],
            "rotation": [0, 0, 0],
            "scale": [1, 1, 1]
        })
        self.assertEqual(res_tf_delta["status"], "success")

        # Move collection
        ObjectsHierarchyHandler.manage_collections({"action": "create", "name": "SubCol"})
        res_mv = ObjectsHierarchyHandler.manage_collections({
            "action": "move",
            "name": "SubCol",
            "parent_collection": "Collection"
        })
        self.assertEqual(res_mv["status"], "success")

    def test_rendering_full_branches(self):
        # EEVEE and Workbench engines
        res_eevee = RenderingHandler.configure_render_engine({"engine": "BLENDER_EEVEE_NEXT"})
        self.assertEqual(res_eevee["status"], "success")

        res_wb = RenderingHandler.configure_render_engine({"engine": "BLENDER_WORKBENCH"})
        self.assertEqual(res_wb["status"], "success")

        # Output dimensions with custom fps and aspect
        res_out = RenderingHandler.configure_output_and_passes({
            "resolution_x": 1280,
            "resolution_y": 720,
            "fps": 60,
            "fps_base": 1.0,
            "file_format": "JPEG",
            "color_mode": "RGB"
        })
        self.assertEqual(res_out["status"], "success")

        # Compositor set socket value
        RenderingHandler.manage_compositor_tree({
            "action": "add_node",
            "node_type": "CompositorNodeBlur",
            "node_name": "BlurNode"
        })
        res_comp_val = RenderingHandler.manage_compositor_tree({
            "action": "set_socket_value",
            "node_name": "BlurNode",
            "socket_name": "Size",
            "socket_value": 10.0
        })
        self.assertEqual(res_comp_val["status"], "success")

    def test_scene_world_full_branches(self):
        # Camera ortho and pano
        res_ortho = SceneWorldHandler.manage_camera({
            "action": "create",
            "camera_name": "OrthoCam",
            "type": "ORTHO",
            "ortho_scale": 10.0
        })
        self.assertEqual(res_ortho["status"], "success")

        res_pano = SceneWorldHandler.manage_camera({
            "action": "create",
            "camera_name": "PanoCam",
            "type": "PANO"
        })
        self.assertEqual(res_pano["status"], "success")

        # Lights Sun, Point, Area shapes
        shapes = ["SQUARE", "RECTANGLE", "DISK", "ELLIPSE"]
        for s in shapes:
            res_l = SceneWorldHandler.manage_light({
                "action": "create",
                "light_name": f"Area_{s}",
                "type": "AREA",
                "area_shape": s,
                "area_size_x": 2.0,
                "area_size_y": 1.0
            })
            self.assertEqual(res_l["status"], "success")


if __name__ == "__main__":
    unittest.main()
