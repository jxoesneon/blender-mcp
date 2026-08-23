"""
Unit tests for ObjectsHierarchyHandler.
"""

import unittest
from tests.mock_bpy import install_mocks

mock_bpy = install_mocks()

from blender_mcp.handlers.objects_hierarchy import ObjectsHierarchyHandler


class TestObjectsHierarchyHandler(unittest.TestCase):
    def test_manage_objects(self):
        # Create
        res_create = ObjectsHierarchyHandler.manage_objects({
            "action": "create",
            "primitive_type": "MESH_CUBE",
            "name": "Box1",
            "location": [1, 2, 3]
        })
        self.assertEqual(res_create["status"], "success")

        # Duplicate
        res_dup = ObjectsHierarchyHandler.manage_objects({"action": "duplicate", "names": ["Box1"], "linked": True})
        self.assertEqual(res_dup["status"], "success")

        # Rename
        res_rn = ObjectsHierarchyHandler.manage_objects({"action": "rename", "name": "Box1", "new_name": "BoxRenamed"})
        self.assertEqual(res_rn["status"], "success")

        # Set Parent
        res_p = ObjectsHierarchyHandler.manage_objects({
            "action": "set_parent",
            "parent_name": "Cube",
            "child_names": ["BoxRenamed"],
            "keep_transform": True
        })
        self.assertEqual(res_p["status"], "success")

        # Clear Parent
        res_cp = ObjectsHierarchyHandler.manage_objects({"action": "clear_parent", "child_names": ["BoxRenamed"]})
        self.assertEqual(res_cp["status"], "success")

        # Manipulate parent inverse
        res_pi = ObjectsHierarchyHandler.manage_objects({
            "action": "manipulate_parent_inverse",
            "name": "BoxRenamed",
            "matrix_parent_inverse": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
        })
        self.assertEqual(res_pi["status"], "success")

        # Delete
        res_del = ObjectsHierarchyHandler.manage_objects({"action": "delete", "names": ["BoxRenamed"], "delete_hierarchy": True})
        self.assertEqual(res_del["status"], "success")

    def test_manage_collections(self):
        # Create
        res_c = ObjectsHierarchyHandler.manage_collections({"action": "create", "name": "Environment"})
        self.assertEqual(res_c["status"], "success")

        # Link object
        res_l = ObjectsHierarchyHandler.manage_collections({
            "action": "link_objects",
            "name": "Environment",
            "object_names": ["Cube"],
            "unlink_from_all_others": False
        })
        self.assertEqual(res_l["status"], "success")

        # Set visibility
        res_vis = ObjectsHierarchyHandler.manage_collections({
            "action": "set_visibility",
            "name": "Environment",
            "hide_viewport": False,
            "color_tag": "COLOR_01"
        })
        self.assertEqual(res_vis["status"], "success")

        # Rename
        res_rn = ObjectsHierarchyHandler.manage_collections({"action": "rename", "name": "Environment", "new_name": "EnvRenamed"})
        self.assertEqual(res_rn["status"], "success")

        # Move
        res_mv = ObjectsHierarchyHandler.manage_collections({"action": "move", "name": "EnvRenamed", "parent_collection": "Collection"})
        self.assertEqual(res_mv["status"], "success")

        # Delete
        res_del = ObjectsHierarchyHandler.manage_collections({"action": "delete", "name": "EnvRenamed"})
        self.assertEqual(res_del["status"], "success")

    def test_transform_object(self):
        res = ObjectsHierarchyHandler.transform_object({
            "name": "Cube",
            "location": [10.0, 20.0, 30.0],
            "relative_location": False,
            "rotation": [0.0, 45.0, 90.0],
            "rotation_in_degrees": True,
            "scale": [2.0, 2.0, 2.0],
        })
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["location"], [10.0, 20.0, 30.0])

        res_rel = ObjectsHierarchyHandler.transform_object({
            "name": "Cube",
            "location": [1.0, 1.0, 1.0],
            "relative_location": True,
            "scale": [0.5, 0.5, 0.5],
            "relative_scale": True,
        })
        self.assertEqual(res_rel["status"], "success")

    def test_manage_constraints(self):
        res_add = ObjectsHierarchyHandler.manage_constraints({
            "action": "add",
            "object_name": "Cube",
            "constraint_name": "TrackToTarget",
            "constraint_type": "TRACK_TO",
            "config": {"target": "Cube", "influence": 0.8}
        })
        self.assertEqual(res_add["status"], "success")

        res_get = ObjectsHierarchyHandler.manage_constraints({"action": "get", "object_name": "Cube"})
        self.assertEqual(res_get["status"], "success")

        res_up = ObjectsHierarchyHandler.manage_constraints({
            "action": "update",
            "object_name": "Cube",
            "constraint_name": "TrackToTarget",
            "config": {"influence": 1.0}
        })
        self.assertEqual(res_up["status"], "success")

        res_rem = ObjectsHierarchyHandler.manage_constraints({
            "action": "remove",
            "object_name": "Cube",
            "constraint_name": "TrackToTarget"
        })
        self.assertEqual(res_rem["status"], "success")


if __name__ == "__main__":
    unittest.main()
