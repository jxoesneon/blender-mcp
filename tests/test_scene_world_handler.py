"""
Unit tests for SceneWorldHandler.
"""

import unittest
from tests.mock_bpy import install_mocks

mock_bpy = install_mocks()

from blender_mcp.handlers.scene_world import SceneWorldHandler


class TestSceneWorldHandler(unittest.TestCase):
    def test_manage_scene(self):
        # List
        res = SceneWorldHandler.manage_scene({"action": "list"})
        self.assertEqual(res["status"], "success")

        # Get Active
        res_act = SceneWorldHandler.manage_scene({"action": "get_active"})
        self.assertEqual(res_act["status"], "success")

        # Create
        res_create = SceneWorldHandler.manage_scene({"action": "create", "scene_name": "TestScene2"})
        self.assertEqual(res_create["status"], "success")

        # Switch
        res_switch = SceneWorldHandler.manage_scene({"action": "switch", "scene_name": "TestScene2"})
        self.assertEqual(res_switch["status"], "success")

        # Configure
        res_cfg = SceneWorldHandler.manage_scene({
            "action": "configure",
            "scene_name": "TestScene2",
            "unit_system": "METRIC",
            "unit_scale_length": 0.01,
            "unit_length": "CENTIMETERS",
            "unit_rotation": "DEGREES",
            "use_gravity": True,
            "gravity": [0, 0, -9.81],
        })
        self.assertEqual(res_cfg["status"], "success")

        # Delete
        res_del = SceneWorldHandler.manage_scene({"action": "delete", "scene_name": "TestScene2"})
        self.assertEqual(res_del["status"], "success")

    def test_manage_world(self):
        # Info
        res_info = SceneWorldHandler.manage_world({"mode": "GET_INFO"})
        self.assertEqual(res_info["status"], "success")

        # Color
        res_col = SceneWorldHandler.manage_world({"mode": "COLOR", "color": [0.1, 0.2, 0.3], "strength": 2.0})
        self.assertEqual(res_col["status"], "success")

        # Sky Texture
        res_sky = SceneWorldHandler.manage_world({"mode": "SKY_TEXTURE", "sky_type": "NISHITA", "sky_sun_intensity": 2.0})
        self.assertEqual(res_sky["status"], "success")

        # HDRI
        res_hdri = SceneWorldHandler.manage_world({
            "mode": "HDRI",
            "hdri_filepath": "/tmp/test.hdr",
            "hdri_rotation_z": 45.0,
            "volume_type": "SCATTER",
            "volume_density": 0.05,
        })
        self.assertEqual(res_hdri["status"], "success")

    def test_manage_viewport(self):
        res_shading = SceneWorldHandler.manage_viewport({
            "action": "set_shading",
            "shading_type": "RENDERED",
            "shading_options": {"use_scene_lights": True}
        })
        self.assertEqual(res_shading["status"], "success")

        res_overlay = SceneWorldHandler.manage_viewport({
            "action": "set_overlays",
            "show_overlays": True,
            "overlay_toggles": {"show_floor": True}
        })
        self.assertEqual(res_overlay["status"], "success")

        res_cursor = SceneWorldHandler.manage_viewport({
            "action": "set_cursor",
            "cursor_location": [1.0, 2.0, 3.0]
        })
        self.assertEqual(res_cursor["status"], "success")

        res_clip = SceneWorldHandler.manage_viewport({
            "action": "set_clipping_lens",
            "clip_start": 0.5,
            "clip_end": 500.0,
            "lens": 85.0
        })
        self.assertEqual(res_clip["status"], "success")

        res_lock = SceneWorldHandler.manage_viewport({
            "action": "lock_view",
            "lock_cursor": True
        })
        self.assertEqual(res_lock["status"], "success")

    def test_manage_camera(self):
        # Create
        res_cam = SceneWorldHandler.manage_camera({
            "action": "create",
            "camera_name": "StudioCam",
            "focal_length": 70.0,
            "dof": {"enabled": True, "focus_distance": 5.0, "fstop": 1.4}
        })
        self.assertEqual(res_cam["status"], "success")

        # Set Active
        res_act = SceneWorldHandler.manage_camera({"action": "set_active", "camera_name": "StudioCam"})
        self.assertEqual(res_act["status"], "success")

        # Update
        res_up = SceneWorldHandler.manage_camera({
            "action": "update",
            "camera_name": "StudioCam",
            "focal_length": 105.0,
            "composition_guides": {"show_thirds": True}
        })
        self.assertEqual(res_up["status"], "success")

        # Get props
        res_props = SceneWorldHandler.manage_camera({"action": "get_properties", "camera_name": "StudioCam"})
        self.assertEqual(res_props["status"], "success")

        # Delete
        res_del = SceneWorldHandler.manage_camera({"action": "delete", "camera_name": "StudioCam"})
        self.assertEqual(res_del["status"], "success")

    def test_manage_light(self):
        # Create Area light with Kelvin
        res_l = SceneWorldHandler.manage_light({
            "action": "create",
            "light_name": "KeyLight",
            "type": "AREA",
            "energy": 500.0,
            "color_type": "KELVIN",
            "color_kelvin": 5600,
            "area_shape": "RECTANGLE",
            "area_size_x": 2.0,
            "area_size_y": 1.0,
        })
        self.assertEqual(res_l["status"], "success")

        # Update Spot
        res_spot = SceneWorldHandler.manage_light({
            "action": "update",
            "light_name": "KeyLight",
            "type": "SPOT",
            "spot_size": 60.0,
            "spot_blend": 0.2,
            "spot_show_cone": True,
        })
        self.assertEqual(res_spot["status"], "success")

        # Set light linking
        res_ll = SceneWorldHandler.manage_light({
            "action": "set_linking",
            "light_name": "KeyLight",
            "light_linking": {"receiver_collection_name": "Collection"}
        })
        self.assertEqual(res_ll["status"], "success")

        # Delete
        res_del = SceneWorldHandler.manage_light({"action": "delete", "light_name": "KeyLight"})
        self.assertEqual(res_del["status"], "success")


if __name__ == "__main__":
    unittest.main()
