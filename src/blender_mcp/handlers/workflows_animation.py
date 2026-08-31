"""
Composite workflow handlers for animation finalization and retargeting.
"""

from __future__ import annotations

import difflib
import math
from typing import Any, Dict, List, Optional

from blender_mcp.exceptions import BlenderExecutionError
from blender_mcp.handlers.base import BaseHandler


class AnimationWorkflowsHandler(BaseHandler):
    """Composite workflows that orchestrate multiple animation operations.

    These handlers build on top of the lower-level animation/rigging primitives
    to perform multi-step, transactional workflows such as finalizing an action
    into an NLA track or retargeting animation between armatures.
    """

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @classmethod
    def _iter_action_fcurves(cls, action: Any) -> List[Any]:
        """Yield all fcurves of an action, supporting both Blender 5.x layered
        actions and the legacy 4.x flat ``action.fcurves`` collection.

        Blender 5.2 introduced a layered action data model where fcurves live
        inside ``action.layers[].strips[].channelbags[].fcurves``. Older
        versions (and legacy actions in 5.x) keep the flat ``action.fcurves``
        collection. This helper transparently handles both layouts.
        """
        curves: List[Any] = []
        # Blender 5.x layered API
        if hasattr(action, "layers") and not hasattr(action, "fcurves"):
            for layer in action.layers:
                for strip in layer.strips:
                    for channelbag in strip.channelbags:
                        for fc in channelbag.fcurves:
                            curves.append(fc)
            return curves
        # Legacy Blender 4.x (and legacy actions in 5.x) API
        if hasattr(action, "fcurves"):
            for fc in action.fcurves:
                curves.append(fc)
        return curves

    @classmethod
    def _set_fcurve_interpolation(cls, action: Any, interpolation: str) -> int:
        """Set the interpolation mode on every keyframe of every fcurve in the
        given action. Returns the number of keyframes updated."""
        valid = {"BEZIER", "LINEAR", "CONSTANT"}
        if interpolation not in valid:
            raise BlenderExecutionError(
                f"Invalid interpolation '{interpolation}'. Must be one of {sorted(valid)}."
            )
        updated = 0
        for fc in cls._iter_action_fcurves(action):
            for kp in fc.keyframe_points:
                kp.interpolation = interpolation
                updated += 1
            if hasattr(fc, "update"):
                fc.update()
        return updated

    @classmethod
    def _ensure_animation_data(cls, obj: Any) -> Any:
        """Ensure the object has animation_data, creating it if necessary."""
        if not getattr(obj, "animation_data", None):
            obj.animation_data_create()
        return obj.animation_data

    @classmethod
    def _get_active_action(cls, obj: Any) -> Optional[Any]:
        """Return the active action on an object, or None."""
        anim_data = getattr(obj, "animation_data", None)
        if anim_data and anim_data.action:
            return anim_data.action
        return None

    @classmethod
    def _get_armature_bone_names(cls, arm_obj: Any) -> List[str]:
        """Return the list of bone names for an armature object."""
        bones = getattr(arm_obj, "data", None)
        if bones is None or not hasattr(bones, "bones"):
            return []
        return [b.name for b in bones.bones]

    @classmethod
    def _build_bone_mapping(
        cls,
        source_bones: List[str],
        target_bones: List[str],
        explicit: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        """Build a mapping of source bone name -> target bone name.

        If an explicit mapping is provided it is used directly (after
        validating that both bones exist). Otherwise bones are matched
        automatically: first by exact name, then case-insensitively, and
        finally via fuzzy matching using ``difflib.SequenceMatcher`` with a
        0.6 similarity threshold.
        """
        if explicit is not None:
            mapping: Dict[str, str] = {}
            for src, tgt in explicit.items():
                if src not in source_bones:
                    raise BlenderExecutionError(
                        f"Explicit bone mapping references unknown source bone '{src}'."
                    )
                if tgt not in target_bones:
                    raise BlenderExecutionError(
                        f"Explicit bone mapping references unknown target bone '{tgt}'."
                    )
                mapping[src] = tgt
            return mapping

        target_set = set(target_bones)
        target_lower = {b.lower(): b for b in target_bones}
        used_targets: set = set()
        mapping = {}

        # 1. Exact match
        remaining_sources: List[str] = []
        for sb in source_bones:
            if sb in target_set and sb not in used_targets:
                mapping[sb] = sb
                used_targets.add(sb)
            else:
                remaining_sources.append(sb)

        # 2. Case-insensitive match
        still_remaining: List[str] = []
        for sb in remaining_sources:
            match = target_lower.get(sb.lower())
            if match and match not in used_targets:
                mapping[sb] = match
                used_targets.add(match)
            else:
                still_remaining.append(sb)

        # 3. Fuzzy match with difflib (threshold 0.6)
        available_targets = [b for b in target_bones if b not in used_targets]
        for sb in still_remaining:
            best_match: Optional[str] = None
            best_score = 0.0
            for tb in available_targets:
                score = difflib.SequenceMatcher(None, sb.lower(), tb.lower()).ratio()
                if score > best_score:
                    best_score = score
                    best_match = tb
            if best_match and best_score >= 0.6:
                mapping[sb] = best_match
                used_targets.add(best_match)
                available_targets.remove(best_match)

        return mapping

    # ------------------------------------------------------------------
    # Workflow 1: bake_animation_to_nla
    # ------------------------------------------------------------------

    @classmethod
    def bake_animation_to_nla(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        """Finalize an action into an NLA track.

        Validates the action, optionally sets fcurve interpolation, cleans
        redundant keyframes, pushes the action down into a new (or existing)
        NLA track, configures the strip's blend settings, and optionally mutes
        all other tracks so the baked strip is the sole contributor.
        """
        bpy = cls.get_bpy()

        # --- Parameter extraction ---
        action_name: str = params["action_name"]
        track_name: str = params.get("track_name") or action_name
        object_name: Optional[str] = params.get("object_name")
        frame_start: int = int(params.get("frame_start", 1))
        frame_end: int = int(params.get("frame_end", 250))
        interpolation: str = params.get("interpolation", "BEZIER")
        clean_keyframes: bool = bool(params.get("clean_keyframes", True))
        blend_mode: str = params.get("blend_mode", "REPLACE")
        blend_in: int = int(params.get("blend_in", 0))
        blend_out: int = int(params.get("blend_out", 0))
        mute_other_tracks: bool = bool(params.get("mute_other_tracks", True))
        use_auto_blend: bool = bool(params.get("use_auto_blend", False))

        valid_blend_modes = {"REPLACE", "ADD", "SUBTRACT", "MULTIPLY"}
        if blend_mode not in valid_blend_modes:
            raise BlenderExecutionError(
                f"Invalid blend_mode '{blend_mode}'. Must be one of {sorted(valid_blend_modes)}."
            )

        with cls.transaction(f"bake_animation_to_nla('{action_name}')"):
            # 1. Resolve target object (active if not specified)
            if object_name:
                obj = cls.get_object(object_name)
            else:
                obj = bpy.context.view_layer.objects.active
                if obj is None:
                    raise BlenderExecutionError(
                        "No object_name provided and no active object in the view layer."
                    )

            # 2. Verify the action exists
            anim_data = cls._ensure_animation_data(obj)
            action = bpy.data.actions.get(action_name)
            if action is None:
                # Fall back to the object's active action if names match
                active = cls._get_active_action(obj)
                if active is not None and active.name == action_name:
                    action = active
                else:
                    raise BlenderExecutionError(
                        f"Action '{action_name}' not found in bpy.data.actions "
                        f"and is not the active action on '{obj.name}'."
                    )

            # Make the action the active action so editing ops apply to it
            anim_data.action = action

            # 3. Set interpolation on all fcurves
            interp_count = cls._set_fcurve_interpolation(action, interpolation)

            # 4. Clean redundant keyframes if requested
            cleaned = False
            if clean_keyframes:
                # action.clean() requires the action to be visible in the
                # action editor. We attempt the operator with a context
                # override and fall back to a manual pass if it is unavailable.
                try:
                    with cls.active_mode(obj, "OBJECT"):
                        ctx_override = {
                            "object": obj,
                            "active_object": obj,
                            "animation_data": anim_data,
                        }
                        if hasattr(bpy.ops, "action") and hasattr(bpy.ops.action, "clean"):
                            with bpy.context.temp_override(**ctx_override):
                                bpy.ops.action.clean()
                            cleaned = True
                except Exception:
                    cleaned = False

            # 5. Push the action into an NLA track
            nla_track = None
            strip = None

            # Try the operator-based pushdown first (requires NLA editor context)
            pushed_via_op = False
            try:
                ctx_override = {
                    "object": obj,
                    "active_object": obj,
                    "animation_data": anim_data,
                }
                if hasattr(bpy.ops, "nla") and hasattr(bpy.ops.nla, "action_pushdown"):
                    with bpy.context.temp_override(**ctx_override):
                        bpy.ops.nla.action_pushdown(
                            action_idname=action.name,
                            track_name=track_name,
                        )
                    pushed_via_op = True
            except Exception:
                pushed_via_op = False

            if pushed_via_op:
                # Locate the track/strip that was just created
                for tr in anim_data.nla_tracks:
                    if tr.name == track_name:
                        nla_track = tr
                        break
                if nla_track is not None and len(nla_track.strips) > 0:
                    strip = nla_track.strips[-1]
            else:
                # Manual creation: create a track and a strip referencing the action
                existing_track = anim_data.nla_tracks.get(track_name)
                if existing_track is not None:
                    nla_track = existing_track
                else:
                    nla_track = anim_data.nla_tracks.new()
                    nla_track.name = track_name
                strip = nla_track.strips.new(
                    name=action.name,
                    start=frame_start,
                    action=action,
                )

            if strip is None:
                raise BlenderExecutionError(
                    f"Failed to create an NLA strip for action '{action_name}'."
                )

            # 6. Configure strip blend settings
            if hasattr(strip, "blend_type"):
                strip.blend_type = blend_mode
            elif hasattr(strip, "blend_mode"):
                strip.blend_mode = blend_mode
            if hasattr(strip, "blend_in"):
                strip.blend_in = blend_in
            if hasattr(strip, "blend_out"):
                strip.blend_out = blend_out

            # 7. Auto blend in/out
            if use_auto_blend and hasattr(strip, "action_frame_end") and hasattr(strip, "action_frame_start"):
                span = float(strip.action_frame_end - strip.action_frame_start)
                auto = max(0, int(math.ceil(span * 0.05)))
                if hasattr(strip, "blend_in"):
                    strip.blend_in = auto
                if hasattr(strip, "blend_out"):
                    strip.blend_out = auto

            # 8. Mute other tracks
            muted_count = 0
            if mute_other_tracks:
                for tr in anim_data.nla_tracks:
                    if tr is nla_track:
                        continue
                    if not getattr(tr, "mute", False):
                        tr.mute = True
                        muted_count += 1
                # Ensure our track is unmuted
                nla_track.mute = False

            # 9. Set the NLA track as the active track
            if hasattr(anim_data, "nla_tracks"):
                # Blender exposes an "active_track" via the action editor; the
                # tracks collection itself is not indexable by name for
                # "active" assignment, but we can deselect others.
                for tr in anim_data.nla_tracks:
                    if hasattr(tr, "select"):
                        tr.select = (tr is nla_track)
            if hasattr(anim_data, "action"):
                # After pushdown the active action is typically cleared so the
                # NLA track drives the animation. Keep it cleared unless the
                # pushdown op already did so.
                if anim_data.action is action and pushed_via_op is False:
                    anim_data.action = None

            # Determine effective frame range
            strip_start = getattr(strip, "frame_start", frame_start)
            strip_end = getattr(strip, "frame_end", frame_end)
            if hasattr(strip, "action_frame_start") and hasattr(strip, "action_frame_end"):
                action_start = strip.action_frame_start
                action_end = strip.action_frame_end
            else:
                action_start, action_end = action.frame_range

            return {
                "status": "success",
                "object": obj.name,
                "action": action.name,
                "track": nla_track.name,
                "strip": strip.name,
                "blend_mode": blend_mode,
                "blend_in": getattr(strip, "blend_in", blend_in),
                "blend_out": getattr(strip, "blend_out", blend_out),
                "interpolation": interpolation,
                "interpolation_keyframes_updated": interp_count,
                "keyframes_cleaned": cleaned,
                "muted_other_tracks": muted_count,
                "strip_frame_start": strip_start,
                "strip_frame_end": strip_end,
                "action_frame_start": action_start,
                "action_frame_end": action_end,
            }

    # ------------------------------------------------------------------
    # Workflow 2: retarget_animation
    # ------------------------------------------------------------------

    @classmethod
    def retarget_animation(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        """Retarget animation from a source armature to a target armature.

        Builds a bone mapping (explicit or auto-detected), adds Copy Rotation
        (and optionally Copy Location) constraints on the target bones that
        reference the corresponding source bones, optionally bakes the
        constraint-driven pose into a new action on the target, and finally
        removes the temporary constraints.
        """
        bpy = cls.get_bpy()

        # --- Parameter extraction ---
        source_armature_name: str = params["source_armature"]
        target_armature_name: str = params["target_armature"]
        action_name: Optional[str] = params.get("action_name")
        bone_mapping: Optional[Dict[str, str]] = params.get("bone_mapping")
        retarget_mode: str = params.get("retarget_mode", "ROTATION_ONLY")
        bake_to_target: bool = bool(params.get("bake_to_target", True))
        bake_frame_start: int = int(params.get("bake_frame_start", 1))
        bake_frame_end: int = int(params.get("bake_frame_end", 250))
        remove_constraints_after_bake: bool = bool(
            params.get("remove_constraints_after_bake", True)
        )
        use_offset_bones: bool = bool(params.get("use_offset_bones", True))

        valid_modes = {"ROTATION_ONLY", "LOCATION_AND_ROTATION"}
        if retarget_mode not in valid_modes:
            raise BlenderExecutionError(
                f"Invalid retarget_mode '{retarget_mode}'. Must be one of {sorted(valid_modes)}."
            )

        with cls.transaction(
            f"retarget_animation('{source_armature_name}' -> '{target_armature_name}')"
        ):
            # 1. Verify both armatures exist
            source_obj = cls.get_object(source_armature_name)
            target_obj = cls.get_object(target_armature_name)
            if source_obj.type != "ARMATURE":
                raise BlenderExecutionError(
                    f"Source object '{source_armature_name}' is not an Armature (type={source_obj.type})."
                )
            if target_obj.type != "ARMATURE":
                raise BlenderExecutionError(
                    f"Target object '{target_armature_name}' is not an Armature (type={target_obj.type})."
                )

            # 2. Get the source action
            source_anim = getattr(source_obj, "animation_data", None)
            source_action = None
            if action_name:
                source_action = bpy.data.actions.get(action_name)
                if source_action is None:
                    raise BlenderExecutionError(
                        f"Action '{action_name}' not found in bpy.data.actions."
                    )
                # Assign it to the source so it drives the pose during baking
                if source_anim is None:
                    source_anim = cls._ensure_animation_data(source_obj)
                source_anim.action = source_action
            else:
                if source_anim and source_anim.action:
                    source_action = source_anim.action
                else:
                    raise BlenderExecutionError(
                        f"Source armature '{source_armature_name}' has no active action "
                        f"and no action_name was provided."
                    )

            # 3. Build bone mapping
            source_bones = cls._get_armature_bone_names(source_obj)
            target_bones = cls._get_armature_bone_names(target_obj)
            mapping = cls._build_bone_mapping(
                source_bones, target_bones, explicit=bone_mapping
            )
            if not mapping:
                raise BlenderExecutionError(
                    "Could not build any bone mapping between source and target armatures."
                )

            # 4. Add constraints for each bone pair
            constraints_created: List[Dict[str, Any]] = []
            offset_bones_created: List[str] = []

            with cls.active_mode(target_obj, "POSE"):
                # Ensure the source armature is visible/selectable for constraint targets
                for src_bone, tgt_bone in mapping.items():
                    pbone = target_obj.pose.bones.get(tgt_bone)
                    if pbone is None:
                        continue

                    constraint_target_bone = src_bone
                    helper_bone_name: Optional[str] = None

                    # 4e. Optionally create an offset/helper bone to hold the constraint
                    if use_offset_bones:
                        helper_bone_name = f"{tgt_bone}_RETARGET"
                        # Create the helper bone in edit mode
                        with cls.active_mode(target_obj, "EDIT"):
                            edit_bones = target_obj.data.edit_bones
                            if helper_bone_name not in edit_bones:
                                helper = edit_bones.new(helper_bone_name)
                                src_edit = source_obj.data.edit_bones.get(src_bone) \
                                    if source_obj.data.is_editmode else None
                                if src_edit is not None:
                                    helper.head = src_edit.head.copy()
                                    helper.tail = src_edit.tail.copy()
                                    helper.roll = src_edit.roll
                                else:
                                    # Fall back to the target bone's rest pose
                                    tgt_rest = target_obj.data.bones.get(tgt_bone)
                                    if tgt_rest is not None:
                                        helper.head = tgt_rest.head_local.copy()
                                        helper.tail = tgt_rest.tail_local.copy()
                                helper.use_deform = False
                                offset_bones_created.append(helper_bone_name)

                    # Switch back to pose mode to add constraints
                    with cls.active_mode(target_obj, "POSE"):
                        # Select only the target bone
                        for pb in target_obj.pose.bones:
                            pb.select = (pb.name == tgt_bone)

                        if use_offset_bones and helper_bone_name:
                            # Constrain the helper bone to the source bone
                            helper_pbone = target_obj.pose.bones.get(helper_bone_name)
                            if helper_pbone is not None:
                                if retarget_mode == "LOCATION_AND_ROTATION":
                                    loc_c = helper_pbone.constraints.new(
                                        type="COPY_LOCATION"
                                    )
                                    loc_c.target = source_obj
                                    loc_c.subtarget = src_bone
                                    constraints_created.append({
                                        "target_bone": helper_bone_name,
                                        "constraint": loc_c.name,
                                        "type": "COPY_LOCATION",
                                        "source_bone": src_bone,
                                    })
                                rot_c = helper_pbone.constraints.new(
                                    type="COPY_ROTATION"
                                )
                                rot_c.target = source_obj
                                rot_c.subtarget = src_bone
                                constraints_created.append({
                                    "target_bone": helper_bone_name,
                                    "constraint": rot_c.name,
                                    "type": "COPY_ROTATION",
                                    "source_bone": src_bone,
                                })
                                # Now constrain the real bone to the helper
                                real_rot = pbone.constraints.new(type="COPY_ROTATION")
                                real_rot.target = target_obj
                                real_rot.subtarget = helper_bone_name
                                constraints_created.append({
                                    "target_bone": tgt_bone,
                                    "constraint": real_rot.name,
                                    "type": "COPY_ROTATION",
                                    "source_bone": helper_bone_name,
                                })
                                if retarget_mode == "LOCATION_AND_ROTATION":
                                    real_loc = pbone.constraints.new(
                                        type="COPY_LOCATION"
                                    )
                                    real_loc.target = target_obj
                                    real_loc.subtarget = helper_bone_name
                                    constraints_created.append({
                                        "target_bone": tgt_bone,
                                        "constraint": real_loc.name,
                                        "type": "COPY_LOCATION",
                                        "source_bone": helper_bone_name,
                                    })
                        else:
                            # Direct constraint from target bone to source bone
                            if retarget_mode == "LOCATION_AND_ROTATION":
                                loc_c = pbone.constraints.new(type="COPY_LOCATION")
                                loc_c.target = source_obj
                                loc_c.subtarget = src_bone
                                constraints_created.append({
                                    "target_bone": tgt_bone,
                                    "constraint": loc_c.name,
                                    "type": "COPY_LOCATION",
                                    "source_bone": src_bone,
                                })
                            rot_c = pbone.constraints.new(type="COPY_ROTATION")
                            rot_c.target = source_obj
                            rot_c.subtarget = src_bone
                            constraints_created.append({
                                "target_bone": tgt_bone,
                                "constraint": rot_c.name,
                                "type": "COPY_ROTATION",
                                "source_bone": src_bone,
                            })

            # 5. Bake the constraint-driven animation onto the target
            baked_action_name: Optional[str] = None
            if bake_to_target:
                # Ensure target has animation data to receive the baked action
                target_anim = cls._ensure_animation_data(target_obj)
                # Clear any existing active action so the bake produces a fresh one
                target_anim.action = None

                with cls.active_mode(target_obj, "POSE"):
                    # Select all mapped target bones so they get baked
                    for pb in target_obj.pose.bones:
                        pb.select = pb.name in set(mapping.values())
                    if use_offset_bones:
                        for hb in offset_bones_created:
                            hpb = target_obj.pose.bones.get(hb)
                            if hpb is not None:
                                hpb.select = True

                    bake_ok = False
                    # Prefer bpy.ops.nla.bake (works on whole object) with override
                    try:
                        ctx_override = {
                            "object": target_obj,
                            "active_object": target_obj,
                            "selected_objects": [target_obj],
                        }
                        if hasattr(bpy.ops, "nla") and hasattr(bpy.ops.nla, "bake"):
                            with bpy.context.temp_override(**ctx_override):
                                bpy.ops.nla.bake(
                                    frame_start=bake_frame_start,
                                    frame_end=bake_frame_end,
                                    step=1,
                                    only_selected=True,
                                    visual_keying=True,
                                    clear_constraints=False,
                                    bake_types={"POSE"},
                                )
                            bake_ok = True
                    except Exception:
                        bake_ok = False

                    if not bake_ok and hasattr(bpy.ops, "pose") and hasattr(
                        bpy.ops.pose, "bake"
                    ):
                        try:
                            ctx_override = {
                                "object": target_obj,
                                "active_object": target_obj,
                                "selected_pose_bones": [
                                    target_obj.pose.bones.get(n)
                                    for n in set(mapping.values())
                                    if target_obj.pose.bones.get(n) is not None
                                ],
                            }
                            with bpy.context.temp_override(**ctx_override):
                                bpy.ops.pose.bake(
                                    frame_start=bake_frame_start,
                                    frame_end=bake_frame_end,
                                    step=1,
                                    only_selected=True,
                                    visual_keying=True,
                                )
                            bake_ok = True
                        except Exception:
                            bake_ok = False

                    if bake_ok and target_anim.action is not None:
                        baked_action_name = target_anim.action.name

            # 6. Remove temporary constraints (and optionally offset bones)
            removed_constraints = 0
            if remove_constraints_after_bake:
                with cls.active_mode(target_obj, "POSE"):
                    for tgt_bone in set(mapping.values()) | set(offset_bones_created):
                        pb = target_obj.pose.bones.get(tgt_bone)
                        if pb is None:
                            continue
                        # Remove constraints whose name we recorded
                        recorded_names = {
                            c["constraint"] for c in constraints_created
                            if c["target_bone"] == tgt_bone
                        }
                        to_remove = [
                            c.name for c in pb.constraints if c.name in recorded_names
                        ]
                        for cname in to_remove:
                            con = pb.constraints.get(cname)
                            if con is not None:
                                pb.constraints.remove(con)
                                removed_constraints += 1

                    # Remove offset/helper bones
                    if use_offset_bones and offset_bones_created:
                        with cls.active_mode(target_obj, "EDIT"):
                            edit_bones = target_obj.data.edit_bones
                            for hb in offset_bones_created:
                                eb = edit_bones.get(hb)
                                if eb is not None:
                                    edit_bones.remove(eb)

            return {
                "status": "success",
                "source_armature": source_obj.name,
                "target_armature": target_obj.name,
                "source_action": source_action.name,
                "baked_action": baked_action_name,
                "retarget_mode": retarget_mode,
                "bone_mapping": mapping,
                "bones_mapped": len(mapping),
                "constraints_created": len(constraints_created),
                "constraints_removed": removed_constraints,
                "offset_bones_created": len(offset_bones_created),
                "bake_frame_start": bake_frame_start,
                "bake_frame_end": bake_frame_end,
            }
