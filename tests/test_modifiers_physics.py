"""
Unit tests for ModifiersPhysicsHandler.
"""

import unittest
from tests.mock_bpy import install_mocks

mock_bpy = install_mocks()

from blender_mcp.handlers.modifiers_physics import ModifiersPhysicsHandler


class TestModifiersPhysicsHandler(unittest.TestCase):
    def test_manage_modifier(self):
        # List
        res_list = ModifiersPhysicsHandler.manage_modifier({"action": "list", "object_name": "Cube"})
        self.assertEqual(res_list["status"], "success")

        # Add Subsurf
        res_add = ModifiersPhysicsHandler.manage_modifier({
            "action": "add",
            "object_name": "Cube",
            "modifier_name": "Subdivision",
            "modifier_type": "SUBSURF",
            "properties": {"levels": 2, "render_levels": 3}
        })
        self.assertEqual(res_add["status"], "success")

        # Configure
        res_cfg = ModifiersPhysicsHandler.manage_modifier({
            "action": "configure",
            "object_name": "Cube",
            "modifier_name": "Subdivision",
            "properties": {"levels": 3}
        })
        self.assertEqual(res_cfg["status"], "success")

        # Reorder
        res_ro = ModifiersPhysicsHandler.manage_modifier({
            "action": "reorder",
            "object_name": "Cube",
            "modifier_name": "Subdivision",
            "new_index": 0
        })
        self.assertEqual(res_ro["status"], "success")

        # Apply
        res_app = ModifiersPhysicsHandler.manage_modifier({
            "action": "apply",
            "object_name": "Cube",
            "modifier_name": "Subdivision"
        })
        self.assertEqual(res_app["status"], "success")

        # Remove
        ModifiersPhysicsHandler.manage_modifier({
            "action": "add",
            "object_name": "Cube",
            "modifier_name": "BevelMod",
            "modifier_type": "BEVEL"
        })
        res_rem = ModifiersPhysicsHandler.manage_modifier({
            "action": "remove",
            "object_name": "Cube",
            "modifier_name": "BevelMod"
        })
        self.assertEqual(res_rem["status"], "success")

    def test_setup_physics_simulation(self):
        # Rigid body enable & disable
        res_rb = ModifiersPhysicsHandler.setup_physics_simulation({
            "object_name": "Cube",
            "physics_type": "RIGID_BODY",
            "action": "enable",
            "rigid_body": {"type": "ACTIVE", "mass": 5.0}
        })
        self.assertEqual(res_rb["status"], "success")

        res_rb_dis = ModifiersPhysicsHandler.setup_physics_simulation({
            "object_name": "Cube",
            "physics_type": "RIGID_BODY",
            "action": "disable"
        })
        self.assertEqual(res_rb_dis["status"], "success")

        # Cloth enable with preset & disable
        res_cloth = ModifiersPhysicsHandler.setup_physics_simulation({
            "object_name": "Cube",
            "physics_type": "CLOTH",
            "action": "enable",
            "cloth": {"preset": "SILK", "mass": 0.2}
        })
        self.assertEqual(res_cloth["status"], "success")

        res_cloth_dis = ModifiersPhysicsHandler.setup_physics_simulation({
            "object_name": "Cube",
            "physics_type": "CLOTH",
            "action": "disable"
        })
        self.assertEqual(res_cloth_dis["status"], "success")

        # Collision
        res_col = ModifiersPhysicsHandler.setup_physics_simulation({
            "object_name": "Cube",
            "physics_type": "COLLISION",
            "action": "enable"
        })
        self.assertEqual(res_col["status"], "success")

        # Fluid
        res_fl = ModifiersPhysicsHandler.setup_physics_simulation({
            "object_name": "Cube",
            "physics_type": "FLUID",
            "action": "enable",
            "fluid": {"fluid_type": "DOMAIN", "domain_type": "LIQUID"}
        })
        self.assertEqual(res_fl["status"], "success")

        # Force field
        res_ff = ModifiersPhysicsHandler.setup_physics_simulation({
            "object_name": "Cube",
            "physics_type": "FORCE_FIELD",
            "action": "enable",
            "force_field": {"field_type": "WIND", "strength": 10.0}
        })
        self.assertEqual(res_ff["status"], "success")

        # Bake
        res_bake = ModifiersPhysicsHandler.setup_physics_simulation({
            "object_name": "Cube",
            "physics_type": "RIGID_BODY",
            "action": "bake",
            "bake_frame_start": 1,
            "bake_frame_end": 50
        })
        self.assertEqual(res_bake["status"], "success")

    def test_manage_particle_system(self):
        # Add
        res_add = ModifiersPhysicsHandler.manage_particle_system({
            "object_name": "Cube",
            "action": "add",
            "system_name": "Sparks",
            "config": {"system_type": "EMITTER", "count": 500, "lifetime": 30.0}
        })
        self.assertEqual(res_add["status"], "success")

        # List
        res_list = ModifiersPhysicsHandler.manage_particle_system({"object_name": "Cube", "action": "list"})
        self.assertEqual(res_list["status"], "success")

        # Configure
        res_cfg = ModifiersPhysicsHandler.manage_particle_system({
            "object_name": "Cube",
            "action": "configure",
            "system_name": "Sparks",
            "config": {"count": 1000}
        })
        self.assertEqual(res_cfg["status"], "success")

        # Remove
        res_rem = ModifiersPhysicsHandler.manage_particle_system({
            "object_name": "Cube",
            "action": "remove",
            "system_name": "Sparks"
        })
        self.assertEqual(res_rem["status"], "success")


if __name__ == "__main__":
    unittest.main()
