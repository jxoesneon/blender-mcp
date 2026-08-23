"""
Unit tests for Blender addon lifecycle, operator executions, and timer loops.
"""

import sys
import unittest
from tests.mock_bpy import install_mocks

mock_bpy = install_mocks()

import addon


class TestAddon(unittest.TestCase):
    def test_addon_registration(self):
        addon.register()
        addon.unregister()

    def test_start_stop_server(self):
        addon.start_mcp_server(host="127.0.0.1", port=9999)
        self.assertTrue(addon._is_running)

        # Main thread timer processing
        addon._main_thread_timer()

        addon.stop_mcp_server()
        self.assertFalse(addon._is_running)

    def test_operators(self):
        class MockContext:
            class Scene:
                class Props:
                    host = "127.0.0.1"
                    port = 9999
                blendermcp_props = Props()
            scene = Scene()

        start_op = addon.BLENDERMCP_OT_start_server()
        start_op.report = lambda level, msg: None
        res_start = start_op.execute(MockContext())
        self.assertEqual(res_start, {'FINISHED'})

        stop_op = addon.BLENDERMCP_OT_stop_server()
        stop_op.report = lambda level, msg: None
        res_stop = stop_op.execute(MockContext())
        self.assertEqual(res_stop, {'FINISHED'})

    def test_panel_draw(self):
        class MockLayout:
            def box(self): return self
            def label(self, text="", icon=""): pass
            def prop(self, data, prop): pass
            def row(self, align=True): return self
            def operator(self, op, icon="", text=""): pass

        class MockContext:
            class Scene:
                class Props:
                    host = "127.0.0.1"
                    port = 9999
                blendermcp_props = Props()
            scene = Scene()

        panel = addon.VIEW3D_PT_blender_mcp_panel()
        panel.layout = MockLayout()
        panel.draw(MockContext())


if __name__ == "__main__":
    unittest.main()
