"""
Coverage maximizer test suite covering all remaining branch paths and error conditions.
"""

import os
import queue
import socket
import struct
import unittest
from unittest.mock import MagicMock, patch

from tests.mock_bpy import install_mocks

mock_bpy = install_mocks()

import addon
import blender_mcp
from blender_mcp import *
from blender_mcp.handlers import *
from blender_mcp.handlers.base import BaseHandler
from blender_mcp.handlers.reflection import ReflectionHandler
from blender_mcp.handlers.scene_world import SceneWorldHandler
from blender_mcp.handlers.objects_hierarchy import ObjectsHierarchyHandler
from blender_mcp.handlers.mesh_geometry import MeshGeometryHandler
from blender_mcp.handlers.materials_shading import MaterialsShadingHandler
from blender_mcp.handlers.modifiers_physics import ModifiersPhysicsHandler
from blender_mcp.handlers.animation_rigging import AnimationRiggingHandler
from blender_mcp.handlers.rendering import RenderingHandler
from blender_mcp.handlers.io_preferences import IOPreferencesHandler
import blender_mcp.server as server
import blender_mcp.utils as utils


class TestCoverageMaximizer(unittest.TestCase):
    def test_imports_and_init(self):
        self.assertIsNotNone(blender_mcp.__version__)
        self.assertIsNotNone(blender_mcp.__author__)
        self.assertIsNotNone(utils.encode_frame)
        self.assertIsNotNone(utils.read_frame)
        self.assertIsNotNone(utils.kelvin_to_rgb)
        self.assertIsNotNone(utils.serialize_bpy_value)

    def test_addon_client_handler_loop(self):
        # Mock client connection
        mock_conn = MagicMock()
        payload = {"action": "eval_expression", "params": {"expression": "5 + 5"}}
        encoded = addon.encode_frame(payload)
        mock_conn.recv.side_effect = [encoded[:4], encoded[4:], ConnectionError("Done")]

        addon._is_running = True
        with patch.object(addon._task_queue, "put", side_effect=lambda task: task["response_channel"].put({"success": True, "result": {"result": 10}})):
            addon._client_handler(mock_conn, ("127.0.0.1", 12345))
        
        mock_conn.sendall.assert_called()

    def test_addon_socket_listener_exception(self):
        with patch("socket.socket") as mock_sock_cls:
            mock_s = MagicMock()
            mock_sock_cls.return_value = mock_s
            mock_s.bind.side_effect = Exception("Bind error")
            addon._socket_listener_thread("127.0.0.1", 8888)
            self.assertEqual(addon._server_status, "Stopped")

    def test_reflection_error_branches(self):
        with self.assertRaises(Exception):
            ReflectionHandler.get_property({"path": "bpy.data.objects['NonExistentObj'].location"})

        with self.assertRaises(Exception):
            ReflectionHandler.set_property({"path": "bpy.data.objects['NonExistentObj'].location", "value": 1})

        with self.assertRaises(Exception):
            ReflectionHandler.eval_expression({"expression": "undefined_var_123"})

        with self.assertRaises(Exception):
            ReflectionHandler.inspect_bpy_path({"path": "bpy.data.objects['NonExistentObj'].location"})

    def test_server_tools_all_parameters(self):
        with patch("blender_mcp.server.default_client.send_command") as mock_send:
            mock_send.return_value = {"status": "success"}

            # Call every tool in server with exhaustive parameters
            server.inspect_bpy_path("bpy.context.scene")
            server.get_rna_schema("Object")
            server.execute_operator("mesh.primitive_cube_add", execution_context="INVOKE_DEFAULT", kwargs={"size": 1.0}, context_override={"area_type": "VIEW_3D"})
            server.get_property("bpy.context.scene.name")
            server.set_property("bpy.context.scene.name", "NewSceneName")
            server.eval_expression("1 + 1")
            server.exec_script("print(1)", use_transaction_rollback=False)

            server.manage_scene(action="create", scene_name="Sc1", create_mode="NEW", unit_system="METRIC", unit_length="METERS", unit_rotation="DEGREES", unit_scale_length=1.0, gravity=[0, 0, -9.81], use_gravity=True, active_camera_name="Cam")
            server.manage_world(mode="HDRI", world_name="World", color=[1, 1, 1], strength=1.0, hdri_filepath="/tmp/h.hdr", hdri_rotation_z=10.0, sky_type="NISHITA", sky_sun_intensity=1.0, sky_sun_elevation=45.0, sky_sun_rotation=180.0, volume_type="SCATTER", volume_density=0.1, volume_color=[1, 1, 1], volume_anisotropy=0.5)
            server.manage_viewport(action="switch_workspace", workspace_name="Layout", shading_type="SOLID", shading_options={}, show_overlays=True, overlay_toggles={}, clip_start=0.1, clip_end=100.0, lens=50.0, cursor_location=[0, 0, 0], cursor_rotation_euler=[0, 0, 0], lock_object_name="Cube", lock_cursor=True)
            server.manage_camera(action="create", camera_name="Cam1", type="PERSP", focal_length=50.0, ortho_scale=6.0, sensor_fit="AUTO", sensor_width=36.0, sensor_height=24.0, clip_start=0.1, clip_end=1000.0, shift_x=0.0, shift_y=0.0, dof={}, composition_guides={})
            server.manage_light(action="create", light_name="L1", type="POINT", energy=100.0, color_type="RGB", color_rgb=[1, 1, 1], color_kelvin=6500.0, radius=0.25, area_shape="SQUARE", area_size_x=1.0, area_size_y=1.0, spot_size=45.0, spot_blend=0.15, spot_show_cone=True, use_shadow=True, light_linking={})
            server.manage_objects(action="create", names=["O1"], name="O1", new_name="O2", primitive_type="MESH_CUBE", location=[0, 0, 0], rotation=[0, 0, 0], scale=[1, 1, 1], linked=False, delete_hierarchy=False, child_names=[], parent_name="P", keep_transform=True, matrix_parent_inverse=[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]])
            server.manage_collections(action="create", name="C1", new_name="C2", parent_collection="Collection", object_names=["O1"], unlink_from_all_others=False, hide_viewport=False, hide_render=False, hide_select=False, color_tag="COLOR_01")
            server.transform_object(name="Cube", space="GLOBAL", location=[0, 0, 0], relative_location=False, rotation_mode="XYZ", rotation=[0, 0, 0], rotation_in_degrees=False, relative_rotation=False, scale=[1, 1, 1], relative_scale=False, delta=False)
            server.manage_constraints(action="add", object_name="Cube", bone_name="Bone", constraint_name="C", constraint_type="TRACK_TO", config={}, new_index=0)
            server.create_primitive(primitive_type="CUBE", name="CubeP", location=[0, 0, 0], rotation=[0, 0, 0], scale=[1, 1, 1], size=2.0, radius=1.0, depth=2.0, segments=32, ring_count=16, subdivisions=3)
            server.manipulate_mesh(object_name="Cube", operation="EXTRUDE_FACES", vertex_indices=[0], edge_indices=[0], face_indices=[0], translation=[0, 0, 1], offset=0.2, thickness=0.0, segments=2, profile=0.5, merge_type="DISTANCE", boolean_target="Cube", boolean_operation="DIFFERENCE", shading_mode="SMOOTH")
            server.create_curve(name="Curve1", curve_type="BEZIER", points=[{"co": [0,0,0]}], is_cyclic=False, bevel_depth=0.1, extrude=0.0)
            server.create_text_3d(body="Text", name="T1", location=[0, 0, 0], size=1.0, extrude=0.1, bevel_depth=0.01)
            server.manage_geometry_nodes(object_name="Cube", modifier_name="GN", tree_name="Tree", nodes=[], links=[])
            server.manage_materials(action="create", material_name="M1", new_name="M2", object_name="Cube", slot_index=0, face_indices=[0], use_nodes=True)
            server.inspect_shader_tree(material_name="M1", group_name="G")
            server.manage_shader_node(action="create", material_name="M1", node_type="ShaderNodeTexNoise", node_name="N", location=[0, 0], group_name="G")
            server.manage_shader_links(material_name="M1", from_node="A", from_socket="Color", to_node="B", to_socket="Base Color", action="link", group_name="G")
            server.set_socket_value(material_name="M1", node_name="A", socket_identifier="Color", value=[1, 1, 1, 1], group_name="G")
            server.setup_procedural_texture(material_name="M1", texture_type="noise", coord_type="UV", location=[0, 0, 0], rotation=[0, 0, 0], scale=[1, 1, 1], connect_to_principled=True)
            server.assign_image_texture(material_name="M1", image_path="/tmp/i.png", pack_image=False, target_socket="Base Color")
            server.perform_uv_unwrap(object_name="Cube", method="smart_project", angle_limit=66.0, island_margin=0.02)
            server.manage_modifier(object_name="Cube", action="add", modifier_name="Sub", modifier_type="SUBSURF", new_index=0, properties={})
            server.setup_physics_simulation(object_name="Cube", physics_type="RIGID_BODY", action="enable", rigid_body={}, cloth={}, soft_body={}, fluid={}, force_field={})
            server.manage_particle_system(object_name="Cube", action="add", system_name="P1", config={})
            server.timeline_control(frame_start=1, frame_end=250, current_frame=1, fps=24, fps_base=1.0)
            server.insert_keyframe(target_name="Cube", data_path="location", target_type="OBJECT", array_index=0, frame=1.0, value=0.0, group="Transform", interpolation="BEZIER")
            server.delete_keyframe(target_name="Cube", data_path="location", target_type="OBJECT", array_index=0, frame=1.0)
            server.list_fcurves(target_name="Cube", target_type="OBJECT")
            server.manage_driver(target_name="Cube", data_path="location", action="add_driver", target_type="OBJECT", array_index=0, driver_expression="1.0")
            server.manage_armature(armature_name="Arm", action="create_armature", location=[0, 0, 0], rotation_euler=[0, 0, 0], bones=[], bone_name="B", bone_transforms={}, constraint_type="IK", constraint_config={})
            server.configure_render_engine(engine="CYCLES", device_type="GPU", render_samples=128, viewport_samples=32, use_noise_threshold=True, noise_threshold=0.01, bounces={})
            server.configure_output_and_passes(resolution_x=1920, resolution_y=1080, resolution_percentage=100, fps=24, output_filepath="/tmp/r", file_format="PNG", passes={})
            server.configure_color_management(display_device="sRGB", view_transform="AgX", look="None", exposure=0.0, gamma=1.0)
            server.manage_compositor_tree(action="inspect", node_type="CompositorNodeComposite", node_name="N", location=[0, 0], from_node="A", from_socket="Image", to_node="B", to_socket="Image")
            server.execute_capture_or_render(mode="STILL", camera_name="Cam", frame_start=1, frame_end=10, shading_mode="RENDERED", show_overlays=False, output_path="/tmp/r.png", return_base64=True)
            server.manage_user_preferences(category="system", action="get", settings={})
            server.manage_addon(module_name="cycles", action="enable", filepath="/tmp/a.zip")
            server.manage_external_data(action="pack_all", directory="/tmp")
            server.universal_import_export(format="fbx", mode="export", filepath="/tmp/out.fbx", options={})


if __name__ == "__main__":
    unittest.main()
