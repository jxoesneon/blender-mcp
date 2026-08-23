"""
Unit tests for colors and serialization utilities.
"""

import math
import unittest
from tests.mock_bpy import install_mocks

install_mocks()

from blender_mcp.utils.colors import kelvin_to_rgb
from blender_mcp.utils.serialization import serialize_bpy_value
import mathutils


class TestColorsSerialization(unittest.TestCase):
    def test_kelvin_to_rgb(self):
        # Warm light (e.g. 2700K)
        r, g, b = kelvin_to_rgb(2700)
        self.assertGreater(r, b)
        self.assertTrue(0.0 <= r <= 1.0)
        self.assertTrue(0.0 <= g <= 1.0)
        self.assertTrue(0.0 <= b <= 1.0)

        # Daylight (e.g. 6500K)
        r65, g65, b65 = kelvin_to_rgb(6500)
        self.assertTrue(0.0 <= r65 <= 1.0)

        # Cool light (e.g. 10000K)
        r10, g10, b10 = kelvin_to_rgb(10000)
        self.assertGreater(b10, r10)

        # Edge cases
        kelvin_to_rgb(500) # clamped to 1000
        kelvin_to_rgb(15000) # clamped to 12000

    def test_serialize_primitives(self):
        self.assertIsNone(serialize_bpy_value(None))
        self.assertEqual(serialize_bpy_value(True), True)
        self.assertEqual(serialize_bpy_value(123), 123)
        self.assertEqual(serialize_bpy_value(3.14), 3.14)
        self.assertEqual(serialize_bpy_value("hello"), "hello")
        self.assertEqual(serialize_bpy_value(float("nan")), "nan")
        self.assertEqual(serialize_bpy_value(float("inf")), "inf")

    def test_serialize_collections(self):
        self.assertEqual(serialize_bpy_value([1, 2, [3, 4]]), [1, 2, [3, 4]])
        self.assertEqual(serialize_bpy_value((1, 2)), [1, 2])
        self.assertEqual(serialize_bpy_value({1, 2}), [1, 2])
        self.assertEqual(serialize_bpy_value({"a": 1, "b": [2, 3]}), {"a": 1, "b": [2, 3]})

    def test_serialize_mathutils(self):
        vec = mathutils.Vector([1.0, 2.0, 3.0])
        self.assertEqual(serialize_bpy_value(vec), [1.0, 2.0, 3.0])

        col = mathutils.Color([0.1, 0.2, 0.3])
        self.assertEqual(serialize_bpy_value(col), [0.1, 0.2, 0.3])

        eul = mathutils.Euler([0.0, 1.0, 2.0], "XYZ")
        self.assertEqual(serialize_bpy_value(eul), {"angles": [0.0, 1.0, 2.0], "order": "XYZ"})

        quat = mathutils.Quaternion(1.0, 0.0, 0.0, 0.0)
        self.assertEqual(serialize_bpy_value(quat), {"w": 1.0, "x": 0.0, "y": 0.0, "z": 0.0})

        mat = mathutils.Matrix([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
        self.assertEqual(serialize_bpy_value(mat), [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])

    def test_serialize_rna_struct(self):
        import bpy
        cube = bpy.data.objects["Cube"]
        res = serialize_bpy_value(cube)
        self.assertIn("_rna_type", res)
        self.assertEqual(res["name"], "Cube")


if __name__ == "__main__":
    unittest.main()
