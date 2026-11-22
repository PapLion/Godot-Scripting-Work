"""Attaches the reusable First-Person Arms & Tactical Gloves Rig to the three existing
weapon .blend files (AK-47, SPAS-12, AWP), adds configurable hand-to-weapon attachment
reference markers, bakes synchronized Weapon + Arm + Finger animations, renders
first-person presentation shots, and exports <weapon>_fp.blend and <weapon>_fp.glb.
"""

import math
import os
import sys
import bpy
from mathutils import Vector, Euler, Matrix

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from weapon_build_utils import (
    add_marker_empty,
    save_blend,
)
from fps_arms_rig import (
    add_fp_arms_to_armature,
    solve_and_pose_arm_ik,
    FINGER_GRIP_PISTOL,
    FINGER_GRIP_TRIGGER_PULL,
    FINGER_GRIP_FOREND,
    FINGER_GRIP_MAG,
    FINGER_GRIP_PINCH,
    FINGER_GRIP_OPEN,
)

PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
WEAPONS_DIR = os.path.join(PROJECT_ROOT, "assets", "weapons")
RIG_RENDER_DIR = os.path.join(PROJECT_ROOT, "portfolio_media", "rig_renders")


def _clear_old_actions_and_nla(arm_obj: bpy.types.Object):
    if arm_obj.animation_data is not None:
        arm_obj.animation_data.action = None
        while len(arm_obj.animation_data.nla_tracks) > 0:
            arm_obj.animation_data.nla_tracks.remove(arm_obj.animation_data.nla_tracks[0])
    for act in list(bpy.data.actions):
        bpy.data.actions.remove(act)


def _reset_pose(arm_obj: bpy.types.Object):
    for pb in arm_obj.pose.bones:
        pb.location = Vector((0.0, 0.0, 0.0))
        pb.rotation_euler = Euler((0.0, 0.0, 0.0), 'XYZ')
        pb.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        pb.scale = Vector((1.0, 1.0, 1.0))
    bpy.context.view_layer.update()


def _bake_synchronized_action(
    arm_obj: bpy.types.Object,
    action_name: str,
    end_frame: int,
    weapon_keyframes: dict,
    hand_keyframes: list,
):
    """Creates one synchronized Action driving BOTH weapon bones AND L/R arms + fingers.
    weapon_keyframes: { bone_name: [(frame, loc, rot_deg, scale), ...] }
    hand_keyframes: [(frame, side, wrist_world_xyz, hand_rot_deg, pole_xyz, finger_dict), ...]
    """
    if arm_obj.animation_data is None:
        arm_obj.animation_data_create()

    action = bpy.data.actions.new(name=action_name)
    arm_obj.animation_data.action = action
    _reset_pose(arm_obj)

    # 1. Weapon mechanical bones
    for bone_name, frames in weapon_keyframes.items():
        pb = arm_obj.pose.bones.get(bone_name)
        if pb is None:
            continue
        pb.rotation_mode = 'XYZ'
        for entry in frames:
            f = entry[0]
            loc = entry[1] if len(entry) > 1 else None
            rot = entry[2] if len(entry) > 2 else None
            scl = entry[3] if len(entry) > 3 else None
            if loc is not None:
                pb.location = Vector(loc)
                pb.keyframe_insert(data_path='location', frame=f)
            if rot is not None:
                pb.rotation_euler = Euler(tuple(math.radians(a) for a in rot), 'XYZ')
                pb.keyframe_insert(data_path='rotation_euler', frame=f)
            if scl is not None:
                pb.scale = Vector(scl)
                pb.keyframe_insert(data_path='scale', frame=f)

    # 2. First-person arms, wrists, and articulated fingers
    for f, side, wrist_xyz, rot_deg, pole_xyz, f_dict in hand_keyframes:
        solve_and_pose_arm_ik(
            arm_obj,
            side,
            Vector(wrist_xyz),
            rot_deg,
            Vector(pole_xyz),
            f_dict,
            f,
        )

    # Push onto NLA track for glTF export
    track = arm_obj.animation_data.nla_tracks.new()
    track.name = action_name
    strip = track.strips.new(action_name, start=1, action=action)
    strip.frame_end = max(2, end_frame)
    arm_obj.animation_data.action = None
    _reset_pose(arm_obj)
    return action


def _export_fp_glb(filepath: str):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=filepath,
        export_format='GLB',
        export_animations=True,
        export_nla_strips=True,
        export_materials='EXPORT',
        export_yup=True,
        export_apply=False,
        export_skins=True,
        export_def_bones=True,
        export_all_influences=False,
    )


def _render_fp_preview(
    prefix: str,
    arm_obj: bpy.types.Object,
    idle_action_name: str,
    cam_fp_loc: tuple,
    cam_fp_target: tuple,
    side_cam_loc: tuple,
    side_cam_target: tuple,
    extra_action_name: str = None,
    extra_frame: int = 12,
):
    """Renders 1) 70-deg First-Person Camera Viewpoint, 2) 3/4 Hand-Grip Side View,
    and optionally 3) Mid-Reload / Bolt-Cycle Action View!
    """
    os.makedirs(RIG_RENDER_DIR, exist_ok=True)
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 720
    scene.render.image_settings.file_format = 'PNG'

    world = bpy.data.worlds.new(f"FPWorld_{prefix}")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.045, 0.055, 0.072, 1.0)
        bg.inputs[1].default_value = 0.72

    def _add_light(name, loc, rot_deg, energy, color, size=1.4):
        ld = bpy.data.lights.new(name=name, type='AREA')
        ld.energy = energy
        ld.color = color
        ld.size = size
        lo = bpy.data.objects.new(name, ld)
        lo.location = Vector(loc)
        lo.rotation_euler = Euler(tuple(math.radians(a) for a in rot_deg), 'XYZ')
        scene.collection.objects.link(lo)
        return lo

    lights = [
        _add_light("Key", (1.2, 0.4, 1.1), (48, 0, 128), 220.0, (1.0, 0.96, 0.92), 1.6),
        _add_light("Fill", (-1.1, -0.3, 0.9), (60, 0, -58), 140.0, (0.82, 0.90, 1.0), 1.8),
        _add_light("Rim", (0.1, 1.1, 1.0), (50, 0, 175), 180.0, (0.96, 0.98, 1.0), 1.4),
    ]

    cam_d = bpy.data.cameras.new("FPCam")
    cam_d.lens_unit = 'FOV'
    cam_d.angle = math.radians(70.0)
    cam_o = bpy.data.objects.new("FPCam", cam_d)
    scene.collection.objects.link(cam_o)
    scene.camera = cam_o

    def _aim(loc, target):
        cam_o.location = Vector(loc)
        cam_o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()

    # Evaluate idle action cleanly by muting all other NLA tracks
    tracks = arm_obj.animation_data.nla_tracks
    for tr in tracks:
        tr.mute = (tr.name != idle_action_name)
    scene.frame_set(1)
    bpy.context.view_layer.update()

    # 1. First-person 70-deg view
    _aim(cam_fp_loc, cam_fp_target)
    scene.render.filepath = os.path.join(RIG_RENDER_DIR, f"{prefix}_01_fp_view.png")
    bpy.ops.render.render(write_still=True)

    # 2. 3/4 Grip inspection view (shows both hands wrapping grip & forend)
    cam_d.lens_unit = 'MILLIMETERS'
    cam_d.lens = 45.0
    _aim(side_cam_loc, side_cam_target)
    scene.render.filepath = os.path.join(RIG_RENDER_DIR, f"{prefix}_02_hand_grip.png")
    bpy.ops.render.render(write_still=True)

    # 3. Mid-action view (reload mag / shell insert / bolt handle lift)
    if extra_action_name:
        for tr in tracks:
            tr.mute = (tr.name != extra_action_name)
        scene.frame_set(extra_frame)
        bpy.context.view_layer.update()
        _aim(side_cam_loc, side_cam_target)
        scene.render.filepath = os.path.join(RIG_RENDER_DIR, f"{prefix}_03_action_pose.png")
        bpy.ops.render.render(write_still=True)

    # Restore all NLA tracks unmuted for glTF export
    for tr in tracks:
        tr.mute = False
    scene.frame_set(1)
    bpy.context.view_layer.update()

    bpy.data.objects.remove(cam_o, do_unlink=True)
    for lo in lights:
        bpy.data.objects.remove(lo, do_unlink=True)


# ==============================================================================
# 1. AK-47 + FIRST-PERSON ARMS INTEGRATION
# ==============================================================================
def build_ak47_fp():
    src = os.path.join(WEAPONS_DIR, "ak47", "source", "ak47.blend")
    bpy.ops.wm.open_mainfile(filepath=src)
    arm = bpy.data.objects["AK47_Rig"]
    _clear_old_actions_and_nla(arm)

    # Add configurable hand-to-weapon attachment reference markers
    add_marker_empty("GripPrimary",  (0.036, -0.055, -0.058), arm)
    add_marker_empty("GripSupport",  (-0.042, 0.195, -0.025), arm)
    add_marker_empty("MagInteract",  (-0.038, 0.112, -0.115), arm)
    add_marker_empty("BoltInteract", (0.048,  0.088,  0.028), arm)
    add_marker_empty("ADSRef",       (0.0,   -0.25,   0.084), arm)

    # Attach reusable First-Person Arms Rig
    add_fp_arms_to_armature(arm, "weapon_root", add_ik_controls=True)

    # Base ergonomic AK-47 hand poses:
    # Right hand grips wooden pistol grip cleanly (palm facing -X, index forward on trigger)
    # Left hand cradles underside of lower wooden handguard (palm facing +Z/+X, fingers wrapping right side)
    R_GRIP = (0.032, -0.072, -0.056)
    R_ROT  = (-16.0, -88.0, 10.0)
    R_POLE = (0.36, -0.18, -0.36)

    L_GRIP = (-0.030, 0.195, -0.036)
    L_ROT  = (18.0, 162.0, -28.0)
    L_POLE = (-0.34, 0.04, -0.36)

    # 1. idle (60f)
    _bake_synchronized_action(arm, "idle", 60, {
        "weapon_body": [(1, (0, 0, 0), (0, 0, 0)), (30, (0, 0, 0.002), (0.3, 0, 0.15)), (60, (0, 0, 0), (0, 0, 0))],
    }, [
        (1,  'R', R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
        (30, 'R', (R_GRIP[0], R_GRIP[1], R_GRIP[2] + 0.002), R_ROT, R_POLE, FINGER_GRIP_PISTOL),
        (60, 'R', R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
        (1,  'L', L_GRIP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
        (30, 'L', (L_GRIP[0], L_GRIP[1], L_GRIP[2] + 0.002), L_ROT, L_POLE, FINGER_GRIP_FOREND),
        (60, 'L', L_GRIP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
    ])

    # 2. fire (7f: trigger pull, bolt carrier reciprocates, both hands kick with rifle)
    _bake_synchronized_action(arm, "fire", 7, {
        "weapon_body": [(1, (0, 0, 0), (0, 0, 0)), (2, (0, -0.016, 0.004), (2.0, 0, 0)), (6, (0, 0, 0), (0, 0, 0))],
        "charging_handle": [(1, (0, 0, 0), None), (2, (0, -0.082, 0), None), (5, (0, 0, 0), None)],
        "trigger": [(1, None, (0, 0, 0)), (2, None, (22, 0, 0)), (5, None, (0, 0, 0))],
    }, [
        (1, 'R', R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
        (2, 'R', (R_GRIP[0], R_GRIP[1] - 0.016, R_GRIP[2] + 0.004), (R_ROT[0] + 2.0, R_ROT[1], R_ROT[2]), R_POLE, FINGER_GRIP_TRIGGER_PULL),
        (6, 'R', R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
        (1, 'L', L_GRIP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
        (2, 'L', (L_GRIP[0], L_GRIP[1] - 0.016, L_GRIP[2] + 0.009), (L_ROT[0] + 2.0, L_ROT[1], L_ROT[2]), L_POLE, FINGER_GRIP_FOREND),
        (6, 'L', L_GRIP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
    ])

    # 3. reload (50f: left hand grabs mag, rocks it out, seats fresh mag, racks right charging handle!)
    R_TILT = (0.024, -0.048, -0.068)
    R_TILT_ROT = (-10.0, -64.0, 26.0)
    _bake_synchronized_action(arm, "reload", 50, {
        "weapon_body": [
            (1, (0, 0, 0), (0, 0, 0)),
            (8, (-0.018, 0.01, -0.018), (8, -12, 16)),
            (35, (-0.018, 0.01, -0.018), (9, -11, 15)),
            (43, (-0.008, 0.0, -0.008), (4, -6, 8)),
            (50, (0, 0, 0), (0, 0, 0)),
        ],
        "mag_release": [(1, None, (0, 0, 0)), (10, None, (0, 0, 0)), (12, None, (-22, 0, 0)), (16, None, (0, 0, 0))],
        "magazine": [
            (1, (0, 0, 0), (0, 0, 0)),
            (10, (0, 0, 0), (0, 0, 0)),
            (15, (0, 0.025, -0.048), (-22, 0, 0)),
            (21, (0, 0.035, -0.23), (-30, 0, 0)),
            (25, (0, 0.035, -0.23), (-30, 0, 0)),
            (31, (0, 0.020, -0.042), (-18, 0, 0)),
            (35, (0, 0, 0), (0, 0, 0)),
        ],
        "charging_handle": [(1, (0, 0, 0), None), (39, (0, 0, 0), None), (44, (0, -0.088, 0), None), (47, (0, 0, 0), None)],
    }, [
        # Right hand stays anchored on tilted pistol grip
        (1,  'R', R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
        (8,  'R', R_TILT, R_TILT_ROT, R_POLE, FINGER_GRIP_PISTOL),
        (35, 'R', R_TILT, R_TILT_ROT, R_POLE, FINGER_GRIP_PISTOL),
        (50, 'R', R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
        # Left hand: forend -> grab mag -> rock mag out -> bring fresh mag -> insert -> rack charging handle -> forend!
        (1,  'L', L_GRIP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
        (9,  'L', (-0.055, 0.095, -0.115), (6.0, 92.0, -18.0), L_POLE, FINGER_GRIP_MAG),
        (15, 'L', (-0.055, 0.115, -0.160), (-12.0, 92.0, -18.0), L_POLE, FINGER_GRIP_MAG),
        (21, 'L', (-0.095, 0.060, -0.295), (-22.0, 88.0, -10.0), L_POLE, FINGER_GRIP_MAG),
        (25, 'L', (-0.095, 0.060, -0.295), (-22.0, 88.0, -10.0), L_POLE, FINGER_GRIP_MAG),
        (31, 'L', (-0.052, 0.110, -0.152), (-10.0, 92.0, -18.0), L_POLE, FINGER_GRIP_MAG),
        (35, 'L', (-0.055, 0.095, -0.115), (6.0, 92.0, -18.0), L_POLE, FINGER_GRIP_MAG),
        (39, 'L', (0.015, 0.075, -0.055), (22.0, 145.0, -45.0), L_POLE, FINGER_GRIP_PINCH),  # Reach under to charging handle
        (44, 'L', (0.015, -0.012, -0.055), (22.0, 145.0, -45.0), L_POLE, FINGER_GRIP_PINCH), # Pull charging handle back
        (47, 'L', (-0.030, 0.090, -0.065), (16.0, 130.0, -28.0), L_POLE, FINGER_GRIP_OPEN),
        (50, 'L', L_GRIP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
    ])

    # 4. equip (11f) & 5. unequip (8f)
    _bake_synchronized_action(arm, "equip", 11, {
        "weapon_body": [(1, (0, -0.06, -0.18), (-32, 8, -10)), (8, (0, 0.005, 0.006), (2, 0, 0)), (11, (0, 0, 0), (0, 0, 0))],
    }, [
        (1,  'R', (R_GRIP[0], R_GRIP[1] - 0.06, R_GRIP[2] - 0.18), (R_ROT[0] - 28, R_ROT[1], R_ROT[2]), R_POLE, FINGER_GRIP_PISTOL),
        (11, 'R', R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
        (1,  'L', (L_GRIP[0], L_GRIP[1] - 0.06, L_GRIP[2] - 0.22), (L_ROT[0] - 26, L_ROT[1], L_ROT[2]), L_POLE, FINGER_GRIP_FOREND),
        (11, 'L', L_GRIP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
    ])

    _bake_synchronized_action(arm, "unequip", 8, {
        "weapon_body": [(1, (0, 0, 0), (0, 0, 0)), (8, (0, -0.06, -0.18), (-32, 8, -10))],
    }, [
        (1, 'R', R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
        (8, 'R', (R_GRIP[0], R_GRIP[1] - 0.06, R_GRIP[2] - 0.18), (R_ROT[0] - 28, R_ROT[1], R_ROT[2]), R_POLE, FINGER_GRIP_PISTOL),
        (1, 'L', L_GRIP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
        (8, 'L', (L_GRIP[0], L_GRIP[1] - 0.06, L_GRIP[2] - 0.22), (L_ROT[0] - 26, L_ROT[1], L_ROT[2]), L_POLE, FINGER_GRIP_FOREND),
    ])

    _render_fp_preview(
        "ak47_hands", arm, "idle",
        cam_fp_loc=(-0.18, -0.32, 0.17), cam_fp_target=(0.0, 0.48, 0.04),
        side_cam_loc=(-0.62, 0.04, 0.16), side_cam_target=(0.0, 0.08, -0.04),
        extra_action_name="reload", extra_frame=16,
    )
    save_blend(os.path.join(WEAPONS_DIR, "ak47", "source", "ak47_fp.blend"))
    _export_fp_glb(os.path.join(WEAPONS_DIR, "ak47", "ak47_fp.glb"))
    print("[AK-47 FP] Built, rigged with hands, animated, rendered, and exported.")


# ==============================================================================
# 2. SPAS-12 + FIRST-PERSON ARMS INTEGRATION
# ==============================================================================
def build_spas12_fp():
    src = os.path.join(WEAPONS_DIR, "spas12", "source", "spas12.blend")
    bpy.ops.wm.open_mainfile(filepath=src)
    arm = bpy.data.objects["SPAS12_Rig"]
    _clear_old_actions_and_nla(arm)

    add_marker_empty("GripPrimary",  (0.038, -0.082, -0.058), arm)
    add_marker_empty("GripSupport",  (-0.046, 0.300, -0.036), arm)
    add_marker_empty("ShellPort",    (-0.015, 0.055, -0.045), arm)
    add_marker_empty("BoltInteract", (0.040,  0.075,  0.024), arm)
    add_marker_empty("ADSRef",       (0.0,   -0.26,   0.072), arm)

    add_fp_arms_to_armature(arm, "weapon_root", add_ik_controls=True)

    R_GRIP = (0.034, -0.095, -0.056)
    R_ROT  = (-18.0, -88.0, 10.0)
    R_POLE = (0.36, -0.20, -0.36)

    L_GRIP = (-0.034, 0.305, -0.034)
    L_ROT  = (16.0, 165.0, -24.0)
    L_POLE = (-0.36, 0.08, -0.36)

    # 1. idle (60f)
    _bake_synchronized_action(arm, "idle", 60, {
        "weapon_body": [(1, (0, 0, 0), (0, 0, 0)), (30, (0, 0, 0.002), (0.3, 0, 0.15)), (60, (0, 0, 0), (0, 0, 0))],
        "shell": [(1, (0, 0, 0), None, (0.001, 0.001, 0.001))],
    }, [
        (1,  'R', R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
        (30, 'R', (R_GRIP[0], R_GRIP[1], R_GRIP[2] + 0.002), R_ROT, R_POLE, FINGER_GRIP_PISTOL),
        (60, 'R', R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
        (1,  'L', L_GRIP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
        (30, 'L', (L_GRIP[0], L_GRIP[1], L_GRIP[2] + 0.002), L_ROT, L_POLE, FINGER_GRIP_FOREND),
        (60, 'L', L_GRIP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
    ])

    # 2. fire (14f: SEMI-AUTO SPAS-12 firing response — bolt reciprocates cleanly, left hand stabilizes forend without contradictory pump!)
    _bake_synchronized_action(arm, "fire", 14, {
        "weapon_body": [(1, (0, 0, 0), (0, 0, 0)), (3, (0, -0.040, 0.012), (6.0, 0, 0)), (8, (0, -0.008, 0.002), (1.2, 0, 0)), (14, (0, 0, 0), (0, 0, 0))],
        "trigger": [(1, None, (0, 0, 0)), (2, None, (24, 0, 0)), (6, None, (0, 0, 0))],
        "bolt": [(1, (0, 0, 0), None), (3, (0, -0.072, 0), None), (7, (0, 0, 0), None)],
        "shell": [(1, (0, 0, 0), None, (0.001, 0.001, 0.001))],
    }, [
        (1,  'R', R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
        (3,  'R', (R_GRIP[0], R_GRIP[1] - 0.038, R_GRIP[2] + 0.010), (R_ROT[0] + 6.0, R_ROT[1], R_ROT[2]), R_POLE, FINGER_GRIP_TRIGGER_PULL),
        (14, 'R', R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
        (1,  'L', L_GRIP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
        (3,  'L', (L_GRIP[0], L_GRIP[1] - 0.038, L_GRIP[2] + 0.022), (L_ROT[0] + 6.0, L_ROT[1], L_ROT[2]), L_POLE, FINGER_GRIP_FOREND),
        (14, 'L', L_GRIP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
    ])

    # Tilted right-hand hold during shell-by-shell loading
    R_SHELL = (0.026, -0.072, -0.074)
    R_SHELL_ROT = (-6.0, -56.0, 34.0)

    # 3. shell_start (9f: tilt shotgun, left hand releases ribbed forend to reach for shell)
    _bake_synchronized_action(arm, "shell_start", 9, {
        "weapon_body": [(1, (0, 0, 0), (0, 0, 0)), (9, (-0.015, 0.01, -0.022), (14, -10, 32))],
        "shell": [(1, (0, 0, 0), None, (0.001, 0.001, 0.001))],
    }, [
        (1, 'R', R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
        (9, 'R', R_SHELL, R_SHELL_ROT, R_POLE, FINGER_GRIP_PISTOL),
        (1, 'L', L_GRIP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
        (9, 'L', (-0.065, 0.015, -0.185), (18.0, 128.0, -14.0), L_POLE, FINGER_GRIP_PINCH),
    ])

    # 4. shell_insert (12f: repeatable per-shell cycle — left hand pushes red 12ga shell into bottom loading gate!)
    _bake_synchronized_action(arm, "shell_insert", 12, {
        "weapon_body": [
            (1, (-0.015, 0.01, -0.022), (14, -10, 32)),
            (7, (-0.015, 0.01, -0.016), (16, -10, 32)),
            (12, (-0.015, 0.01, -0.022), (14, -10, 32)),
        ],
        "loading_gate": [(1, None, (0, 0, 0)), (5, None, (28, 0, 0)), (9, None, (32, 0, 0)), (12, None, (0, 0, 0))],
        "shell": [
            (1, (0, -0.035, -0.135), (18, 0, 0), (1, 1, 1)),
            (5, (0, -0.005, -0.032), (10, 0, 0), (1, 1, 1)),
            (9, (0, 0.035, 0.000), (0, 0, 0), (1, 1, 1)),
            (11, (0, 0.055, 0.005), (0, 0, 0), (0.001, 0.001, 0.001)),
        ],
    }, [
        (1,  'R', R_SHELL, R_SHELL_ROT, R_POLE, FINGER_GRIP_PISTOL),
        (12, 'R', R_SHELL, R_SHELL_ROT, R_POLE, FINGER_GRIP_PISTOL),
        (1,  'L', (-0.065, 0.015, -0.185), (18.0, 128.0, -14.0), L_POLE, FINGER_GRIP_PINCH),
        (6,  'L', (-0.048, 0.042, -0.095), (26.0, 140.0, -24.0), L_POLE, FINGER_GRIP_PINCH),
        (9,  'L', (-0.042, 0.058, -0.072), (30.0, 145.0, -26.0), L_POLE, FINGER_GRIP_PINCH),
        (12, 'L', (-0.065, 0.015, -0.185), (18.0, 128.0, -14.0), L_POLE, FINGER_GRIP_PINCH),
    ])

    # 5. shell_end (10f: left hand returns smoothly to ribbed forend, racks forend once to ready chamber)
    _bake_synchronized_action(arm, "shell_end", 10, {
        "weapon_body": [(1, (-0.015, 0.01, -0.022), (14, -10, 32)), (10, (0, 0, 0), (0, 0, 0))],
        "pump": [(1, (0, 0, 0), None), (4, (0, 0, 0), None), (7, (0, -0.075, 0), None), (10, (0, 0, 0), None)],
        "bolt": [(1, (0, 0, 0), None), (4, (0, 0, 0), None), (7, (0, -0.070, 0), None), (10, (0, 0, 0), None)],
        "shell": [(1, (0, 0, 0), None, (0.001, 0.001, 0.001))],
    }, [
        (1,  'R', R_SHELL, R_SHELL_ROT, R_POLE, FINGER_GRIP_PISTOL),
        (10, 'R', R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
        (1,  'L', (-0.065, 0.015, -0.185), (18.0, 128.0, -14.0), L_POLE, FINGER_GRIP_OPEN),
        (4,  'L', L_GRIP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
        (7,  'L', (L_GRIP[0], L_GRIP[1] - 0.075, L_GRIP[2]), L_ROT, L_POLE, FINGER_GRIP_FOREND),
        (10, 'L', L_GRIP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
    ])

    # 6. reload_interrupt (6f: fast snap back onto ribbed forend)
    _bake_synchronized_action(arm, "reload_interrupt", 6, {
        "weapon_body": [(1, (-0.015, 0.01, -0.022), (14, -10, 32)), (6, (0, 0, 0), (0, 0, 0))],
        "loading_gate": [(1, None, (0, 0, 0))],
        "shell": [(1, (0, 0, 0), None, (0.001, 0.001, 0.001))],
    }, [
        (1, 'R', R_SHELL, R_SHELL_ROT, R_POLE, FINGER_GRIP_PISTOL),
        (6, 'R', R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
        (1, 'L', (-0.055, 0.060, -0.125), (18.0, 130.0, -18.0), L_POLE, FINGER_GRIP_OPEN),
        (6, 'L', L_GRIP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
    ])

    # 7. equip (12f) & 8. unequip (8f)
    _bake_synchronized_action(arm, "equip", 12, {
        "weapon_body": [(1, (0, -0.06, -0.18), (-34, 10, -10)), (9, (0, 0.005, 0.006), (2, 0, 0)), (12, (0, 0, 0), (0, 0, 0))],
        "shell": [(1, (0, 0, 0), None, (0.001, 0.001, 0.001))],
    }, [
        (1,  'R', (R_GRIP[0], R_GRIP[1] - 0.06, R_GRIP[2] - 0.18), (R_ROT[0] - 28, R_ROT[1], R_ROT[2]), R_POLE, FINGER_GRIP_PISTOL),
        (12, 'R', R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
        (1,  'L', (L_GRIP[0], L_GRIP[1] - 0.06, L_GRIP[2] - 0.22), (L_ROT[0] - 26, L_ROT[1], L_ROT[2]), L_POLE, FINGER_GRIP_FOREND),
        (12, 'L', L_GRIP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
    ])

    _bake_synchronized_action(arm, "unequip", 8, {
        "weapon_body": [(1, (0, 0, 0), (0, 0, 0)), (8, (0, -0.06, -0.18), (-34, 10, -10))],
        "shell": [(1, (0, 0, 0), None, (0.001, 0.001, 0.001))],
    }, [
        (1, 'R', R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
        (8, 'R', (R_GRIP[0], R_GRIP[1] - 0.06, R_GRIP[2] - 0.18), (R_ROT[0] - 28, R_ROT[1], R_ROT[2]), R_POLE, FINGER_GRIP_PISTOL),
        (1, 'L', L_GRIP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
        (8, 'L', (L_GRIP[0], L_GRIP[1] - 0.06, L_GRIP[2] - 0.22), (L_ROT[0] - 26, L_ROT[1], L_ROT[2]), L_POLE, FINGER_GRIP_FOREND),
    ])

    _render_fp_preview(
        "spas12_hands", arm, "idle",
        cam_fp_loc=(-0.18, -0.34, 0.17), cam_fp_target=(0.0, 0.50, 0.03),
        side_cam_loc=(-0.64, 0.08, 0.16), side_cam_target=(0.0, 0.12, -0.03),
        extra_action_name="shell_insert", extra_frame=7,
    )
    save_blend(os.path.join(WEAPONS_DIR, "spas12", "source", "spas12_fp.blend"))
    _export_fp_glb(os.path.join(WEAPONS_DIR, "spas12", "spas12_fp.glb"))
    print("[SPAS-12 FP] Built, rigged with hands, animated, rendered, and exported.")


# ==============================================================================
# 3. AWP + FIRST-PERSON ARMS INTEGRATION (WITH AUTHENTIC BOLT-ACTION HAND CYCLE)
# ==============================================================================
def build_awp_fp():
    src = os.path.join(WEAPONS_DIR, "awp", "source", "awp.blend")
    bpy.ops.wm.open_mainfile(filepath=src)
    arm = bpy.data.objects["AWP_Rig"]
    _clear_old_actions_and_nla(arm)

    add_marker_empty("GripPrimary",  (0.036, -0.068, -0.056), arm)
    add_marker_empty("GripSupport",  (-0.044, 0.235, -0.038), arm)
    add_marker_empty("MagInteract",  (-0.036, 0.105, -0.080), arm)
    add_marker_empty("BoltInteract", (0.056, -0.020,  0.022), arm)
    add_marker_empty("ADSRef",       (0.0,   -0.26,   0.105), arm)

    add_fp_arms_to_armature(arm, "weapon_root", add_ik_controls=True)

    R_GRIP = (0.032, -0.080, -0.054)
    R_ROT  = (-16.0, -88.0, 10.0)
    R_POLE = (0.36, -0.18, -0.36)

    L_GRIP = (-0.032, 0.245, -0.044)
    L_ROT  = (18.0, 165.0, -26.0)
    L_POLE = (-0.36, 0.06, -0.36)

    # 1. idle (60f)
    _bake_synchronized_action(arm, "idle", 60, {
        "weapon_body": [(1, (0, 0, 0), (0, 0, 0)), (30, (0, 0, 0.0015), (0.2, 0, 0.1)), (60, (0, 0, 0), (0, 0, 0))],
    }, [
        (1,  'R', R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
        (30, 'R', (R_GRIP[0], R_GRIP[1], R_GRIP[2] + 0.0015), R_ROT, R_POLE, FINGER_GRIP_PISTOL),
        (60, 'R', R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
        (1,  'L', L_GRIP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
        (30, 'L', (L_GRIP[0], L_GRIP[1], L_GRIP[2] + 0.0015), L_ROT, L_POLE, FINGER_GRIP_FOREND),
        (60, 'L', L_GRIP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
    ])

    # 2. fire (10f: sharp sniper recoil impulse — bolt cycling follows in dedicated bolt_action!)
    _bake_synchronized_action(arm, "fire", 10, {
        "weapon_body": [(1, (0, 0, 0), (0, 0, 0)), (3, (0, -0.042, 0.011), (5.5, 0, 0)), (9, (0, 0, 0), (0, 0, 0))],
        "trigger": [(1, None, (0, 0, 0)), (2, None, (22, 0, 0)), (6, None, (0, 0, 0))],
    }, [
        (1,  'R', R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
        (3,  'R', (R_GRIP[0], R_GRIP[1] - 0.040, R_GRIP[2] + 0.010), (R_ROT[0] + 5.5, R_ROT[1], R_ROT[2]), R_POLE, FINGER_GRIP_TRIGGER_PULL),
        (10, 'R', R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
        (1,  'L', L_GRIP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
        (3,  'L', (L_GRIP[0], L_GRIP[1] - 0.040, L_GRIP[2] + 0.022), (L_ROT[0] + 5.5, L_ROT[1], L_ROT[2]), L_POLE, FINGER_GRIP_FOREND),
        (10, 'L', L_GRIP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
    ])

    # 3. bolt_action (24f = 0.80s: right hand leaves grip -> grabs bolt knob -> lifts 68deg -> pulls back -> pushes forward -> locks -> returns to grip!)
    _bake_synchronized_action(arm, "bolt_action", 24, {
        "weapon_body": [
            (1, (0, 0, 0), (0, 0, 0)),
            (6, (-0.008, 0.0, -0.006), (2.0, -4.5, 7.0)),
            (18, (-0.008, 0.0, -0.006), (2.0, -4.5, 7.0)),
            (24, (0, 0, 0), (0, 0, 0)),
        ],
        "bolt_handle": [
            (1, None, (0, 0, 0)),
            (5, None, (0, 0, 0)),
            (9, None, (0, -68, 0)),
            (17, None, (0, -68, 0)),
            (20, None, (0, 0, 0)),
        ],
        "bolt": [
            (1, (0, 0, 0), None),
            (9, (0, 0, 0), None),
            (13, (0, -0.092, 0), None),
            (17, (0, 0, 0), None),
        ],
    }, [
        # Left hand keeps rock-steady support on olive-drab forend
        (1,  'L', L_GRIP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
        (24, 'L', L_GRIP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
        # Right hand operates bolt handle through all 4 stages!
        (1,  'R', R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
        (5,  'R', (0.072, -0.042, 0.002), (-10.0, -52.0, 20.0), R_POLE, FINGER_GRIP_PINCH),  # Grab bolt knob
        (9,  'R', (0.068, -0.042, 0.044), (10.0, -34.0, 26.0), R_POLE, FINGER_GRIP_PINCH),   # Lift knob up 68 deg
        (13, 'R', (0.068, -0.132, 0.044), (10.0, -34.0, 26.0), R_POLE, FINGER_GRIP_PINCH),   # Pull bolt straight back
        (17, 'R', (0.068, -0.042, 0.044), (10.0, -34.0, 26.0), R_POLE, FINGER_GRIP_PINCH),   # Push bolt forward
        (20, 'R', (0.072, -0.042, 0.002), (-10.0, -52.0, 20.0), R_POLE, FINGER_GRIP_PINCH),  # Lock handle down
        (24, 'R', R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
    ])

    # 4. reload (60f: left hand swaps detachable box magazine -> returns to forend -> right hand cycles bolt!)
    _bake_synchronized_action(arm, "reload", 60, {
        "weapon_body": [
            (1, (0, 0, 0), (0, 0, 0)),
            (8, (-0.014, 0.01, -0.018), (6, -9, 13)),
            (38, (-0.014, 0.01, -0.018), (6, -9, 13)),
            (54, (-0.006, 0.0, -0.006), (2, -4, 6)),
            (60, (0, 0, 0), (0, 0, 0)),
        ],
        "magazine": [
            (1, (0, 0, 0), None),
            (10, (0, 0, 0), None),
            (18, (0, 0.0, -0.22), None),
            (26, (0, 0.0, -0.22), None),
            (35, (0, 0, 0), None),
        ],
        "bolt_handle": [(1, None, (0, 0, 0)), (41, None, (0, 0, 0)), (45, None, (0, -68, 0)), (53, None, (0, -68, 0)), (56, None, (0, 0, 0))],
        "bolt": [(1, (0, 0, 0), None), (45, (0, 0, 0), None), (49, (0, -0.092, 0), None), (53, (0, 0, 0), None)],
    }, [
        # Left hand swaps box magazine cleanly, then returns to support forend
        (1,  'L', L_GRIP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
        (10, 'L', (-0.052, 0.095, -0.092), (4.0, 96.0, -18.0), L_POLE, FINGER_GRIP_MAG),
        (18, 'L', (-0.078, 0.075, -0.285), (-12.0, 92.0, -14.0), L_POLE, FINGER_GRIP_MAG),
        (26, 'L', (-0.078, 0.075, -0.285), (-12.0, 92.0, -14.0), L_POLE, FINGER_GRIP_MAG),
        (35, 'L', (-0.052, 0.095, -0.092), (4.0, 96.0, -18.0), L_POLE, FINGER_GRIP_MAG),
        (41, 'L', L_GRIP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
        (60, 'L', L_GRIP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
        # Right hand holds tilted grip during mag swap, then cycles bolt!
        (1,  'R', R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
        (8,  'R', (0.026, -0.058, -0.068), (-10.0, -64.0, 24.0), R_POLE, FINGER_GRIP_PISTOL),
        (38, 'R', (0.026, -0.058, -0.068), (-10.0, -64.0, 24.0), R_POLE, FINGER_GRIP_PISTOL),
        (41, 'R', (0.072, -0.042, 0.002), (-10.0, -52.0, 20.0), R_POLE, FINGER_GRIP_PINCH),
        (45, 'R', (0.068, -0.042, 0.044), (10.0, -34.0, 26.0), R_POLE, FINGER_GRIP_PINCH),
        (49, 'R', (0.068, -0.132, 0.044), (10.0, -34.0, 26.0), R_POLE, FINGER_GRIP_PINCH),
        (53, 'R', (0.068, -0.042, 0.044), (10.0, -34.0, 26.0), R_POLE, FINGER_GRIP_PINCH),
        (56, 'R', (0.072, -0.042, 0.002), (-10.0, -52.0, 20.0), R_POLE, FINGER_GRIP_PINCH),
        (60, 'R', R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
    ])

    # 5. equip (13f) & 6. unequip (9f)
    _bake_synchronized_action(arm, "equip", 13, {
        "weapon_body": [(1, (0, -0.07, -0.20), (-34, 10, -10)), (9, (0, 0.005, 0.006), (2, 0, 0)), (13, (0, 0, 0), (0, 0, 0))],
    }, [
        (1,  'R', (R_GRIP[0], R_GRIP[1] - 0.07, R_GRIP[2] - 0.20), (R_ROT[0] - 28, R_ROT[1], R_ROT[2]), R_POLE, FINGER_GRIP_PISTOL),
        (13, 'R', R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
        (1,  'L', (L_GRIP[0], L_GRIP[1] - 0.07, L_GRIP[2] - 0.24), (L_ROT[0] - 26, L_ROT[1], L_ROT[2]), L_POLE, FINGER_GRIP_FOREND),
        (13, 'L', L_GRIP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
    ])

    _bake_synchronized_action(arm, "unequip", 9, {
        "weapon_body": [(1, (0, 0, 0), (0, 0, 0)), (9, (0, -0.07, -0.20), (-34, 10, -10))],
    }, [
        (1, 'R', R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
        (9, 'R', (R_GRIP[0], R_GRIP[1] - 0.07, R_GRIP[2] - 0.20), (R_ROT[0] - 28, R_ROT[1], R_ROT[2]), R_POLE, FINGER_GRIP_PISTOL),
        (1, 'L', L_GRIP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
        (9, 'L', (L_GRIP[0], L_GRIP[1] - 0.07, L_GRIP[2] - 0.24), (L_ROT[0] - 26, L_ROT[1], L_ROT[2]), L_POLE, FINGER_GRIP_FOREND),
    ])

    _render_fp_preview(
        "awp_hands", arm, "idle",
        cam_fp_loc=(-0.19, -0.34, 0.18), cam_fp_target=(0.0, 0.55, 0.05),
        side_cam_loc=(0.68, 0.02, 0.18), side_cam_target=(0.0, 0.08, -0.02),
        extra_action_name="bolt_action", extra_frame=13,
    )
    save_blend(os.path.join(WEAPONS_DIR, "awp", "source", "awp_fp.blend"))
    _export_fp_glb(os.path.join(WEAPONS_DIR, "awp", "awp_fp.glb"))
    print("[AWP FP] Built, rigged with hands, animated, rendered, and exported.")


if __name__ == "__main__":
    build_ak47_fp()
    build_spas12_fp()
    build_awp_fp()
