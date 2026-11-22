"""Builds, rigs, animates, renders, and exports the AK-47 Assault Rifle (.blend + .glb)."""

import math
import os
import sys
import bpy
import bmesh
from mathutils import Vector

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from weapon_build_utils import (
    reset_scene,
    create_pbr_material,
    finalize_mesh,
    add_box_to_bm,
    add_cyl_to_bm,
    add_lathe_y,
    add_extruded_profile_x,
    join_objects,
    build_armature,
    bind_mesh_rigid_to_bone,
    add_marker_empty,
    create_action_from_keyframes,
    export_glb,
    save_blend,
    render_studio_views,
)

PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
OUT_DIR = os.path.join(PROJECT_ROOT, "assets", "weapons", "ak47")
RENDER_DIR = os.path.join(PROJECT_ROOT, "portfolio_media", "models")


def build_ak47():
    reset_scene()

    # Materials
    mat_steel_dark = create_pbr_material("AK_StampedSteel", (0.11, 0.12, 0.135), metallic=0.86, roughness=0.42, pattern='metal', seed=11)
    mat_steel_worn = create_pbr_material("AK_WornSteel", (0.20, 0.21, 0.23), metallic=0.90, roughness=0.32, pattern='metal', seed=22)
    mat_bolt_chrome = create_pbr_material("AK_BoltSteel", (0.48, 0.50, 0.53), metallic=0.94, roughness=0.24, pattern='metal', seed=33)
    mat_wood = create_pbr_material("AK_LaminatedWood", (0.42, 0.20, 0.085), metallic=0.0, roughness=0.44, pattern='wood', seed=44)
    mat_wood_grip = create_pbr_material("AK_WoodGrip", (0.34, 0.15, 0.065), metallic=0.0, roughness=0.52, pattern='wood', seed=55)
    mat_sight_glow = create_pbr_material("AK_SightDot", (0.15, 0.95, 0.42), metallic=0.0, roughness=0.25, pattern='solid', emission_color=(0.15, 0.95, 0.42), emission_strength=1.8)

    body_parts = []

    # 1. Stamped Steel Receiver (Y: -0.08 to +0.15, Z: -0.025 to +0.036)
    bm = bmesh.new()
    add_box_to_bm(bm, (0.038, 0.23, 0.056), (0.0, 0.035, 0.005))
    # Ribbed Dust Cover (rounded top)
    add_box_to_bm(bm, (0.034, 0.205, 0.024), (0.0, 0.028, 0.042))
    for i in range(4):
        add_box_to_bm(bm, (0.036, 0.012, 0.006), (0.0, -0.03 + i * 0.036, 0.054))
    # Rear trunnion & rivets
    for ry in (-0.06, -0.02, 0.11, 0.135):
        add_cyl_to_bm(bm, 0.0035, 0.0035, 0.041, (0.0, ry, -0.006), axis='X', segments=10)
    # Trigger guard
    add_box_to_bm(bm, (0.014, 0.062, 0.005), (0.0, 0.012, -0.056))
    add_box_to_bm(bm, (0.014, 0.006, 0.032), (0.0, 0.042, -0.041))
    add_box_to_bm(bm, (0.014, 0.006, 0.030), (0.0, -0.018, -0.041))
    # Rear tangent sight block
    add_box_to_bm(bm, (0.026, 0.052, 0.024), (0.0, 0.145, 0.052))
    add_box_to_bm(bm, (0.014, 0.038, 0.008), (0.0, 0.145, 0.066))
    body_parts.append(finalize_mesh("AK_Receiver", bm, mat_steel_dark, bevel_width=0.0025))

    # 2. Barrel, Gas Tube, Gas Block, Front Sight Tower, Cleaning Rod & Slant Muzzle
    bm = bmesh.new()
    # Main barrel lathe
    add_lathe_y(bm, [
        (0.14, 0.0115), (0.31, 0.0105), (0.38, 0.0098),
        (0.51, 0.0092), (0.545, 0.0092), (0.548, 0.0112), (0.585, 0.0102)
    ], offset=(0.0, 0.0, 0.020), segments=20)
    # Gas tube (upper)
    add_lathe_y(bm, [
        (0.15, 0.0095), (0.365, 0.0095)
    ], offset=(0.0, 0.0, 0.047), segments=16)
    # Angled Gas Block (connects barrel to gas tube)
    add_extruded_profile_x(bm, [
        (0.352, 0.010), (0.388, 0.010), (0.376, 0.056), (0.356, 0.056)
    ], width_x=0.022)
    # Underbarrel cleaning rod
    add_cyl_to_bm(bm, 0.0032, 0.0032, 0.36, (0.0, 0.32, 0.004), axis='Y', segments=10)
    # Hooded Front Sight Tower
    add_extruded_profile_x(bm, [
        (0.495, 0.012), (0.525, 0.012), (0.518, 0.068), (0.502, 0.068)
    ], width_x=0.018)
    # Protective ears on front sight
    add_box_to_bm(bm, (0.004, 0.018, 0.024), (-0.009, 0.510, 0.074))
    add_box_to_bm(bm, (0.004, 0.018, 0.024), (0.009, 0.510, 0.074))
    # Front sight post
    add_cyl_to_bm(bm, 0.0018, 0.0014, 0.018, (0.0, 0.510, 0.073), axis='Z', segments=8)
    # Handguard steel retainer rings
    add_box_to_bm(bm, (0.036, 0.014, 0.044), (0.0, 0.312, 0.026))
    body_parts.append(finalize_mesh("AK_BarrelAssembly", bm, mat_steel_worn, bevel_width=0.0012))

    # Glowing front sight tip (for crisp ADS sight picture)
    bm = bmesh.new()
    add_box_to_bm(bm, (0.0035, 0.004, 0.004), (0.0, 0.510, 0.082))
    body_parts.append(finalize_mesh("AK_FrontSightDot", bm, mat_sight_glow))

    # 3. Laminated Wood Buttstock + Steel Buttplate
    bm = bmesh.new()
    add_extruded_profile_x(bm, [
        (-0.078, 0.032), (-0.078, -0.018),
        (-0.315, -0.095), (-0.322, -0.090),
        (-0.315, 0.008), (-0.160, 0.024)
    ], width_x=0.034)
    body_parts.append(finalize_mesh("AK_WoodStock", bm, mat_wood, bevel_width=0.0045))

    bm = bmesh.new()
    add_extruded_profile_x(bm, [
        (-0.315, -0.095), (-0.328, -0.095),
        (-0.328, 0.008), (-0.315, 0.008)
    ], width_x=0.035)
    body_parts.append(finalize_mesh("AK_Buttplate", bm, mat_steel_dark, bevel_width=0.002))

    # 4. Wooden Upper & Lower Handguards
    bm = bmesh.new()
    # Lower handguard
    add_extruded_profile_x(bm, [
        (0.152, 0.024), (0.306, 0.024),
        (0.304, -0.006), (0.245, -0.014), (0.152, -0.012)
    ], width_x=0.042)
    # Upper handguard (around gas tube)
    add_cyl_to_bm(bm, 0.018, 0.017, 0.145, (0.0, 0.230, 0.046), axis='Y', segments=16)
    body_parts.append(finalize_mesh("AK_WoodHandguard", bm, mat_wood, bevel_width=0.003))

    # 5. Contoured Pistol Grip
    bm = bmesh.new()
    add_extruded_profile_x(bm, [
        (-0.046, -0.018), (-0.010, -0.018),
        (-0.036, -0.125), (-0.072, -0.118)
    ], width_x=0.030)
    body_parts.append(finalize_mesh("AK_PistolGrip", bm, mat_wood_grip, bevel_width=0.004))

    mesh_body = join_objects(body_parts, "AK47_Body")

    # 6. RIGGED PART: Curved 30-Round Banana Magazine (bone: magazine)
    bm = bmesh.new()
    segs = 8
    arc_pts = []
    for i in range(segs + 1):
        t = i / float(segs)
        ang = t * 0.56
        y_c = 0.095 + math.sin(ang) * 0.195 * 0.45 + t * 0.045
        z_c = 0.008 - math.cos(ang) * 0.014 - t * 0.210
        arc_pts.append((y_c, z_c, ang))

    # Build curved mag segments
    for i in range(segs):
        y0, z0, a0 = arc_pts[i]
        y1, z1, a1 = arc_pts[i + 1]
        ym = (y0 + y1) * 0.5
        zm = (z0 + z1) * 0.5
        seg_len = math.hypot(y1 - y0, z1 - z0) + 0.004
        pitch = math.degrees(math.atan2(y1 - y0, -(z1 - z0)))
        add_box_to_bm(bm, (0.026, 0.062, seg_len), (0.0, ym, zm), rot_deg=(pitch, 0.0, 0.0))
        # Stamped reinforcement ribs on sides
        if i in (2, 4, 6):
            add_box_to_bm(bm, (0.030, 0.056, 0.007), (0.0, ym, zm), rot_deg=(pitch, 0.0, 0.0))
    # Floorplate
    yf, zf, af = arc_pts[-1]
    add_box_to_bm(bm, (0.031, 0.070, 0.010), (0.0, yf + 0.003, zf - 0.004), rot_deg=(24.0, 0.0, 0.0))
    mesh_mag = finalize_mesh("AK47_Magazine", bm, mat_steel_dark, bevel_width=0.0018)

    # 7. RIGGED PART: Bolt Carrier & Charging Handle (bone: charging_handle)
    bm = bmesh.new()
    add_box_to_bm(bm, (0.012, 0.088, 0.020), (0.015, 0.058, 0.026))
    # Hooked right-side charging handle
    add_box_to_bm(bm, (0.028, 0.012, 0.011), (0.030, 0.088, 0.025))
    add_box_to_bm(bm, (0.009, 0.014, 0.016), (0.042, 0.086, 0.030), rot_deg=(0.0, 12.0, 0.0))
    mesh_bolt = finalize_mesh("AK47_ChargingHandle", bm, mat_bolt_chrome, bevel_width=0.0015)

    # 8. RIGGED PART: Trigger (bone: trigger)
    bm = bmesh.new()
    add_extruded_profile_x(bm, [
        (0.015, -0.020), (0.022, -0.020),
        (0.012, -0.046), (0.005, -0.044)
    ], width_x=0.006)
    mesh_trigger = finalize_mesh("AK47_Trigger", bm, mat_steel_worn, bevel_width=0.001)

    # 9. RIGGED PART: Fire Selector Lever (bone: selector)
    bm = bmesh.new()
    add_box_to_bm(bm, (0.004, 0.082, 0.012), (0.021, 0.015, 0.014), rot_deg=(-10.0, 0.0, 0.0))
    add_box_to_bm(bm, (0.010, 0.016, 0.010), (0.024, 0.052, 0.008))
    mesh_selector = finalize_mesh("AK47_FireSelector", bm, mat_steel_worn, bevel_width=0.001)

    # 10. RIGGED PART: Magazine Release Paddle (bone: mag_release)
    bm = bmesh.new()
    add_box_to_bm(bm, (0.014, 0.012, 0.026), (0.0, 0.052, -0.034), rot_deg=(12.0, 0.0, 0.0))
    mesh_mag_rel = finalize_mesh("AK47_MagRelease", bm, mat_steel_worn, bevel_width=0.001)

    # Build Armature
    arm = build_armature("AK47_Rig", [
        ("weapon_root", None, (0.0, 0.0, 0.0), (0.0, 0.08, 0.0)),
        ("weapon_body", "weapon_root", (0.0, 0.0, 0.0), (0.0, 0.16, 0.0)),
        ("magazine", "weapon_body", (0.0, 0.095, -0.025), (0.0, 0.12, -0.16)),
        ("charging_handle", "weapon_body", (0.02, 0.088, 0.026), (0.02, 0.14, 0.026)),
        ("trigger", "weapon_body", (0.0, 0.018, -0.020), (0.0, 0.012, -0.048)),
        ("selector", "weapon_body", (0.021, -0.024, 0.022), (0.021, 0.048, 0.010)),
        ("mag_release", "weapon_body", (0.0, 0.052, -0.022), (0.0, 0.052, -0.046)),
    ])

    bind_mesh_rigid_to_bone(mesh_body, arm, "weapon_body")
    bind_mesh_rigid_to_bone(mesh_mag, arm, "magazine")
    bind_mesh_rigid_to_bone(mesh_bolt, arm, "charging_handle")
    bind_mesh_rigid_to_bone(mesh_trigger, arm, "trigger")
    bind_mesh_rigid_to_bone(mesh_selector, arm, "selector")
    bind_mesh_rigid_to_bone(mesh_mag_rel, arm, "mag_release")

    # Helper Markers for Godot
    add_marker_empty("MuzzlePoint", (0.0, 0.59, 0.020), arm)
    add_marker_empty("EjectPoint", (0.032, 0.065, 0.030), arm)
    add_marker_empty("OpticMount", (0.0, 0.045, 0.058), arm)
    add_marker_empty("MuzzleMount", (0.0, 0.59, 0.020), arm)
    add_marker_empty("MagMount", (0.0, 0.115, -0.15), arm)
    add_marker_empty("LaserMount", (0.024, 0.25, 0.012), arm)

    # Animations (30 fps)
    # 1. idle
    create_action_from_keyframes(arm, "idle", {
        "weapon_body": [
            (1, (0, 0, 0), (0, 0, 0)),
            (30, (0, 0, 0.002), (0.3, 0, 0.2)),
            (60, (0, 0, 0), (0, 0, 0)),
        ],
    }, 60)

    # 2. fire (fast crisp bolt reciprocation + trigger pull + receiver kick)
    create_action_from_keyframes(arm, "fire", {
        "weapon_body": [
            (1, (0, 0, 0), (0, 0, 0)),
            (2, (0, -0.018, 0.004), (2.2, 0, 0)),
            (6, (0, 0, 0), (0, 0, 0)),
        ],
        "charging_handle": [
            (1, (0, 0, 0), None),
            (2, (0, -0.082, 0), None),
            (5, (0, 0, 0), None),
        ],
        "trigger": [
            (1, None, (0, 0, 0)),
            (2, None, (22, 0, 0)),
            (5, None, (0, 0, 0)),
        ],
    }, 7)

    # 3. reload (full coordinated AK tactical/empty reload: ~1.65s = 50 frames)
    create_action_from_keyframes(arm, "reload", {
        "weapon_body": [
            (1, (0, 0, 0), (0, 0, 0)),
            (8, (-0.02, 0.01, -0.02), (8, -14, 18)),
            (34, (-0.02, 0.01, -0.02), (10, -12, 16)),
            (42, (-0.01, 0.0, -0.01), (4, -8, 10)),
            (50, (0, 0, 0), (0, 0, 0)),
        ],
        "mag_release": [
            (1, None, (0, 0, 0)),
            (9, None, (0, 0, 0)),
            (11, None, (-22, 0, 0)),
            (15, None, (0, 0, 0)),
        ],
        "magazine": [
            (1, (0, 0, 0), (0, 0, 0)),
            (10, (0, 0, 0), (0, 0, 0)),
            (15, (0, 0.025, -0.045), (-22, 0, 0)),
            (21, (0, 0.04, -0.24), (-32, 0, 0)),
            (25, (0, 0.04, -0.24), (-32, 0, 0)),
            (31, (0, 0.02, -0.04), (-18, 0, 0)),
            (35, (0, 0, 0), (0, 0, 0)),
        ],
        "charging_handle": [
            (1, (0, 0, 0), None),
            (38, (0, 0, 0), None),
            (43, (0, -0.088, 0), None),
            (46, (0, 0, 0), None),
        ],
    }, 50)

    # 4. reload_mag_out
    create_action_from_keyframes(arm, "reload_mag_out", {
        "mag_release": [(1, None, (0, 0, 0)), (4, None, (-22, 0, 0)), (9, None, (0, 0, 0))],
        "magazine": [
            (1, (0, 0, 0), (0, 0, 0)),
            (6, (0, 0.025, -0.05), (-20, 0, 0)),
            (14, (0, 0.04, -0.24), (-32, 0, 0)),
        ],
    }, 15)

    # 5. reload_mag_in
    create_action_from_keyframes(arm, "reload_mag_in", {
        "magazine": [
            (1, (0, 0.04, -0.24), (-32, 0, 0)),
            (9, (0, 0.02, -0.04), (-18, 0, 0)),
            (14, (0, 0, 0), (0, 0, 0)),
        ],
        "charging_handle": [
            (1, (0, 0, 0), None),
            (15, (0, 0, 0), None),
            (20, (0, -0.088, 0), None),
            (23, (0, 0, 0), None),
        ],
    }, 24)

    # 6. equip & 7. unequip
    create_action_from_keyframes(arm, "equip", {
        "weapon_body": [
            (1, (0, -0.06, -0.18), (-34, 8, -10)),
            (7, (0, 0.005, 0.008), (2, 0, 0)),
            (11, (0, 0, 0), (0, 0, 0)),
        ],
    }, 11)

    create_action_from_keyframes(arm, "unequip", {
        "weapon_body": [
            (1, (0, 0, 0), (0, 0, 0)),
            (8, (0, -0.06, -0.18), (-34, 8, -10)),
        ],
    }, 8)

    # Render studio presentation images
    render_studio_views(
        "ak47",
        RENDER_DIR,
        arm,
        center_y=0.14,
        hero_dist=0.96,
        explode_offsets={
            "magazine": (0.0, 0.03, -0.14),
            "charging_handle": (0.10, 0.02, 0.04),
            "selector": (0.09, -0.02, -0.02),
            "trigger": (0.0, 0.0, -0.06),
            "mag_release": (0.0, 0.0, -0.05),
        },
    )

    save_blend(os.path.join(OUT_DIR, "ak47.blend"))
    export_glb(os.path.join(OUT_DIR, "ak47.glb"))
    print("[AK-47] Successfully built, rigged, animated, rendered, and exported.")


if __name__ == "__main__":
    build_ak47()
