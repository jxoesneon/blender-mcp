"""
Unit tests for FastMCP server tool registry and endpoint invocation.
"""

import unittest
from unittest.mock import patch

from tests.mock_bpy import install_mocks

install_mocks()

import blender_mcp.server as server


class TestServerTools(unittest.TestCase):
    @patch("blender_mcp.server.default_client.send_command")
    def test_reflection_tools(self, mock_send):
        mock_send.return_value = {"status": "success"}

        server.inspect_bpy_path("bpy.context.scene")
        mock_send.assert_called_with("inspect_bpy_path", {"path": "bpy.context.scene"})

        server.get_rna_schema("Object")
        mock_send.assert_called_with("get_rna_schema", {"rna_type_name": "Object"})

        server.execute_operator("mesh.primitive_cube_add", kwargs={"size": 2.0})
        mock_send.assert_called_with("execute_operator", {
            "operator": "mesh.primitive_cube_add",
            "execution_context": "EXEC_DEFAULT",
            "kwargs": {"size": 2.0},
            "context_override": {}
        })

        server.get_property("bpy.data.objects['Cube'].location")
        mock_send.assert_called_with("get_property", {"path": "bpy.data.objects['Cube'].location"})

        server.set_property("bpy.data.objects['Cube'].location", [1, 2, 3])
        mock_send.assert_called_with("set_property", {"path": "bpy.data.objects['Cube'].location", "value": [1, 2, 3]})

        server.eval_expression("1 + 1")
        mock_send.assert_called_with("eval_expression", {"expression": "1 + 1"})

        server.exec_script("print('test')")
        mock_send.assert_called_with("exec_script", {"script": "print('test')", "use_transaction_rollback": True})

    @patch("blender_mcp.server.default_client.send_command")
    def test_domain_tools(self, mock_send):
        mock_send.return_value = {"status": "success"}

        server.manage_scene(action="create", scene_name="SceneX")
        server.manage_world(mode="COLOR", color=[1, 1, 1])
        server.manage_viewport(action="set_shading", shading_type="RENDERED")
        server.manage_camera(action="create", camera_name="CamX")
        server.manage_light(action="create", light_name="LightX")
        server.manage_objects(action="create", primitive_type="MESH_CUBE")
        server.manage_collections(action="create", name="ColX")
        server.transform_object(name="Cube", location=[1, 2, 3])
        server.manage_constraints(action="add", object_name="Cube", constraint_type="TRACK_TO")
        server.create_primitive(primitive_type="UV_SPHERE")
        server.manipulate_mesh(object_name="Cube", operation="EXTRUDE_FACES")
        server.create_curve(name="CurveX")
        server.create_text_3d(body="Hello")
        server.manage_geometry_nodes(object_name="Cube")
        server.manage_materials(action="create", material_name="MatX")
        server.inspect_shader_tree(material_name="MatX")
        server.manage_shader_node(action="create", material_name="MatX", node_type="ShaderNodeTexNoise")
        server.manage_shader_links(material_name="MatX", from_node="A", from_socket="Color", to_node="B", to_socket="Base Color")
        server.set_socket_value(material_name="MatX", node_name="A", socket_identifier="Scale", value=5.0)
        server.setup_procedural_texture(material_name="MatX", texture_type="noise")
        server.assign_image_texture(material_name="MatX", image_path="/tmp/img.png")
        server.perform_uv_unwrap(object_name="Cube")
        server.manage_modifier(object_name="Cube", action="add", modifier_type="SUBSURF")
        server.setup_physics_simulation(object_name="Cube", physics_type="RIGID_BODY")
        server.manage_particle_system(object_name="Cube", action="add")
        server.timeline_control(frame_start=1, frame_end=100)
        server.insert_keyframe(target_name="Cube", data_path="location")
        server.delete_keyframe(target_name="Cube", data_path="location")
        server.list_fcurves(target_name="Cube")
        server.manage_driver(target_name="Cube", data_path="location")
        server.manage_armature(armature_name="ArmX")
        server.configure_render_engine(engine="CYCLES")
        server.configure_output_and_passes(resolution_x=1920, resolution_y=1080)
        server.configure_color_management(view_transform="AgX")
        server.manage_compositor_tree(action="inspect")
        server.execute_capture_or_render(mode="STILL")
        server.manage_user_preferences(category="system")
        server.manage_addon(module_name="cycles", action="enable")
        server.manage_external_data(action="pack_all")
        server.universal_import_export(format="fbx", mode="export", filepath="/tmp/out.fbx")

        self.assertGreaterEqual(mock_send.call_count, 35)


if __name__ == "__main__":
    unittest.main()
