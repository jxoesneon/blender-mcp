"""
Unit tests for Pydantic input/output schemas.
"""

import unittest
from blender_mcp.schemas import (
    InspectBpyPathInput,
    GetRNASchemaInput,
    ExecuteOperatorInput,
    PropertyGetSetInput,
    ScriptSandboxInput,
    SceneManageInput,
    WorldManageInput,
    ViewportManageInput,
    CameraManageInput,
    LightManageInput,
    ObjectHierarchyInput,
    CollectionManageInput,
    TransformObjectInput,
    ConstraintManageInput,
    MeshPrimitiveInput,
    MeshManipulateInput,
    GeometryNodesInput,
    MaterialManageInput,
    ShaderNodeManageInput,
    UVUnwrapInput,
    ModifierManageInput,
    PhysicsSimulationInput,
    ParticleSystemInput,
    TimelineKeyframeInput,
    ArmatureRiggingInput,
    RenderConfigureInput,
    RenderOutputPassesInput,
    ColorManagementInput,
    CompositorManageInput,
    CaptureRenderInput,
    UserPreferencesInput,
    AddonManageInput,
    ExternalDataInput,
    UniversalIOInput,
    MCPResponse,
)


class TestSchemas(unittest.TestCase):
    def test_reflection_schemas(self):
        obj = InspectBpyPathInput(path="bpy.context.scene")
        self.assertEqual(obj.path, "bpy.context.scene")

        rna = GetRNASchemaInput(rna_type_name="Object")
        self.assertEqual(rna.rna_type_name, "Object")

        op = ExecuteOperatorInput(operator="mesh.primitive_cube_add", kwargs={"size": 2.0})
        self.assertEqual(op.operator, "mesh.primitive_cube_add")

        prop = PropertyGetSetInput(path="bpy.data.objects['Cube'].location", value=[1, 2, 3])
        self.assertEqual(prop.value, [1, 2, 3])

        script = ScriptSandboxInput(script="import bpy\nprint('test')", use_transaction_rollback=True)
        self.assertTrue(script.use_transaction_rollback)

    def test_scene_world_schemas(self):
        sc = SceneManageInput(action="create", scene_name="TestScene", unit_system="METRIC")
        self.assertEqual(sc.scene_name, "TestScene")

        w = WorldManageInput(mode="HDRI", hdri_filepath="/path/to/hdri.hdr")
        self.assertEqual(w.hdri_filepath, "/path/to/hdri.hdr")

        vp = ViewportManageInput(action="set_shading", shading_type="RENDERED")
        self.assertEqual(vp.shading_type, "RENDERED")

        cam = CameraManageInput(action="create", camera_name="MainCam", focal_length=85.0)
        self.assertEqual(cam.focal_length, 85.0)

        lt = LightManageInput(action="create", light_name="SunLight", type="SUN", energy=5.0)
        self.assertEqual(lt.type, "SUN")

    def test_object_mesh_schemas(self):
        obj_h = ObjectHierarchyInput(action="create", primitive_type="MESH_CUBE", location=[0, 0, 0])
        self.assertEqual(obj_h.action, "create")

        col = CollectionManageInput(action="create", name="Props")
        self.assertEqual(col.name, "Props")

        tf = TransformObjectInput(name="Cube", location=[1, 2, 3], relative_location=True)
        self.assertTrue(tf.relative_location)

        cons = ConstraintManageInput(action="add", object_name="Cube", constraint_type="TRACK_TO")
        self.assertEqual(cons.constraint_type, "TRACK_TO")

        prim = MeshPrimitiveInput(primitive_type="UV_SPHERE", radius=2.5)
        self.assertEqual(prim.radius, 2.5)

        mesh_op = MeshManipulateInput(object_name="Cube", operation="EXTRUDE_FACES", translation=[0, 0, 2])
        self.assertEqual(mesh_op.operation, "EXTRUDE_FACES")

        geo = GeometryNodesInput(object_name="Cube", nodes=[{"name": "Grid", "type_name": "GeometryNodeMeshGrid"}])
        self.assertEqual(len(geo.nodes), 1)

    def test_materials_render_schemas(self):
        mat = MaterialManageInput(action="create", material_name="Gold")
        self.assertEqual(mat.material_name, "Gold")

        node = ShaderNodeManageInput(action="create", material_name="Gold", node_type="ShaderNodeBsdfPrincipled")
        self.assertEqual(node.node_type, "ShaderNodeBsdfPrincipled")

        uv = UVUnwrapInput(object_name="Cube", method="smart_project")
        self.assertEqual(uv.method, "smart_project")

        mod = ModifierManageInput(object_name="Cube", action="add", modifier_type="SUBSURF")
        self.assertEqual(mod.modifier_type, "SUBSURF")

        phys = PhysicsSimulationInput(object_name="Cube", physics_type="RIGID_BODY")
        self.assertEqual(phys.physics_type, "RIGID_BODY")

        part = ParticleSystemInput(object_name="Cube", action="add")
        self.assertEqual(part.action, "add")

        tk = TimelineKeyframeInput(action="set_range", frame_start=1, frame_end=120)
        self.assertEqual(tk.frame_end, 120)

        arm = ArmatureRiggingInput(action="create_armature", armature_name="HeroRig")
        self.assertEqual(arm.armature_name, "HeroRig")

        rc = RenderConfigureInput(engine="CYCLES", render_samples=256)
        self.assertEqual(rc.render_samples, 256)

        rp = RenderOutputPassesInput(resolution_x=3840, resolution_y=2160)
        self.assertEqual(rp.resolution_x, 3840)

        cm = ColorManagementInput(view_transform="AgX")
        self.assertEqual(cm.view_transform, "AgX")

        comp = CompositorManageInput(action="add_node", node_type="CompositorNodeBlur")
        self.assertEqual(comp.node_type, "CompositorNodeBlur")

        cap = CaptureRenderInput(mode="VIEWPORT_SCREENSHOT")
        self.assertEqual(cap.mode, "VIEWPORT_SCREENSHOT")

        pref = UserPreferencesInput(category="system", action="get")
        self.assertEqual(pref.category, "system")

        addon = AddonManageInput(module_name="cycles", action="enable")
        self.assertEqual(addon.module_name, "cycles")

        ext = ExternalDataInput(action="pack_all")
        self.assertEqual(ext.action, "pack_all")

        uio = UniversalIOInput(format="fbx", mode="export", filepath="/tmp/model.fbx")
        self.assertEqual(uio.format, "fbx")

        resp = MCPResponse(status="success", result={"id": 1})
        self.assertEqual(resp.status, "success")


if __name__ == "__main__":
    unittest.main()
