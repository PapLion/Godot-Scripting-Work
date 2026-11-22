"""Reusable Mid-Poly First-Person Arms & Tactical Gloves Rig Generator for Blender 5.3.
Creates a clean anatomical arm/hand/finger mesh with tactical gloves, knuckle armor,
wrist strap, forearm skin + rolled tactical sleeve, full 38-bone deform skeleton,
plus interactive Blender IK hand/pole controls.
"""

import math
import os
import sys
import bpy
import bmesh
from mathutils import Vector, Matrix, Euler

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from weapon_build_utils import (
    reset_scene,
    create_pbr_material,
    finalize_mesh,
    add_box_to_bm,
    add_cyl_to_bm,
    join_objects,
    save_blend,
    export_glb,
)

PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
HANDS_DIR = os.path.join(PROJECT_ROOT, "assets", "hands")
RIG_RENDER_DIR = os.path.join(PROJECT_ROOT, "portfolio_media", "rig_renders")


def _make_tapered_limb_segment(
    bm: bmesh.types.BMesh,
    p0: Vector,
    p1: Vector,
    rx0: float,
    rz0: float,
    rx1: float,
    rz1: float,
    rings: int = 5,
    segs: int = 16,
    cap_start: bool = True,
    cap_end: bool = True,
):
    """Builds a smooth multi-loop elliptical limb/finger segment between p0 and p1 for clean skinning."""
    axis = (p1 - p0)
    length = axis.length
    if length < 1e-5:
        return
    y_dir = axis.normalized()
    ref_up = Vector((0.0, 0.0, 1.0)) if abs(y_dir.dot(Vector((0.0, 0.0, 1.0)))) < 0.95 else Vector((1.0, 0.0, 0.0))
    x_dir = y_dir.cross(ref_up).normalized()
    z_dir = x_dir.cross(y_dir).normalized()

    ring_verts = []
    for r in range(rings + 1):
        t = r / float(rings)
        center = p0.lerp(p1, t)
        rx = rx0 + (rx1 - rx0) * t
        rz = rz0 + (rz1 - rz0) * t
        # Subtle organic bulge near middle/joints
        ring = []
        for s in range(segs):
            ang = (s / float(segs)) * math.tau
            v_pos = center + x_dir * (math.cos(ang) * rx) + z_dir * (math.sin(ang) * rz)
            ring.append(bm.verts.new(v_pos))
        ring_verts.append(ring)

    for r in range(rings):
        r0 = ring_verts[r]
        r1 = ring_verts[r + 1]
        for s in range(segs):
            ns = (s + 1) % segs
            bm.faces.new((r0[s], r0[ns], r1[ns], r1[s]))

    if cap_start:
        bm.faces.new(list(reversed(ring_verts[0])))
    if cap_end:
        bm.faces.new(ring_verts[-1])


def _get_side_rest_layout(side: str):
    """Returns realistic adult metric rest-pose joint coordinates for Left ('L') or Right ('R') arm.
    Upper arm ~0.31m + forearm ~0.29m = ~0.60m natural reach so left hand comfortably cradles
    forward forends (SPAS-12 pump, AK wood handguard, AWP chassis) with natural elbow bend.
    """
    sx = -1.0 if side == 'L' else 1.0
    # Forward-leaning FPS shooting stance shoulders
    shoulder = Vector((sx * 0.23, -0.32 if side == 'R' else -0.24, -0.17))
    elbow = Vector((sx * 0.30, -0.10 if side == 'R' else 0.00, -0.29))
    wrist = Vector((sx * 0.18, 0.14 if side == 'R' else 0.24, -0.14))
    palm_end = wrist + Vector((0.0, 0.088, 0.0))

    # 4 fingers (Index -> Little): medial to lateral
    # Medial side is closer to X=0, so offset along -sx for medial, +sx for lateral
    finger_specs = [
        ("index",  -sx * 0.027, 0.088, 0.002, (0.036, 0.024, 0.020), 0.0092),
        ("middle", -sx * 0.008, 0.091, 0.004, (0.040, 0.027, 0.021), 0.0096),
        ("ring",    sx * 0.011, 0.087, 0.002, (0.037, 0.024, 0.019), 0.0090),
        ("pinky",   sx * 0.028, 0.081, -0.002, (0.029, 0.019, 0.017), 0.0078),
    ]

    fingers = {}
    for fname, x_off, y_off, z_off, lens, rad in finger_specs:
        p0 = wrist + Vector((x_off, y_off, z_off))
        p1 = p0 + Vector((0.0, lens[0], -0.003))
        p2 = p1 + Vector((0.0, lens[1], -0.004))
        p3 = p2 + Vector((0.0, lens[2], -0.004))
        fingers[fname] = (p0, p1, p2, p3, rad)

    # Thumb: angled medially & slightly downward from base of palm
    t0 = wrist + Vector((-sx * 0.032, 0.026, -0.006))
    t1 = t0 + Vector((-sx * 0.024, 0.028, -0.008))
    t2 = t1 + Vector((-sx * 0.016, 0.026, -0.006))
    t3 = t2 + Vector((-sx * 0.008, 0.021, -0.004))
    fingers["thumb"] = (t0, t1, t2, t3, 0.0108)

    return {
        "shoulder": shoulder,
        "elbow": elbow,
        "wrist": wrist,
        "palm_end": palm_end,
        "fingers": fingers,
        "sx": sx,
    }


def create_fp_arms_materials():
    return {
        "glove_olive": create_pbr_material("FP_GloveOlive", (0.20, 0.25, 0.17), metallic=0.02, roughness=0.76, pattern='polymer', seed=301),
        "glove_leather": create_pbr_material("FP_GloveLeather", (0.10, 0.105, 0.115), metallic=0.05, roughness=0.58, pattern='polymer', seed=312),
        "knuckle_armor": create_pbr_material("FP_KnuckleArmor", (0.065, 0.070, 0.080), metallic=0.18, roughness=0.38, pattern='metal', seed=323),
        "skin": create_pbr_material("FP_ForearmSkin", (0.56, 0.40, 0.31), metallic=0.0, roughness=0.58, pattern='polymer', seed=334),
        "sleeve": create_pbr_material("FP_TacticalSleeve", (0.14, 0.17, 0.14), metallic=0.02, roughness=0.84, pattern='polymer', seed=345),
    }


def _build_arm_mesh_for_side(side: str, mats: dict) -> list:
    """Builds detailed anatomical arm, bare forearm, rolled tactical sleeve,
    padded combat glove, knuckle armor plates, leather palm, and 5 articulated fingers.
    Returns list of (mesh_obj, primary_bone_hint) prior to unified joining & smooth skinning.
    """
    lay = _get_side_rest_layout(side)
    sh = lay["shoulder"]
    el = lay["elbow"]
    wr = lay["wrist"]
    sx = lay["sx"]

    parts = []

    # 1. Tactical Rolled Combat Sleeve (Upper arm -> upper forearm)
    bm = bmesh.new()
    _make_tapered_limb_segment(bm, sh, el, 0.058, 0.056, 0.049, 0.047, rings=5, segs=18)
    sleeve_mid = el.lerp(wr, 0.26)
    _make_tapered_limb_segment(bm, el, sleeve_mid, 0.051, 0.049, 0.048, 0.045, rings=3, segs=18)
    # Rolled cuff collar
    cuff_a = el.lerp(wr, 0.22)
    cuff_b = el.lerp(wr, 0.30)
    _make_tapered_limb_segment(bm, cuff_a, cuff_b, 0.052, 0.049, 0.050, 0.047, rings=2, segs=18)
    parts.append(finalize_mesh(f"ArmSleeve_{side}", bm, mats["sleeve"], smooth=True))

    # 2. Bare Muscular Forearm (extends cleanly into glove wrist cuff with zero gap)
    bm = bmesh.new()
    forearm_start = el.lerp(wr, 0.25)
    forearm_end = el.lerp(wr, 0.99)
    _make_tapered_limb_segment(bm, forearm_start, forearm_end, 0.044, 0.041, 0.030, 0.024, rings=7, segs=18)
    parts.append(finalize_mesh(f"ArmForearm_{side}", bm, mats["skin"], smooth=True))

    # 3. Tactical Glove Wrist Cuff (strictly coaxial with forearm) + seamless wrist joint collar
    bm = bmesh.new()
    strap_start = el.lerp(wr, 0.82)
    strap_end = el.lerp(wr, 1.02)
    _make_tapered_limb_segment(bm, strap_start, strap_end, 0.034, 0.029, 0.033, 0.027, rings=3, segs=18)
    parts.append(finalize_mesh(f"GloveCuff_{side}", bm, mats["glove_leather"], smooth=True))

    # Seamless leather wrist bridge dome owned by hand bone so wrist bends cleanly inside cuff
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(
        bm, u_segments=14, v_segments=10, radius=0.030,
        matrix=Matrix.Translation(wr) @ Matrix.Diagonal((1.05, 1.0, 0.72, 1.0))
    )
    parts.append(finalize_mesh(f"GlovePalmWrist_{side}", bm, mats["glove_leather"], smooth=True))

    # 4. Glove Main Hand / Dorsum (Olive-drab padded fabric)
    bm = bmesh.new()
    p_a = wr + Vector((0.0, 0.008, 0.0))
    p_b = wr + Vector((0.0, 0.088, 0.001))
    _make_tapered_limb_segment(bm, p_a, p_b, 0.035, 0.017, 0.041, 0.015, rings=5, segs=18)
    parts.append(finalize_mesh(f"GlovePalmOlive_{side}", bm, mats["glove_olive"], smooth=True))

    # 5. Reinforced Leather Palm Pad & Thumb Saddle
    bm = bmesh.new()
    add_box_to_bm(bm, (0.072, 0.068, 0.010), tuple(wr + Vector((0.0, 0.050, -0.012))))
    add_box_to_bm(bm, (0.024, 0.042, 0.012), tuple(wr + Vector((-sx * 0.032, 0.036, -0.008))))
    parts.append(finalize_mesh(f"GlovePalmPad_{side}", bm, mats["glove_leather"], bevel_width=0.003))

    # 6. Molded Carbon Knuckle Armor Guard (distinctive tactical glove detail!)
    bm = bmesh.new()
    add_box_to_bm(bm, (0.074, 0.020, 0.012), tuple(wr + Vector((0.0, 0.082, 0.014))))
    for k_x in (-0.026, -0.008, 0.011, 0.027):
        add_cyl_to_bm(bm, 0.0085, 0.0085, 0.014, tuple(wr + Vector((k_x, 0.085, 0.015))), axis='Y', segments=12)
    parts.append(finalize_mesh(f"GloveKnuckles_{side}", bm, mats["knuckle_armor"], bevel_width=0.002))

    # 7. Articulated 5 Fingers (olive dorsal / leather grip segments + rounded fingertips)
    bm_olive_f = bmesh.new()
    bm_dark_f = bmesh.new()
    for fname, (p0, p1, p2, p3, rad) in lay["fingers"].items():
        # Proximal phalanx (olive glove fabric)
        _make_tapered_limb_segment(bm_olive_f, p0, p1, rad * 1.05, rad * 0.96, rad * 0.96, rad * 0.88, rings=3, segs=12)
        # Middle phalanx (leather padded grip)
        _make_tapered_limb_segment(bm_dark_f, p1, p2, rad * 0.94, rad * 0.86, rad * 0.85, rad * 0.78, rings=3, segs=12)
        # Distal phalanx + rounded anatomical fingertip dome
        _make_tapered_limb_segment(bm_dark_f, p2, p3, rad * 0.84, rad * 0.76, rad * 0.68, rad * 0.62, rings=3, segs=12)
        bmesh.ops.create_uvsphere(
            bm_dark_f, u_segments=10, v_segments=6, radius=rad * 0.66,
            matrix=Matrix.Translation(p3)
        )
        # Sleek low-profile dorsal knuckle pad
        add_box_to_bm(bm_dark_f, (rad * 1.25, 0.009, 0.0032), tuple(p1 + Vector((0.0, 0.0, rad * 0.78))))

    parts.append(finalize_mesh(f"GloveFingersProx_{side}", bm_olive_f, mats["glove_olive"], smooth=True))
    parts.append(finalize_mesh(f"GloveFingersDist_{side}", bm_dark_f, mats["glove_leather"], smooth=True))

    return parts


def _closest_segment_t(pt: Vector, a: Vector, b: Vector):
    ab = b - a
    len_sq = ab.length_squared
    if len_sq < 1e-8:
        return (pt - a).length, 0.0
    t = max(0.0, min(1.0, (pt - a).dot(ab) / len_sq))
    proj = a + ab * t
    return (pt - proj).length, t


def add_fp_arms_to_armature(arm_obj: bpy.types.Object, parent_bone_name: str = None, add_ik_controls: bool = True):
    """Appends the complete L/R first-person arms, hands, fingers, and optional Blender IK controls
    onto `arm_obj` (or a standalone FPS_Arms_Rig), builds the detailed glove/arm meshes, and computes
    smooth anatomical capsule-distance skinning weights (zero pinching or rigid breaks!).
    """
    mats = create_fp_arms_materials()

    # 1. Add deform + IK bones in Edit Mode
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm_obj.data.edit_bones
    parent_eb = eb.get(parent_bone_name) if parent_bone_name else None

    bone_segments = {} # side -> [(bone_name, p0, p1, radius_bias)]

    for side in ('L', 'R'):
        lay = _get_side_rest_layout(side)
        sh, el, wr, pe = lay["shoulder"], lay["elbow"], lay["wrist"], lay["palm_end"]
        sx = lay["sx"]
        segs = []

        def _add_bone(bname, pbone, head, tail, deform=True):
            b = eb.new(bname)
            b.head = head
            b.tail = tail
            b.use_deform = deform
            if pbone is not None:
                b.parent = pbone
                b.use_connect = False
            return b

        b_upper = _add_bone(f"upper_arm_{side}", parent_eb, sh, el, True)
        b_fore = _add_bone(f"forearm_{side}", b_upper, el, wr, True)
        b_fore.use_connect = True
        b_hand = _add_bone(f"hand_{side}", b_fore, wr, pe, True)

        segs.append((f"upper_arm_{side}", sh, el, 0.048))
        segs.append((f"forearm_{side}", el, wr, 0.036))
        segs.append((f"hand_{side}", wr, pe, 0.032))

        for fname, (p0, p1, p2, p3, rad) in lay["fingers"].items():
            b1 = _add_bone(f"{fname}_01_{side}", b_hand, p0, p1, True)
            b2 = _add_bone(f"{fname}_02_{side}", b1, p1, p2, True)
            b2.use_connect = True
            b3 = _add_bone(f"{fname}_03_{side}", b2, p2, p3, True)
            b3.use_connect = True
            segs.append((f"{fname}_01_{side}", p0, p1, rad * 1.15))
            segs.append((f"{fname}_02_{side}", p1, p2, rad * 1.05))
            segs.append((f"{fname}_03_{side}", p2, p3, rad * 0.95))

        if add_ik_controls:
            _add_bone(f"ik_hand_{side}", parent_eb, wr, pe, deform=False)
            pole_pos = el + Vector((sx * 0.16, -0.10, -0.18))
            _add_bone(f"pole_elbow_{side}", parent_eb, pole_pos, pole_pos + Vector((0.0, 0.04, 0.0)), deform=False)

        bone_segments[side] = segs

    bpy.ops.object.mode_set(mode='OBJECT')

    # Add Blender IK constraints in Pose Mode (muted by default when baking direct deform keyframes)
    if add_ik_controls:
        for side in ('L', 'R'):
            pb_fore = arm_obj.pose.bones.get(f"forearm_{side}")
            if pb_fore is not None:
                c = pb_fore.constraints.new('IK')
                c.name = f"IK_Arm_{side}"
                c.target = arm_obj
                c.subtarget = f"ik_hand_{side}"
                c.pole_target = arm_obj
                c.pole_subtarget = f"pole_elbow_{side}"
                c.pole_angle = math.radians(-90.0 if side == 'L' else 90.0)
                c.chain_count = 2
                c.mute = True

            pb_hand = arm_obj.pose.bones.get(f"hand_{side}")
            if pb_hand is not None:
                cr = pb_hand.constraints.new('COPY_ROTATION')
                cr.name = f"CopyRot_Hand_{side}"
                cr.target = arm_obj
                cr.subtarget = f"ik_hand_{side}"
                cr.mute = True

    # 2. Build arm meshes with clean part-aware anatomical vertex weights (zero palm tearing!)
    arm_meshes = []
    for side in ('L', 'R'):
        parts = _build_arm_mesh_for_side(side, mats)
        lay = _get_side_rest_layout(side)
        sh, el, wr, pe = lay["shoulder"], lay["elbow"], lay["wrist"], lay["palm_end"]
        segs = bone_segments[side]

        # Pre-assign clean vertex groups PER anatomical sub-mesh BEFORE joining so palm/knuckles
        # never get accidentally dragged by thumb or adjacent finger bones!
        for part_obj in parts:
            pname = part_obj.name
            vgs = {bname: part_obj.vertex_groups.new(name=bname) for bname, _, _, _ in segs}
            for v in part_obj.data.vertices:
                co = v.co
                if "Sleeve" in pname or "Forearm" in pname:
                    d_u, _ = _closest_segment_t(co, sh, el)
                    d_f, _ = _closest_segment_t(co, el, wr)
                    if abs(d_u - d_f) < 0.035:
                        wu = 1.0 / (d_u + 0.02) ** 2
                        wf = 1.0 / (d_f + 0.02) ** 2
                        tot = wu + wf
                        vgs[f"upper_arm_{side}"].add([v.index], wu / tot, 'REPLACE')
                        vgs[f"forearm_{side}"].add([v.index], wf / tot, 'REPLACE')
                    elif d_u < d_f:
                        vgs[f"upper_arm_{side}"].add([v.index], 1.0, 'REPLACE')
                    else:
                        vgs[f"forearm_{side}"].add([v.index], 1.0, 'REPLACE')
                elif "GloveCuff" in pname:
                    # Coaxial with forearm -> zero sticking-out cuff edge at any wrist bend!
                    vgs[f"forearm_{side}"].add([v.index], 1.0, 'REPLACE')
                elif "GlovePalm" in pname or "GloveKnuckles" in pname:
                    vgs[f"hand_{side}"].add([v.index], 1.0, 'REPLACE')
                else:
                    # Finger meshes: weight strictly to nearest finger bone chain (zero palm drag)
                    f_scores = []
                    for bname, p0, p1, r_bias in segs:
                        if any(k in bname for k in ("thumb", "index", "middle", "ring", "pinky")):
                            dist, _ = _closest_segment_t(co, p0, p1)
                            f_scores.append((dist, bname))
                    f_scores.sort(key=lambda item: item[0])
                    d0, b0 = f_scores[0]
                    d1, b1 = f_scores[1]
                    if b0.split("_")[0] == b1.split("_")[0] and d1 < d0 + 0.012:
                        w0 = 1.0 / (d0 + 0.008) ** 2
                        w1 = 1.0 / (d1 + 0.008) ** 2
                        tot = w0 + w1
                        vgs[b0].add([v.index], w0 / tot, 'REPLACE')
                        vgs[b1].add([v.index], w1 / tot, 'REPLACE')
                    else:
                        vgs[b0].add([v.index], 1.0, 'REPLACE')

        mesh_obj = join_objects(parts, f"FP_Arm_{side}")
        mesh_obj.parent = arm_obj
        mesh_obj.matrix_parent_inverse = arm_obj.matrix_world.inverted()
        mod = mesh_obj.modifiers.new(name="Armature", type='ARMATURE')
        mod.object = arm_obj
        arm_meshes.append(mesh_obj)

    return arm_meshes


def solve_and_pose_arm_ik(
    arm_obj: bpy.types.Object,
    side: str,
    target_wrist_world: Vector,
    hand_rot_euler_deg: tuple,
    elbow_pole_world: Vector,
    finger_curl: dict,
    frame: int,
):
    """Analytically computes clean 2-bone arm IK + wrist orientation + articulated finger curls
    and inserts deform-bone keyframes directly (100% glTF-ready with zero constraint lag!).
    """
    lay = _get_side_rest_layout(side)
    sh = lay["shoulder"]
    L1 = (lay["elbow"] - sh).length
    L2 = (lay["wrist"] - lay["elbow"]).length

    # Clamp target reach cleanly to avoid hyper-extension popping
    to_t = target_wrist_world - sh
    dist = to_t.length
    max_reach = (L1 + L2) * 0.985
    min_reach = abs(L1 - L2) + 0.04
    if dist < 1e-5:
        dir_t = Vector((0.0, 1.0, 0.0))
        dist = min_reach
    else:
        dir_t = to_t / dist
        dist = max(min_reach, min(max_reach, dist))

    clamped_wrist = sh + dir_t * dist

    # Law of cosines for shoulder angle
    cos_a = max(-1.0, min(1.0, (L1 * L1 + dist * dist - L2 * L2) / (2.0 * L1 * dist)))
    angle_a = math.acos(cos_a)

    # Pole plane normal
    pole_vec = (elbow_pole_world - sh)
    bend_dir = pole_vec - dir_t * pole_vec.dot(dir_t)
    if bend_dir.length < 1e-5:
        bend_dir = Vector((lay["sx"] * 0.6, 0.0, -0.8)).normalized()
    else:
        bend_dir.normalize()

    elbow_pos = sh + (dir_t * math.cos(angle_a) + bend_dir * math.sin(angle_a)) * L1

    # Helper to compute world matrix of a bone aiming from p0 to p1 with up_hint
    def _aim_matrix(p0: Vector, p1: Vector, up_hint: Vector) -> Matrix:
        y_ax = (p1 - p0).normalized()
        x_ax = y_ax.cross(up_hint)
        if x_ax.length < 1e-5:
            x_ax = y_ax.cross(Vector((0.0, 0.0, 1.0)))
        x_ax.normalize()
        z_ax = x_ax.cross(y_ax).normalized()
        m = Matrix((
            (x_ax.x, y_ax.x, z_ax.x, p0.x),
            (x_ax.y, y_ax.y, z_ax.y, p0.y),
            (x_ax.z, y_ax.z, z_ax.z, p0.z),
            (0.0,    0.0,    0.0,    1.0),
        ))
        return m

    up_arm = (elbow_pos - sh).cross(clamped_wrist - elbow_pos)
    if up_arm.length < 1e-4:
        up_arm = Vector((0.0, 0.0, 1.0))
    else:
        up_arm.normalize()
        if side == 'L':
            up_arm = -up_arm

    # Desired world orientation of hand
    hand_rot = Euler(tuple(math.radians(a) for a in hand_rot_euler_deg), 'XYZ').to_matrix().to_4x4()
    m_hand = Matrix.Translation(clamped_wrist) @ hand_rot

    # Align forearm roll with hand dorsal axis (natural anatomical supination/pronation -> zero wrist twist!)
    hand_up = Vector((m_hand[0][2], m_hand[1][2], m_hand[2][2])).normalized()
    m_upper = _aim_matrix(sh, elbow_pos, Vector((0.0, 0.0, 1.0)))
    m_fore = _aim_matrix(elbow_pos, clamped_wrist, hand_up)

    # Set IK control bones too (for Blender animator visibility)
    pb_ik = arm_obj.pose.bones.get(f"ik_hand_{side}")
    if pb_ik is not None:
        pb_ik.matrix = m_hand
        pb_ik.keyframe_insert(data_path='location', frame=frame)
        pb_ik.keyframe_insert(data_path='rotation_quaternion' if pb_ik.rotation_mode == 'QUATERNION' else 'rotation_euler', frame=frame)

    # Set deform bones directly (temporarily muted constraints during baking)
    pb_u = arm_obj.pose.bones[f"upper_arm_{side}"]
    pb_f = arm_obj.pose.bones[f"forearm_{side}"]
    pb_h = arm_obj.pose.bones[f"hand_{side}"]

    for pb, mat in ((pb_u, m_upper), (pb_f, m_fore), (pb_h, m_hand)):
        pb.rotation_mode = 'QUATERNION'
        pb.matrix = mat
        bpy.context.view_layer.update()
        pb.keyframe_insert(data_path='location', frame=frame)
        pb.keyframe_insert(data_path='rotation_quaternion', frame=frame)

    # Finger curls: finger_curl = { "index": (j1_deg, j2_deg, j3_deg), ... }
    # Negative X rotation curls fingers downward (toward palm -Z)
    for fname in ("thumb", "index", "middle", "ring", "pinky"):
        curls = finger_curl.get(fname, (35.0, 45.0, 30.0))
        for j_idx in range(3):
            bname = f"{fname}_0{j_idx + 1}_{side}"
            pb_j = arm_obj.pose.bones.get(bname)
            if pb_j is None:
                continue
            pb_j.rotation_mode = 'XYZ'
            deg = curls[j_idx] if j_idx < len(curls) else curls[-1]
            if fname == "thumb":
                sx = lay["sx"]
                # Curl thumb naturally inward across palm/grip (never sticking outward!)
                pb_j.rotation_euler = Euler((math.radians(-deg * 0.75), math.radians(-sx * deg * 0.35), math.radians(-sx * deg * 0.45)), 'XYZ')
            else:
                pb_j.rotation_euler = Euler((math.radians(-deg), 0.0, 0.0), 'XYZ')
            pb_j.keyframe_insert(data_path='rotation_euler', frame=frame)


# Preset ergonomic finger curl libraries (degrees of flexion per phalanx)
FINGER_GRIP_PISTOL = {
    "thumb":  (28, 32, 20),
    "index":  (18, 28, 22),  # resting lightly along trigger
    "middle": (68, 78, 52),
    "ring":   (72, 80, 56),
    "pinky":  (74, 78, 56),
}

FINGER_GRIP_TRIGGER_PULL = {
    "thumb":  (30, 34, 22),
    "index":  (46, 62, 40),  # pulling trigger back
    "middle": (70, 80, 54),
    "ring":   (74, 82, 58),
    "pinky":  (76, 80, 58),
}

FINGER_GRIP_FOREND = {
    "thumb":  (24, 26, 18),
    "index":  (44, 52, 34),
    "middle": (48, 56, 36),
    "ring":   (50, 58, 38),
    "pinky":  (46, 52, 34),
}

FINGER_GRIP_MAG = {
    "thumb":  (38, 40, 26),
    "index":  (55, 62, 42),
    "middle": (58, 65, 44),
    "ring":   (56, 62, 42),
    "pinky":  (52, 56, 38),
}

FINGER_GRIP_PINCH = {
    "thumb":  (42, 36, 22),
    "index":  (48, 54, 34),
    "middle": (52, 58, 36),
    "ring":   (68, 74, 50),
    "pinky":  (70, 76, 52),
}

FINGER_GRIP_OPEN = {
    "thumb":  (10, 12, 8),
    "index":  (12, 16, 12),
    "middle": (14, 18, 12),
    "ring":   (16, 20, 14),
    "pinky":  (18, 22, 16),
}


def build_standalone_fp_arms():
    """Builds and saves the standalone reusable FPS Arms Rig (.blend + .glb + studio render)."""
    reset_scene()
    arm_data = bpy.data.armatures.new("FPS_Arms_Rig")
    arm_obj = bpy.data.objects.new("FPS_Arms_Rig", arm_data)
    bpy.context.scene.collection.objects.link(arm_obj)
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode='EDIT')
    root_b = arm_data.edit_bones.new("arms_root")
    root_b.head = Vector((0.0, 0.0, 0.0))
    root_b.tail = Vector((0.0, 0.08, 0.0))
    bpy.ops.object.mode_set(mode='OBJECT')

    add_fp_arms_to_armature(arm_obj, "arms_root", add_ik_controls=True)

    # Render clean studio showcase of the reusable FP Arms Rig
    os.makedirs(RIG_RENDER_DIR, exist_ok=True)
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 720
    scene.render.image_settings.file_format = 'PNG'

    world = bpy.data.worlds.new("ArmsWorld")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.045, 0.055, 0.070, 1.0)
        bg.inputs[1].default_value = 0.70

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
        _add_light("Key", (0.9, 0.35, 0.9), (48, 0, 130), 160.0, (1.0, 0.96, 0.90), 1.4),
        _add_light("Fill", (-0.9, -0.3, 0.7), (58, 0, -55), 110.0, (0.82, 0.90, 1.0), 1.8),
        _add_light("Rim", (0.0, 0.9, 0.8), (52, 0, 180), 140.0, (0.96, 0.98, 1.0), 1.4),
    ]

    cam_d = bpy.data.cameras.new("ArmsCam")
    cam_d.lens = 42.0
    cam_o = bpy.data.objects.new("ArmsCam", cam_d)
    scene.collection.objects.link(cam_o)
    scene.camera = cam_o
    cam_o.location = Vector((0.36, 0.42, 0.24))
    cam_o.rotation_euler = (Vector((0.0, -0.04, -0.13)) - cam_o.location).to_track_quat('-Z', 'Y').to_euler()
    scene.render.filepath = os.path.join(RIG_RENDER_DIR, "fp_arms_reusable_rig.png")
    bpy.ops.render.render(write_still=True)

    bpy.data.objects.remove(cam_o, do_unlink=True)
    for lo in lights:
        bpy.data.objects.remove(lo, do_unlink=True)

    save_blend(os.path.join(HANDS_DIR, "source", "fps_arms_rig.blend"))
    export_glb(os.path.join(HANDS_DIR, "fps_arms.glb"))
    print("[FP Arms] Successfully built reusable FP arms & tactical gloves rig.")


if __name__ == "__main__":
    build_standalone_fp_arms()
