"""
Additional targeted unit tests to achieve comprehensive test coverage across all modules.
"""

import queue
import socket
import unittest
from unittest.mock import MagicMock, patch

from tests.mock_bpy import install_mocks

mock_bpy = install_mocks()

import addon
import main
import blender_mcp
import blender_mcp.handlers as handlers
from blender_mcp.handlers.base import BaseHandler
from blender_mcp.handlers.reflection import ReflectionHandler
from blender_mcp.handlers.scene_world import SceneWorldHandler
from blender_mcp.handlers.objects_hierarchy import ObjectsHierarchyHandler
from blender_mcp.handlers.mesh_geometry import MeshGeometryHandler
from blender_mcp.handlers.materials_shading import MaterialsShadingHandler
from blender_mcp.handlers.modifiers_physics import ModifiersPhysicsHandler
from blender_mcp.handlers.animation_rigging import AnimationRiggingHandler
from blender_mcp.handlers.rendering import RenderingHandler
from blender_mcp.handlers.io_preferences import IOPreferencesHandler
import blender_mcp.server as server


class TestCoverageBoost(unittest.TestCase):
    def test_dispatch_all_registered_actions(self):
        # Test unknown action
        err_res = handlers.dispatch_blender_command("completely_unknown_action", {})
        self.assertFalse(err_res["success"])
        self.assertIn("Unknown Blender MCP action", err_res["error"])

        # Test dispatching valid actions through the central router
        res_scene = handlers.dispatch_blender_command("manage_scene", {"action": "list"})
        self.assertTrue(res_scene["success"])

        res_expr = handlers.dispatch_blender_command("eval_expression", {"expression": "2 + 2"})
        self.assertTrue(res_expr["success"])
        self.assertEqual(res_expr["result"]["result"], 4)

        # Test exception catching in dispatcher
        res_fail = handlers.dispatch_blender_command("manage_scene", {"action": "invalid_action_name"})
        self.assertFalse(res_fail["success"])

    def test_base_handler_branches(self):
        # Transaction success
        with BaseHandler.transaction("Test OK"):
            x = 1

        # Transaction error rollback
        with self.assertRaises(Exception):
            with BaseHandler.transaction("Test Fail"):
                raise RuntimeError("Boom")

        # Active mode context
        obj = BaseHandler.get_object("Cube")
        with BaseHandler.active_mode(obj, "EDIT"):
            self.assertEqual(obj.name, "Cube")

    def test_addon_client_handler_and_socket(self):
        # Test kelvin_to_rgb in addon
        r, g, b = addon.kelvin_to_rgb(3200)
        self.assertTrue(0.0 <= r <= 1.0)

        # Test serialize_bpy_value in addon
        self.assertEqual(addon.serialize_bpy_value(None), None)
        self.assertEqual(addon.serialize_bpy_value(100), 100)
        self.assertEqual(addon.serialize_bpy_value([1, 2]), [1, 2])
        self.assertEqual(addon.serialize_bpy_value({"a": 1}), {"a": 1})

        # Test addon main thread timer with tasks
        resp_q = queue.Queue()
        addon._task_queue.put({
            "action": "eval_expression",
            "params": {"expression": "10 * 10"},
            "response_channel": resp_q
        })
        addon._is_running = True
        addon._main_thread_timer()
        res = resp_q.get(timeout=1.0)
        self.assertTrue(res["success"])
        self.assertEqual(res["result"]["result"], 100)

    def test_main_cli_entry(self):
        # Run main function safely
        main.main()

    def test_reflection_handler_extended(self):
        # Inspect parented path
        res = ReflectionHandler.inspect_bpy_path({"path": "bpy.context.scene.unit_settings.system"})
        self.assertEqual(res["type_name"], "str")

    def test_scene_world_handler_extended(self):
        # Full copy scene
        res = SceneWorldHandler.manage_scene({"action": "create", "create_mode": "FULL_COPY", "scene_name": "FullCopyScene"})
        self.assertEqual(res["status"], "success")

        # Volumetrics with absorption / principled
        res_vol = SceneWorldHandler.manage_world({
            "mode": "COLOR",
            "volume_type": "ABSORPTION",
            "volume_density": 0.1,
            "volume_color": [0.8, 0.2, 0.2]
        })
        self.assertEqual(res_vol["status"], "success")

    def test_objects_hierarchy_extended(self):
        # Empty and Camera primitive creation
        res_empty = ObjectsHierarchyHandler.manage_objects({"action": "create", "primitive_type": "EMPTY_ARROWS", "name": "ArrowEmpty"})
        self.assertEqual(res_empty["status"], "success")

        res_cam = ObjectsHierarchyHandler.manage_objects({"action": "create", "primitive_type": "CAMERA", "name": "CamObj"})
        self.assertEqual(res_cam["status"], "success")

        res_arm = ObjectsHierarchyHandler.manage_objects({"action": "create", "primitive_type": "ARMATURE", "name": "ArmObj"})
        self.assertEqual(res_arm["status"], "success")

    def test_mesh_geometry_extended(self):
        # Sphere project UV
        res_uv = MaterialsShadingHandler.perform_uv_unwrap({"object_name": "Cube", "method": "sphere_project"})
        self.assertEqual(res_uv["status"], "success")

        # Cylinder project UV
        res_uv_cyl = MaterialsShadingHandler.perform_uv_unwrap({"object_name": "Cube", "method": "cylinder_project"})
        self.assertEqual(res_uv_cyl["status"], "success")

        # Lightmap pack UV
        res_uv_lm = MaterialsShadingHandler.perform_uv_unwrap({"object_name": "Cube", "method": "lightmap_pack"})
        self.assertEqual(res_uv_lm["status"], "success")

        # Cube project UV
        res_uv_cb = MaterialsShadingHandler.perform_uv_unwrap({"object_name": "Cube", "method": "cube_project"})
        self.assertEqual(res_uv_cb["status"], "success")

    def test_io_preferences_extended(self):
        # File paths preferences
        res_fp = IOPreferencesHandler.manage_user_preferences({"category": "filepaths", "action": "get"})
        self.assertEqual(res_fp["category"], "filepaths")

        # View preferences
        res_vw = IOPreferencesHandler.manage_user_preferences({"category": "view", "action": "get"})
        self.assertEqual(res_vw["category"], "view")

        # Keymap preferences
        res_km = IOPreferencesHandler.manage_user_preferences({"category": "keymap", "action": "get"})
        self.assertEqual(res_km["category"], "keymap")

        # Experimental preferences
        res_ex = IOPreferencesHandler.manage_user_preferences({"category": "experimental", "action": "get"})
        self.assertEqual(res_ex["category"], "experimental")


if __name__ == "__main__":
    unittest.main()
