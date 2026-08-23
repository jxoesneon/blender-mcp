"""
Unit tests for RenderingHandler.
"""

import os
import unittest
from tests.mock_bpy import install_mocks

mock_bpy = install_mocks()

from blender_mcp.handlers.rendering import RenderingHandler


class TestRenderingHandler(unittest.TestCase):
    def test_configure_render_engine(self):
        res = RenderingHandler.configure_render_engine({
            "engine": "CYCLES",
            "device_type": "GPU",
            "render_samples": 256,
            "viewport_samples": 64,
            "use_noise_threshold": True,
            "noise_threshold": 0.005,
            "bounces": {"max_bounces": 16, "diffuse_bounces": 4}
        })
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["engine"], "CYCLES")

    def test_configure_output_and_passes(self):
        res = RenderingHandler.configure_output_and_passes({
            "resolution_x": 3840,
            "resolution_y": 2160,
            "resolution_percentage": 100,
            "fps": 30,
            "output_filepath": "/tmp/test_render",
            "file_format": "PNG",
            "passes": {"z": True, "normal": True, "shadow": True}
        })
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["resolution"], [3840, 2160])

    def test_configure_color_management(self):
        res = RenderingHandler.configure_color_management({
            "display_device": "sRGB",
            "view_transform": "AgX",
            "look": "Medium High Contrast",
            "exposure": 0.5,
            "gamma": 1.1
        })
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["view_transform"], "AgX")

    def test_manage_compositor_tree(self):
        # Inspect
        res_ins = RenderingHandler.manage_compositor_tree({"action": "inspect"})
        self.assertEqual(res_ins["status"], "success")

        # Add node
        res_add = RenderingHandler.manage_compositor_tree({
            "action": "add_node",
            "node_type": "CompositorNodeBlur",
            "node_name": "PostBlur",
            "location": [100, 200]
        })
        self.assertEqual(res_add["status"], "success")

        # Link
        res_link = RenderingHandler.manage_compositor_tree({
            "action": "link",
            "from_node": "PostBlur",
            "to_node": "PostBlur"
        })
        self.assertEqual(res_link["status"], "success")

        # Remove node
        res_rem = RenderingHandler.manage_compositor_tree({"action": "remove_node", "node_name": "PostBlur"})
        self.assertEqual(res_rem["status"], "success")

        # Clear
        res_clear = RenderingHandler.manage_compositor_tree({"action": "clear"})
        self.assertEqual(res_clear["status"], "success")

    def test_execute_capture_or_render(self):
        # Still render
        res_still = RenderingHandler.execute_capture_or_render({
            "mode": "STILL",
            "output_path": "/tmp/test_still.png",
            "return_base64": False
        })
        self.assertEqual(res_still["status"], "success")
        self.assertEqual(res_still["mode"], "STILL")

        # Animation render
        res_anim = RenderingHandler.execute_capture_or_render({
            "mode": "ANIMATION",
            "frame_start": 1,
            "frame_end": 5
        })
        self.assertEqual(res_anim["status"], "success")
        self.assertEqual(res_anim["mode"], "ANIMATION")

        # Viewport screenshot
        res_vp = RenderingHandler.execute_capture_or_render({
            "mode": "VIEWPORT_SCREENSHOT",
            "output_path": "/tmp/test_vp.png",
            "return_base64": False
        })
        self.assertEqual(res_vp["status"], "success")
        self.assertEqual(res_vp["mode"], "VIEWPORT_SCREENSHOT")


if __name__ == "__main__":
    unittest.main()
