"""
Unit tests for MaterialsShadingHandler.
"""

import os
import unittest
from tests.mock_bpy import install_mocks

mock_bpy = install_mocks()

from blender_mcp.handlers.materials_shading import MaterialsShadingHandler


class TestMaterialsShadingHandler(unittest.TestCase):
    def setUp(self):
        MaterialsShadingHandler.manage_materials({"action": "create", "material_name": "Chrome"})

    def test_manage_materials(self):
        # Duplicate
        res_dup = MaterialsShadingHandler.manage_materials({"action": "duplicate", "material_name": "Chrome", "new_name": "Chrome2"})
        self.assertEqual(res_dup["status"], "success")

        # Set use nodes
        res_nodes = MaterialsShadingHandler.manage_materials({"action": "set_use_nodes", "material_name": "Chrome", "use_nodes": True})
        self.assertEqual(res_nodes["status"], "success")

        # Assign
        res_assign = MaterialsShadingHandler.manage_materials({
            "action": "assign",
            "material_name": "Chrome",
            "object_name": "Cube",
            "face_indices": [0, 1, 2]
        })
        self.assertEqual(res_assign["status"], "success")

        # Delete
        res_del = MaterialsShadingHandler.manage_materials({"action": "delete", "material_name": "Chrome2"})
        self.assertEqual(res_del["status"], "success")

    def test_inspect_and_manage_nodes(self):
        # Inspect
        res_ins = MaterialsShadingHandler.inspect_shader_tree({"material_name": "Chrome"})
        self.assertEqual(res_ins["status"], "success")

        # Create node
        res_node = MaterialsShadingHandler.manage_shader_node({
            "action": "create",
            "material_name": "Chrome",
            "node_type": "ShaderNodeTexNoise",
            "node_name": "NoisePattern",
            "location": [-300, 0]
        })
        self.assertEqual(res_node["status"], "success")

        # Move node
        res_mv = MaterialsShadingHandler.manage_shader_node({
            "action": "move",
            "material_name": "Chrome",
            "node_name": "NoisePattern",
            "location": [-400, 50]
        })
        self.assertEqual(res_mv["status"], "success")

        # Set socket value
        res_val = MaterialsShadingHandler.set_socket_value({
            "material_name": "Chrome",
            "node_name": "NoisePattern",
            "socket_identifier": "Scale",
            "value": 15.0
        })
        self.assertEqual(res_val["status"], "success")

        # Delete node
        res_del = MaterialsShadingHandler.manage_shader_node({
            "action": "delete",
            "material_name": "Chrome",
            "node_name": "NoisePattern"
        })
        self.assertEqual(res_del["status"], "success")

    def test_manage_shader_links(self):
        # Create 2 nodes
        MaterialsShadingHandler.manage_shader_node({"action": "create", "material_name": "Chrome", "node_type": "ShaderNodeTexNoise", "node_name": "N1"})
        MaterialsShadingHandler.manage_shader_node({"action": "create", "material_name": "Chrome", "node_type": "ShaderNodeBsdfPrincipled", "node_name": "N2"})

        res_link = MaterialsShadingHandler.manage_shader_links({
            "action": "link",
            "material_name": "Chrome",
            "from_node": "N1",
            "from_socket": "Color",
            "to_node": "N2",
            "to_socket": "Base Color"
        })
        self.assertEqual(res_link["status"], "success")

        res_unlink = MaterialsShadingHandler.manage_shader_links({
            "action": "unlink",
            "material_name": "Chrome",
            "from_node": "N1",
            "from_socket": "Color",
            "to_node": "N2",
            "to_socket": "Base Color"
        })
        self.assertEqual(res_unlink["status"], "success")

    def test_setup_procedural_texture(self):
        res = MaterialsShadingHandler.setup_procedural_texture({
            "material_name": "Chrome",
            "texture_type": "voronoi",
            "coord_type": "UV",
            "location": [0, 0, 0],
            "scale": [5, 5, 5]
        })
        self.assertEqual(res["status"], "success")

    def test_assign_image_texture(self):
        temp_img = "/tmp/test_tex.png"
        with open(temp_img, "wb") as f:
            f.write(b"PNG_DATA")

        res = MaterialsShadingHandler.assign_image_texture({
            "material_name": "Chrome",
            "image_path": temp_img,
            "pack_image": True,
            "target_socket": "Base Color"
        })
        self.assertEqual(res["status"], "success")
        if os.path.exists(temp_img):
            os.remove(temp_img)

    def test_perform_uv_unwrap(self):
        res = MaterialsShadingHandler.perform_uv_unwrap({
            "object_name": "Cube",
            "method": "smart_project",
            "angle_limit": 66.0,
            "island_margin": 0.02
        })
        self.assertEqual(res["status"], "success")


if __name__ == "__main__":
    unittest.main()
