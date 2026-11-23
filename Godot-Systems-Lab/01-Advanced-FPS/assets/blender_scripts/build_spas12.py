"""Overhauled Hard-Surface SPAS-12 Shotgun Builder (.blend + hero/alt/exploded renders).
Features sculpted arched SPAS-12 receiver, ventilated U-channel heatshield, contoured
ribbed polymer pump forend, ergonomic pistol grip, skeletal folding stock with recoil pad,
bone-parented mount markers, and bone-skinned modular hard-surface attachments.
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
OUT_DIR = os.path.join(PROJECT_ROOT, "assets", "weapons", "spas12")
RENDER_DIR = os.path.join(PROJECT_ROOT, "portfolio_media", "models")


def build_spas12():
    reset_scene()

    mat_parkerized = create_pbr_material("SPAS_ParkerizedSteel", (0.115, 0.120, 0.132), metallic=0.84, roughness=0.42, pattern='metal', seed=101, normal_strength=0.16)
    mat_shroud = create_pbr_material("SPAS_HeatshieldSteel", (0.145, 0.150, 0.165), metallic=0.88, roughness=0.35, pattern='metal', seed=112, normal_strength=0.16)
    mat_polymer = create_pbr_material("SPAS_TacticalPolymer", (0.075, 0.078, 0.086), metallic=0.04, roughness=0.62, pattern='polymer', seed=123, normal_strength=0.22)
    mat_chrome = create_pbr_material("SPAS_BoltChrome", (0.58, 0.60, 0.63), metallic=0.95, roughness=0.18, pattern='metal', seed=134, normal_strength=0.10)
    mat_shell_red = create_pbr_material("SPAS_ShellRed", (0.72, 0.085, 0.075), metallic=0.05, roughness=0.34, pattern='polymer', seed=145, normal_strength=0.22)
    mat_brass = create_pbr_material("SPAS_BrassRim", (0.80, 0.62, 0.22), metallic=0.93, roughness=0.24, pattern='metal', seed=156, normal_strength=0.18)
    mat_sight_glow = create_pbr_material("SPAS_SightDot", (0.14, 0.96, 0.44), metallic=0.0, roughness=0.20, pattern='solid', emission_color=(0.14, 0.96, 0.44), emission_strength=2.2)

    body_parts = []

    # 1. Sleek Contoured SPAS-12 Receiver (multi-station vaulted arch loft, NO boxy slab!)
    bm = bmesh.new()
    add_lofted_sections_y(bm, [
        (-0.088, make_arch_ring(0.038, -0.016, 0.012, 0.014, bevel=0.004)),
        (-0.068, make_arch_ring(0.042, -0.022, 0.036, 0.014, bevel=0.0045)),
        (-0.025, make_arch_ring(0.044, -0.023, 0.044, 0.013, bevel=0.0045)),
        (0.155,  make_arch_ring(0.044, -0.023, 0.044, 0.013, bevel=0.0045)),
        (0.172,  make_arch_ring(0.040, -0.020, 0.042, 0.011, bevel=0.004)),
    ])
    # Top receiver optics rail
    add_picatinny_rail_y(bm, -0.010, 0.135, 0.055, width=0.020, height=0.007)
    # Recessed ghost-ring rear sight hood
    add_cyl_to_bm(bm, 0.010, 0.010, 0.014, (0.0, -0.032, 0.062), axis='Y', segments=16)
    # Arched trigger guard
    add_rounded_profile_x(bm, [
        (-0.046, -0.020), (-0.040, -0.020), (-0.036, -0.050),
        (0.018, -0.050), (0.022, -0.020), (0.028, -0.020),
        (0.022, -0.057), (-0.042, -0.057)
    ], width_x=0.016, chamfer_x=0.0025, chamfer_in=0.001)
    body_parts.append(finalize_mesh("SPAS_Receiver", bm, mat_parkerized, bevel_width=0.0012, split_angle_deg=36.0))

    # 2. Heavy 12-Gauge Barrel + Full-Length Underbarrel Magazine Tube + Figure-8 Clamp + Front Sight
    bm = bmesh.new()
    add_lathe_y(bm, [
        (0.160, 0.0152), (0.240, 0.0144), (0.585, 0.0138), (0.635, 0.0144), (0.638, 0.0105)
    ], offset=(0.0, 0.0, 0.033), segments=28)
    add_lathe_y(bm, [
        (0.160, 0.0138), (0.565, 0.0138), (0.578, 0.0154), (0.602, 0.0152), (0.614, 0.0124)
    ], offset=(0.0, 0.0, 0.001), segments=24)
    # Sculpted figure-8 barrel/magazine clamp
    add_lofted_sections_y(bm, [
        (0.528, make_arch_ring(0.032, -0.014, 0.046, 0.008, bevel=0.004)),
        (0.552, make_arch_ring(0.032, -0.014, 0.046, 0.008, bevel=0.004)),
    ])
    # Swept front ramp sight blade
    add_rounded_profile_x(bm, [
        (0.572, 0.044), (0.616, 0.044), (0.609, 0.069), (0.594, 0.069)
    ], width_x=0.009, chamfer_x=0.002, chamfer_in=0.001)
    body_parts.append(finalize_mesh("SPAS_Barrels", bm, mat_parkerized, bevel_width=0.0008, split_angle_deg=38.0))

    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=6, radius=0.0024, matrix=Matrix.Translation(Vector((0.0, 0.602, 0.071))))
    body_parts.append(finalize_mesh("SPAS_SightDot", bm, mat_sight_glow, smooth=True))

    # 3. Iconic SPAS-12 Arched Ventilated Heatshield / Barrel Shroud
    bm = bmesh.new()
    # Vaulted upper spine
    add_lofted_sections_y(bm, [
        (0.172, make_arch_ring(0.038, 0.043, 0.049, 0.007, bevel=0.003)),
        (0.518, make_arch_ring(0.038, 0.043, 0.049, 0.007, bevel=0.003)),
    ])
    # Slotted ventilated side ribs with chamfered vents
    for side in (-1.0, 1.0):
        xs = side * 0.0195
        add_box_to_bm(bm, (0.005, 0.346, 0.007), (xs, 0.345, 0.023))
        for i in range(9):
            yb = 0.184 + i * 0.039
            add_box_to_bm(bm, (0.005, 0.015, 0.026), (xs, yb, 0.036))
    body_parts.append(finalize_mesh("SPAS_Heatshield", bm, mat_shroud, bevel_width=0.0012, split_angle_deg=36.0))

    # 4. Sculpted Ergonomic Polymer Pistol Grip (lofted curved grip!)
    bm = bmesh.new()
    grip_rings = []
    for gy, gz, rx, ry_h in [
        (-0.058, -0.015, 0.0165, 0.022),
        (-0.068, -0.046, 0.0175, 0.023),
        (-0.078, -0.082, 0.0180, 0.024),
        (-0.088, -0.118, 0.0170, 0.024),
        (-0.090, -0.130, 0.0155, 0.022),
    ]:
        ring = [bm.verts.new((math.cos(s / 16.0 * math.tau) * rx, gy + math.sin(s / 16.0 * math.tau) * ry_h, gz)) for s in range(16)]
        grip_rings.append(ring)
    for r_i in range(len(grip_rings) - 1):
        r0, r1 = grip_rings[r_i], grip_rings[r_i + 1]
        for s in range(16):
            ns = (s + 1) % 16
            bm.faces.new((r0[s], r0[ns], r1[ns], r1[s]))
    bm.faces.new(list(reversed(grip_rings[0])))
    bm.faces.new(grip_rings[-1])
    body_parts.append(finalize_mesh("SPAS_PistolGrip", bm, mat_polymer, smooth=True, split_angle_deg=55.0))

    mesh_body = join_objects(body_parts, "SPAS12_Body")

    # 5. RIGGED PART: Sculpted Ribbed SPAS-12 Forend / Pump (bone: pump)
    bm = bmesh.new()
    # Contoured rounded polymer forend core
    add_lofted_sections_y(bm, [
        (0.242, make_oval_ring(0.023, 0.022, 0.002, segs=18)),
        (0.262, make_oval_ring(0.027, 0.025, 0.001, segs=18)),
        (0.452, make_oval_ring(0.027, 0.025, 0.001, segs=18)),
        (0.472, make_oval_ring(0.023, 0.022, 0.002, segs=18)),
    ])
    # 11 smoothly sculpted wrap-around tactile grip ribs
    for i in range(11):
        yr = 0.264 + i * 0.0185
        add_lofted_sections_y(bm, [
            (yr - 0.0045, make_oval_ring(0.0295, 0.027, 0.001, segs=18)),
            (yr + 0.0045, make_oval_ring(0.0295, 0.027, 0.001, segs=18)),
        ])
    # Dual machined steel action bars
    for side in (-1.0, 1.0):
        add_box_to_bm(bm, (0.005, 0.145, 0.010), (side * 0.023, 0.20, 0.006))
    mesh_pump = finalize_mesh("SPAS12_PumpForend", bm, mat_polymer, bevel_width=0.0010, split_angle_deg=42.0)

    # 6. RIGGED PART: Folding Skeletal Metal Stock with Curved Recoil Pad & Hook (bone: stock)
    bm = bmesh.new()
    # Rear receiver stock hinge block (connects cleanly into receiver tang & both struts)
    add_box_to_bm(bm, (0.036, 0.034, 0.044), (0.0, -0.094, 0.012))
    add_box_to_bm(bm, (0.026, 0.236, 0.014), (0.0, -0.210, 0.014), rot_deg=(-4.0, 0.0, 0.0))
    add_box_to_bm(bm, (0.026, 0.240, 0.014), (0.0, -0.202, -0.036), rot_deg=(14.0, 0.0, 0.0))
    add_box_to_bm(bm, (0.024, 0.016, 0.068), (0.0, -0.248, -0.022))
    add_lofted_sections_y(bm, [
        (-0.332, make_oval_ring(0.019, 0.058, -0.030, segs=16)),
        (-0.314, make_oval_ring(0.019, 0.058, -0.030, segs=16)),
    ])
    add_box_to_bm(bm, (0.014, 0.044, 0.012), (0.0, -0.305, -0.088))
    mesh_stock = finalize_mesh("SPAS12_FoldingStock", bm, mat_shroud, bevel_width=0.0016, split_angle_deg=38.0)

    # 7. RIGGED PART: Chrome Bolt (bone: bolt)
    bm = bmesh.new()
    add_box_to_bm(bm, (0.014, 0.072, 0.020), (0.018, 0.065, 0.025))
    add_cyl_to_bm(bm, 0.0045, 0.0040, 0.020, (0.030, 0.082, 0.025), axis='X', segments=12)
    mesh_bolt = finalize_mesh("SPAS12_Bolt", bm, mat_chrome, bevel_width=0.0012)

    # 8. RIGGED PART: Bottom Shell Lifter / Loading Gate (bone: loading_gate)
    bm = bmesh.new()
    add_box_to_bm(bm, (0.024, 0.070, 0.005), (0.0, 0.062, -0.023))
    mesh_gate = finalize_mesh("SPAS12_LoadingGate", bm, mat_chrome, bevel_width=0.001)

    # 9. RIGGED PART: Trigger (bone: trigger)
    bm = bmesh.new()
    add_rounded_profile_x(bm, [
        (-0.008, -0.020), (-0.001, -0.020), (-0.007, -0.035), (-0.012, -0.048), (-0.018, -0.045)
    ], width_x=0.007, chamfer_x=0.0015, chamfer_in=0.001)
    mesh_trigger = finalize_mesh("SPAS12_Trigger", bm, mat_parkerized, smooth=True)

    # 10. RIGGED PART: Detailed 12-Gauge Red/Brass Shell (bone: shell)
    bm_hull = bmesh.new()
    add_cyl_to_bm(bm_hull, 0.0098, 0.0098, 0.052, (0.0, 0.065, -0.010), axis='Y', segments=20)
    obj_hull = finalize_mesh("SPAS_ShellHull", bm_hull, mat_shell_red, bevel_width=0.001)
    bm_rim = bmesh.new()
    add_lathe_y(bm_rim, [(0.028, 0.0108), (0.030, 0.0108), (0.031, 0.0102), (0.043, 0.0102)], offset=(0.0, 0.0, -0.010), segments=20)
    obj_rim = finalize_mesh("SPAS_ShellRim", bm_rim, mat_brass, smooth=True)
    mesh_shell = join_objects([obj_hull, obj_rim], "SPAS12_Shell")

    arm = build_armature("SPAS12_Rig", [
        ("weapon_root", None, (0.0, 0.0, 0.0), (0.0, 0.08, 0.0)),
        ("weapon_body", "weapon_root", (0.0, 0.0, 0.0), (0.0, 0.16, 0.0)),
        ("pump", "weapon_body", (0.0, 0.355, 0.002), (0.0, 0.45, 0.002)),
        ("bolt", "weapon_body", (0.018, 0.065, 0.025), (0.018, 0.12, 0.025)),
        ("loading_gate", "weapon_body", (0.0, 0.028, -0.023), (0.0, 0.095, -0.023)),
        ("trigger", "weapon_body", (0.0, -0.005, -0.020), (0.0, -0.012, -0.048)),
        ("stock", "weapon_body", (0.0, -0.098, 0.020), (0.0, -0.31, -0.02)),
        ("shell", "weapon_body", (0.0, 0.060, -0.010), (0.0, 0.10, -0.010)),
    ])

    bind_mesh_rigid_to_bone(mesh_body, arm, "weapon_body")
    bind_mesh_rigid_to_bone(mesh_pump, arm, "pump")
    bind_mesh_rigid_to_bone(mesh_bolt, arm, "bolt")
    bind_mesh_rigid_to_bone(mesh_gate, arm, "loading_gate")
    bind_mesh_rigid_to_bone(mesh_trigger, arm, "trigger")
    bind_mesh_rigid_to_bone(mesh_stock, arm, "stock")
    bind_mesh_rigid_to_bone(mesh_shell, arm, "shell")

    # Bone-Skinned Modular Hard-Surface Attachments (Tubular Shotgun Mag Extension!)
    build_modular_attachments_for_weapon(
        arm,
        optic_pos=(0.0, 0.055, 0.061),
        muzzle_pos=(0.0, 0.640, 0.033),
        mag_ext_pos=(0.0, 0.614, 0.001),
        laser_pos=(0.026, 0.495, 0.008),
        mag_bone_name="weapon_body",
        mag_is_tube=True,
    )

    add_bone_marker_empty("MuzzlePoint", (0.0, 0.642, 0.033), arm, "weapon_body")
    add_bone_marker_empty("EjectPoint", (0.034, 0.068, 0.028), arm, "weapon_body")
    add_bone_marker_empty("OpticMount", (0.0, 0.055, 0.061), arm, "weapon_body")
    add_bone_marker_empty("MuzzleMount", (0.0, 0.640, 0.033), arm, "weapon_body")
    add_bone_marker_empty("MagMount", (0.0, 0.614, 0.001), arm, "weapon_body")
    add_bone_marker_empty("LaserMount", (0.026, 0.495, 0.008), arm, "weapon_body")

    render_studio_views(
        "spas12", RENDER_DIR, arm, center_y=0.16, hero_dist=1.18,
        explode_offsets={
            "pump": (0.0, 0.06, -0.075),
            "bolt": (0.10, 0.02, 0.03),
            "loading_gate": (0.0, 0.0, -0.07),
            "shell": (0.0, -0.02, -0.12),
            "trigger": (0.0, 0.0, -0.06),
            "stock": (0.0, -0.10, 0.02),
        },
    )
    save_blend(os.path.join(OUT_DIR, "source", "spas12.blend"))
    print("[SPAS-12 Overhaul] Hard-surface model, bone mounts, attachments & renders complete.")


if __name__ == "__main__":
    build_spas12()
