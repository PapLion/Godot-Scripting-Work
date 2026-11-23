"""Upgraded Blender 5.3 Hard-Surface Weapon Modeling, 512px PBR Albedo+Roughness+Normal
Generator, Modular Bone-Bound Attachments, Smooth Bezier NLA Baking & Studio Rendering Utilities.
"""

import math
import os
import struct
import zlib
import bpy
import bmesh
from mathutils import Vector, Matrix, Euler

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
TEXTURE_DIR = os.path.join(PROJECT_ROOT, "assets", "weapons", "textures")


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.fps = 30
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0
    return scene


def _write_png_rgb(filepath: str, w: int, h: int, rgb_bytes: bytearray):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    raw = bytearray()
    stride = w * 3
    for y in range(h):
        raw.append(0)
        start = y * stride
        raw.extend(rgb_bytes[start:start + stride])

    def _chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    idat = zlib.compress(bytes(raw), level=6)
    with open(filepath, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(_chunk(b"IHDR", ihdr))
        f.write(_chunk(b"IDAT", idat))
        f.write(_chunk(b"IEND", b""))


def _load_packed_png(filepath: str, colorspace: str = 'sRGB'):
    img = bpy.data.images.load(filepath, check_existing=False)
    img.colorspace_settings.name = colorspace
    img.pack()
    return img


def _hash2(x: int, y: int, seed: int) -> float:
    n = (x * 374761393 + y * 668265263 + seed * 1442695041) & 0x7FFFFFFF
    n = (n ^ (n >> 13)) * 1274126177 & 0x7FFFFFFF
    return ((n ^ (n >> 16)) & 0xFFFF) / 65535.0


def _tile_value_noise(u: float, v: float, freq_x: int, freq_y: int, seed: int) -> float:
    """Seamless tileable 2D value noise."""
    fx = u * freq_x
    fy = v * freq_y
    ix = int(math.floor(fx))
    iy = int(math.floor(fy))
    tx = fx - ix
    ty = fy - iy
    tx = tx * tx * (3.0 - 2.0 * tx)
    ty = ty * ty * (3.0 - 2.0 * ty)
    ix0 = ix % freq_x
    ix1 = (ix + 1) % freq_x
    iy0 = iy % freq_y
    iy1 = (iy + 1) % freq_y
    c00 = _hash2(ix0, iy0, seed)
    c10 = _hash2(ix1, iy0, seed)
    c01 = _hash2(ix0, iy1, seed)
    c11 = _hash2(ix1, iy1, seed)
    nx0 = c00 + (c10 - c00) * tx
    nx1 = c01 + (c11 - c01) * tx
    return nx0 + (nx1 - nx0) * ty


def _tile_fbm(u: float, v: float, fx: int, fy: int, seed: int, octaves: int = 3) -> float:
    val = 0.0
    amp = 0.55
    total = 0.0
    for o in range(octaves):
        mul = 1 << o
        val += _tile_value_noise(u, v, fx * mul, fy * mul, seed + o * 23) * amp
        total += amp
        amp *= 0.5
    return val / total


def create_pbr_material(
    name: str,
    base_color: tuple,
    metallic: float = 0.0,
    roughness: float = 0.5,
    pattern: str = 'metal',
    seed: int = 1,
    tex_size: int = 512,
    normal_strength: float = 0.35,
    emission_color: tuple = None,
    emission_strength: float = 0.0,
    alpha: float = 1.0,
):
    """Creates a glTF-2.0-ready Principled BSDF PBR material with seamless Albedo, Roughness,
    and Tangent-Space Normal PNG maps for realistic micro-surface relief in Blender & Godot.
    """
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()

    out = nt.nodes.new('ShaderNodeOutputMaterial')
    out.location = (520, 0)
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (180, 0)
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])

    bsdf.inputs['Metallic'].default_value = metallic
    if alpha < 0.999 and 'Alpha' in bsdf.inputs:
        bsdf.inputs['Alpha'].default_value = alpha
        mat.blend_method = 'BLEND' if hasattr(mat, 'blend_method') else 'OPAQUE'
    if emission_color is not None and emission_strength > 0.0:
        if 'Emission Color' in bsdf.inputs:
            bsdf.inputs['Emission Color'].default_value = (*emission_color, 1.0)
            bsdf.inputs['Emission Strength'].default_value = emission_strength

    if pattern == 'solid':
        bsdf.inputs['Base Color'].default_value = (*base_color, 1.0)
        bsdf.inputs['Roughness'].default_value = roughness
        return mat

    # Use 256px for simple glass/chrome, 512px for hero wood/metal/polymer/fabric/skin
    sz = tex_size if pattern in ('wood', 'metal', 'polymer', 'fabric') else min(256, tex_size)
    albedo_rgb = bytearray(sz * sz * 3)
    rough_rgb = bytearray(sz * sz * 3)
    heights = [0.0] * (sz * sz)

    r0, g0, b0 = base_color[0], base_color[1], base_color[2]
    inv_sz = 1.0 / float(sz)

    for y in range(sz):
        v = y * inv_sz
        row_off = y * sz
        for x in range(sz):
            u = x * inv_sz
            idx = (row_off + x) * 3

            if pattern == 'wood':
                warp = _tile_fbm(u, v, 4, 16, seed, 3)
                ring = 0.5 + 0.5 * math.sin((v * 14.0 + warp * 4.2) * math.pi)
                pores = _tile_fbm(u, v, 48, 8, seed + 51, 2)
                micro = _hash2(x, y, seed + 7)
                mix = 0.72 + 0.30 * ring * 0.8 + 0.12 * (pores - 0.5) - 0.04 * (micro - 0.5)
                ar = r0 * mix
                ag = g0 * mix * 0.93
                ab = b0 * mix * 0.84
                rv = roughness + (0.5 - ring) * 0.14 + (pores - 0.5) * 0.08
                h_val = ring * 0.65 + pores * 0.35
            elif pattern == 'metal':
                # Fine horizontal machined gunmetal brushing + subtle parkerized micro-grain
                brush = _tile_fbm(u, v, 8, 64, seed, 2)
                patina = _tile_fbm(u, v, 6, 6, seed + 33, 3)
                speck = _hash2(x, y, seed + 71)
                delta = (brush - 0.5) * 0.042 + (patina - 0.5) * 0.036 + (speck - 0.5) * 0.015
                ar = r0 + delta
                ag = g0 + delta
                ab = b0 + delta * 1.04
                rv = roughness + (patina - 0.5) * 0.14 + (brush - 0.5) * 0.04
                h_val = brush * 0.55 + speck * 0.20 + patina * 0.25
            elif pattern == 'polymer':
                # Fine injection-molded matte polymer micro-stippling (never coarse stucco!)
                micro_cell = _tile_fbm(u, v, 64, 64, seed, 2)
                stipple = _hash2(x, y, seed + 11)
                macro = _tile_fbm(u, v, 8, 8, seed + 19, 2)
                delta = (micro_cell - 0.5) * 0.028 + (stipple - 0.5) * 0.018 + (macro - 0.5) * 0.025
                ar = r0 + delta
                ag = g0 + delta
                ab = b0 + delta
                rv = roughness + (micro_cell - 0.5) * 0.08
                h_val = micro_cell * 0.65 + stipple * 0.20 + macro * 0.15
            elif pattern == 'fabric':
                # Subtle fine tactical cordura / ripstop micro-weave
                wx = 0.5 + 0.5 * math.sin(u * sz * 1.45)
                wy = 0.5 + 0.5 * math.sin(v * sz * 1.45)
                weave = 0.5 * (wx + wy)
                rip = 1.0 if (x % 24 == 0 or y % 24 == 0) else 0.0
                macro = _tile_fbm(u, v, 8, 8, seed + 41, 2)
                delta = (weave - 0.5) * 0.018 + rip * 0.010 + (macro - 0.5) * 0.028
                ar = r0 + delta
                ag = g0 + delta
                ab = b0 + delta
                rv = roughness + (0.5 - weave) * 0.05
                h_val = weave * 0.65 + rip * 0.25 + macro * 0.10
            elif pattern == 'skin':
                pores = _tile_fbm(u, v, 24, 24, seed + 13, 2)
                tone = _tile_fbm(u, v, 6, 6, seed + 67, 2)
                ar = r0 + (tone - 0.5) * 0.05 + (pores - 0.5) * 0.02
                ag = g0 + (tone - 0.5) * 0.04 + (pores - 0.5) * 0.015
                ab = b0 + (tone - 0.5) * 0.035 + (pores - 0.5) * 0.015
                rv = roughness + (pores - 0.5) * 0.08
                h_val = pores * 0.6 + tone * 0.4
            elif pattern == 'glass':
                grad = 0.80 + 0.20 * math.sin((u + v) * math.pi)
                ar, ag, ab, rv, h_val = r0 * grad, g0 * grad, b0 * grad, 0.06, 0.5
            else:
                ar, ag, ab, rv, h_val = r0, g0, b0, roughness, 0.5

            albedo_rgb[idx] = int(round(max(0.0, min(1.0, ar)) * 255.0))
            albedo_rgb[idx + 1] = int(round(max(0.0, min(1.0, ag)) * 255.0))
            albedo_rgb[idx + 2] = int(round(max(0.0, min(1.0, ab)) * 255.0))

            rb = int(round(max(0.06, min(0.96, rv)) * 255.0))
            rough_rgb[idx] = rb
            rough_rgb[idx + 1] = rb
            rough_rgb[idx + 2] = rb
            heights[row_off + x] = h_val

    # Derive crisp tangent-space Normal map via finite differences (subtle micro-relief!)
    normal_rgb = bytearray(sz * sz * 3)
    n_amp = {'wood': 1.20, 'fabric': 1.55, 'polymer': 0.90, 'skin': 0.70, 'metal': 0.75}.get(pattern, 0.80)
    for y in range(sz):
        ym = ((y - 1) % sz) * sz
        y0 = y * sz
        yp = ((y + 1) % sz) * sz
        for x in range(sz):
            xm = (x - 1) % sz
            xp = (x + 1) % sz
            dx = (heights[y0 + xp] - heights[y0 + xm]) * n_amp
            dy = (heights[yp + x] - heights[ym + x]) * n_amp
            nx = -dx
            ny = -dy
            nz = 1.0
            inv_len = 1.0 / math.sqrt(nx * nx + ny * ny + nz * nz)
            idx = (y0 + x) * 3
            normal_rgb[idx] = int(round((nx * inv_len * 0.5 + 0.5) * 255.0))
            normal_rgb[idx + 1] = int(round((ny * inv_len * 0.5 + 0.5) * 255.0))
            normal_rgb[idx + 2] = int(round((nz * inv_len * 0.5 + 0.5) * 255.0))

    albedo_path = os.path.join(TEXTURE_DIR, f"{name}_albedo.png")
    rough_path = os.path.join(TEXTURE_DIR, f"{name}_roughness.png")
    normal_path = os.path.join(TEXTURE_DIR, f"{name}_normal.png")
    _write_png_rgb(albedo_path, sz, sz, albedo_rgb)
    _write_png_rgb(rough_path, sz, sz, rough_rgb)
    _write_png_rgb(normal_path, sz, sz, normal_rgb)

    tex_a = nt.nodes.new('ShaderNodeTexImage')
    tex_a.image = _load_packed_png(albedo_path, 'sRGB')
    tex_a.location = (-360, 200)
    nt.links.new(tex_a.outputs['Color'], bsdf.inputs['Base Color'])

    tex_r = nt.nodes.new('ShaderNodeTexImage')
    tex_r.image = _load_packed_png(rough_path, 'Non-Color')
    tex_r.location = (-360, -40)
    nt.links.new(tex_r.outputs['Color'], bsdf.inputs['Roughness'])

    if normal_strength > 0.01:
        tex_n = nt.nodes.new('ShaderNodeTexImage')
        tex_n.image = _load_packed_png(normal_path, 'Non-Color')
        tex_n.location = (-360, -280)
        nmap = nt.nodes.new('ShaderNodeNormalMap')
        nmap.location = (-80, -280)
        nmap.inputs['Strength'].default_value = normal_strength
        nt.links.new(tex_n.outputs['Color'], nmap.inputs['Color'])
        nt.links.new(nmap.outputs['Normal'], bsdf.inputs['Normal'])

    return mat


def _apply_box_uv(mesh: bpy.types.Mesh, scale: float = 3.2):
    bm = bmesh.new()
    bm.from_mesh(mesh)
    uv_layer = bm.loops.layers.uv.verify()
    for f in bm.faces:
        n = f.normal
        ax, ay, az = abs(n.x), abs(n.y), abs(n.z)
        for loop in f.loops:
            co = loop.vert.co
            if az >= ax and az >= ay:
                loop[uv_layer].uv = (co.x * scale, co.y * scale)
            elif ax >= ay and ax >= az:
                loop[uv_layer].uv = (co.y * scale, co.z * scale)
            else:
                loop[uv_layer].uv = (co.x * scale, co.z * scale)
    bm.to_mesh(mesh)
    bm.free()


def finalize_mesh(
    name: str,
    bm: bmesh.types.BMesh,
    material: bpy.types.Material,
    bevel_width: float = 0.0,
    bevel_segments: int = 2,
    smooth: bool = True,
    split_angle_deg: float = 38.0,
    uv_scale: float = 3.4,
    collection=None,
) -> bpy.types.Object:
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if bevel_width > 0.0 and len(bm.edges) > 0:
        bmesh.ops.bevel(
            bm,
            geom=list(bm.edges),
            offset=bevel_width,
            segments=bevel_segments,
            affect='EDGES',
            clamp_overlap=True,
        )
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()

    _apply_box_uv(mesh, uv_scale)
    if smooth:
        mesh.polygons.foreach_set('use_smooth', [True] * len(mesh.polygons))
    mesh.update()

    obj = bpy.data.objects.new(name, mesh)
    if material is not None:
        obj.data.materials.append(material)
    target_col = collection if collection is not None else bpy.context.scene.collection
    target_col.objects.link(obj)

    if smooth and split_angle_deg < 179.0:
        es = obj.modifiers.new(name="EdgeSplit", type='EDGE_SPLIT')
        es.split_angle = math.radians(split_angle_deg)
        es.use_edge_angle = True
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_apply(modifier=es.name)

    return obj


def add_box_to_bm(bm, size: tuple, center: tuple = (0, 0, 0), rot_deg: tuple = (0, 0, 0)):
    mat = (
        Matrix.Translation(Vector(center))
        @ Euler(tuple(math.radians(a) for a in rot_deg), 'XYZ').to_matrix().to_4x4()
        @ Matrix.Diagonal((size[0], size[1], size[2], 1.0))
    )
    bmesh.ops.create_cube(bm, size=1.0, matrix=mat)


def add_cyl_to_bm(bm, r1: float, r2: float, length: float, center: tuple = (0, 0, 0), axis: str = 'Y', segments: int = 24, rot_deg: tuple = (0, 0, 0)):
    if axis == 'Y':
        base_rot = Euler((math.radians(90.0), 0.0, 0.0), 'XYZ').to_matrix().to_4x4()
    elif axis == 'X':
        base_rot = Euler((0.0, math.radians(90.0), 0.0), 'XYZ').to_matrix().to_4x4()
    else:
        base_rot = Matrix.Identity(4)
    extra_rot = Euler(tuple(math.radians(a) for a in rot_deg), 'XYZ').to_matrix().to_4x4()
    mat = Matrix.Translation(Vector(center)) @ extra_rot @ base_rot
    bmesh.ops.create_cone(
        bm, cap_ends=True, cap_tris=False, segments=segments,
        radius1=r1, radius2=r2, depth=length, matrix=mat,
    )


def add_lathe_y(bm, profile: list, offset: tuple = (0, 0, 0), segments: int = 28, cap_start: bool = True, cap_end: bool = True):
    ox, oy, oz = offset
    rings = []
    for y_val, rad in profile:
        ring = []
        for i in range(segments):
            ang = (i / float(segments)) * math.tau
            ring.append(bm.verts.new((ox + math.cos(ang) * rad, oy + y_val, oz + math.sin(ang) * rad)))
        rings.append(ring)
    for r_idx in range(len(rings) - 1):
        r0, r1 = rings[r_idx], rings[r_idx + 1]
        for i in range(segments):
            ni = (i + 1) % segments
            bm.faces.new((r0[i], r0[ni], r1[ni], r1[i]))
    if cap_start and rings:
        bm.faces.new(list(reversed(rings[0])))
    if cap_end and rings:
        bm.faces.new(rings[-1])


def add_fluted_barrel_y(bm, y_start: float, y_end: float, radius: float, offset_xz: tuple = (0, 0), flutes: int = 8, flute_depth: float = 0.0014, slices: int = 12):
    """Builds a precision fluted steel barrel along +Y."""
    ox, oz = offset_xz
    segs = flutes * 4
    rings = []
    for s in range(slices + 1):
        t = s / float(slices)
        y = y_start + (y_end - y_start) * t
        # Fade flutes smoothly at barrel chamber & muzzle ends
        flute_env = math.sin(min(1.0, max(0.0, (t - 0.08) / 0.84)) * math.pi) if 0.08 < t < 0.92 else 0.0
        ring = []
        for i in range(segs):
            ang = (i / float(segs)) * math.tau
            groove = max(0.0, math.cos(ang * flutes)) ** 2
            r = radius - flute_depth * groove * flute_env
            ring.append(bm.verts.new((ox + math.cos(ang) * r, y, oz + math.sin(ang) * r)))
        rings.append(ring)
    for r_idx in range(len(rings) - 1):
        r0, r1 = rings[r_idx], rings[r_idx + 1]
        for i in range(segs):
            ni = (i + 1) % segs
            bm.faces.new((r0[i], r0[ni], r1[ni], r1[i]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])


def add_lofted_sections_y(bm, sections: list, cap_start: bool = True, cap_end: bool = True):
    """Lofts arbitrary closed 2D (x, z) cross-sections placed along Y:
    sections = [ (y_val, [(x0, z0), (x1, z1), ...]), ... ] — all sections must have equal vertex count.
    Ideal for arched AK dust covers, palm-swelled wooden handguards, sculpted stocks & contoured receivers!
    """
    rings = []
    for y_val, pts_xz in sections:
        rings.append([bm.verts.new((x, y_val, z)) for (x, z) in pts_xz])
    n = len(rings[0])
    for r_idx in range(len(rings) - 1):
        r0, r1 = rings[r_idx], rings[r_idx + 1]
        for i in range(n):
            ni = (i + 1) % n
            bm.faces.new((r0[i], r0[ni], r1[ni], r1[i]))
    if cap_start:
        bm.faces.new(list(reversed(rings[0])))
    if cap_end:
        bm.faces.new(rings[-1])


def make_arch_ring(w: float, h_bot: float, h_top: float, arch_h: float, bevel: float = 0.004) -> list:
    """12-point vaulted hard-surface cross-section (flat/beveled bottom + rounded arch top)."""
    hw = w * 0.5
    bw = hw - bevel
    return [
        (-bw, h_bot),
        (bw, h_bot),
        (hw, h_bot + bevel),
        (hw, h_top - bevel),
        (hw * 0.88, h_top + arch_h * 0.42),
        (hw * 0.55, h_top + arch_h * 0.84),
        (0.0, h_top + arch_h),
        (-hw * 0.55, h_top + arch_h * 0.84),
        (-hw * 0.88, h_top + arch_h * 0.42),
        (-hw, h_top - bevel),
        (-hw, h_bot + bevel),
    ]


def make_oval_ring(rx: float, rz: float, z_center: float, segs: int = 16, flat_top: float = 1.0) -> list:
    """Smooth sculpted oval cross-section for ergonomic grips, stocks, and forends."""
    pts = []
    for i in range(segs):
        ang = (i / float(segs)) * math.tau
        vx = math.cos(ang) * rx
        vz = math.sin(ang) * rz
        if vz > 0:
            vz *= flat_top
        pts.append((vx, z_center + vz))
    return pts


def add_rounded_profile_x(bm, points_yz: list, width_x: float, chamfer_x: float = 0.004, chamfer_in: float = 0.003, x_center: float = 0.0):
    """Builds a 3-slice chamfered hard-surface extrusion along X (no razor-flat planks!)."""
    n = len(points_yz)
    cy = sum(p[0] for p in points_yz) / n
    cz = sum(p[1] for p in points_yz) / n
    hw = width_x * 0.5
    iw = max(0.001, hw - chamfer_x)

    def _inset(y, z, amount):
        dy, dz = y - cy, z - cz
        L = math.hypot(dy, dz)
        if L < 1e-5:
            return y, z
        s = max(0.2, (L - amount) / L)
        return cy + dy * s, cz + dz * s

    outer_l = [bm.verts.new((x_center - hw, *_inset(y, z, chamfer_in))) for (y, z) in points_yz]
    inner_l = [bm.verts.new((x_center - iw, y, z)) for (y, z) in points_yz]
    inner_r = [bm.verts.new((x_center + iw, y, z)) for (y, z) in points_yz]
    outer_r = [bm.verts.new((x_center + hw, *_inset(y, z, chamfer_in))) for (y, z) in points_yz]

    bm.faces.new(outer_l)
    bm.faces.new(list(reversed(outer_r)))
    for i in range(n):
        ni = (i + 1) % n
        bm.faces.new((outer_l[i], inner_l[i], inner_l[ni], outer_l[ni]))
        bm.faces.new((inner_l[i], inner_r[i], inner_r[ni], inner_l[ni]))
        bm.faces.new((inner_r[i], outer_r[i], outer_r[ni], inner_r[ni]))


def add_picatinny_rail_y(bm, y_start: float, y_end: float, z_base: float, width: float = 0.021, height: float = 0.009):
    """Builds an authentic beveled MIL-STD-1913 Picatinny rail with cross-slots."""
    length = y_end - y_start
    ym = (y_start + y_end) * 0.5
    # Dovetail rail stem + top flange
    add_box_to_bm(bm, (width * 0.72, length, height * 0.52), (0.0, ym, z_base + height * 0.26))
    slots = max(2, int(length / 0.011))
    step = length / float(slots)
    for i in range(slots):
        ys = y_start + (i + 0.5) * step
        add_box_to_bm(bm, (width, step * 0.56, height * 0.52), (0.0, ys, z_base + height * 0.74))


def join_objects(objects: list, new_name: str) -> bpy.types.Object:
    valid = [o for o in objects if o is not None]
    if len(valid) == 1:
        valid[0].name = new_name
        return valid[0]
    bpy.ops.object.select_all(action='DESELECT')
    for o in valid:
        o.select_set(True)
    bpy.context.view_layer.objects.active = valid[0]
    bpy.ops.object.join()
    res = bpy.context.view_layer.objects.active
    res.name = new_name
    return res


def build_armature(name: str, bone_defs: list) -> bpy.types.Object:
    arm_data = bpy.data.armatures.new(name)
    arm_obj = bpy.data.objects.new(name, arm_data)
    bpy.context.scene.collection.objects.link(arm_obj)
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode='EDIT')

    eb = arm_data.edit_bones
    created = {}
    for b_name, p_name, head, tail in bone_defs:
        bone = eb.new(b_name)
        bone.head = Vector(head)
        bone.tail = Vector(tail)
        if p_name and p_name in created:
            bone.parent = created[p_name]
            bone.use_connect = False
        created[b_name] = bone

    bpy.ops.object.mode_set(mode='OBJECT')
    arm_obj.data.display_type = 'OCTAHEDRAL'
    arm_obj.show_in_front = True
    return arm_obj


def bind_mesh_rigid_to_bone(mesh_obj: bpy.types.Object, arm_obj: bpy.types.Object, bone_name: str):
    mesh_obj.parent = arm_obj
    mesh_obj.matrix_parent_inverse = arm_obj.matrix_world.inverted()
    vg = mesh_obj.vertex_groups.new(name=bone_name)
    vg.add(list(range(len(mesh_obj.data.vertices))), 1.0, 'REPLACE')
    mod = mesh_obj.modifiers.new(name="Armature", type='ARMATURE')
    mod.object = arm_obj


def add_bone_marker_empty(name: str, world_pos: tuple, arm_obj: bpy.types.Object, bone_name: str = "weapon_body"):
    """Creates a marker Empty parented directly to a specific bone so it ALWAYS follows animations."""
    emp = bpy.data.objects.new(name, None)
    emp.empty_display_type = 'PLAIN_AXES'
    emp.empty_display_size = 0.028
    bpy.context.scene.collection.objects.link(emp)
    emp.location = Vector(world_pos)
    emp.parent = arm_obj
    emp.parent_type = 'BONE'
    emp.parent_bone = bone_name
    # Compute proper matrix_parent_inverse so empty stays at exact world_pos in rest pose
    pose_bone = arm_obj.pose.bones.get(bone_name)
    if pose_bone is not None:
        # Blender bone parenting originates at bone tail in armature space
        bone_tail_mat = Matrix.Translation(arm_obj.data.bones[bone_name].tail_local)
        emp.matrix_parent_inverse = (arm_obj.matrix_world @ bone_tail_mat).inverted()
    return emp


def build_modular_attachments_for_weapon(
    arm_obj: bpy.types.Object,
    optic_pos: tuple,
    muzzle_pos: tuple,
    mag_ext_pos: tuple,
    laser_pos: tuple,
    mag_bone_name: str = "magazine",
    mag_is_tube: bool = False,
):
    """Builds 4 detailed hard-surface modular attachment meshes directly inside the weapon rig,
    rigidly skinned to weapon_body (Optic, Compensator, Tactical Laser) and magazine (Extended Mag Base)!
    Eliminates floating attachments permanently across recoil, reload, ADS, equip, lean, and shoulder switches.
    """
    mat_att_body = create_pbr_material("Att_AnodizedBlack", (0.09, 0.095, 0.105), metallic=0.82, roughness=0.36, pattern='metal', seed=401, tex_size=256)
    mat_att_tan = create_pbr_material("Att_FDEPolymer", (0.42, 0.34, 0.22), metallic=0.05, roughness=0.58, pattern='polymer', seed=412, tex_size=256)
    mat_att_glass = create_pbr_material("Att_HoloGlass", (0.28, 0.58, 0.72), metallic=0.10, roughness=0.06, pattern='glass', seed=423, tex_size=128, alpha=0.22)
    mat_red_dot = create_pbr_material("Att_RedDotGlow", (1.0, 0.14, 0.14), metallic=0.0, roughness=0.2, pattern='solid', emission_color=(1.0, 0.16, 0.14), emission_strength=4.5)
    mat_laser_dot = create_pbr_material("Att_GreenLaserGlow", (0.14, 1.0, 0.42), metallic=0.0, roughness=0.2, pattern='solid', emission_color=(0.14, 1.0, 0.42), emission_strength=3.5)

    # 1. Att_Optic_Holo (EOTech-inspired beveled reflex sight with protective hood, QD clamp, battery hump, windage knobs, glowing dot)
    ox, oy, oz = optic_pos
    optic_parts = []
    bm = bmesh.new()
    # QD Rail clamp base + front battery compartment
    add_box_to_bm(bm, (0.032, 0.072, 0.011), (ox, oy, oz + 0.0055))
    add_box_to_bm(bm, (0.036, 0.034, 0.018), (ox, oy + 0.022, oz + 0.014))
    # Protective beveled aluminum hood arches (left, right, top)
    add_box_to_bm(bm, (0.0055, 0.044, 0.032), (ox - 0.0185, oy - 0.006, oz + 0.026))
    add_box_to_bm(bm, (0.0055, 0.044, 0.032), (ox + 0.0185, oy - 0.006, oz + 0.026))
    add_box_to_bm(bm, (0.042, 0.044, 0.0055), (ox, oy - 0.006, oz + 0.043))
    # Side windage/elevation turrets & QD lever
    add_cyl_to_bm(bm, 0.0045, 0.0045, 0.006, (ox + 0.022, oy - 0.004, oz + 0.018), axis='X', segments=12)
    add_cyl_to_bm(bm, 0.0045, 0.0045, 0.006, (ox + 0.022, oy + 0.008, oz + 0.018), axis='X', segments=12)
    optic_parts.append(finalize_mesh("Att_HoloFrame", bm, mat_att_body, bevel_width=0.0014))

    # Crisp glowing red reticle dot suspended in optic window
    bm_d = bmesh.new()
    bmesh.ops.create_uvsphere(bm_d, u_segments=10, v_segments=6, radius=0.0020, matrix=Matrix.Translation(Vector((ox, oy - 0.002, oz + 0.027))))
    optic_parts.append(finalize_mesh("Att_HoloDot", bm_d, mat_red_dot, smooth=True))

    obj_optic = join_objects(optic_parts, "Att_Optic_Holo")
    bind_mesh_rigid_to_bone(obj_optic, arm_obj, "weapon_body")

    # 2. Att_Muzzle_Comp (Machined multi-port tactical compensator brake)
    mx, my, mz = muzzle_pos
    bm = bmesh.new()
    add_lathe_y(bm, [
        (0.0, 0.0125), (0.014, 0.0138), (0.016, 0.0155),
        (0.068, 0.0155), (0.072, 0.0135)
    ], offset=(mx, my - 0.006, mz), segments=20)
    # Top/side baffle ribs
    for bi in range(3):
        add_box_to_bm(bm, (0.032, 0.008, 0.026), (mx, my + 0.016 + bi * 0.016, mz))
    obj_muzzle = finalize_mesh("Att_Muzzle_Comp", bm, mat_att_body, bevel_width=0.0012)
    bind_mesh_rigid_to_bone(obj_muzzle, arm_obj, "weapon_body")

    # 3. Att_Mag_Ext (Tubular shotgun mag extension OR sculpted FDE Polymer Extended Mag Basepad)
    ex, ey, ez = mag_ext_pos
    bm = bmesh.new()
    if mag_is_tube:
        # Machined steel tubular shotgun magazine extension + barrel clamp ring
        add_lathe_y(bm, [
            (-0.020, 0.0145), (-0.008, 0.0160), (0.004, 0.0142),
            (0.088, 0.0142), (0.098, 0.0154), (0.112, 0.0142), (0.116, 0.0110)
        ], offset=(ex, ey, ez), segments=24)
        obj_mag_ext = finalize_mesh("Att_Mag_Ext", bm, mat_att_body, bevel_width=0.0008)
    else:
        add_box_to_bm(bm, (0.034, 0.070, 0.044), (ex, ey, ez))
        add_box_to_bm(bm, (0.037, 0.074, 0.008), (ex, ey, ez - 0.022))
        obj_mag_ext = finalize_mesh("Att_Mag_Ext", bm, mat_att_tan, bevel_width=0.0025)
    target_mag_bone = mag_bone_name if mag_bone_name in arm_obj.data.bones else "weapon_body"
    bind_mesh_rigid_to_bone(obj_mag_ext, arm_obj, target_mag_bone)

    # 4. Att_Underbarrel_Laser (PEQ-15 style tactical side laser box + emitter lens)
    lx, ly, lz = laser_pos
    laser_parts = []
    bm = bmesh.new()
    add_box_to_bm(bm, (0.024, 0.078, 0.022), (lx, ly, lz))
    add_cyl_to_bm(bm, 0.006, 0.006, 0.014, (lx + 0.004, ly + 0.040, lz + 0.003), axis='Y', segments=12)
    add_cyl_to_bm(bm, 0.005, 0.005, 0.008, (lx, ly - 0.010, lz + 0.013), axis='Z', segments=10)
    laser_parts.append(finalize_mesh("Att_LaserBody", bm, mat_att_tan, bevel_width=0.0018))

    bm_l = bmesh.new()
    add_cyl_to_bm(bm_l, 0.0042, 0.0042, 0.004, (lx + 0.004, ly + 0.047, lz + 0.003), axis='Y', segments=10)
    laser_parts.append(finalize_mesh("Att_LaserEmitter", bm_l, mat_laser_dot, smooth=True))

    obj_laser = join_objects(laser_parts, "Att_Underbarrel_Laser")
    bind_mesh_rigid_to_bone(obj_laser, arm_obj, "weapon_body")

    return [obj_optic, obj_muzzle, obj_mag_ext, obj_laser]


def set_action_bezier_smooth(action: bpy.types.Action):
    """Applies smooth AUTO_CLAMPED Bezier interpolation to all F-curves in an Action (Blender 4/5 safe)."""
    fcurves = []
    if hasattr(action, "fcurves") and action.fcurves is not None:
        try:
            fcurves.extend(list(action.fcurves))
        except Exception:
            pass
    if hasattr(action, "layers"):
        for layer in action.layers:
            for strip in layer.strips:
                if hasattr(strip, "channelbags"):
                    for bag in strip.channelbags:
                        fcurves.extend(list(bag.fcurves))
    for fc in fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = 'BEZIER'
            kp.handle_left_type = 'AUTO_CLAMPED'
            kp.handle_right_type = 'AUTO_CLAMPED'


def save_blend(filepath: str):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=filepath)


def export_glb(filepath: str, def_bones_only: bool = True):
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
        export_def_bones=def_bones_only,
        export_all_influences=False,
    )


def render_studio_views(
    weapon_prefix: str,
    out_dir: str,
    arm_obj: bpy.types.Object,
    center_y: float = 0.12,
    hero_dist: float = 1.05,
    explode_offsets: dict = None,
    hide_objects_prefixes: tuple = ("Att_",),
):
    """Renders 3 studio presentation images (Hero 3/4, Alternate close-up, Exploded Rig)."""
    os.makedirs(out_dir, exist_ok=True)
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 720
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = 'PNG'

    hidden_saved = []
    for obj in bpy.data.objects:
        if any(obj.name.startswith(p) for p in hide_objects_prefixes):
            hidden_saved.append((obj, obj.hide_render))
            obj.hide_render = True

    nla_tracks = arm_obj.animation_data.nla_tracks if (arm_obj and arm_obj.animation_data) else []
    for tr in nla_tracks:
        tr.mute = True
    if arm_obj:
        for pb in arm_obj.pose.bones:
            pb.location = Vector((0, 0, 0))
            pb.rotation_euler = Euler((0, 0, 0), 'XYZ')
            pb.rotation_quaternion = (1, 0, 0, 0)
            pb.scale = Vector((1, 1, 1))
        bpy.context.view_layer.update()

    world = bpy.data.worlds.new(f"StudioWorld_{weapon_prefix}")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.042, 0.048, 0.062, 1.0)
        bg.inputs[1].default_value = 0.68

    def _add_light(name, loc, rot_deg, energy, color, size=1.8):
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
        _add_light("KeyLight", (1.8, center_y + 0.5, 1.4), (52, 0, 118), 340.0, (1.0, 0.96, 0.90), 2.0),
        _add_light("FillLight", (-1.8, center_y - 0.5, 1.0), (62, 0, -64), 210.0, (0.82, 0.90, 1.0), 2.4),
        _add_light("RimLight", (0.2, center_y + 1.6, 1.4), (50, 0, 175), 260.0, (0.96, 0.98, 1.0), 1.8),
        _add_light("UnderFill", (1.2, center_y, -1.0), (-55, 0, 100), 100.0, (0.75, 0.80, 0.90), 2.2),
    ]

    cam_data = bpy.data.cameras.new("StudioCam")
    cam_data.lens = 52.0
    cam_obj = bpy.data.objects.new("StudioCam", cam_data)
    scene.collection.objects.link(cam_obj)
    scene.camera = cam_obj

    def _aim(loc, target):
        cam_obj.location = Vector(loc)
        cam_obj.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()

    d = hero_dist * 1.38

    # 1. Hero 3/4 view
    _aim((d * 0.94, center_y - d * 0.34, 0.22), (0.0, center_y, -0.01))
    scene.render.filepath = os.path.join(out_dir, f"{weapon_prefix}_01_hero.png")
    bpy.ops.render.render(write_still=True)

    # 2. Alternate left/receiver close-up view
    _aim((-d * 0.72, center_y + d * 0.38, 0.22), (0.0, center_y + 0.04, 0.01))
    scene.render.filepath = os.path.join(out_dir, f"{weapon_prefix}_02_alternate.png")
    bpy.ops.render.render(write_still=True)

    # 3. Exploded parts view
    if explode_offsets and arm_obj is not None:
        for b_name, offset in explode_offsets.items():
            pb = arm_obj.pose.bones.get(b_name)
            if pb is not None:
                pb.location = Vector(offset)
        bpy.context.view_layer.update()
        _aim((d * 1.06, center_y - d * 0.20, 0.25), (0.0, center_y, -0.02))
        scene.render.filepath = os.path.join(out_dir, f"{weapon_prefix}_03_exploded_rig.png")
        bpy.ops.render.render(write_still=True)
        for pb in arm_obj.pose.bones:
            pb.location = Vector((0, 0, 0))
        bpy.context.view_layer.update()

    for tr in nla_tracks:
        tr.mute = False
    for obj, prev_h in hidden_saved:
        obj.hide_render = prev_h

    bpy.data.objects.remove(cam_obj, do_unlink=True)
    for lo in lights:
        bpy.data.objects.remove(lo, do_unlink=True)
