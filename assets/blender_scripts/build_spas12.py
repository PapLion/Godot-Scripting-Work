"""Builds, rigs, animates, renders, and exports the SPAS-12 Shotgun (.blend + .glb)."""

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
OUT_DIR = os.path.join(PROJECT_ROOT, "assets", "weapons", "spas12")
RENDER_DIR = os.path.join(PROJECT_ROOT, "portfolio_media", "models")


def build_spas12():
    reset_scene()

    # Materials
    mat_parkerized = create_pbr_material("SPAS_ParkerizedSteel", (0.11, 0.115, 0.125), metallic=0.84, roughness=0.46, pattern='metal', seed=101)
    mat_shroud = create_pbr_material("SPAS_HeatshieldSteel", (0.14, 0.145, 0.16), metallic=0.88, roughness=0.38, pattern='metal', seed=112)
    mat_polymer = create_pbr_material("SPAS_TacticalPolymer", (0.075, 0.078, 0.084), metallic=0.04, roughness=0.68, pattern='polymer', seed=123)
    mat_chrome = create_pbr_material("SPAS_BoltChrome", (0.58, 0.60, 0.63), metallic=0.95, roughness=0.20, pattern='metal', seed=134)
    mat_shell_red = create_pbr_material("SPAS_ShellRed", (0.68, 0.09, 0.08), metallic=0.05, roughness=0.35, pattern='polymer', seed=145)
    mat_brass = create_pbr_material("SPAS_BrassRim", (0.78, 0.60, 0.22), metallic=0.92, roughness=0.25, pattern='metal', seed=156)
    mat_sight_glow = create_pbr_material("SPAS_SightDot", (0.15, 0.95, 0.42), metallic=0.0, roughness=0.25, pattern='solid', emission_color=(0.15, 0.95, 0.42), emission_strength=1.8)

    body_parts = []

    # 1. Distinctive SPAS-12 Curved Receiver (Y: -0.08 to +0.16)
    bm = bmesh.new()
    add_extruded_profile_x(bm, [
        (-0.085, 0.005), (-0.072, 0.042), (-0.030, 0.052),
        (0.165, 0.052), (0.165, -0.022), (-0.068, -0.022)
    ], width_x=0.044)
    # Trigger guard
    add_box_to_bm(bm, (0.018, 0.064, 0.006), (0.0, -0.010, -0.056))
    add_box_to_bm(bm, (0.018, 0.007, 0.036), (0.0, 0.022, -0.039))
    add_box_to_bm(bm, (0.018, 0.007, 0.034), (0.0, -0.042, -0.039))
    # Rear aperture sight
    add_box_to_bm(bm, (0.022, 0.016, 0.018), (0.0, -0.025, 0.060))
    body_parts.append(finalize_mesh("SPAS_Receiver", bm, mat_parkerized, bevel_width=0.003))

    # 2. Barrel & Full-Length Underbarrel Magazine Tube + Front Sight
    bm = bmesh.new()
    # Heavy 12-gauge barrel (upper)
    add_lathe_y(bm, [
        (0.16, 0.0145), (0.58, 0.0138), (0.635, 0.0142)
    ], offset=(0.0, 0.0, 0.032), segments=22)
    # Underbarrel tubular magazine (lower)
    add_lathe_y(bm, [
        (0.16, 0.0135), (0.57, 0.0135), (0.595, 0.0148), (0.610, 0.0125)
    ], offset=(0.0, 0.0, 0.001), segments=20)
    # Barrel/mag-tube clamp
    add_box_to_bm(bm, (0.032, 0.022, 0.056), (0.0, 0.54, 0.018))
    # Front ramp sight
    add_extruded_profile_x(bm, [
        (0.575, 0.044), (0.615, 0.044), (0.608, 0.068), (0.596, 0.068)
    ], width_x=0.008)
    body_parts.append(finalize_mesh("SPAS_Barrels", bm, mat_parkerized, bevel_width=0.001))

    # Glowing front sight dot
    bm = bmesh.new()
    add_box_to_bm(bm, (0.004, 0.005, 0.004), (0.0, 0.602, 0.070))
    body_parts.append(finalize_mesh("SPAS_SightDot", bm, mat_sight_glow))

    # 3. Iconic SPAS-12 Ventilated Heatshield / Barrel Shroud (slotted steel shroud!)
    bm = bmesh.new()
    # Top rail strip of shroud
    add_box_to_bm(bm, (0.034, 0.34, 0.008), (0.0, 0.335, 0.051))
    # Left & right shroud ribs creating distinctive ventilation slots
    for side in (-1.0, 1.0):
        x_s = side * 0.019
        add_box_to_bm(bm, (0.005, 0.34, 0.008), (x_s, 0.335, 0.048))
        add_box_to_bm(bm, (0.005, 0.34, 0.008), (x_s, 0.335, 0.024))
        for i in range(9):
            y_bar = 0.18 + i * 0.038
            add_box_to_bm(bm, (0.005, 0.014, 0.028), (x_s, y_bar, 0.036))
    body_parts.append(finalize_mesh("SPAS_Heatshield", bm, mat_shroud, bevel_width=0.001))

    # 4. Tactical Pistol Grip
    bm = bmesh.new()
    add_extruded_profile_x(bm, [
        (-0.082, -0.012), (-0.040, -0.016),
        (-0.066, -0.128), (-0.106, -0.120)
    ], width_x=0.034)
    body_parts.append(finalize_mesh("SPAS_PistolGrip", bm, mat_polymer, bevel_width=0.004))

    mesh_body = join_objects(body_parts, "SPAS12_Body")

    # 5. RIGGED PART: Ribbed SPAS-12 Pump / Forend (bone: pump)
    bm = bmesh.new()
    # Main blocky ergonomic forend body around underbarrel tube
    add_box_to_bm(bm, (0.050, 0.215, 0.048), (0.0, 0.355, 0.002))
    # Distinctive SPAS-12 vertical grip ribs along the forend
    for i in range(11):
        y_rib = 0.262 + i * 0.0185
        add_box_to_bm(bm, (0.055, 0.009, 0.052), (0.0, y_rib, 0.001))
    # Dual action bars connecting forend back into receiver
    for side in (-1.0, 1.0):
        add_box_to_bm(bm, (0.005, 0.14, 0.010), (side * 0.022, 0.20, 0.006))
    mesh_pump = finalize_mesh("SPAS12_PumpForend", bm, mat_polymer, bevel_width=0.002)

    # 6. RIGGED PART: Folding Skeletal Metal Stock (bone: stock)
    bm = bmesh.new()
    # Hinge block behind receiver
    add_box_to_bm(bm, (0.036, 0.028, 0.034), (0.0, -0.095, 0.022))
    # Upper & lower stamped struts
    add_box_to_bm(bm, (0.028, 0.23, 0.014), (0.0, -0.210, 0.014), rot_deg=(-4.0, 0.0, 0.0))
    add_box_to_bm(bm, (0.028, 0.22, 0.014), (0.0, -0.205, -0.044), rot_deg=(12.0, 0.0, 0.0))
    # Cross brace
    add_box_to_bm(bm, (0.026, 0.016, 0.068), (0.0, -0.245, -0.022))
    # Buttplate + iconic folding arm hook
    add_box_to_bm(bm, (0.036, 0.018, 0.115), (0.0, -0.320, -0.028))
    add_box_to_bm(bm, (0.014, 0.042, 0.012), (0.0, -0.305, -0.088))
    mesh_stock = finalize_mesh("SPAS12_FoldingStock", bm, mat_shroud, bevel_width=0.002)

    # 7. RIGGED PART: Bolt (bone: bolt)
    bm = bmesh.new()
    add_box_to_bm(bm, (0.014, 0.072, 0.020), (0.018, 0.065, 0.024))
    add_cyl_to_bm(bm, 0.004, 0.004, 0.020, (0.030, 0.082, 0.024), axis='X', segments=10)
    mesh_bolt = finalize_mesh("SPAS12_Bolt", bm, mat_chrome, bevel_width=0.0012)

    # 8. RIGGED PART: Bottom Loading Gate / Shell Lifter (bone: loading_gate)
    bm = bmesh.new()
    add_box_to_bm(bm, (0.022, 0.068, 0.005), (0.0, 0.062, -0.022))
    mesh_gate = finalize_mesh("SPAS12_LoadingGate", bm, mat_chrome, bevel_width=0.001)

    # 9. RIGGED PART: Trigger (bone: trigger)
    bm = bmesh.new()
    add_extruded_profile_x(bm, [
        (-0.008, -0.020), (-0.001, -0.020),
        (-0.012, -0.047), (-0.019, -0.044)
    ], width_x=0.007)
    mesh_trigger = finalize_mesh("SPAS12_Trigger", bm, mat_parkerized, bevel_width=0.001)

    # 10. RIGGED PART: 12-Gauge Shotgun Shell (bone: shell)
    bm_hull = bmesh.new()
    add_cyl_to_bm(bm_hull, 0.0095, 0.0095, 0.052, (0.0, 0.065, -0.010), axis='Y', segments=16)
    obj_hull = finalize_mesh("SPAS_ShellHull", bm_hull, mat_shell_red, bevel_width=0.001)
    bm_rim = bmesh.new()
    add_cyl_to_bm(bm_rim, 0.0102, 0.0102, 0.015, (0.0, 0.036, -0.010), axis='Y', segments=16)
    obj_rim = finalize_mesh("SPAS_ShellRim", bm_rim, mat_brass, bevel_width=0.001)
    mesh_shell = join_objects([obj_hull, obj_rim], "SPAS12_Shell")

    # Build Armature
    arm = build_armature("SPAS12_Rig", [
        ("weapon_root", None, (0.0, 0.0, 0.0), (0.0, 0.08, 0.0)),
        ("weapon_body", "weapon_root", (0.0, 0.0, 0.0), (0.0, 0.16, 0.0)),
        ("pump", "weapon_body", (0.0, 0.355, 0.002), (0.0, 0.45, 0.002)),
        ("bolt", "weapon_body", (0.018, 0.065, 0.024), (0.018, 0.12, 0.024)),
        ("loading_gate", "weapon_body", (0.0, 0.028, -0.022), (0.0, 0.095, -0.022)),
        ("trigger", "weapon_body", (0.0, -0.005, -0.020), (0.0, -0.012, -0.048)),
        ("stock", "weapon_body", (0.0, -0.095, 0.022), (0.0, -0.30, -0.02)),
        ("shell", "weapon_body", (0.0, 0.060, -0.010), (0.0, 0.10, -0.010)),
    ])

    bind_mesh_rigid_to_bone(mesh_body, arm, "weapon_body")
    bind_mesh_rigid_to_bone(mesh_pump, arm, "pump")
    bind_mesh_rigid_to_bone(mesh_bolt, arm, "bolt")
    bind_mesh_rigid_to_bone(mesh_gate, arm, "loading_gate")
    bind_mesh_rigid_to_bone(mesh_trigger, arm, "trigger")
    bind_mesh_rigid_to_bone(mesh_stock, arm, "stock")
    bind_mesh_rigid_to_bone(mesh_shell, arm, "shell")

    # Markers for Godot
    add_marker_empty("MuzzlePoint", (0.0, 0.64, 0.032), arm)
    add_marker_empty("EjectPoint", (0.034, 0.068, 0.028), arm)
    add_marker_empty("OpticMount", (0.0, 0.055, 0.056), arm)
    add_marker_empty("MuzzleMount", (0.0, 0.64, 0.032), arm)
    add_marker_empty("MagMount", (0.0, 0.60, 0.001), arm)
    add_marker_empty("LaserMount", (0.026, 0.48, 0.005), arm)

    # Animations (30 fps)
    # 1. idle (hide shell scaled to 0 inside receiver)
    create_action_from_keyframes(arm, "idle", {
        "weapon_body": [
            (1, (0, 0, 0), (0, 0, 0)),
            (30, (0, 0, 0.002), (0.3, 0, 0.15)),
            (60, (0, 0, 0), (0, 0, 0)),
        ],
        "shell": [(1, (0, 0, 0), None, (0.001, 0.001, 0.001))],
    }, 60)

    # 2. fire (kick + trigger + pump/bolt cycle)
    create_action_from_keyframes(arm, "fire", {
        "weapon_body": [
            (1, (0, 0, 0), (0, 0, 0)),
            (3, (0, -0.045, 0.012), (6.5, 0, 0)),
            (9, (0, -0.010, 0.003), (1.5, 0, 0)),
            (18, (0, 0, 0), (0, 0, 0)),
        ],
        "trigger": [(1, None, (0, 0, 0)), (2, None, (24, 0, 0)), (6, None, (0, 0, 0))],
        "pump": [
            (1, (0, 0, 0), None),
            (7, (0, 0, 0), None),
            (11, (0, -0.088, 0), None),
            (16, (0, 0, 0), None),
        ],
        "bolt": [
            (1, (0, 0, 0), None),
            (7, (0, 0, 0), None),
            (11, (0, -0.075, 0), None),
            (16, (0, 0, 0), None),
        ],
        "shell": [(1, (0, 0, 0), None, (0.001, 0.001, 0.001))],
    }, 18)

    # 3. shell_start (0.30s = 9 frames: tilt shotgun to expose bottom loading port)
    create_action_from_keyframes(arm, "shell_start", {
        "weapon_body": [
            (1, (0, 0, 0), (0, 0, 0)),
            (9, (-0.015, 0.01, -0.025), (14, -12, 34)),
        ],
        "shell": [(1, (0, 0, 0), None, (0.001, 0.001, 0.001))],
    }, 9)

    # 4. shell_insert (0.38s = 12 frames: red shell visibly slides up into loading gate!)
    create_action_from_keyframes(arm, "shell_insert", {
        "weapon_body": [
            (1, (-0.015, 0.01, -0.025), (14, -12, 34)),
            (6, (-0.015, 0.01, -0.018), (16, -12, 34)),
            (12, (-0.015, 0.01, -0.025), (14, -12, 34)),
        ],
        "loading_gate": [
            (1, None, (0, 0, 0)),
            (5, None, (28, 0, 0)),
            (9, None, (32, 0, 0)),
            (12, None, (0, 0, 0)),
        ],
        "shell": [
            (1, (0, -0.04, -0.14), (20, 0, 0), (1, 1, 1)),
            (5, (0, -0.01, -0.035), (12, 0, 0), (1, 1, 1)),
            (9, (0, 0.035, 0.0), (0, 0, 0), (1, 1, 1)),
            (11, (0, 0.055, 0.005), (0, 0, 0), (0.001, 0.001, 0.001)),
        ],
    }, 12)

    # 5. shell_end (0.28s = 9 frames: return level + brisk pump cycle)
    create_action_from_keyframes(arm, "shell_end", {
        "weapon_body": [
            (1, (-0.015, 0.01, -0.025), (14, -12, 34)),
            (9, (0, 0, 0), (0, 0, 0)),
        ],
        "pump": [
            (1, (0, 0, 0), None),
            (4, (0, -0.082, 0), None),
            (8, (0, 0, 0), None),
        ],
        "bolt": [
            (1, (0, 0, 0), None),
            (4, (0, -0.072, 0), None),
            (8, (0, 0, 0), None),
        ],
        "shell": [(1, (0, 0, 0), None, (0.001, 0.001, 0.001))],
    }, 9)

    # 6. reload_interrupt (fast snap back to firing posture)
    create_action_from_keyframes(arm, "reload_interrupt", {
        "weapon_body": [
            (1, (-0.015, 0.01, -0.025), (14, -12, 34)),
            (5, (0, 0, 0), (0, 0, 0)),
        ],
        "loading_gate": [(1, None, (0, 0, 0))],
        "shell": [(1, (0, 0, 0), None, (0.001, 0.001, 0.001))],
    }, 5)

    # 7. equip & 8. unequip
    create_action_from_keyframes(arm, "equip", {
        "weapon_body": [
            (1, (0, -0.06, -0.20), (-36, 10, -10)),
            (8, (0, 0.006, 0.008), (2, 0, 0)),
            (12, (0, 0, 0), (0, 0, 0)),
        ],
        "shell": [(1, (0, 0, 0), None, (0.001, 0.001, 0.001))],
    }, 12)

    create_action_from_keyframes(arm, "unequip", {
        "weapon_body": [
            (1, (0, 0, 0), (0, 0, 0)),
            (8, (0, -0.06, -0.20), (-36, 10, -10)),
        ],
        "shell": [(1, (0, 0, 0), None, (0.001, 0.001, 0.001))],
    }, 8)

    # Render studio presentation images (show shell visibly for exploded rig view!)
    render_studio_views(
        "spas12",
        RENDER_DIR,
        arm,
        center_y=0.16,
        hero_dist=1.02,
        explode_offsets={
            "pump": (0.0, 0.06, -0.075),
            "bolt": (0.10, 0.02, 0.03),
            "loading_gate": (0.0, 0.0, -0.07),
            "shell": (0.0, -0.02, -0.12),
            "trigger": (0.0, 0.0, -0.06),
            "stock": (0.0, -0.10, 0.02),
        },
    )

    save_blend(os.path.join(OUT_DIR, "spas12.blend"))
    export_glb(os.path.join(OUT_DIR, "spas12.glb"))
    print("[SPAS-12] Successfully built, rigged, animated, rendered, and exported.")


if __name__ == "__main__":
    build_spas12()
