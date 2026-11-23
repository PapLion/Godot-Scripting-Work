"""Overhauled Hard-Surface AK-47 Assault Rifle Builder (.blend + hero/alt/exploded renders).
Features sculpted vaulted dust cover, palm-swell laminated walnut furniture, lofted curved
ribbed steel magazine, multi-step barrel/gas assembly, bone-parented mount markers, and
bone-skinned modular hard-surface attachments.
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
    add_lathe_y,
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
OUT_DIR = os.path.join(PROJECT_ROOT, "assets", "weapons", "ak47")
RENDER_DIR = os.path.join(PROJECT_ROOT, "portfolio_media", "models")


def build_ak47():
    reset_scene()

    # 512px Albedo + Roughness + Normal PBR materials
    mat_steel_dark = create_pbr_material("AK_StampedSteel", (0.115, 0.122, 0.136), metallic=0.86, roughness=0.38, pattern='metal', seed=11, normal_strength=0.16)
    mat_steel_worn = create_pbr_material("AK_WornSteel", (0.195, 0.205, 0.222), metallic=0.90, roughness=0.30, pattern='metal', seed=22, normal_strength=0.18)
    mat_bolt_chrome = create_pbr_material("AK_BoltSteel", (0.52, 0.54, 0.57), metallic=0.95, roughness=0.20, pattern='metal', seed=33, normal_strength=0.12)
    mat_wood = create_pbr_material("AK_LaminatedWood", (0.40, 0.175, 0.072), metallic=0.0, roughness=0.44, pattern='wood', seed=44, normal_strength=0.24)
    mat_wood_grip = create_pbr_material("AK_WoodGrip", (0.30, 0.132, 0.058), metallic=0.0, roughness=0.52, pattern='wood', seed=55, normal_strength=0.26)
    mat_sight_glow = create_pbr_material("AK_SightDot", (0.14, 0.96, 0.44), metallic=0.0, roughness=0.20, pattern='solid', emission_color=(0.14, 0.96, 0.44), emission_strength=2.2)

    body_parts = []

    # 1. Stamped Steel Receiver + Vaulted Rounded Dust Cover + Side Optics Rail + Rear Sight
    bm = bmesh.new()
    # Chamfered lower stamped receiver body (Y: -0.082 to +0.155)
    add_lofted_sections_y(bm, [
        (-0.082, make_arch_ring(0.036, -0.022, 0.030, 0.004, bevel=0.0035)),
        (-0.065, make_arch_ring(0.038, -0.024, 0.032, 0.004, bevel=0.0035)),
        (0.140,  make_arch_ring(0.038, -0.024, 0.032, 0.004, bevel=0.0035)),
        (0.156,  make_arch_ring(0.035, -0.020, 0.030, 0.004, bevel=0.0035)),
    ])
    # Vaulted rounded stamped-steel dust cover with authentic smooth arch & stamped cross-ribs
    dust_sections = [
        (-0.076, make_arch_ring(0.032, 0.028, 0.036, 0.015, bevel=0.003)),
        (-0.064, make_arch_ring(0.035, 0.029, 0.039, 0.021, bevel=0.003)),
        (-0.028, make_arch_ring(0.035, 0.029, 0.039, 0.021, bevel=0.003)),
        (-0.022, make_arch_ring(0.0365, 0.029, 0.041, 0.0225, bevel=0.003)),  # Rib 1
        (-0.014, make_arch_ring(0.035, 0.029, 0.039, 0.021, bevel=0.003)),
        (0.014,  make_arch_ring(0.035, 0.029, 0.039, 0.021, bevel=0.003)),
        (0.020,  make_arch_ring(0.0365, 0.029, 0.041, 0.0225, bevel=0.003)),  # Rib 2
        (0.028,  make_arch_ring(0.035, 0.029, 0.039, 0.021, bevel=0.003)),
        (0.056,  make_arch_ring(0.035, 0.029, 0.039, 0.021, bevel=0.003)),
        (0.062,  make_arch_ring(0.0365, 0.029, 0.041, 0.0225, bevel=0.003)),  # Rib 3
        (0.070,  make_arch_ring(0.035, 0.029, 0.039, 0.021, bevel=0.003)),
        (0.118,  make_arch_ring(0.034, 0.029, 0.038, 0.019, bevel=0.003)),
        (0.128,  make_arch_ring(0.031, 0.029, 0.035, 0.013, bevel=0.003)),
    ]
    add_lofted_sections_y(bm, dust_sections)

    # Low-profile top dust-cover optics rail (for Holo Reflex mounting)
    add_picatinny_rail_y(bm, -0.025, 0.105, 0.058, width=0.020, height=0.007)

    # Left-side AK dovetail rail plate + stamped rivets
    add_box_to_bm(bm, (0.005, 0.105, 0.020), (-0.021, 0.015, 0.006))
    for ry in (-0.064, -0.024, 0.088, 0.118, 0.142):
        add_cyl_to_bm(bm, 0.0032, 0.0032, 0.041, (0.0, ry, -0.008), axis='X', segments=10)

    # Rounded rear tangent sight block + U-notch sight leaf
    add_lofted_sections_y(bm, [
        (0.124, make_arch_ring(0.027, 0.028, 0.056, 0.008, bevel=0.0025)),
        (0.172, make_arch_ring(0.025, 0.028, 0.054, 0.007, bevel=0.0025)),
        (0.180, make_arch_ring(0.022, 0.028, 0.048, 0.005, bevel=0.0025)),
    ])
    # Side sight-leaf ears creating genuine center notch
    add_box_to_bm(bm, (0.006, 0.036, 0.010), (-0.008, 0.148, 0.066))
    add_box_to_bm(bm, (0.006, 0.036, 0.010), (0.008, 0.148, 0.066))

    # Contoured arched trigger guard
    add_rounded_profile_x(bm, [
        (-0.020, -0.022), (-0.014, -0.022), (-0.012, -0.050),
        (0.036, -0.050), (0.040, -0.022), (0.046, -0.022),
        (0.042, -0.056), (-0.018, -0.056)
    ], width_x=0.013, chamfer_x=0.002, chamfer_in=0.001)

    body_parts.append(finalize_mesh("AK_Receiver", bm, mat_steel_dark, bevel_width=0.0014, split_angle_deg=36.0))

    # 2. Detailed Barrel, Gas Tube, Angled Gas Block, Front Sight Hood & Slant Muzzle Brake
    bm = bmesh.new()
    add_lathe_y(bm, [
        (0.145, 0.0122), (0.185, 0.0112), (0.310, 0.0104),
        (0.375, 0.0098), (0.505, 0.0092), (0.542, 0.0092),
        (0.546, 0.0115), (0.562, 0.0115), (0.588, 0.0100), (0.590, 0.0072)
    ], offset=(0.0, 0.0, 0.020), segments=28)
    # Recessed dark bore cavity lip
    add_lathe_y(bm, [(0.155, 0.0095), (0.365, 0.0095)], offset=(0.0, 0.0, 0.047), segments=20)
    # Sculpted angled AK gas block with rounded top + bayonet lug
    add_rounded_profile_x(bm, [
        (0.350, 0.006), (0.388, 0.006), (0.382, 0.032),
        (0.375, 0.057), (0.354, 0.057), (0.350, 0.032)
    ], width_x=0.022, chamfer_x=0.0035, chamfer_in=0.002)
    # Cleaning rod + underbarrel ferrule ring
    add_cyl_to_bm(bm, 0.0030, 0.0030, 0.365, (0.0, 0.325, 0.004), axis='Y', segments=12)
    # Handguard steel retainer ferrules (front & rear)
    add_lofted_sections_y(bm, [
        (0.305, make_arch_ring(0.035, -0.008, 0.048, 0.010, bevel=0.003)),
        (0.319, make_arch_ring(0.034, -0.008, 0.048, 0.010, bevel=0.003)),
    ])
    # Sculpted Hooded Front Sight Base + curved protective ears + front sight post
    add_rounded_profile_x(bm, [
        (0.492, 0.008), (0.526, 0.008), (0.520, 0.068), (0.502, 0.068)
    ], width_x=0.018, chamfer_x=0.003, chamfer_in=0.0015)
    add_box_to_bm(bm, (0.0038, 0.018, 0.024), (-0.0088, 0.510, 0.075), rot_deg=(0.0, -6.0, 0.0))
    add_box_to_bm(bm, (0.0038, 0.018, 0.024), (0.0088, 0.510, 0.075), rot_deg=(0.0, 6.0, 0.0))
    add_cyl_to_bm(bm, 0.0018, 0.0014, 0.018, (0.0, 0.510, 0.073), axis='Z', segments=10)
    body_parts.append(finalize_mesh("AK_BarrelAssembly", bm, mat_steel_worn, bevel_width=0.0010, split_angle_deg=38.0))

    # Glowing tritium front sight tip
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=6, radius=0.0022, matrix=Matrix.Translation(Vector((0.0, 0.510, 0.082))))
    body_parts.append(finalize_mesh("AK_FrontSightDot", bm, mat_sight_glow, smooth=True))

    # 3. Sculpted Contoured Laminated Walnut Buttstock (smooth multi-station loft, NO plank!)
    bm = bmesh.new()
    add_lofted_sections_y(bm, [
        (-0.316, make_oval_ring(0.019, 0.056, -0.044, segs=18)),
        (-0.270, make_oval_ring(0.0185, 0.048, -0.036, segs=18)),
        (-0.200, make_oval_ring(0.0175, 0.038, -0.023, segs=18)),
        (-0.130, make_oval_ring(0.0165, 0.030, -0.010, segs=18)),
        (-0.078, make_oval_ring(0.0175, 0.026,  0.004, segs=18)),
    ])
    body_parts.append(finalize_mesh("AK_WoodStock", bm, mat_wood, smooth=True, split_angle_deg=55.0, uv_scale=2.6))

    # Contoured steel buttplate + sling swivel loop
    bm = bmesh.new()
    add_lofted_sections_y(bm, [
        (-0.326, make_oval_ring(0.0195, 0.057, -0.044, segs=18)),
        (-0.315, make_oval_ring(0.0195, 0.057, -0.044, segs=18)),
    ])
    body_parts.append(finalize_mesh("AK_Buttplate", bm, mat_steel_dark, bevel_width=0.0015))

    # 4. Sculpted Palm-Swell Wooden Handguards (Lower & Upper)
    bm = bmesh.new()
    # Lower handguard with genuine ergonomic AKM palm swell!
    add_lofted_sections_y(bm, [
        (0.154, make_oval_ring(0.019, 0.019, 0.006, segs=16, flat_top=0.85)),
        (0.185, make_oval_ring(0.023, 0.021, 0.005, segs=16, flat_top=0.85)),
        (0.230, make_oval_ring(0.024, 0.021, 0.006, segs=16, flat_top=0.85)),
        (0.275, make_oval_ring(0.021, 0.019, 0.007, segs=16, flat_top=0.85)),
        (0.305, make_oval_ring(0.018, 0.017, 0.009, segs=16, flat_top=0.85)),
    ])
    # Upper wooden gas-tube handguard (smoothly rounded sleeve)
    add_lofted_sections_y(bm, [
        (0.160, make_oval_ring(0.0165, 0.0155, 0.047, segs=16)),
        (0.195, make_oval_ring(0.0185, 0.0175, 0.047, segs=16)),
        (0.265, make_oval_ring(0.0180, 0.0170, 0.047, segs=16)),
        (0.302, make_oval_ring(0.0155, 0.0145, 0.047, segs=16)),
    ])
    body_parts.append(finalize_mesh("AK_WoodHandguard", bm, mat_wood, smooth=True, split_angle_deg=55.0, uv_scale=3.0))

    # 5. Sculpted Contoured Pistol Grip (multi-station lofted ergonomic oval!)
    bm = bmesh.new()
    grip_rings = []
    for idx, (gy, gz, rx, ry_half) in enumerate([
        (-0.028, -0.018, 0.0145, 0.020),
        (-0.036, -0.048, 0.0155, 0.021),
        (-0.046, -0.082, 0.0160, 0.022),
        (-0.056, -0.118, 0.0155, 0.023),
        (-0.058, -0.128, 0.0140, 0.021),
    ]):
        ring = []
        for s in range(16):
            a = (s / 16.0) * math.tau
            ring.append(bm.verts.new((math.cos(a) * rx, gy + math.sin(a) * ry_half, gz)))
        grip_rings.append(ring)
    for r_i in range(len(grip_rings) - 1):
        r0, r1 = grip_rings[r_i], grip_rings[r_i + 1]
        for s in range(16):
            ns = (s + 1) % 16
            bm.faces.new((r0[s], r0[ns], r1[ns], r1[s]))
    bm.faces.new(list(reversed(grip_rings[0])))
    bm.faces.new(grip_rings[-1])
    body_parts.append(finalize_mesh("AK_PistolGrip", bm, mat_wood_grip, smooth=True, split_angle_deg=55.0, uv_scale=3.5))

    mesh_body = join_objects(body_parts, "AK47_Body")

    # 6. RIGGED PART: Smooth Lofted Curved 30-Round AK Banana Magazine (bone: magazine)
    bm = bmesh.new()
    mag_rings = []
    segs_m = 14
    for i in range(segs_m + 1):
        t = i / float(segs_m)
        # Authentic progressive AK-47 curved banana arc
        yc = 0.096 + 0.040 * t + 0.072 * (t ** 1.75)
        zc = -0.008 - 0.222 * t + 0.016 * (t ** 2.0)
        # Cross-section perpendicular to curve tangent (beveled stamped-steel profile)
        pitch = 0.18 + 0.52 * (t ** 1.25)
        cy, cz = math.cos(pitch), math.sin(pitch)
        rib_bump = 0.0018 if i in (4, 8, 12) else 0.0
        hw = 0.0138 + rib_bump
        hd = 0.0315
        local_pts = [
            (-hw * 0.72, -hd), (hw * 0.72, -hd), (hw, -hd * 0.70), (hw, hd * 0.70),
            (hw * 0.72, hd), (-hw * 0.72, hd), (-hw, hd * 0.70), (-hw, -hd * 0.70)
        ]
        ring = []
        for lx, ly in local_pts:
            wy = yc + ly * cy
            wz = zc + ly * cz
            ring.append(bm.verts.new((lx, wy, wz)))
        mag_rings.append(ring)
    for r_i in range(len(mag_rings) - 1):
        r0, r1 = mag_rings[r_i], mag_rings[r_i + 1]
        for s in range(8):
            ns = (s + 1) % 8
            bm.faces.new((r0[s], r0[ns], r1[ns], r1[s]))
    bm.faces.new(list(reversed(mag_rings[0])))
    bm.faces.new(mag_rings[-1])
    # Flared locking floorplate aligned smoothly to magazine base
    yc_end = 0.096 + 0.040 + 0.072
    zc_end = -0.008 - 0.222 + 0.016
    add_box_to_bm(bm, (0.032, 0.072, 0.010), (0.0, yc_end + 0.004, zc_end - 0.004), rot_deg=(38.0, 0.0, 0.0))
    mesh_mag = finalize_mesh("AK47_Magazine", bm, mat_steel_dark, bevel_width=0.0012, split_angle_deg=35.0)

    # 7. RIGGED PART: Contoured Bolt Carrier & Hooked Charging Handle (bone: charging_handle)
    bm = bmesh.new()
    add_box_to_bm(bm, (0.013, 0.092, 0.020), (0.0145, 0.058, 0.026))
    add_cyl_to_bm(bm, 0.0052, 0.0046, 0.028, (0.029, 0.088, 0.025), axis='X', segments=14)
    add_cyl_to_bm(bm, 0.0056, 0.0044, 0.018, (0.042, 0.086, 0.030), axis='Z', segments=14, rot_deg=(0.0, 14.0, 0.0))
    mesh_bolt = finalize_mesh("AK47_ChargingHandle", bm, mat_bolt_chrome, bevel_width=0.0012)

    # 8. RIGGED PART: Curved Trigger (bone: trigger)
    bm = bmesh.new()
    add_rounded_profile_x(bm, [
        (0.015, -0.020), (0.022, -0.020), (0.016, -0.034), (0.012, -0.047), (0.006, -0.045), (0.011, -0.033)
    ], width_x=0.006, chamfer_x=0.0015, chamfer_in=0.001)
    mesh_trigger = finalize_mesh("AK47_Trigger", bm, mat_steel_worn, smooth=True)

    # 9. RIGGED PART: Stamped AK Fire Selector Lever (bone: selector)
    bm = bmesh.new()
    add_box_to_bm(bm, (0.004, 0.086, 0.012), (0.021, 0.015, 0.014), rot_deg=(-8.0, 0.0, 0.0))
    add_box_to_bm(bm, (0.010, 0.016, 0.011), (0.024, 0.055, 0.008))
    add_cyl_to_bm(bm, 0.005, 0.005, 0.006, (0.021, -0.024, 0.020), axis='X', segments=12)
    mesh_selector = finalize_mesh("AK47_FireSelector", bm, mat_steel_worn, bevel_width=0.001)

    # 10. RIGGED PART: Magazine Release Paddle (bone: mag_release)
    bm = bmesh.new()
    add_box_to_bm(bm, (0.014, 0.011, 0.026), (0.0, 0.052, -0.034), rot_deg=(12.0, 0.0, 0.0))
    mesh_mag_rel = finalize_mesh("AK47_MagRelease", bm, mat_steel_worn, bevel_width=0.001)

    # Coherent Single-Root Armature
    arm = build_armature("AK47_Rig", [
        ("weapon_root", None, (0.0, 0.0, 0.0), (0.0, 0.08, 0.0)),
        ("weapon_body", "weapon_root", (0.0, 0.0, 0.0), (0.0, 0.16, 0.0)),
        ("magazine", "weapon_body", (0.0, 0.095, -0.025), (0.0, 0.12, -0.16)),
        ("charging_handle", "weapon_body", (0.02, 0.088, 0.026), (0.02, 0.14, 0.026)),
        ("trigger", "weapon_body", (0.0, 0.018, -0.020), (0.0, 0.012, -0.048)),
        ("selector", "weapon_body", (0.021, -0.024, 0.020), (0.021, 0.050, 0.008)),
        ("mag_release", "weapon_body", (0.0, 0.052, -0.022), (0.0, 0.052, -0.046)),
    ])

    bind_mesh_rigid_to_bone(mesh_body, arm, "weapon_body")
    bind_mesh_rigid_to_bone(mesh_mag, arm, "magazine")
    bind_mesh_rigid_to_bone(mesh_bolt, arm, "charging_handle")
    bind_mesh_rigid_to_bone(mesh_trigger, arm, "trigger")
    bind_mesh_rigid_to_bone(mesh_selector, arm, "selector")
    bind_mesh_rigid_to_bone(mesh_mag_rel, arm, "mag_release")

    # Bone-Skinned Modular Hard-Surface Attachments (ZERO floating accessories!)
    build_modular_attachments_for_weapon(
        arm,
        optic_pos=(0.0, 0.042, 0.064),
        muzzle_pos=(0.0, 0.592, 0.020),
        mag_ext_pos=(0.0, yc_end + 0.010, zc_end - 0.024),
        laser_pos=(0.026, 0.245, 0.014),
        mag_bone_name="magazine",
    )

    # Bone-Parented Reference Markers (ALWAYS follow weapon_body / magazine bones!)
    add_bone_marker_empty("MuzzlePoint", (0.0, 0.595, 0.020), arm, "weapon_body")
    add_bone_marker_empty("EjectPoint", (0.032, 0.065, 0.030), arm, "weapon_body")
    add_bone_marker_empty("OpticMount", (0.0, 0.042, 0.064), arm, "weapon_body")
    add_bone_marker_empty("MuzzleMount", (0.0, 0.592, 0.020), arm, "weapon_body")
    add_bone_marker_empty("MagMount", (0.0, yc_end, zc_end), arm, "magazine")
    add_bone_marker_empty("LaserMount", (0.026, 0.245, 0.014), arm, "weapon_body")

    render_studio_views(
        "ak47", RENDER_DIR, arm, center_y=0.14, hero_dist=1.12,
        explode_offsets={
            "magazine": (0.0, 0.03, -0.14),
            "charging_handle": (0.10, 0.02, 0.04),
            "selector": (0.09, -0.02, -0.02),
            "trigger": (0.0, 0.0, -0.06),
            "mag_release": (0.0, 0.0, -0.05),
        },
    )
    save_blend(os.path.join(OUT_DIR, "source", "ak47.blend"))
    print("[AK-47 Overhaul] Hard-surface model, bone mounts, attachments & renders complete.")


if __name__ == "__main__":
    build_ak47()
