"""Builds, rigs, animates, renders, and exports the AWP Precision Rifle (.blend + .glb)."""

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
OUT_DIR = os.path.join(PROJECT_ROOT, "assets", "weapons", "awp")
RENDER_DIR = os.path.join(PROJECT_ROOT, "portfolio_media", "models")


def build_awp():
    reset_scene()

    # Materials
    mat_olive = create_pbr_material("AWP_OliveChassis", (0.19, 0.27, 0.16), metallic=0.04, roughness=0.58, pattern='polymer', seed=201)
    mat_steel_matte = create_pbr_material("AWP_MatteSteel", (0.11, 0.12, 0.13), metallic=0.86, roughness=0.40, pattern='metal', seed=212)
    mat_bolt_steel = create_pbr_material("AWP_BoltSteel", (0.42, 0.44, 0.47), metallic=0.94, roughness=0.22, pattern='metal', seed=223)
    mat_rubber = create_pbr_material("AWP_RubberPad", (0.06, 0.062, 0.068), metallic=0.0, roughness=0.82, pattern='polymer', seed=234)
    mat_scope_lens = create_pbr_material("AWP_ScopeLens", (0.08, 0.24, 0.36), metallic=0.25, roughness=0.06, pattern='glass', seed=245, emission_color=(0.06, 0.22, 0.34), emission_strength=0.35)

    body_parts = []

    # 1. Iconic Olive-Drab AWP Thumbhole Chassis (built around thumbhole opening!)
    bm = bmesh.new()
    # Forend chassis (Y: 0.02 to 0.42)
    add_extruded_profile_x(bm, [
        (0.02, 0.024), (0.42, 0.020), (0.41, -0.024), (0.02, -0.032)
    ], width_x=0.044)
    # Upper stock spine (above thumbhole, Y: -0.32 to +0.02)
    add_extruded_profile_x(bm, [
        (-0.32, 0.020), (0.02, 0.024), (0.02, -0.008), (-0.32, -0.012)
    ], width_x=0.040)
    # Lower stock bar (below thumbhole, Y: -0.32 to -0.065)
    add_extruded_profile_x(bm, [
        (-0.32, -0.072), (-0.19, -0.072), (-0.15, -0.105),
        (-0.075, -0.115), (-0.075, -0.095), (-0.16, -0.056), (-0.32, -0.056)
    ], width_x=0.036)
    # Rear stock vertical web (behind thumbhole)
    add_extruded_profile_x(bm, [
        (-0.32, 0.020), (-0.18, 0.018), (-0.18, -0.072), (-0.32, -0.072)
    ], width_x=0.038)
    # Pistol grip strut (front of thumbhole)
    add_extruded_profile_x(bm, [
        (-0.065, -0.004), (-0.024, -0.004),
        (-0.048, -0.115), (-0.088, -0.112)
    ], width_x=0.034)
    body_parts.append(finalize_mesh("AWP_Chassis", bm, mat_olive, bevel_width=0.0035))

    # 2. Black Rubber Buttpad & Cheek Rest
    bm = bmesh.new()
    add_box_to_bm(bm, (0.042, 0.026, 0.108), (0.0, -0.335, -0.024))
    # Adjustable cheek piece
    add_box_to_bm(bm, (0.043, 0.115, 0.024), (0.0, -0.225, 0.026))
    # Trigger guard
    add_box_to_bm(bm, (0.018, 0.062, 0.006), (0.0, 0.008, -0.058))
    add_box_to_bm(bm, (0.018, 0.007, 0.032), (0.0, 0.038, -0.042))
    add_box_to_bm(bm, (0.018, 0.007, 0.032), (0.0, -0.022, -0.042))
    body_parts.append(finalize_mesh("AWP_RubberAndGuard", bm, mat_rubber, bevel_width=0.0025))

    # 3. Heavy Receiver, Picatinny Rail, Fluted Free-Float Barrel & Tactical Muzzle Brake
    bm = bmesh.new()
    # Flat-sided AWP steel receiver action
    add_box_to_bm(bm, (0.040, 0.24, 0.042), (0.0, 0.075, 0.032))
    # Top Picatinny rail slots
    add_box_to_bm(bm, (0.022, 0.21, 0.010), (0.0, 0.078, 0.056))
    for i in range(10):
        add_box_to_bm(bm, (0.023, 0.008, 0.004), (0.0, -0.015 + i * 0.020, 0.062))
    # Heavy precision barrel lathe (Y: 0.19 to 0.78)
    add_lathe_y(bm, [
        (0.18, 0.0165), (0.28, 0.0148), (0.76, 0.0125), (0.78, 0.0125)
    ], offset=(0.0, 0.0, 0.034), segments=24)
    # Multi-port rectangular/cylindrical muzzle brake (Y: 0.78 to 0.85)
    add_box_to_bm(bm, (0.032, 0.068, 0.028), (0.0, 0.812, 0.034))
    for i in range(3):
        add_box_to_bm(bm, (0.035, 0.007, 0.016), (0.0, 0.792 + i * 0.020, 0.034))
    body_parts.append(finalize_mesh("AWP_ActionAndBarrel", bm, mat_steel_matte, bevel_width=0.0015))

    mesh_body = join_objects(body_parts, "AWP_Body")

    # 4. RIGGED PART: Variable Scope + Dual Rings + Lenses (bone: scope)
    scope_parts = []
    bm = bmesh.new()
    # Scope tube lathe (ocular bell -> main tube -> objective bell)
    add_lathe_y(bm, [
        (-0.085, 0.022), (-0.015, 0.022), (0.005, 0.0155),
        (0.165, 0.0155), (0.215, 0.029), (0.295, 0.029)
    ], offset=(0.0, 0.0, 0.096), segments=24)
    # Elevation & Windage Turrets
    add_cyl_to_bm(bm, 0.011, 0.011, 0.024, (0.0, 0.082, 0.118), axis='Z', segments=16)
    add_cyl_to_bm(bm, 0.010, 0.010, 0.024, (0.022, 0.082, 0.096), axis='X', segments=16)
    add_cyl_to_bm(bm, 0.009, 0.009, 0.020, (-0.020, 0.082, 0.096), axis='X', segments=16)
    # Dual Scope Mount Rings
    for ry in (0.030, 0.138):
        add_box_to_bm(bm, (0.032, 0.022, 0.044), (0.0, ry, 0.078))
    scope_parts.append(finalize_mesh("AWP_ScopeBody", bm, mat_steel_matte, bevel_width=0.0012))

    bm_l = bmesh.new()
    add_cyl_to_bm(bm_l, 0.025, 0.025, 0.004, (0.0, 0.294, 0.096), axis='Y', segments=20)
    add_cyl_to_bm(bm_l, 0.019, 0.019, 0.004, (0.0, -0.084, 0.096), axis='Y', segments=20)
    scope_parts.append(finalize_mesh("AWP_ScopeLenses", bm_l, mat_scope_lens))
    mesh_scope = join_objects(scope_parts, "AWP_Scope")

    # 5. RIGGED PART: Steel Bolt Body (bone: bolt)
    bm = bmesh.new()
    add_cyl_to_bm(bm, 0.011, 0.011, 0.145, (0.0, 0.042, 0.034), axis='Y', segments=16)
    # Rear bolt shroud
    add_box_to_bm(bm, (0.024, 0.026, 0.026), (0.0, -0.032, 0.034))
    mesh_bolt = finalize_mesh("AWP_Bolt", bm, mat_bolt_steel, bevel_width=0.0012)

    # 6. RIGGED PART: Bolt Handle + Spherical Knob (bone: bolt_handle, child of bolt!)
    bm = bmesh.new()
    add_box_to_bm(bm, (0.036, 0.010, 0.010), (0.024, -0.012, 0.028), rot_deg=(0.0, 22.0, -10.0))
    bmesh.ops.create_uvsphere(
        bm, u_segments=14, v_segments=10, radius=0.011,
        matrix=bpy.context.scene.cursor.matrix.Translation(Vector((0.045, -0.018, 0.018)))
    )
    mesh_bolt_handle = finalize_mesh("AWP_BoltHandle", bm, mat_bolt_steel, bevel_width=0.001)

    # 7. RIGGED PART: Detachable 10-Round Box Magazine (bone: magazine)
    bm = bmesh.new()
    add_box_to_bm(bm, (0.028, 0.082, 0.096), (0.0, 0.105, -0.056))
    add_box_to_bm(bm, (0.032, 0.088, 0.010), (0.0, 0.105, -0.104))
    mesh_mag = finalize_mesh("AWP_Magazine", bm, mat_steel_matte, bevel_width=0.0018)

    # 8. RIGGED PART: Match Trigger (bone: trigger)
    bm = bmesh.new()
    add_extruded_profile_x(bm, [
        (0.010, -0.022), (0.016, -0.022),
        (0.008, -0.049), (0.002, -0.047)
    ], width_x=0.006)
    mesh_trigger = finalize_mesh("AWP_Trigger", bm, mat_bolt_steel, bevel_width=0.0008)

    # 9. RIGGED PART: Folding Bipod (bone: bipod)
    bm = bmesh.new()
    add_box_to_bm(bm, (0.038, 0.036, 0.022), (0.0, 0.39, -0.032))
    for side in (-1.0, 1.0):
        add_cyl_to_bm(bm, 0.0065, 0.0055, 0.19, (side * 0.022, 0.48, -0.042), axis='Y', segments=12, rot_deg=(-4.0, 0.0, side * 4.0))
        add_cyl_to_bm(bm, 0.009, 0.009, 0.016, (side * 0.028, 0.575, -0.048), axis='Y', segments=12)
    mesh_bipod = finalize_mesh("AWP_Bipod", bm, mat_steel_matte, bevel_width=0.001)

    # Build Armature (bolt_handle is child of bolt for authentic lift + pull!)
    arm = build_armature("AWP_Rig", [
        ("weapon_root", None, (0.0, 0.0, 0.0), (0.0, 0.08, 0.0)),
        ("weapon_body", "weapon_root", (0.0, 0.0, 0.0), (0.0, 0.16, 0.0)),
        ("bolt", "weapon_body", (0.0, -0.012, 0.034), (0.0, 0.10, 0.034)),
        ("bolt_handle", "bolt", (0.0, -0.012, 0.034), (0.045, -0.018, 0.018)),
        ("magazine", "weapon_body", (0.0, 0.105, -0.015), (0.0, 0.105, -0.105)),
        ("trigger", "weapon_body", (0.0, 0.012, -0.022), (0.0, 0.006, -0.048)),
        ("scope", "weapon_body", (0.0, 0.08, 0.096), (0.0, 0.20, 0.096)),
        ("bipod", "weapon_body", (0.0, 0.39, -0.032), (0.0, 0.56, -0.045)),
    ])

    bind_mesh_rigid_to_bone(mesh_body, arm, "weapon_body")
    bind_mesh_rigid_to_bone(mesh_scope, arm, "scope")
    bind_mesh_rigid_to_bone(mesh_bolt, arm, "bolt")
    bind_mesh_rigid_to_bone(mesh_bolt_handle, arm, "bolt_handle")
    bind_mesh_rigid_to_bone(mesh_mag, arm, "magazine")
    bind_mesh_rigid_to_bone(mesh_trigger, arm, "trigger")
    bind_mesh_rigid_to_bone(mesh_bipod, arm, "bipod")

    # Markers for Godot
    add_marker_empty("MuzzlePoint", (0.0, 0.85, 0.034), arm)
    add_marker_empty("EjectPoint", (0.028, 0.075, 0.040), arm)
    add_marker_empty("OpticMount", (0.0, 0.082, 0.130), arm)
    add_marker_empty("MuzzleMount", (0.0, 0.85, 0.034), arm)
    add_marker_empty("MagMount", (0.0, 0.105, -0.115), arm)
    add_marker_empty("LaserMount", (0.026, 0.36, 0.005), arm)

    # Animations (30 fps)
    # 1. idle
    create_action_from_keyframes(arm, "idle", {
        "weapon_body": [
            (1, (0, 0, 0), (0, 0, 0)),
            (30, (0, 0, 0.0015), (0.2, 0, 0.1)),
            (60, (0, 0, 0), (0, 0, 0)),
        ],
    }, 60)

    # 2. fire (sharp sniper kick + authentic 4-stage bolt-action cycling: lift -> pull -> push -> lock!)
    create_action_from_keyframes(arm, "fire", {
        "weapon_body": [
            (1, (0, 0, 0), (0, 0, 0)),
            (3, (0, -0.042, 0.010), (5.5, 0, 0)),
            (8, (0, -0.008, 0.002), (1.0, 0, 0)),
            (14, (-0.006, 0.0, -0.004), (1.2, -3.5, 5.0)),
            (20, (0, 0, 0), (0, 0, 0)),
        ],
        "trigger": [(1, None, (0, 0, 0)), (2, None, (22, 0, 0)), (6, None, (0, 0, 0))],
        "bolt_handle": [
            (1, None, (0, 0, 0)),
            (7, None, (0, 0, 0)),
            (10, None, (0, -68, 0)),   # Lift bolt handle 68 deg up
            (16, None, (0, -68, 0)),   # Keep lifted while cycling
            (19, None, (0, 0, 0)),     # Lock handle back down
        ],
        "bolt": [
            (1, (0, 0, 0), None),
            (10, (0, 0, 0), None),
            (13, (0, -0.092, 0), None),  # Pull bolt straight back
            (16, (0, 0, 0), None),       # Push bolt straight forward
        ],
    }, 21)

    # 3. bolt_cycle (standalone 4-stage bolt action)
    create_action_from_keyframes(arm, "bolt_cycle", {
        "bolt_handle": [
            (1, None, (0, 0, 0)),
            (4, None, (0, -68, 0)),
            (11, None, (0, -68, 0)),
            (14, None, (0, 0, 0)),
        ],
        "bolt": [
            (1, (0, 0, 0), None),
            (4, (0, 0, 0), None),
            (8, (0, -0.092, 0), None),
            (11, (0, 0, 0), None),
        ],
    }, 15)

    # 4. reload (full sniper reload: ~2.0s = 60 frames: mag out -> mag in -> bolt cycle!)
    create_action_from_keyframes(arm, "reload", {
        "weapon_body": [
            (1, (0, 0, 0), (0, 0, 0)),
            (8, (-0.015, 0.01, -0.02), (6, -10, 14)),
            (40, (-0.015, 0.01, -0.02), (6, -10, 14)),
            (54, (-0.005, 0.0, -0.005), (2, -4, 6)),
            (60, (0, 0, 0), (0, 0, 0)),
        ],
        "magazine": [
            (1, (0, 0, 0), (0, 0, 0)),
            (10, (0, 0, 0), (0, 0, 0)),
            (18, (0, 0.0, -0.22), (0, 0, 0)),
            (26, (0, 0.0, -0.22), (0, 0, 0)),
            (36, (0, 0, 0), (0, 0, 0)),
        ],
        "bolt_handle": [
            (1, None, (0, 0, 0)),
            (41, None, (0, 0, 0)),
            (45, None, (0, -68, 0)),
            (53, None, (0, -68, 0)),
            (57, None, (0, 0, 0)),
        ],
        "bolt": [
            (1, (0, 0, 0), None),
            (45, (0, 0, 0), None),
            (49, (0, -0.092, 0), None),
            (53, (0, 0, 0), None),
        ],
    }, 60)

    # 5. reload_mag_out & 6. reload_mag_in
    create_action_from_keyframes(arm, "reload_mag_out", {
        "magazine": [(1, (0, 0, 0), None), (12, (0, 0, -0.22), None)],
    }, 12)

    create_action_from_keyframes(arm, "reload_mag_in", {
        "magazine": [(1, (0, 0, -0.22), None), (12, (0, 0, 0), None)],
    }, 12)

    # 7. equip & 8. unequip
    create_action_from_keyframes(arm, "equip", {
        "weapon_body": [
            (1, (0, -0.07, -0.22), (-36, 10, -10)),
            (9, (0, 0.006, 0.008), (2, 0, 0)),
            (13, (0, 0, 0), (0, 0, 0)),
        ],
    }, 13)

    create_action_from_keyframes(arm, "unequip", {
        "weapon_body": [
            (1, (0, 0, 0), (0, 0, 0)),
            (9, (0, -0.07, -0.22), (-36, 10, -10)),
        ],
    }, 9)

    # Render studio presentation images
    render_studio_views(
        "awp",
        RENDER_DIR,
        arm,
        center_y=0.22,
        hero_dist=1.22,
        explode_offsets={
            "scope": (0.0, 0.0, 0.11),
            "bolt": (0.0, -0.14, 0.04),
            "magazine": (0.0, 0.0, -0.13),
            "bipod": (0.0, 0.06, -0.10),
            "trigger": (0.0, 0.0, -0.05),
        },
    )

    save_blend(os.path.join(OUT_DIR, "awp.blend"))
    export_glb(os.path.join(OUT_DIR, "awp.glb"))
    print("[AWP] Successfully built, rigged, animated, rendered, and exported.")


if __name__ == "__main__":
    build_awp()
