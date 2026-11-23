"""Overhauled Hard-Surface AWP Precision Rifle Builder (.blend + hero/alt/exploded renders).
Features sculpted olive-drab Accuracy International thumbhole chassis, adjustable cheek rest,
fluted free-float steel barrel, machined muzzle brake, high-detail variable scope with knurled
turrets & scope rings, ergonomic bolt handle, bone-parented mounts & bone-skinned attachments.
"""

import math
import os
import sys
import bpy
import bmesh
from mathutils import Vector, Matrix

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
    add_fluted_barrel_y,
    add_lofted_sections_y,
    make_arch_ring,
    make_oval_ring,
    add_rounded_profile_x,
    add_picatinny_rail_y,
    join_objects,
    build_armature,
    bind_mesh_rigid_to_bone,
    add_bone_marker_empty,
    build_modular_attachments_for_weapon,
    save_blend,
    render_studio_views,
)

PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
OUT_DIR = os.path.join(PROJECT_ROOT, "assets", "weapons", "awp")
RENDER_DIR = os.path.join(PROJECT_ROOT, "portfolio_media", "models")


def build_awp():
    reset_scene()

    mat_olive = create_pbr_material("AWP_OliveChassis", (0.145, 0.215, 0.125), metallic=0.04, roughness=0.56, pattern='polymer', seed=201, normal_strength=0.18)
    mat_steel_matte = create_pbr_material("AWP_MatteSteel", (0.112, 0.118, 0.130), metallic=0.86, roughness=0.36, pattern='metal', seed=212, normal_strength=0.15)
    mat_bolt_steel = create_pbr_material("AWP_BoltSteel", (0.50, 0.52, 0.55), metallic=0.95, roughness=0.19, pattern='metal', seed=223, normal_strength=0.10)
    mat_rubber = create_pbr_material("AWP_RubberPad", (0.065, 0.068, 0.075), metallic=0.0, roughness=0.78, pattern='polymer', seed=234, normal_strength=0.20)
    mat_scope_lens = create_pbr_material("AWP_ScopeLens", (0.08, 0.25, 0.38), metallic=0.25, roughness=0.05, pattern='glass', seed=245, normal_strength=0.0, emission_color=(0.06, 0.22, 0.36), emission_strength=0.35)

    body_parts = []

    # 1. Sculpted Olive-Drab Accuracy International Thumbhole Chassis
    bm = bmesh.new()
    # Contoured forend chassis with chamfered lower bevels & sling-swivel nose
    add_lofted_sections_y(bm, [
        (0.005, make_arch_ring(0.044, -0.032, 0.022, 0.004, bevel=0.0055)),
        (0.240, make_arch_ring(0.043, -0.028, 0.021, 0.004, bevel=0.0055)),
        (0.415, make_arch_ring(0.038, -0.022, 0.019, 0.004, bevel=0.0050)),
        (0.432, make_arch_ring(0.032, -0.014, 0.016, 0.003, bevel=0.0045)),
    ])
    # Upper spine & buttstock body with smoothly arched thumbhole ceiling
    add_rounded_profile_x(bm, [
        (-0.322, 0.020), (0.016, 0.023), (0.016, -0.012),
        (-0.042, -0.012), (-0.072, -0.004), (-0.112, 0.001),
        (-0.152, -0.006), (-0.175, -0.022), (-0.184, -0.076), (-0.322, -0.076)
    ], width_x=0.040, chamfer_x=0.0055, chamfer_in=0.0030)
    # Smoothly curved lower thumbhole bridge & toe connecting flush into pistol grip
    add_rounded_profile_x(bm, [
        (-0.322, -0.056), (-0.172, -0.056), (-0.148, -0.074),
        (-0.118, -0.092), (-0.072, -0.092), (-0.056, -0.112),
        (-0.114, -0.116), (-0.156, -0.098), (-0.192, -0.076), (-0.322, -0.076)
    ], width_x=0.036, chamfer_x=0.0050, chamfer_in=0.0025)
    # Ergonomically contoured curved pistol grip (rounded oval loft, zero blocky step!)
    grip_rings = []
    for gy, gz, rx, ry_h in [
        (-0.042, -0.004, 0.0170, 0.022),
        (-0.048, -0.034, 0.0180, 0.023),
        (-0.058, -0.068, 0.0185, 0.024),
        (-0.070, -0.102, 0.0180, 0.025),
        (-0.074, -0.116, 0.0165, 0.023),
    ]:
        grip_rings.append([bm.verts.new((math.cos(s / 16.0 * math.tau) * rx, gy + math.sin(s / 16.0 * math.tau) * ry_h, gz)) for s in range(16)])
    for r_i in range(len(grip_rings) - 1):
        r0, r1 = grip_rings[r_i], grip_rings[r_i + 1]
        for s in range(16):
            ns = (s + 1) % 16
            bm.faces.new((r0[s], r0[ns], r1[ns], r1[s]))
    bm.faces.new(list(reversed(grip_rings[0])))
    bm.faces.new(grip_rings[-1])
    body_parts.append(finalize_mesh("AWP_Chassis", bm, mat_olive, bevel_width=0.0010, split_angle_deg=40.0))

    # Signature Accuracy International dark-steel chassis hex fasteners along olive side panels
    bm = bmesh.new()
    for by, bz in [(-0.275, -0.026), (-0.195, -0.026), (0.048, -0.004), (0.165, -0.002), (0.310, 0.000)]:
        add_cyl_to_bm(bm, 0.0040, 0.0040, 0.0445, (0.0, by, bz), axis='X', segments=10)
    body_parts.append(finalize_mesh("AWP_ChassisBolts", bm, mat_steel_matte, smooth=True))

    # 2. Ribbed Rubber Buttpad, Elevated Sculpted Cheek Rest & Trigger Guard
    bm = bmesh.new()
    # Spacer + contoured oval rubber buttpad
    add_lofted_sections_y(bm, [
        (-0.348, make_oval_ring(0.021, 0.056, -0.026, segs=18)),
        (-0.322, make_oval_ring(0.021, 0.056, -0.026, segs=18)),
    ])
    # Sculpted saddle cheek piece on twin vertical pillars
    add_lofted_sections_y(bm, [
        (-0.285, make_arch_ring(0.042, 0.020, 0.030, 0.012, bevel=0.004)),
        (-0.172, make_arch_ring(0.042, 0.020, 0.030, 0.012, bevel=0.004)),
    ])
    for py in (-0.255, -0.200):
        add_cyl_to_bm(bm, 0.005, 0.005, 0.018, (0.0, py, 0.018), axis='Z', segments=10)
    # Arched trigger guard
    add_rounded_profile_x(bm, [
        (-0.024, -0.022), (-0.018, -0.022), (-0.016, -0.052),
        (0.034, -0.052), (0.038, -0.022), (0.044, -0.022),
        (0.038, -0.058), (-0.020, -0.058)
    ], width_x=0.017, chamfer_x=0.0025, chamfer_in=0.001)
    body_parts.append(finalize_mesh("AWP_RubberAndGuard", bm, mat_rubber, bevel_width=0.0012, split_angle_deg=42.0))

    # 3. Chamfered Receiver Action, MIL-STD Picatinny Rail, Fluted Heavy Barrel & Machined Muzzle Brake
    bm = bmesh.new()
    add_lofted_sections_y(bm, [
        (-0.046, make_arch_ring(0.040, 0.012, 0.048, 0.008, bevel=0.0045)),
        (0.190,  make_arch_ring(0.040, 0.012, 0.048, 0.008, bevel=0.0045)),
        (0.202,  make_arch_ring(0.034, 0.016, 0.044, 0.006, bevel=0.0040)),
    ])
    add_picatinny_rail_y(bm, -0.024, 0.184, 0.055, width=0.021, height=0.009)
    # Genuine 8-flute precision free-float barrel!
    add_fluted_barrel_y(bm, 0.195, 0.775, 0.0142, offset_xz=(0.0, 0.034), flutes=8, flute_depth=0.0014, slices=14)
    # Barrel collar & multi-chamber machined tactical muzzle brake
    add_lathe_y(bm, [
        (0.768, 0.0155), (0.782, 0.0165), (0.848, 0.0165), (0.854, 0.0140), (0.856, 0.0095)
    ], offset=(0.0, 0.0, 0.034), segments=24)
    for bi in range(3):
        add_box_to_bm(bm, (0.035, 0.008, 0.024), (0.0, 0.794 + bi * 0.020, 0.034))
    body_parts.append(finalize_mesh("AWP_ActionAndBarrel", bm, mat_steel_matte, bevel_width=0.0010, split_angle_deg=36.0))

    mesh_body = join_objects(body_parts, "AWP_Body")

    # 4. RIGGED PART: High-Detail Variable Sniper Scope + Dual Rings + Knurled Turrets (bone: scope)
    scope_parts = []
    bm = bmesh.new()
    add_lathe_y(bm, [
        (-0.092, 0.0215), (-0.088, 0.0235), (-0.022, 0.0235), (-0.012, 0.0255), # Ocular + zoom ring
        (0.004,  0.0255), (0.012,  0.0165), (0.168,  0.0165),                   # Main 34mm tube
        (0.215,  0.0295), (0.296,  0.0305), (0.304,  0.0290), (0.304,  0.0250)  # Objective bell + lip
    ], offset=(0.0, 0.0, 0.098), segments=32)
    # Saddle housing + knurled tactical turrets (Elevation, Windage, Parallax)
    add_box_to_bm(bm, (0.038, 0.036, 0.038), (0.0, 0.084, 0.098))
    add_cyl_to_bm(bm, 0.0125, 0.0115, 0.022, (0.0, 0.084, 0.124), axis='Z', segments=20)
    add_cyl_to_bm(bm, 0.0110, 0.0102, 0.022, (0.024, 0.084, 0.098), axis='X', segments=20)
    add_cyl_to_bm(bm, 0.0100, 0.0095, 0.018, (-0.022, 0.084, 0.098), axis='X', segments=20)
    # Dual sculpted scope mount rings with rail clamp cross-bolts
    for ry in (0.028, 0.140):
        add_cyl_to_bm(bm, 0.0215, 0.0215, 0.022, (0.0, ry, 0.098), axis='Y', segments=24)
        add_box_to_bm(bm, (0.028, 0.022, 0.034), (0.0, ry, 0.074))
        add_cyl_to_bm(bm, 0.0045, 0.0045, 0.036, (0.0, ry, 0.066), axis='X', segments=10)
    scope_parts.append(finalize_mesh("AWP_ScopeBody", bm, mat_steel_matte, bevel_width=0.0010, split_angle_deg=38.0))

    bm_l = bmesh.new()
    add_cyl_to_bm(bm_l, 0.0255, 0.0255, 0.004, (0.0, 0.300, 0.098), axis='Y', segments=24)
    add_cyl_to_bm(bm_l, 0.0195, 0.0195, 0.004, (0.0, -0.090, 0.098), axis='Y', segments=24)
    scope_parts.append(finalize_mesh("AWP_ScopeLenses", bm_l, mat_scope_lens, smooth=True))
    mesh_scope = join_objects(scope_parts, "AWP_Scope")

    # 5. RIGGED PART: Fluted Steel Bolt Body & Rear Shroud (bone: bolt)
    bm = bmesh.new()
    add_cyl_to_bm(bm, 0.0112, 0.0112, 0.148, (0.0, 0.042, 0.034), axis='Y', segments=20)
    add_lofted_sections_y(bm, [
        (-0.046, make_arch_ring(0.024, 0.022, 0.042, 0.007, bevel=0.003)),
        (-0.020, make_arch_ring(0.024, 0.022, 0.042, 0.007, bevel=0.003)),
    ])
    mesh_bolt = finalize_mesh("AWP_Bolt", bm, mat_bolt_steel, bevel_width=0.0010, split_angle_deg=38.0)

    # 6. RIGGED PART: Swept Bolt Handle & Spherical Tactical Knob (bone: bolt_handle)
    bm = bmesh.new()
    add_cyl_to_bm(bm, 0.0052, 0.0046, 0.040, (0.025, -0.013, 0.028), axis='X', segments=14, rot_deg=(0.0, 22.0, -10.0))
    bmesh.ops.create_uvsphere(bm, u_segments=18, v_segments=12, radius=0.0115, matrix=Matrix.Translation(Vector((0.047, -0.019, 0.018))))
    mesh_bolt_handle = finalize_mesh("AWP_BoltHandle", bm, mat_bolt_steel, smooth=True)

    # 7. RIGGED PART: Detachable 10-Round Box Magazine with Baseplate (bone: magazine)
    bm = bmesh.new()
    add_lofted_sections_y(bm, [
        (0.064, make_arch_ring(0.028, -0.104, -0.012, 0.002, bevel=0.003)),
        (0.146, make_arch_ring(0.028, -0.104, -0.012, 0.002, bevel=0.003)),
    ])
    add_box_to_bm(bm, (0.033, 0.090, 0.010), (0.0, 0.105, -0.105))
    mesh_mag = finalize_mesh("AWP_Magazine", bm, mat_steel_matte, bevel_width=0.0014, split_angle_deg=36.0)

    # 8. RIGGED PART: Match Trigger (bone: trigger)
    bm = bmesh.new()
    add_rounded_profile_x(bm, [
        (0.010, -0.022), (0.016, -0.022), (0.011, -0.036), (0.008, -0.050), (0.002, -0.048)
    ], width_x=0.006, chamfer_x=0.0015, chamfer_in=0.001)
    mesh_trigger = finalize_mesh("AWP_Trigger", bm, mat_bolt_steel, smooth=True)

    # 9. RIGGED PART: Detailed Folding Tactical Bipod (bone: bipod)
    bm = bmesh.new()
    add_box_to_bm(bm, (0.036, 0.038, 0.022), (0.0, 0.395, -0.032))
    for side in (-1.0, 1.0):
        add_cyl_to_bm(bm, 0.0068, 0.0056, 0.195, (side * 0.023, 0.485, -0.040), axis='Y', segments=14, rot_deg=(-4.0, 0.0, side * 4.0))
        add_cyl_to_bm(bm, 0.0095, 0.0090, 0.018, (side * 0.029, 0.582, -0.046), axis='Y', segments=14)
    mesh_bipod = finalize_mesh("AWP_Bipod", bm, mat_steel_matte, bevel_width=0.0010, split_angle_deg=38.0)

    arm = build_armature("AWP_Rig", [
        ("weapon_root", None, (0.0, 0.0, 0.0), (0.0, 0.08, 0.0)),
        ("weapon_body", "weapon_root", (0.0, 0.0, 0.0), (0.0, 0.16, 0.0)),
        ("bolt", "weapon_body", (0.0, -0.012, 0.034), (0.0, 0.10, 0.034)),
        ("bolt_handle", "bolt", (0.0, -0.012, 0.034), (0.047, -0.019, 0.018)),
        ("magazine", "weapon_body", (0.0, 0.105, -0.015), (0.0, 0.105, -0.105)),
        ("trigger", "weapon_body", (0.0, 0.012, -0.022), (0.0, 0.006, -0.048)),
        ("scope", "weapon_body", (0.0, 0.08, 0.098), (0.0, 0.20, 0.098)),
        ("bipod", "weapon_body", (0.0, 0.395, -0.032), (0.0, 0.56, -0.045)),
    ])

    bind_mesh_rigid_to_bone(mesh_body, arm, "weapon_body")
    bind_mesh_rigid_to_bone(mesh_scope, arm, "scope")
    bind_mesh_rigid_to_bone(mesh_bolt, arm, "bolt")
    bind_mesh_rigid_to_bone(mesh_bolt_handle, arm, "bolt_handle")
    bind_mesh_rigid_to_bone(mesh_mag, arm, "magazine")
    bind_mesh_rigid_to_bone(mesh_trigger, arm, "trigger")
    bind_mesh_rigid_to_bone(mesh_bipod, arm, "bipod")

    # Bone-Skinned Modular Attachments (Piggyback Holo on Scope, Muzzle Comp, Mag Extension on magazine bone, Side Laser)
    build_modular_attachments_for_weapon(
        arm,
        optic_pos=(0.0, 0.140, 0.120),
        muzzle_pos=(0.0, 0.858, 0.034),
        mag_ext_pos=(0.0, 0.105, -0.128),
        laser_pos=(0.028, 0.355, 0.004),
        mag_bone_name="magazine",
    )

    add_bone_marker_empty("MuzzlePoint", (0.0, 0.860, 0.034), arm, "weapon_body")
    add_bone_marker_empty("EjectPoint", (0.028, 0.075, 0.040), arm, "weapon_body")
    add_bone_marker_empty("OpticMount", (0.0, 0.140, 0.120), arm, "weapon_body")
    add_bone_marker_empty("MuzzleMount", (0.0, 0.858, 0.034), arm, "weapon_body")
    add_bone_marker_empty("MagMount", (0.0, 0.105, -0.112), arm, "magazine")
    add_bone_marker_empty("LaserMount", (0.028, 0.355, 0.004), arm, "weapon_body")

    render_studio_views(
        "awp", RENDER_DIR, arm, center_y=0.22, hero_dist=1.34,
        explode_offsets={
            "scope": (0.0, 0.0, 0.11),
            "bolt": (0.0, -0.14, 0.04),
            "magazine": (0.0, 0.0, -0.13),
            "bipod": (0.0, 0.06, -0.10),
            "trigger": (0.0, 0.0, -0.05),
        },
    )
    save_blend(os.path.join(OUT_DIR, "source", "awp.blend"))
    print("[AWP Overhaul] Hard-surface model, bone mounts, attachments & renders complete.")


if __name__ == "__main__":
    build_awp()
