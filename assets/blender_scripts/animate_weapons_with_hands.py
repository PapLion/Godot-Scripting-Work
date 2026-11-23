"""Overhauled First-Person Arms & Synchronized Weapon Animation Pipeline (Blender 5.3).
Attaches the reusable anatomical FP Arms & Tactical Gloves Rig to AK-47, SPAS-12, and AWP,
tracks hands mathematically onto animated weapon bones (zero grip drift or floating hands),
frames reloads / shell-loading / bolt-cycling cleanly inside the 70-deg first-person viewport,
applies smooth AUTO_CLAMPED Bezier interpolation to all F-curves, preserves bone-skinned
modular attachments (Att_Optic_Holo, Att_Muzzle_Comp, Att_Mag_Ext, Att_Underbarrel_Laser),
renders first-person & action previews, and exports <weapon>_fp.blend and <weapon>_fp.glb.
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
    add_bone_marker_empty,
    set_action_bezier_smooth,
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


def _bone_delta_matrix(arm_obj: bpy.types.Object, bone_name: str) -> Matrix:
    """Returns the rigid-body world delta matrix of `bone_name` relative to its rest pose.
    Any rest-pose point `p` rigidly attached to `bone_name` moves to `M_delta @ p`.
    """
    pb = arm_obj.pose.bones.get(bone_name)
    rb = arm_obj.data.bones.get(bone_name)
    if pb is None or rb is None:
        return Matrix.Identity(4)
    return pb.matrix @ rb.matrix_local.inverted()


def _lerp_finger_dicts(d0: dict, d1: dict, t: float) -> dict:
    out = {}
    for k in ("thumb", "index", "middle", "ring", "pinky"):
        a = d0.get(k, (35.0, 45.0, 30.0))
        b = d1.get(k, a)
        out[k] = tuple(a[i] + (b[i] - a[i]) * t for i in range(3))
    return out


def _bake_synchronized_action(
    arm_obj: bpy.types.Object,
    action_name: str,
    end_frame: int,
    weapon_keyframes: dict,
    hand_specs: dict,
    sample_step: int = 2,
):
    """Creates one smooth Bezier-interpolated Action driving BOTH weapon mechanical bones
    AND mathematically bone-locked L/R arms + articulated fingers.

    weapon_keyframes: { bone_name: [(frame, loc, rot_deg, scale), ...] }
    hand_specs: {
        'R': [ (frame, mode, bone_name, pos_xyz, rot_deg, pole_xyz, finger_dict), ... ],
        'L': [ ... ],
    }
    mode:
      - 'lock':      position AND rotation follow bone_name rigid delta!
      - 'lock_pos':  position follows bone_name rigid delta, rotation uses explicit rot_deg (great for bolt knob!)
      - 'world':     position & rotation in world space (e.g. reaching down to ammo pouch).
    Between two consecutive 'lock'/'lock_pos' entries on the same bone, we densely sample every
    `sample_step` frames so hands track curved Bezier weapon arcs with ZERO drift!
    """
    scene = bpy.context.scene
    if arm_obj.animation_data is None:
        arm_obj.animation_data_create()

    action = bpy.data.actions.new(name=action_name)
    arm_obj.animation_data.action = action
    _reset_pose(arm_obj)

    # 1. Keyframe weapon mechanical bones & smooth their F-curves FIRST
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

    # Smooth weapon F-curves before evaluating hand tracking along them
    set_action_bezier_smooth(action)

    # 2. Evaluate & bake bone-locked L/R arms and articulated fingers
    for side in ('R', 'L'):
        entries = sorted(hand_specs.get(side, []), key=lambda e: e[0])
        if not entries:
            continue
        prev_quats = {}

        # Build dense sample list where consecutive keys share a locked bone
        eval_points = []
        for idx, cur in enumerate(entries):
            eval_points.append(cur)
            if idx + 1 < len(entries):
                nxt = entries[idx + 1]
                f0, m0, b0, p0, r0, pole0, fg0 = cur
                f1, m1, b1, p1, r1, pole1, fg1 = nxt
                if m0 in ('lock', 'lock_pos') and m1 == m0 and b0 == b1 and (f1 - f0) > sample_step:
                    for fm in range(f0 + sample_step, f1, sample_step):
                        t = (fm - f0) / float(f1 - f0)
                        pm = tuple(p0[k] + (p1[k] - p0[k]) * t for k in range(3))
                        rm = tuple(r0[k] + (r1[k] - r0[k]) * t for k in range(3))
                        polem = tuple(pole0[k] + (pole1[k] - pole0[k]) * t for k in range(3))
                        fgm = _lerp_finger_dicts(fg0, fg1, t)
                        eval_points.append((fm, m0, b0, pm, rm, polem, fgm))

        eval_points.sort(key=lambda e: e[0])

        for f, mode, bname, pos_xyz, rot_deg, pole_xyz, f_dict in eval_points:
            scene.frame_set(f)
            bpy.context.view_layer.update()

            local_rot_mat = Euler(tuple(math.radians(a) for a in rot_deg), 'XYZ').to_matrix().to_4x4()
            if mode == 'lock' and bname:
                m_delta = _bone_delta_matrix(arm_obj, bname)
                world_wrist = m_delta @ Vector(pos_xyz)
                world_rot_mat = m_delta.to_3x3().to_4x4() @ local_rot_mat
            elif mode == 'lock_pos' and bname:
                m_delta = _bone_delta_matrix(arm_obj, bname)
                world_wrist = m_delta @ Vector(pos_xyz)
                world_rot_mat = local_rot_mat
            else:
                world_wrist = Vector(pos_xyz)
                world_rot_mat = local_rot_mat

            solve_and_pose_arm_ik(
                arm_obj,
                side,
                world_wrist,
                rot_deg,
                Vector(pole_xyz),
                f_dict,
                f,
                hand_rot_matrix=world_rot_mat,
                prev_quats=prev_quats,
            )

    # Apply smooth AUTO_CLAMPED Bezier handles across ALL weapon + arm + finger F-curves
    set_action_bezier_smooth(action)

    # Push onto NLA track for glTF export
    track = arm_obj.animation_data.nla_tracks.new()
    track.name = action_name
    strip = track.strips.new(action_name, start=1, action=action)
    strip.frame_end = max(2, end_frame)
    arm_obj.animation_data.action = None
    _reset_pose(arm_obj)
    return action


def _export_fp_glb(filepath: str):
    # Guarantee all bone-skinned modular attachments (Att_*) are visible & exported cleanly in GLB!
    for obj in bpy.data.objects:
        if obj.name.startswith("Att_"):
            obj.hide_viewport = False
            obj.hide_render = False
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
    render_attachments_shot: bool = False,
):
    """Renders:
      1) 70-deg First-Person Camera Viewpoint (clean base weapon)
      2) 3/4 Hand-Grip inspection shot
      3) 70-deg First-Person MID-ACTION shot (proves reload/shell/bolt framing!)
      4) Optional 70-deg First-Person shot with bone-skinned modular attachments visible!
    """
    os.makedirs(RIG_RENDER_DIR, exist_ok=True)
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 720
    scene.render.image_settings.file_format = 'PNG'

    att_objs = [o for o in bpy.data.objects if o.name.startswith("Att_")]
    for o in att_objs:
        o.hide_render = True

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
        _add_light("Key", (1.2, 0.4, 1.1), (48, 0, 128), 240.0, (1.0, 0.96, 0.92), 1.6),
        _add_light("Fill", (-1.1, -0.3, 0.9), (60, 0, -58), 150.0, (0.82, 0.90, 1.0), 1.8),
        _add_light("Rim", (0.1, 1.1, 1.0), (50, 0, 175), 190.0, (0.96, 0.98, 1.0), 1.4),
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

    tracks = arm_obj.animation_data.nla_tracks
    for tr in tracks:
        tr.mute = (tr.name != idle_action_name)
    scene.frame_set(1)
    bpy.context.view_layer.update()

    # 1. First-person 70-deg idle view
    _aim(cam_fp_loc, cam_fp_target)
    scene.render.filepath = os.path.join(RIG_RENDER_DIR, f"{prefix}_01_fp_view.png")
    bpy.ops.render.render(write_still=True)

    # 2. 3/4 Hand-grip inspection view
    cam_d.lens_unit = 'MILLIMETERS'
    cam_d.lens = 45.0
    _aim(side_cam_loc, side_cam_target)
    scene.render.filepath = os.path.join(RIG_RENDER_DIR, f"{prefix}_02_hand_grip.png")
    bpy.ops.render.render(write_still=True)

    # 3. 70-deg First-Person MID-ACTION view (verify reload/shell/bolt framing directly!)
    if extra_action_name:
        cam_d.lens_unit = 'FOV'
        cam_d.angle = math.radians(70.0)
        for tr in tracks:
            tr.mute = (tr.name != extra_action_name)
        scene.frame_set(extra_frame)
        bpy.context.view_layer.update()
        _aim(cam_fp_loc, cam_fp_target)
        scene.render.filepath = os.path.join(RIG_RENDER_DIR, f"{prefix}_03_action_pose.png")
        bpy.ops.render.render(write_still=True)

    # 4. Optional Attachments-Equipped First-Person preview
    if render_attachments_shot:
        for o in att_objs:
            o.hide_render = False
        cam_d.lens_unit = 'FOV'
        cam_d.angle = math.radians(70.0)
        for tr in tracks:
            tr.mute = (tr.name != idle_action_name)
        scene.frame_set(1)
        bpy.context.view_layer.update()
        _aim(cam_fp_loc, cam_fp_target)
        scene.render.filepath = os.path.join(RIG_RENDER_DIR, f"{prefix}_04_attachments.png")
        bpy.ops.render.render(write_still=True)

    # Restore everything cleanly for glTF export
    for o in att_objs:
        o.hide_render = False
        o.hide_viewport = False
    for tr in tracks:
        tr.mute = False
    scene.frame_set(1)
    bpy.context.view_layer.update()

    bpy.data.objects.remove(cam_o, do_unlink=True)
    for lo in lights:
        bpy.data.objects.remove(lo, do_unlink=True)


# ==============================================================================
# 1. AK-47 + FIRST-PERSON ARMS OVERHAUL
# ==============================================================================
def build_ak47_fp():
    src = os.path.join(WEAPONS_DIR, "ak47", "source", "ak47.blend")
    bpy.ops.wm.open_mainfile(filepath=src)
    arm = bpy.data.objects["AK47_Rig"]
    _clear_old_actions_and_nla(arm)

    # Bone-parented hand interaction reference markers (always move with weapon_body!)
    add_bone_marker_empty("GripPrimary",  (0.030, -0.068, -0.056), arm, "weapon_body")
    add_bone_marker_empty("GripSupport",  (-0.028, 0.210, -0.028), arm, "weapon_body")
    add_bone_marker_empty("MagInteract",  (-0.044, 0.132, -0.118), arm, "magazine")
    add_bone_marker_empty("BoltInteract", (0.042,  0.088,  0.028), arm, "charging_handle")
    add_bone_marker_empty("ADSRef",       (0.0,   -0.25,   0.084), arm, "weapon_body")

    add_fp_arms_to_armature(arm, "weapon_root", add_ik_controls=True)

    # Exact weapon-body-local grip coordinates (mathematically locked via M_delta!)
    R_GRIP = (0.030, -0.068, -0.056)
    R_ROT  = (-16.0, -88.0, 10.0)
    R_POLE = (0.36, -0.18, -0.36)

    L_GRIP = (-0.022, 0.215, -0.022)
    L_ROT  = (18.0, 158.0, -24.0)
    L_POLE = (-0.34, 0.04, -0.36)

    # Magazine-bone-local left hand grip (locked directly to magazine!)
    L_MAG     = (-0.044, 0.132, -0.118)
    L_MAG_ROT = (8.0, 96.0, -18.0)

    # Charging-handle-bone-local left hand underhand reach
    L_CHG     = (0.014, 0.084, -0.026)
    L_CHG_ROT = (20.0, 142.0, -40.0)

    # 1. idle (60f: calm organic breathing sway, hands locked seamlessly to weapon_body)
    _bake_synchronized_action(arm, "idle", 60, {
        "weapon_body": [
            (1,  (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
            (20, (0.0012, 0.0, 0.0022), (0.28, -0.18, 0.15)),
            (40, (-0.0010, 0.0, 0.0010), (-0.15, 0.15, -0.10)),
            (60, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
        ],
    }, {
        'R': [
            (1,  'lock', "weapon_body", R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
            (60, 'lock', "weapon_body", R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
        ],
        'L': [
            (1,  'lock', "weapon_body", L_GRIP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
            (60, 'lock', "weapon_body", L_GRIP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
        ],
    }, sample_step=6)

    # 2. ads_idle (60f: rock-steady cheek-weld aim breath)
    _bake_synchronized_action(arm, "ads_idle", 60, {
        "weapon_body": [
            (1,  (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
            (30, (0.0, 0.0, 0.0005), (0.06, 0.0, 0.03)),
            (60, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
        ],
    }, {
        'R': [
            (1,  'lock', "weapon_body", R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
            (60, 'lock', "weapon_body", R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
        ],
        'L': [
            (1,  'lock', "weapon_body", L_GRIP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
            (60, 'lock', "weapon_body", L_GRIP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
        ],
    }, sample_step=10)

    # 3. fire (7f: snappy stamped-steel recoil + bolt carrier cycle + trigger squeeze)
    _bake_synchronized_action(arm, "fire", 7, {
        "weapon_body": [
            (1, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
            (2, (0.0, -0.017, 0.0045), (2.2, -0.6, 0.0)),
            (4, (0.0, -0.006, 0.0015), (0.7, 0.2, 0.0)),
            (7, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
        ],
        "charging_handle": [(1, (0, 0, 0), None), (2, (0, -0.084, 0), None), (5, (0, 0, 0), None)],
        "trigger": [(1, None, (0, 0, 0)), (2, None, (22, 0, 0)), (5, None, (0, 0, 0))],
    }, {
        'R': [
            (1, 'lock', "weapon_body", R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
            (2, 'lock', "weapon_body", R_GRIP, R_ROT, R_POLE, FINGER_GRIP_TRIGGER_PULL),
            (5, 'lock', "weapon_body", R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
            (7, 'lock', "weapon_body", R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
        ],
        'L': [
            (1, 'lock', "weapon_body", L_GRIP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
            (7, 'lock', "weapon_body", L_GRIP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
        ],
    }, sample_step=1)

    # 4. reload (tactical reload, 46f ≈ 1.53s: camera-framed lift & cant so curved banana mag + left hand sit dead-center in 70-deg view!)
    _bake_synchronized_action(arm, "reload", 46, {
        "weapon_body": [
            (1,  (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
            (8,  (-0.088, 0.085, 0.092), (18.0, 34.0, 14.0)),
            (15, (-0.090, 0.082, 0.098), (20.0, 36.0, 14.0)),
            (32, (-0.088, 0.085, 0.092), (18.0, 34.0, 14.0)),
            (37, (-0.084, 0.088, 0.104), (21.0, 32.0, 12.0)),
            (46, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
        ],
        "mag_release": [(1, None, (0, 0, 0)), (10, None, (0, 0, 0)), (12, None, (-24, 0, 0)), (16, None, (0, 0, 0))],
        "magazine": [
            (1,  (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
            (11, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
            (16, (0.0, 0.024, -0.052), (-24.0, 0.0, 0.0)),       # Authentic AK rock-forward release!
            (22, (0.0, 0.038, -0.240), (-34.0, 0.0, 0.0)),       # Clear frame to belt pouch
            (27, (0.0, 0.038, -0.240), (-34.0, 0.0, 0.0)),
            (33, (0.0, 0.022, -0.045), (-20.0, 0.0, 0.0)),       # Hook front lug into receiver
            (37, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),              # Lock rear lug with firm click!
        ],
    }, {
        'R': [
            (1,  'lock', "weapon_body", R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
            (46, 'lock', "weapon_body", R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
        ],
        'L': [
            (1,  'lock', "weapon_body", L_GRIP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
            (5,  'lock', "weapon_body", (-0.046, 0.165, -0.068), (12.0, 124.0, -22.0), L_POLE, FINGER_GRIP_OPEN),
            (10, 'lock', "magazine", L_MAG, L_MAG_ROT, L_POLE, FINGER_GRIP_MAG),
            (22, 'lock', "magazine", L_MAG, L_MAG_ROT, L_POLE, FINGER_GRIP_MAG),
            (27, 'lock', "magazine", L_MAG, L_MAG_ROT, L_POLE, FINGER_GRIP_MAG),
            (37, 'lock', "magazine", L_MAG, L_MAG_ROT, L_POLE, FINGER_GRIP_MAG),
            (41, 'lock', "weapon_body", (-0.042, 0.160, -0.062), (14.0, 134.0, -24.0), L_POLE, FINGER_GRIP_OPEN),
            (46, 'lock', "weapon_body", L_GRIP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
        ],
    }, sample_step=2)

    # 5. reload_empty (empty reload, 62f ≈ 2.07s: mag swap + cant rifle left to clearly show charging handle rack!)
    _bake_synchronized_action(arm, "reload_empty", 62, {
        "weapon_body": [
            (1,  (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
            (8,  (-0.088, 0.085, 0.092), (18.0, 34.0, 14.0)),
            (15, (-0.090, 0.082, 0.098), (20.0, 36.0, 14.0)),
            (32, (-0.088, 0.085, 0.092), (18.0, 34.0, 14.0)),
            (37, (-0.084, 0.088, 0.104), (21.0, 32.0, 12.0)),
            (45, (-0.078, 0.068, 0.068), (10.0, -32.0, 12.0)),   # Roll left & lift to showcase right-side chrome charging handle!
            (53, (-0.078, 0.058, 0.064), (12.0, -34.0, 12.0)),
            (56, (-0.074, 0.070, 0.068), (9.0, -28.0, 10.0)),
            (62, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
        ],
        "mag_release": [(1, None, (0, 0, 0)), (10, None, (0, 0, 0)), (12, None, (-24, 0, 0)), (16, None, (0, 0, 0))],
        "magazine": [
            (1,  (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
            (11, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
            (16, (0.0, 0.024, -0.052), (-24.0, 0.0, 0.0)),
            (22, (0.0, 0.038, -0.240), (-34.0, 0.0, 0.0)),
            (27, (0.0, 0.038, -0.240), (-34.0, 0.0, 0.0)),
            (33, (0.0, 0.022, -0.045), (-20.0, 0.0, 0.0)),
            (37, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
        ],
        "charging_handle": [
            (1,  (0.0, 0.0, 0.0), None),
            (46, (0.0, 0.0, 0.0), None),
            (52, (0.0, -0.088, 0.0), None),
            (55, (0.0, 0.0, 0.0), None),
        ],
    }, {
        'R': [
            (1,  'lock', "weapon_body", R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
            (62, 'lock', "weapon_body", R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
        ],
        'L': [
            (1,  'lock', "weapon_body", L_GRIP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
            (5,  'lock', "weapon_body", (-0.046, 0.165, -0.068), (12.0, 124.0, -22.0), L_POLE, FINGER_GRIP_OPEN),
            (10, 'lock', "magazine", L_MAG, L_MAG_ROT, L_POLE, FINGER_GRIP_MAG),
            (22, 'lock', "magazine", L_MAG, L_MAG_ROT, L_POLE, FINGER_GRIP_MAG),
            (27, 'lock', "magazine", L_MAG, L_MAG_ROT, L_POLE, FINGER_GRIP_MAG),
            (37, 'lock', "magazine", L_MAG, L_MAG_ROT, L_POLE, FINGER_GRIP_MAG),
            # Underhand reach to chrome charging handle, pull back, release, return to forend!
            (46, 'lock_pos', "charging_handle", L_CHG, L_CHG_ROT, L_POLE, FINGER_GRIP_PINCH),
            (52, 'lock_pos', "charging_handle", L_CHG, L_CHG_ROT, L_POLE, FINGER_GRIP_PINCH),
            (56, 'lock', "weapon_body", (-0.036, 0.125, -0.056), (16.0, 140.0, -28.0), L_POLE, FINGER_GRIP_OPEN),
            (62, 'lock', "weapon_body", L_GRIP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
        ],
    }, sample_step=2)

    # 6. equip (12f) & 7. unequip (8f)
    _bake_synchronized_action(arm, "equip", 12, {
        "weapon_body": [
            (1,  (0.0, -0.05, -0.19), (-34.0, 10.0, -10.0)),
            (8,  (0.0, 0.005, 0.008), (2.5, -1.0, 0.5)),
            (12, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
        ],
    }, {
        'R': [
            (1,  'lock', "weapon_body", R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
            (12, 'lock', "weapon_body", R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
        ],
        'L': [
            (1,  'lock', "weapon_body", L_GRIP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
            (12, 'lock', "weapon_body", L_GRIP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
        ],
    }, sample_step=2)

    _bake_synchronized_action(arm, "unequip", 8, {
        "weapon_body": [
            (1, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
            (8, (0.0, -0.05, -0.19), (-34.0, 10.0, -10.0)),
        ],
    }, {
        'R': [
            (1, 'lock', "weapon_body", R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
            (8, 'lock', "weapon_body", R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
        ],
        'L': [
            (1, 'lock', "weapon_body", L_GRIP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
            (8, 'lock', "weapon_body", L_GRIP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
        ],
    }, sample_step=2)

    # Exact Godot-matching 70-deg FP camera: hip_position=(+0.20, -0.18, -0.34) => cam at (-0.20, -0.34, +0.18) looking along +Y!
    _render_fp_preview(
        "ak47_hands", arm, "idle",
        cam_fp_loc=(-0.20, -0.34, 0.18), cam_fp_target=(-0.20, 0.66, 0.18),
        side_cam_loc=(-0.62, 0.06, 0.16), side_cam_target=(0.0, 0.08, -0.04),
        extra_action_name="reload", extra_frame=16,
        render_attachments_shot=True,
    )
    save_blend(os.path.join(WEAPONS_DIR, "ak47", "source", "ak47_fp.blend"))
    _export_fp_glb(os.path.join(WEAPONS_DIR, "ak47", "ak47_fp.glb"))
    print("[AK-47 FP Overhaul] Built, bone-locked hands, Bezier animated, rendered & exported.")


# ==============================================================================
# 2. SPAS-12 + FIRST-PERSON ARMS OVERHAUL (CAMERA-FRAMED VISIBLE SHELL LOADING!)
# ==============================================================================
def build_spas12_fp():
    src = os.path.join(WEAPONS_DIR, "spas12", "source", "spas12.blend")
    bpy.ops.wm.open_mainfile(filepath=src)
    arm = bpy.data.objects["SPAS12_Rig"]
    _clear_old_actions_and_nla(arm)

    add_bone_marker_empty("GripPrimary",  (0.032, -0.092, -0.056), arm, "weapon_body")
    add_bone_marker_empty("GripSupport",  (-0.032, 0.345, -0.034), arm, "pump")
    add_bone_marker_empty("ShellPort",    (-0.015, 0.060, -0.035), arm, "weapon_body")
    add_bone_marker_empty("BoltInteract", (0.036,  0.075,  0.025), arm, "bolt")
    add_bone_marker_empty("ADSRef",       (0.0,   -0.26,   0.072), arm, "weapon_body")

    add_fp_arms_to_armature(arm, "weapon_root", add_ik_controls=True)

    R_GRIP = (0.032, -0.092, -0.056)
    R_ROT  = (-18.0, -88.0, 10.0)
    R_POLE = (0.36, -0.20, -0.36)

    # Locked to `pump` bone so left hand automatically slides cleanly during shell_end pump rack!
    L_PUMP = (-0.026, 0.345, -0.026)
    L_ROT  = (16.0, 160.0, -22.0)
    L_POLE = (-0.36, 0.08, -0.36)

    # Locked directly to `shell` bone during shell_insert so left hand visibly pushes red shell into loading gate!
    L_SHELL     = (-0.034, 0.030, -0.048)
    L_SHELL_ROT = (26.0, 140.0, -22.0)

    # Camera-framed elevated + rolled loading pose: lifts red shell & chrome loading gate cleanly into upper-center of 70-deg view!
    LOAD_POS = (-0.068, 0.060, 0.076)
    LOAD_ROT = (18.0, 48.0, 14.0)

    # 1. idle (60f)
    _bake_synchronized_action(arm, "idle", 60, {
        "weapon_body": [
            (1,  (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
            (30, (0.001, 0.0, 0.0022), (0.28, -0.15, 0.14)),
            (60, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
        ],
        "shell": [(1, (0, 0, 0), None, (0.001, 0.001, 0.001))],
    }, {
        'R': [
            (1,  'lock', "weapon_body", R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
            (60, 'lock', "weapon_body", R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
        ],
        'L': [
            (1,  'lock', "pump", L_PUMP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
            (60, 'lock', "pump", L_PUMP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
        ],
    }, sample_step=6)

    # 2. ads_idle (60f)
    _bake_synchronized_action(arm, "ads_idle", 60, {
        "weapon_body": [
            (1,  (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
            (30, (0.0, 0.0, 0.0005), (0.06, 0.0, 0.03)),
            (60, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
        ],
        "shell": [(1, (0, 0, 0), None, (0.001, 0.001, 0.001))],
    }, {
        'R': [
            (1,  'lock', "weapon_body", R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
            (60, 'lock', "weapon_body", R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
        ],
        'L': [
            (1,  'lock', "pump", L_PUMP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
            (60, 'lock', "pump", L_PUMP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
        ],
    }, sample_step=10)

    # 3. fire (14f: genuine semi-auto SPAS-12 heavy blast recoil + chrome bolt reciprocation, NO contradictory pump!)
    _bake_synchronized_action(arm, "fire", 14, {
        "weapon_body": [
            (1,  (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
            (3,  (0.0, -0.042, 0.014), (6.5, -1.0, 0.0)),
            (8,  (0.0, -0.008, 0.003), (1.3, 0.4, 0.0)),
            (14, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
        ],
        "trigger": [(1, None, (0, 0, 0)), (2, None, (24, 0, 0)), (6, None, (0, 0, 0))],
        "bolt": [(1, (0, 0, 0), None), (3, (0, -0.072, 0), None), (7, (0, 0, 0), None)],
        "shell": [(1, (0, 0, 0), None, (0.001, 0.001, 0.001))],
    }, {
        'R': [
            (1,  'lock', "weapon_body", R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
            (3,  'lock', "weapon_body", R_GRIP, R_ROT, R_POLE, FINGER_GRIP_TRIGGER_PULL),
            (7,  'lock', "weapon_body", R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
            (14, 'lock', "weapon_body", R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
        ],
        'L': [
            (1,  'lock', "pump", L_PUMP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
            (14, 'lock', "pump", L_PUMP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
        ],
    }, sample_step=2)

    # 4. shell_start (10f: lift & roll shotgun cleanly into view, left hand drops from ribbed forend to shell belt)
    _bake_synchronized_action(arm, "shell_start", 10, {
        "weapon_body": [(1, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)), (10, LOAD_POS, LOAD_ROT)],
        "shell": [(1, (0, 0, 0), None, (0.001, 0.001, 0.001))],
    }, {
        'R': [
            (1,  'lock', "weapon_body", R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
            (10, 'lock', "weapon_body", R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
        ],
        'L': [
            (1,  'lock', "pump", L_PUMP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
            (5,  'lock', "weapon_body", (-0.068, 0.160, -0.085), (18.0, 140.0, -20.0), L_POLE, FINGER_GRIP_OPEN),
            (10, 'lock', "weapon_body", (-0.085, 0.015, -0.155), (20.0, 128.0, -14.0), L_POLE, FINGER_GRIP_PINCH),
        ],
    }, sample_step=2)

    # 5. shell_insert (13f: repeatable visible red-shell insertion right in the middle of the camera!)
    _bake_synchronized_action(arm, "shell_insert", 13, {
        "weapon_body": [
            (1,  LOAD_POS, LOAD_ROT),
            (8,  (LOAD_POS[0], LOAD_POS[1] + 0.004, LOAD_POS[2] + 0.009), (LOAD_ROT[0] + 2.5, LOAD_ROT[1] + 2.0, LOAD_ROT[2])),
            (13, LOAD_POS, LOAD_ROT),
        ],
        "loading_gate": [(1, None, (0, 0, 0)), (5, None, (30, 0, 0)), (10, None, (34, 0, 0)), (13, None, (0, 0, 0))],
        "shell": [
            (1,  (0.0, -0.045, -0.115), (22.0, 0.0, 0.0), (1.0, 1.0, 1.0)),
            (6,  (0.0, -0.008, -0.032), (12.0, 0.0, 0.0), (1.0, 1.0, 1.0)),
            (10, (0.0,  0.038,  0.000), (0.0,  0.0, 0.0), (1.0, 1.0, 1.0)),
            (12, (0.0,  0.062,  0.004), (0.0,  0.0, 0.0), (0.001, 0.001, 0.001)),
        ],
    }, {
        'R': [
            (1,  'lock', "weapon_body", R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
            (13, 'lock', "weapon_body", R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
        ],
        'L': [
            (1,  'lock_pos', "shell", L_SHELL, L_SHELL_ROT, L_POLE, FINGER_GRIP_PINCH),
            (6,  'lock_pos', "shell", L_SHELL, (30.0, 144.0, -24.0), L_POLE, FINGER_GRIP_PINCH),
            (10, 'lock_pos', "shell", L_SHELL, (34.0, 148.0, -26.0), L_POLE, FINGER_GRIP_PINCH),
            (13, 'lock', "weapon_body", (-0.085, 0.015, -0.155), (20.0, 128.0, -14.0), L_POLE, FINGER_GRIP_PINCH),
        ],
    }, sample_step=2)

    # 6. shell_end (12f: roll back level, left hand snaps onto ribbed forend & racks pump + chrome bolt cleanly!)
    _bake_synchronized_action(arm, "shell_end", 12, {
        "weapon_body": [
            (1,  LOAD_POS, LOAD_ROT),
            (6,  (0.0, -0.008, 0.004), (2.0, 0.0, 0.0)),
            (9,  (0.0, -0.016, 0.006), (3.5, 0.0, 0.0)),
            (12, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
        ],
        "pump": [(1, (0, 0, 0), None), (5, (0, 0, 0), None), (9, (0, -0.078, 0), None), (12, (0, 0, 0), None)],
        "bolt": [(1, (0, 0, 0), None), (5, (0, 0, 0), None), (9, (0, -0.072, 0), None), (12, (0, 0, 0), None)],
        "shell": [(1, (0, 0, 0), None, (0.001, 0.001, 0.001))],
    }, {
        'R': [
            (1,  'lock', "weapon_body", R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
            (12, 'lock', "weapon_body", R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
        ],
        'L': [
            (1,  'lock', "weapon_body", (-0.085, 0.015, -0.155), (20.0, 128.0, -14.0), L_POLE, FINGER_GRIP_OPEN),
            (5,  'lock', "pump", L_PUMP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
            (12, 'lock', "pump", L_PUMP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
        ],
    }, sample_step=2)

    # 7. reload_interrupt (7f: instant tactical snap back to firing stance!)
    _bake_synchronized_action(arm, "reload_interrupt", 7, {
        "weapon_body": [(1, LOAD_POS, LOAD_ROT), (7, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0))],
        "loading_gate": [(1, None, (0, 0, 0))],
        "shell": [(1, (0, 0, 0), None, (0.001, 0.001, 0.001))],
    }, {
        'R': [
            (1, 'lock', "weapon_body", R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
            (7, 'lock', "weapon_body", R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
        ],
        'L': [
            (1, 'lock', "weapon_body", (-0.068, 0.085, -0.115), (18.0, 136.0, -18.0), L_POLE, FINGER_GRIP_OPEN),
            (7, 'lock', "pump", L_PUMP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
        ],
    }, sample_step=2)

    # 8. equip (12f) & 9. unequip (8f)
    _bake_synchronized_action(arm, "equip", 12, {
        "weapon_body": [
            (1,  (0.0, -0.06, -0.19), (-34.0, 10.0, -10.0)),
            (9,  (0.0, 0.005, 0.008), (2.5, 0.0, 0.0)),
            (12, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
        ],
        "shell": [(1, (0, 0, 0), None, (0.001, 0.001, 0.001))],
    }, {
        'R': [
            (1,  'lock', "weapon_body", R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
            (12, 'lock', "weapon_body", R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
        ],
        'L': [
            (1,  'lock', "pump", L_PUMP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
            (12, 'lock', "pump", L_PUMP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
        ],
    }, sample_step=2)

    _bake_synchronized_action(arm, "unequip", 8, {
        "weapon_body": [(1, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)), (8, (0.0, -0.06, -0.19), (-34.0, 10.0, -10.0))],
        "shell": [(1, (0, 0, 0), None, (0.001, 0.001, 0.001))],
    }, {
        'R': [
            (1, 'lock', "weapon_body", R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
            (8, 'lock', "weapon_body", R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
        ],
        'L': [
            (1, 'lock', "pump", L_PUMP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
            (8, 'lock', "pump", L_PUMP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
        ],
    }, sample_step=2)

    _render_fp_preview(
        "spas12_hands", arm, "idle",
        cam_fp_loc=(-0.20, -0.35, 0.18), cam_fp_target=(-0.20, 0.65, 0.18),
        side_cam_loc=(-0.64, 0.10, 0.16), side_cam_target=(0.0, 0.12, -0.03),
        extra_action_name="shell_insert", extra_frame=7,
    )
    save_blend(os.path.join(WEAPONS_DIR, "spas12", "source", "spas12_fp.blend"))
    _export_fp_glb(os.path.join(WEAPONS_DIR, "spas12", "spas12_fp.glb"))
    print("[SPAS-12 FP Overhaul] Built, bone-locked hands, Bezier animated, rendered & exported.")


# ==============================================================================
# 3. AWP + FIRST-PERSON ARMS OVERHAUL (CAMERA-FRAMED BOLT CYCLE & MAG RELOAD!)
# ==============================================================================
def build_awp_fp():
    src = os.path.join(WEAPONS_DIR, "awp", "source", "awp.blend")
    bpy.ops.wm.open_mainfile(filepath=src)
    arm = bpy.data.objects["AWP_Rig"]
    _clear_old_actions_and_nla(arm)

    add_bone_marker_empty("GripPrimary",  (0.030, -0.072, -0.054), arm, "weapon_body")
    add_bone_marker_empty("GripSupport",  (-0.032, 0.245, -0.044), arm, "weapon_body")
    add_bone_marker_empty("MagInteract",  (-0.044, 0.105, -0.074), arm, "magazine")
    add_bone_marker_empty("BoltInteract", (0.054, -0.020,  0.018), arm, "bolt_handle")
    add_bone_marker_empty("ADSRef",       (0.0,   -0.26,   0.105), arm, "weapon_body")

    add_fp_arms_to_armature(arm, "weapon_root", add_ik_controls=True)

    R_GRIP = (0.030, -0.072, -0.054)
    R_ROT  = (-16.0, -88.0, 10.0)
    R_POLE = (0.36, -0.18, -0.36)

    L_GRIP = (-0.026, 0.245, -0.036)
    L_ROT  = (18.0, 160.0, -22.0)
    L_POLE = (-0.36, 0.06, -0.36)

    L_MAG     = (-0.044, 0.105, -0.074)
    L_MAG_ROT = (4.0, 96.0, -18.0)

    # Bolt-handle-locked right wrist anchor (follows spherical bolt knob through all 4 bolt phases!)
    R_BOLT_PT  = (0.066, -0.042, 0.002)
    R_BOLT_LOW = (-8.0, -50.0, 20.0)
    R_BOLT_UP  = (10.0, -32.0, 26.0)

    # Camera-framed bolt-cycle pose: brought forward, centered & canted left so right hand + spherical bolt sit DEAD-CENTER above HUD!
    BOLT_BODY_POS = (-0.096, 0.086, 0.072)
    BOLT_BODY_ROT = (10.0, -34.0, 14.0)

    # 1. idle (60f)
    _bake_synchronized_action(arm, "idle", 60, {
        "weapon_body": [
            (1,  (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
            (30, (0.0008, 0.0, 0.0016), (0.18, -0.10, 0.08)),
            (60, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
        ],
    }, {
        'R': [
            (1,  'lock', "weapon_body", R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
            (60, 'lock', "weapon_body", R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
        ],
        'L': [
            (1,  'lock', "weapon_body", L_GRIP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
            (60, 'lock', "weapon_body", L_GRIP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
        ],
    }, sample_step=6)

    # 2. ads_idle (60f)
    _bake_synchronized_action(arm, "ads_idle", 60, {
        "weapon_body": [
            (1,  (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
            (30, (0.0, 0.0, 0.0004), (0.04, 0.0, 0.02)),
            (60, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
        ],
    }, {
        'R': [
            (1,  'lock', "weapon_body", R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
            (60, 'lock', "weapon_body", R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
        ],
        'L': [
            (1,  'lock', "weapon_body", L_GRIP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
            (60, 'lock', "weapon_body", L_GRIP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
        ],
    }, sample_step=10)

    # 3. fire (10f: authoritative .338 Lapua recoil kick)
    _bake_synchronized_action(arm, "fire", 10, {
        "weapon_body": [
            (1,  (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
            (3,  (0.0, -0.044, 0.013), (5.8, -0.8, 0.0)),
            (7,  (0.0, -0.010, 0.003), (1.2, 0.3, 0.0)),
            (10, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
        ],
        "trigger": [(1, None, (0, 0, 0)), (2, None, (22, 0, 0)), (6, None, (0, 0, 0))],
    }, {
        'R': [
            (1,  'lock', "weapon_body", R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
            (3,  'lock', "weapon_body", R_GRIP, R_ROT, R_POLE, FINGER_GRIP_TRIGGER_PULL),
            (7,  'lock', "weapon_body", R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
            (10, 'lock', "weapon_body", R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
        ],
        'L': [
            (1,  'lock', "weapon_body", L_GRIP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
            (10, 'lock', "weapon_body", L_GRIP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
        ],
    }, sample_step=2)

    # 4. bolt_action (26f ≈ 0.85s: camera-framed right-hand lift -> pull back -> push forward -> lock down!)
    _bake_synchronized_action(arm, "bolt_action", 26, {
        "weapon_body": [
            (1,  (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
            (6,  BOLT_BODY_POS, BOLT_BODY_ROT),
            (14, (BOLT_BODY_POS[0], BOLT_BODY_POS[1] - 0.012, BOLT_BODY_POS[2] + 0.005), (BOLT_BODY_ROT[0] + 2.0, BOLT_BODY_ROT[1] - 2.0, BOLT_BODY_ROT[2])),
            (20, BOLT_BODY_POS, BOLT_BODY_ROT),
            (26, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
        ],
        "bolt_handle": [
            (1,  None, (0.0, 0.0, 0.0)),
            (5,  None, (0.0, 0.0, 0.0)),
            (10, None, (0.0, -68.0, 0.0)),
            (18, None, (0.0, -68.0, 0.0)),
            (21, None, (0.0, 0.0, 0.0)),
        ],
        "bolt": [
            (1,  (0.0, 0.0, 0.0), None),
            (10, (0.0, 0.0, 0.0), None),
            (14, (0.0, -0.092, 0.0), None),
            (18, (0.0, 0.0, 0.0), None),
        ],
    }, {
        'L': [
            (1,  'lock', "weapon_body", L_GRIP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
            (26, 'lock', "weapon_body", L_GRIP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
        ],
        'R': [
            (1,  'lock', "weapon_body", R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
            (5,  'lock_pos', "bolt_handle", R_BOLT_PT, R_BOLT_LOW, R_POLE, FINGER_GRIP_PINCH),
            (10, 'lock_pos', "bolt_handle", R_BOLT_PT, R_BOLT_UP,  R_POLE, FINGER_GRIP_PINCH),
            (14, 'lock_pos', "bolt_handle", R_BOLT_PT, R_BOLT_UP,  R_POLE, FINGER_GRIP_PINCH),
            (18, 'lock_pos', "bolt_handle", R_BOLT_PT, R_BOLT_UP,  R_POLE, FINGER_GRIP_PINCH),
            (21, 'lock_pos', "bolt_handle", R_BOLT_PT, R_BOLT_LOW, R_POLE, FINGER_GRIP_PINCH),
            (26, 'lock', "weapon_body", R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
        ],
    }, sample_step=2)

    # 5. reload (tactical mag swap, 50f ≈ 1.67s: camera-framed box mag drop & fresh mag lock!)
    _bake_synchronized_action(arm, "reload", 50, {
        "weapon_body": [
            (1,  (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
            (8,  (-0.082, 0.075, 0.088), (16.0, 30.0, 12.0)),
            (36, (-0.082, 0.075, 0.088), (16.0, 30.0, 12.0)),
            (40, (-0.078, 0.078, 0.098), (18.5, 28.0, 10.0)),   # Positive upward seating tap!
            (50, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
        ],
        "magazine": [
            (1,  (0.0, 0.0, 0.0), None),
            (11, (0.0, 0.0, 0.0), None),
            (19, (0.0, 0.0, -0.23), None),
            (28, (0.0, 0.0, -0.23), None),
            (38, (0.0, 0.0, 0.0), None),
        ],
    }, {
        'R': [
            (1,  'lock', "weapon_body", R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
            (50, 'lock', "weapon_body", R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
        ],
        'L': [
            (1,  'lock', "weapon_body", L_GRIP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
            (11, 'lock', "magazine", L_MAG, L_MAG_ROT, L_POLE, FINGER_GRIP_MAG),
            (19, 'lock', "magazine", L_MAG, L_MAG_ROT, L_POLE, FINGER_GRIP_MAG),
            (28, 'lock', "magazine", L_MAG, L_MAG_ROT, L_POLE, FINGER_GRIP_MAG),
            (38, 'lock', "magazine", L_MAG, L_MAG_ROT, L_POLE, FINGER_GRIP_MAG),
            (44, 'lock', "weapon_body", (-0.046, 0.185, -0.068), (14.0, 138.0, -24.0), L_POLE, FINGER_GRIP_OPEN),
            (50, 'lock', "weapon_body", L_GRIP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
        ],
    }, sample_step=2)

    # 6. reload_empty (70f ≈ 2.33s: box mag swap + full camera-framed right-hand bolt cycle!)
    _bake_synchronized_action(arm, "reload_empty", 70, {
        "weapon_body": [
            (1,  (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
            (8,  (-0.082, 0.075, 0.088), (16.0, 30.0, 12.0)),
            (36, (-0.082, 0.075, 0.088), (16.0, 30.0, 12.0)),
            (40, (-0.078, 0.078, 0.098), (18.5, 28.0, 10.0)),
            (48, BOLT_BODY_POS, BOLT_BODY_ROT),
            (57, (BOLT_BODY_POS[0], BOLT_BODY_POS[1] - 0.012, BOLT_BODY_POS[2] + 0.005), (BOLT_BODY_ROT[0] + 2.0, BOLT_BODY_ROT[1] - 2.0, BOLT_BODY_ROT[2])),
            (63, BOLT_BODY_POS, BOLT_BODY_ROT),
            (70, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
        ],
        "magazine": [
            (1,  (0.0, 0.0, 0.0), None),
            (11, (0.0, 0.0, 0.0), None),
            (19, (0.0, 0.0, -0.23), None),
            (28, (0.0, 0.0, -0.23), None),
            (38, (0.0, 0.0, 0.0), None),
        ],
        "bolt_handle": [
            (1,  None, (0.0, 0.0, 0.0)),
            (48, None, (0.0, 0.0, 0.0)),
            (53, None, (0.0, -68.0, 0.0)),
            (61, None, (0.0, -68.0, 0.0)),
            (64, None, (0.0, 0.0, 0.0)),
        ],
        "bolt": [
            (1,  (0.0, 0.0, 0.0), None),
            (53, (0.0, 0.0, 0.0), None),
            (57, (0.0, -0.092, 0.0), None),
            (61, (0.0, 0.0, 0.0), None),
        ],
    }, {
        'L': [
            (1,  'lock', "weapon_body", L_GRIP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
            (11, 'lock', "magazine", L_MAG, L_MAG_ROT, L_POLE, FINGER_GRIP_MAG),
            (19, 'lock', "magazine", L_MAG, L_MAG_ROT, L_POLE, FINGER_GRIP_MAG),
            (28, 'lock', "magazine", L_MAG, L_MAG_ROT, L_POLE, FINGER_GRIP_MAG),
            (38, 'lock', "magazine", L_MAG, L_MAG_ROT, L_POLE, FINGER_GRIP_MAG),
            (45, 'lock', "weapon_body", L_GRIP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
            (70, 'lock', "weapon_body", L_GRIP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
        ],
        'R': [
            (1,  'lock', "weapon_body", R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
            (42, 'lock', "weapon_body", R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
            (48, 'lock_pos', "bolt_handle", R_BOLT_PT, R_BOLT_LOW, R_POLE, FINGER_GRIP_PINCH),
            (53, 'lock_pos', "bolt_handle", R_BOLT_PT, R_BOLT_UP,  R_POLE, FINGER_GRIP_PINCH),
            (57, 'lock_pos', "bolt_handle", R_BOLT_PT, R_BOLT_UP,  R_POLE, FINGER_GRIP_PINCH),
            (61, 'lock_pos', "bolt_handle", R_BOLT_PT, R_BOLT_UP,  R_POLE, FINGER_GRIP_PINCH),
            (64, 'lock_pos', "bolt_handle", R_BOLT_PT, R_BOLT_LOW, R_POLE, FINGER_GRIP_PINCH),
            (70, 'lock', "weapon_body", R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
        ],
    }, sample_step=2)

    # 7. equip (13f) & 8. unequip (9f)
    _bake_synchronized_action(arm, "equip", 13, {
        "weapon_body": [
            (1,  (0.0, -0.07, -0.21), (-34.0, 10.0, -10.0)),
            (9,  (0.0, 0.005, 0.008), (2.5, 0.0, 0.0)),
            (13, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
        ],
    }, {
        'R': [
            (1,  'lock', "weapon_body", R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
            (13, 'lock', "weapon_body", R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
        ],
        'L': [
            (1,  'lock', "weapon_body", L_GRIP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
            (13, 'lock', "weapon_body", L_GRIP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
        ],
    }, sample_step=2)

    _bake_synchronized_action(arm, "unequip", 9, {
        "weapon_body": [(1, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)), (9, (0.0, -0.07, -0.21), (-34.0, 10.0, -10.0))],
    }, {
        'R': [
            (1, 'lock', "weapon_body", R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
            (9, 'lock', "weapon_body", R_GRIP, R_ROT, R_POLE, FINGER_GRIP_PISTOL),
        ],
        'L': [
            (1, 'lock', "weapon_body", L_GRIP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
            (9, 'lock', "weapon_body", L_GRIP, L_ROT, L_POLE, FINGER_GRIP_FOREND),
        ],
    }, sample_step=2)

    _render_fp_preview(
        "awp_hands", arm, "idle",
        cam_fp_loc=(-0.21, -0.34, 0.19), cam_fp_target=(-0.21, 0.66, 0.19),
        side_cam_loc=(0.68, 0.04, 0.18), side_cam_target=(0.0, 0.08, -0.02),
        extra_action_name="bolt_action", extra_frame=14,
    )
    save_blend(os.path.join(WEAPONS_DIR, "awp", "source", "awp_fp.blend"))
    _export_fp_glb(os.path.join(WEAPONS_DIR, "awp", "awp_fp.glb"))
    print("[AWP FP Overhaul] Built, bone-locked hands, Bezier animated, rendered & exported.")


if __name__ == "__main__":
    build_ak47_fp()
    build_spas12_fp()
    build_awp_fp()
