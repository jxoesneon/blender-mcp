"""
Unit tests for AnimationRiggingHandler.
"""

import unittest
from tests.mock_bpy import install_mocks

mock_bpy = install_mocks()

from blender_mcp.handlers.animation_rigging import AnimationRiggingHandler


class TestAnimationRiggingHandler(unittest.TestCase):
    def test_timeline_control(self):
        res = AnimationRiggingHandler.timeline_control({
            "frame_start": 10,
            "frame_end": 300,
            "current_frame": 45,
            "fps": 60,
            "fps_base": 1.001
        })
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["frame_current"], 45)
        self.assertEqual(res["frame_start"], 10)
        self.assertEqual(res["frame_end"], 300)

    def test_insert_and_delete_keyframe(self):
        res_ins = AnimationRiggingHandler.insert_keyframe({
            "target_type": "OBJECT",
            "target_name": "Cube",
            "data_path": "location",
            "array_index": 0,
            "frame": 24,
            "value": 10.0,
            "group": "Transform"
        })
        self.assertEqual(res_ins["status"], "success")

        res_del = AnimationRiggingHandler.delete_keyframe({
            "target_type": "OBJECT",
            "target_name": "Cube",
            "data_path": "location",
            "array_index": 0,
            "frame": 24
        })
        self.assertEqual(res_del["status"], "success")

    def test_fcurves_and_keyframes(self):
        res_list = AnimationRiggingHandler.list_fcurves({"target_type": "OBJECT", "target_name": "Cube"})
        self.assertEqual(res_list["status"], "success")

        res_mod = AnimationRiggingHandler.modify_keyframe({
            "target_type": "OBJECT",
            "target_name": "Cube",
            "data_path": "location",
            "array_index": 0,
            "frame": 1.0,
            "new_frame": 2.0,
            "new_value": 3.5,
            "interpolation": "LINEAR"
        })
        self.assertEqual(res_mod["status"], "success")

    def test_manage_driver(self):
        res_add = AnimationRiggingHandler.manage_driver({
            "target_type": "OBJECT",
            "target_name": "Cube",
            "data_path": "location",
            "array_index": 1,
            "action": "add_driver",
            "driver_expression": "sin(frame * 0.1) * 2.0"
        })
        self.assertEqual(res_add["status"], "success")

        res_rem = AnimationRiggingHandler.manage_driver({
            "target_type": "OBJECT",
            "target_name": "Cube",
            "data_path": "location",
            "array_index": 1,
            "action": "remove_driver"
        })
        self.assertEqual(res_rem["status"], "success")

    def test_manage_nla(self):
        res_push = AnimationRiggingHandler.manage_nla({
            "action": "push_nla",
            "target_name": "Cube",
            "track_name": "MainTrack"
        })
        self.assertEqual(res_push["status"], "success")

        res_cfg = AnimationRiggingHandler.manage_nla({
            "action": "configure_nla",
            "target_name": "Cube",
            "track_name": "MainTrack",
            "strip_name": "DefaultAction",
            "nla_properties": {"scale": 1.5, "repeat": 2.0}
        })
        self.assertEqual(res_cfg["status"], "success")

    def test_manage_armature(self):
        # Create armature
        res_arm = AnimationRiggingHandler.manage_armature({
            "action": "create_armature",
            "armature_name": "RobotRig",
            "bones": [
                {"bone_name": "Root", "head": [0, 0, 0], "tail": [0, 0, 1]},
                {"bone_name": "Spine", "head": [0, 0, 1], "tail": [0, 0, 2], "parent_name": "Root"}
            ]
        })
        self.assertEqual(res_arm["status"], "success")

        # Pose bone
        res_pose = AnimationRiggingHandler.manage_armature({
            "action": "pose_bone",
            "armature_name": "RobotRig",
            "bone_name": "Spine",
            "bone_transforms": {"location": [0, 0, 0.5], "rotation_euler": [0.1, 0, 0]}
        })
        self.assertEqual(res_pose["status"], "success")

        # Add bone constraint
        res_c = AnimationRiggingHandler.manage_armature({
            "action": "add_constraint",
            "armature_name": "RobotRig",
            "bone_name": "Spine",
            "constraint_type": "IK",
            "constraint_config": {"target": "Cube", "chain_count": 2}
        })
        self.assertEqual(res_c["status"], "success")


if __name__ == "__main__":
    unittest.main()
