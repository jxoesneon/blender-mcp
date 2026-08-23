"""
Unit tests for ReflectionHandler (dynamic RNA introspection, operators, scripting).
"""

import unittest
from tests.mock_bpy import install_mocks

mock_bpy = install_mocks()

from blender_mcp.handlers.reflection import ReflectionHandler


class TestReflectionHandler(unittest.TestCase):
    def test_inspect_bpy_path(self):
        res = ReflectionHandler.inspect_bpy_path({"path": "bpy.data.objects['Cube'].location"})
        self.assertEqual(res["path"], "bpy.data.objects['Cube'].location")
        self.assertIn("value", res)

    def test_get_rna_schema(self):
        res = ReflectionHandler.get_rna_schema({"rna_type_name": "Object"})
        self.assertEqual(res["type_name"], "Object")
        self.assertIn("properties", res)

    def test_get_rna_schema_not_found(self):
        with self.assertRaises(ValueError):
            ReflectionHandler.get_rna_schema({"rna_type_name": "NonExistentType"})

    def test_execute_operator(self):
        res = ReflectionHandler.execute_operator({
            "operator": "mesh.primitive_cube_add",
            "kwargs": {"size": 2.0},
            "context_override": {"area_type": "VIEW_3D"}
        })
        self.assertEqual(res["operator"], "mesh.primitive_cube_add")

    def test_execute_operator_invalid(self):
        with self.assertRaises(AttributeError):
            ReflectionHandler.execute_operator({"operator": "non_existent_op.run"})

    def test_get_set_property(self):
        res_set = ReflectionHandler.set_property({"path": "bpy.data.objects['Cube'].location", "value": [5.0, 6.0, 7.0]})
        self.assertEqual(res_set["set_value"], [5.0, 6.0, 7.0])

        res_get = ReflectionHandler.get_property({"path": "bpy.data.objects['Cube'].location"})
        self.assertEqual(res_get["value"], [5.0, 6.0, 7.0])

    def test_eval_expression(self):
        res = ReflectionHandler.eval_expression({"expression": "len(bpy.data.objects)"})
        self.assertGreaterEqual(res["result"], 1)

    def test_exec_script_success(self):
        script = "import bpy\nbpy.data.objects['Cube'].location[0] = 42.0"
        res = ReflectionHandler.exec_script({"script": script, "use_transaction_rollback": True})
        self.assertTrue(res["success"])
        self.assertFalse(res["rolled_back"])

    def test_exec_script_error_rollback(self):
        script = "raise RuntimeError('Script failure simulation')"
        res = ReflectionHandler.exec_script({"script": script, "use_transaction_rollback": True})
        self.assertFalse(res["success"])
        self.assertTrue(res["rolled_back"])
        self.assertIn("Script failure simulation", res["error"])


if __name__ == "__main__":
    unittest.main()
