"""
Unit tests for IOPreferencesHandler.
"""

import unittest
from tests.mock_bpy import install_mocks

mock_bpy = install_mocks()

from blender_mcp.handlers.io_preferences import IOPreferencesHandler


class TestIOPreferencesHandler(unittest.TestCase):
    def test_manage_user_preferences(self):
        res_get = IOPreferencesHandler.manage_user_preferences({"category": "system", "action": "get"})
        self.assertEqual(res_get["category"], "system")

        res_set = IOPreferencesHandler.manage_user_preferences({
            "category": "system",
            "action": "set",
            "settings": {"use_preview_images": True}
        })
        self.assertEqual(res_set["status"], "updated")

    def test_manage_addon(self):
        res_status = IOPreferencesHandler.manage_addon({"module_name": "cycles", "action": "check_status"})
        self.assertTrue(res_status["is_enabled"])

        res_en = IOPreferencesHandler.manage_addon({"module_name": "cycles", "action": "enable"})
        self.assertEqual(res_en["status"], "enabled")

        res_dis = IOPreferencesHandler.manage_addon({"module_name": "cycles", "action": "disable"})
        self.assertEqual(res_dis["status"], "disabled")

    def test_manage_external_data(self):
        actions = ["pack_all", "unpack_all", "find_missing", "make_paths_relative", "make_paths_absolute"]
        for act in actions:
            res = IOPreferencesHandler.manage_external_data({"action": act, "directory": "/tmp"})
            self.assertEqual(res["status"], "completed")

    def test_universal_import_export(self):
        formats = ["fbx", "obj", "gltf", "glb", "usd", "abc", "stl", "ply", "bvh", "dae"]
        for fmt in formats:
            # Export
            res_exp = IOPreferencesHandler.universal_import_export({
                "format": fmt,
                "mode": "export",
                "filepath": f"/tmp/test_export.{fmt}"
            })
            self.assertEqual(res_exp["status"], "success")

            # Import
            res_imp = IOPreferencesHandler.universal_import_export({
                "format": fmt,
                "mode": "import",
                "filepath": f"/tmp/test_export.{fmt}"
            })
            self.assertEqual(res_imp["status"], "success")


if __name__ == "__main__":
    unittest.main()
