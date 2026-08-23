"""
Unit tests for MeshGeometryHandler.
"""

import unittest
from tests.mock_bpy import install_mocks

mock_bpy = install_mocks()

from blender_mcp.handlers.mesh_geometry import MeshGeometryHandler


class TestMeshGeometryHandler(unittest.TestCase):
    def test_create_primitive_all_types(self):
        prims = ["CUBE", "UV_SPHERE", "ICO_SPHERE", "CYLINDER", "CONE", "TORUS", "GRID", "PLANE", "CIRCLE", "MONKEY", "EMPTY"]
        for p in prims:
            res = MeshGeometryHandler.create_primitive({
                "primitive_type": p,
                "name": f"Prim_{p}",
                "location": [0, 0, 0],
                "size": 2.0,
                "radius": 1.0,
            })
            self.assertEqual(res["status"], "success")

    def test_manipulate_mesh(self):
        # Shading
        res_shade = MeshGeometryHandler.manipulate_mesh({
            "object_name": "Cube",
            "operation": "SET_SHADING",
            "shading_mode": "SMOOTH"
        })
        self.assertEqual(res_shade["status"], "success")

        # Boolean
        res_bool = MeshGeometryHandler.manipulate_mesh({
            "object_name": "Cube",
            "operation": "BOOLEAN",
            "boolean_target": "Cube",
            "boolean_operation": "DIFFERENCE"
        })
        self.assertEqual(res_bool["status"], "success")

        # Low level bmesh operations
        bmesh_ops = ["EXTRUDE_FACES", "INSET_FACES", "BEVEL", "SUBDIVIDE", "MERGE_VERTICES", "RECALCULATE_NORMALS", "DELETE_ELEMENTS"]
        for op in bmesh_ops:
            res = MeshGeometryHandler.manipulate_mesh({
                "object_name": "Cube",
                "operation": op,
                "face_indices": [0, 1],
                "translation": [0, 0, 1.0],
                "offset": 0.2,
                "segments": 2,
            })
            self.assertEqual(res["status"], "success")

    def test_create_curve(self):
        res = MeshGeometryHandler.create_curve({
            "name": "SplinePath",
            "curve_type": "BEZIER",
            "points": [
                {"co": [0, 0, 0], "handle_left": [-1, 0, 0], "handle_right": [1, 0, 0]},
                {"co": [5, 5, 0], "handle_left": [4, 5, 0], "handle_right": [6, 5, 0]}
            ],
            "bevel_depth": 0.1,
            "extrude": 0.05
        })
        self.assertEqual(res["status"], "success")

    def test_create_text(self):
        res = MeshGeometryHandler.create_text({
            "name": "BrandTitle",
            "body": "Blender MCP",
            "size": 2.0,
            "extrude": 0.1,
            "bevel_depth": 0.02
        })
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["body"], "Blender MCP")

    def test_create_volume(self):
        res = MeshGeometryHandler.create_volume({"name": "CloudVolume"})
        self.assertEqual(res["status"], "success")

    def test_manage_geometry_nodes(self):
        res = MeshGeometryHandler.manage_geometry_nodes({
            "object_name": "Cube",
            "modifier_name": "ProceduralGeo",
            "nodes": [
                {"name": "GridNode", "type_name": "GeometryNodeMeshGrid", "location": [-200, 0]},
                {"name": "OutNode", "type_name": "NodeGroupOutput", "location": [200, 0]}
            ],
            "links": [
                {"from_node": "GridNode", "to_node": "OutNode"}
            ]
        })
        self.assertEqual(res["status"], "success")


if __name__ == "__main__":
    unittest.main()
