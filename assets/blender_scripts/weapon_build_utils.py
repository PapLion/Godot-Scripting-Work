"""Shared Blender 5.x utilities for high-detail FPS weapon modeling, PBR textures,
rigid armature rigging, NLA animation export (glTF/GLB), and studio presentation renders.
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
    """Writes a standard 8-bit RGB PNG file with zero external dependencies."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    raw = bytearray()
    stride = w * 3
    for y in range(h):
        raw.append(0)  # filter type 0
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


def _value_noise(u: float, v: float, freq_x: float, freq_y: float, seed: int) -> float:
    fx = u * freq_x
    fy = v * freq_y
    ix = int(math.floor(fx))
    iy = int(math.floor(fy))
    tx = fx - ix
    ty = fy - iy
    tx = tx * tx * (3.0 - 2.0 * tx)
    ty = ty * ty * (3.0 - 2.0 * ty)
    c00 = _hash2(ix, iy, seed)
    c10 = _hash2(ix + 1, iy, seed)
    c01 = _hash2(ix, iy + 1, seed)
    c11 = _hash2(ix + 1, iy + 1, seed)
    nx0 = c00 + (c10 - c00) * tx
    nx1 = c01 + (c11 - c01) * tx
    return nx0 + (nx1 - nx0) * ty


def _fbm(u: float, v: float, fx: float, fy: float, seed: int, octaves: int = 3) -> float:
    val = 0.0
    amp = 0.55
    total = 0.0
    for o in range(octaves):
        val += _value_noise(u, v, fx * (2 ** o), fy * (2 ** o), seed + o * 17) * amp
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
    tex_size: int = 256,
    emission_color: tuple = None,
    emission_strength: float = 0.0,
):
    """Creates a glTF-compatible Principled BSDF material backed by real PNG PBR textures."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()

    out = nt.nodes.new('ShaderNodeOutputMaterial')
    out.location = (420, 0)
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (120, 0)
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])

    bsdf.inputs['Metallic'].default_value = metallic
    if emission_color is not None and emission_strength > 0.0:
        if 'Emission Color' in bsdf.inputs:
            bsdf.inputs['Emission Color'].default_value = (*emission_color, 1.0)
            bsdf.inputs['Emission Strength'].default_value = emission_strength

    if pattern == 'solid':
        bsdf.inputs['Base Color'].default_value = (*base_color, 1.0)
        bsdf.inputs['Roughness'].default_value = roughness
        return mat

    albedo_rgb = bytearray(tex_size * tex_size * 3)
    rough_rgb = bytearray(tex_size * tex_size * 3)

    r0, g0, b0 = base_color[0], base_color[1], base_color[2]
    for y in range(tex_size):
        v = y / float(tex_size)
        for x in range(tex_size):
            u = x / float(tex_size)
            idx = (y * tex_size + x) * 3

            if pattern == 'wood':
                n = _fbm(u, v, 4.0, 22.0, seed, 3)
                ring = 0.5 + 0.5 * math.sin((v * 18.0 + n * 4.5) * math.pi)
                grain = _fbm(u, v, 36.0, 6.0, seed + 55, 2)
                mix = 0.70 + 0.34 * ring * 0.75 + 0.16 * (grain - 0.5)
                ar = max(0.0, min(1.0, r0 * mix))
                ag = max(0.0, min(1.0, g0 * mix * 0.94))
                ab = max(0.0, min(1.0, b0 * mix * 0.86))
                rv = max(0.24, min(0.85, roughness + (0.5 - ring) * 0.16))
            elif pattern == 'metal':
                brush = _fbm(u, v, 42.0, 5.0, seed, 3)
                wear = _fbm(u, v, 7.0, 7.0, seed + 33, 3)
                delta = (brush - 0.5) * 0.12 + (wear - 0.5) * 0.09
                ar = max(0.0, min(1.0, r0 + delta))
                ag = max(0.0, min(1.0, g0 + delta))
                ab = max(0.0, min(1.0, b0 + delta * 1.06))
                rv = max(0.18, min(0.85, roughness + (wear - 0.5) * 0.20 + (brush - 0.5) * 0.08))
            elif pattern == 'polymer':
                stipple = _hash2(x, y, seed)
                macro = _fbm(u, v, 9.0, 9.0, seed + 19, 2)
                delta = (stipple - 0.5) * 0.05 + (macro - 0.5) * 0.06
                ar = max(0.0, min(1.0, r0 + delta))
                ag = max(0.0, min(1.0, g0 + delta))
                ab = max(0.0, min(1.0, b0 + delta))
                rv = max(0.38, min(0.92, roughness + (stipple - 0.5) * 0.12))
            elif pattern == 'glass':
                grad = 0.75 + 0.25 * math.sin((u + v) * math.pi)
                ar = max(0.0, min(1.0, r0 * grad))
                ag = max(0.0, min(1.0, g0 * grad))
                ab = max(0.0, min(1.0, b0 * grad))
                rv = 0.08
            else:
                ar, ag, ab, rv = r0, g0, b0, roughness

            # Write direct sRGB values (avoid double gamma washout)
            albedo_rgb[idx] = int(round(max(0.0, min(1.0, ar)) * 255.0))
            albedo_rgb[idx + 1] = int(round(max(0.0, min(1.0, ag)) * 255.0))
            albedo_rgb[idx + 2] = int(round(max(0.0, min(1.0, ab)) * 255.0))

            rb = int(round(rv * 255.0))
            rough_rgb[idx] = rb
            rough_rgb[idx + 1] = rb
            rough_rgb[idx + 2] = rb

    albedo_path = os.path.join(TEXTURE_DIR, f"{name}_albedo.png")
    rough_path = os.path.join(TEXTURE_DIR, f"{name}_roughness.png")
    _write_png_rgb(albedo_path, tex_size, tex_size, albedo_rgb)
    _write_png_rgb(rough_path, tex_size, tex_size, rough_rgb)

    img_albedo = _load_packed_png(albedo_path, 'sRGB')
    img_rough = _load_packed_png(rough_path, 'Non-Color')

    tex_a = nt.nodes.new('ShaderNodeTexImage')
    tex_a.image = img_albedo
    tex_a.location = (-280, 140)
    nt.links.new(tex_a.outputs['Color'], bsdf.inputs['Base Color'])

    tex_r = nt.nodes.new('ShaderNodeTexImage')
    tex_r.image = img_rough
    tex_r.location = (-280, -140)
    nt.links.new(tex_r.outputs['Color'], bsdf.inputs['Roughness'])

    return mat


def _apply_box_uv(mesh: bpy.types.Mesh, scale: float = 2.5):
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
    uv_scale: float = 3.0,
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

    if smooth:
        es = obj.modifiers.new(name="EdgeSplit", type='EDGE_SPLIT')
        es.split_angle = math.radians(36.0)
        es.use_edge_angle = True
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_apply(modifier=es.name)

    return obj


def add_box_to_bm(
    bm: bmesh.types.BMesh,
    size: tuple,
    center: tuple = (0.0, 0.0, 0.0),
    rot_deg: tuple = (0.0, 0.0, 0.0),
):
    mat = (
        Matrix.Translation(Vector(center))
        @ Euler(tuple(math.radians(a) for a in rot_deg), 'XYZ').to_matrix().to_4x4()
        @ Matrix.Diagonal((size[0], size[1], size[2], 1.0))
    )
    bmesh.ops.create_cube(bm, size=1.0, matrix=mat)


def add_cyl_to_bm(
    bm: bmesh.types.BMesh,
    radius1: float,
    radius2: float,
    length: float,
    center: tuple = (0.0, 0.0, 0.0),
    axis: str = 'Y',
    segments: int = 20,
    rot_deg: tuple = (0.0, 0.0, 0.0),
):
    if axis == 'Y':
        base_rot = Euler((math.radians(90.0), 0.0, 0.0), 'XYZ').to_matrix().to_4x4()
    elif axis == 'X':
        base_rot = Euler((0.0, math.radians(90.0), 0.0), 'XYZ').to_matrix().to_4x4()
    else:
        base_rot = Matrix.Identity(4)

    extra_rot = Euler(tuple(math.radians(a) for a in rot_deg), 'XYZ').to_matrix().to_4x4()
    mat = Matrix.Translation(Vector(center)) @ extra_rot @ base_rot
    bmesh.ops.create_cone(
        bm,
        cap_ends=True,
        cap_tris=False,
        segments=segments,
        radius1=radius1,
        radius2=radius2,
        depth=length,
        matrix=mat,
    )


def add_lathe_y(
    bm: bmesh.types.BMesh,
    profile: list,
    offset: tuple = (0.0, 0.0, 0.0),
    segments: int = 24,
    cap_start: bool = True,
    cap_end: bool = True,
):
    ox, oy, oz = offset
    rings = []
    for y_val, rad in profile:
        ring = []
        for i in range(segments):
            ang = (i / float(segments)) * math.tau
            vx = ox + math.cos(ang) * rad
            vz = oz + math.sin(ang) * rad
            ring.append(bm.verts.new((vx, oy + y_val, vz)))
        rings.append(ring)

    for r_idx in range(len(rings) - 1):
        r0 = rings[r_idx]
        r1 = rings[r_idx + 1]
        for i in range(segments):
            ni = (i + 1) % segments
            bm.faces.new((r0[i], r0[ni], r1[ni], r1[i]))

    if cap_start and len(rings) > 0:
        bm.faces.new(list(reversed(rings[0])))
    if cap_end and len(rings) > 0:
        bm.faces.new(rings[-1])


def add_extruded_profile_x(
    bm: bmesh.types.BMesh,
    points_yz: list,
    width_x: float,
    x_center: float = 0.0,
    taper_end_scale: float = 1.0,
):
    half_x = width_x * 0.5
    left_v = []
    right_v = []
    for y, z in points_yz:
        left_v.append(bm.verts.new((x_center - half_x * taper_end_scale, y, z)))
        right_v.append(bm.verts.new((x_center + half_x * taper_end_scale, y, z)))

    n = len(points_yz)
    bm.faces.new(left_v)
    bm.faces.new(list(reversed(right_v)))
    for i in range(n):
        ni = (i + 1) % n
        bm.faces.new((left_v[i], right_v[i], right_v[ni], left_v[ni]))


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


def add_marker_empty(name: str, pos: tuple, parent_obj: bpy.types.Object):
    emp = bpy.data.objects.new(name, None)
    emp.empty_display_type = 'PLAIN_AXES'
    emp.empty_display_size = 0.03
    emp.location = Vector(pos)
    bpy.context.scene.collection.objects.link(emp)
    emp.parent = parent_obj
    return emp


def create_action_from_keyframes(arm_obj: bpy.types.Object, action_name: str, keyframes: dict, end_frame: int):
    if arm_obj.animation_data is None:
        arm_obj.animation_data_create()

    action = bpy.data.actions.new(name=action_name)
    arm_obj.animation_data.action = action

    for pb in arm_obj.pose.bones:
        pb.rotation_mode = 'XYZ'
        pb.location = Vector((0.0, 0.0, 0.0))
        pb.rotation_euler = Euler((0.0, 0.0, 0.0), 'XYZ')
        pb.scale = Vector((1.0, 1.0, 1.0))

    for bone_name, frames in keyframes.items():
        pb = arm_obj.pose.bones.get(bone_name)
        if pb is None:
            continue
        pb.rotation_mode = 'XYZ'
        for entry in frames:
            frame = entry[0]
            loc = entry[1] if len(entry) > 1 else None
            rot = entry[2] if len(entry) > 2 else None
            scl = entry[3] if len(entry) > 3 else None

            if loc is not None:
                pb.location = Vector(loc)
                pb.keyframe_insert(data_path='location', frame=frame)
            if rot is not None:
                pb.rotation_euler = Euler(tuple(math.radians(a) for a in rot), 'XYZ')
                pb.keyframe_insert(data_path='rotation_euler', frame=frame)
            if scl is not None:
                pb.scale = Vector(scl)
                pb.keyframe_insert(data_path='scale', frame=frame)

    track = arm_obj.animation_data.nla_tracks.new()
    track.name = action_name
    strip = track.strips.new(action_name, start=1, action=action)
    strip.frame_end = max(2, end_frame)
    arm_obj.animation_data.action = None

    for pb in arm_obj.pose.bones:
        pb.location = Vector((0.0, 0.0, 0.0))
        pb.rotation_euler = Euler((0.0, 0.0, 0.0), 'XYZ')
        pb.scale = Vector((1.0, 1.0, 1.0))

    return action


def export_glb(filepath: str):
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
        export_all_influences=False,
    )


def save_blend(filepath: str):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=filepath)


def render_studio_views(
    weapon_prefix: str,
    out_dir: str,
    arm_obj: bpy.types.Object,
    center_y: float = 0.12,
    hero_dist: float = 1.05,
    explode_offsets: dict = None,
):
    """Renders 3 studio portfolio images with clean rest pose (NLA temporarily muted)."""
    os.makedirs(out_dir, exist_ok=True)
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 720
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = 'PNG'

    # Mute NLA tracks during studio renders so rest pose is 100% assembled!
    nla_tracks = arm_obj.animation_data.nla_tracks if (arm_obj and arm_obj.animation_data) else []
    for tr in nla_tracks:
        tr.mute = True
    if arm_obj:
        for pb in arm_obj.pose.bones:
            pb.location = Vector((0.0, 0.0, 0.0))
            pb.rotation_euler = Euler((0.0, 0.0, 0.0), 'XYZ')
            pb.scale = Vector((1.0, 1.0, 1.0))
        bpy.context.view_layer.update()

    # Dark dramatic studio world background
    world = bpy.data.worlds.new("StudioWorld")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.04, 0.048, 0.062, 1.0)
        bg.inputs[1].default_value = 0.65

    def _add_light(name, loc, rot_deg, energy, color, size=1.6):
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
        _add_light("KeyLight", (1.8, center_y + 0.5, 1.4), (52, 0, 118), 320.0, (1.0, 0.96, 0.90), 2.0),
        _add_light("FillLight", (-1.8, center_y - 0.5, 1.0), (62, 0, -64), 190.0, (0.82, 0.90, 1.0), 2.4),
        _add_light("RimLight", (0.2, center_y + 1.6, 1.4), (50, 0, 175), 240.0, (0.96, 0.98, 1.0), 1.8),
        _add_light("UnderFill", (1.2, center_y, -1.0), (-55, 0, 100), 90.0, (0.75, 0.80, 0.90), 2.2),
    ]

    cam_data = bpy.data.cameras.new("StudioCam")
    cam_data.lens = 50.0
    cam_obj = bpy.data.objects.new("StudioCam", cam_data)
    scene.collection.objects.link(cam_obj)
    scene.camera = cam_obj

    def _aim_cam(loc, target):
        cam_obj.location = Vector(loc)
        direction = Vector(target) - Vector(loc)
        cam_obj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()

    d = hero_dist * 1.42

    # 1. Hero 3/4 view (full weapon cleanly framed)
    _aim_cam((d * 0.94, center_y - d * 0.36, 0.22), (0.0, center_y, -0.02))
    scene.render.filepath = os.path.join(out_dir, f"{weapon_prefix}_01_hero.png")
    bpy.ops.render.render(write_still=True)

    # 2. Alternate reverse/front 3/4 view
    _aim_cam((-d * 0.88, center_y + d * 0.44, 0.24), (0.0, center_y + 0.02, -0.01))
    scene.render.filepath = os.path.join(out_dir, f"{weapon_prefix}_02_alternate.png")
    bpy.ops.render.render(write_still=True)

    # 3. Exploded rig/parts presentation view
    if explode_offsets and arm_obj is not None:
        for b_name, offset in explode_offsets.items():
            pb = arm_obj.pose.bones.get(b_name)
            if pb is not None:
                pb.location = Vector(offset)
        bpy.context.view_layer.update()
        _aim_cam((d * 1.08, center_y - d * 0.20, 0.26), (0.0, center_y, -0.03))
        scene.render.filepath = os.path.join(out_dir, f"{weapon_prefix}_03_exploded_rig.png")
        bpy.ops.render.render(write_still=True)
        for pb in arm_obj.pose.bones:
            pb.location = Vector((0.0, 0.0, 0.0))
        bpy.context.view_layer.update()

    # Unmute NLA tracks so glTF exporter writes all animations cleanly!
    for tr in nla_tracks:
        tr.mute = False

    bpy.data.objects.remove(cam_obj, do_unlink=True)
    for lo in lights:
        bpy.data.objects.remove(lo, do_unlink=True)
