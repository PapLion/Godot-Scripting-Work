class_name WeaponViewmodel
extends Node3D
## First-person weapon viewmodel supporting rigged, animated glTF/GLB assets (with procedural fallback).
## Synchronizes AnimationPlayer playback with WeaponManager events, aligns ADS sightlines,
## anchors muzzle flash / shell ejection / modular attachments to imported rig markers,
## and guarantees clean reset on reload interruption or weapon switching.

var _weapon_root: Node3D
var _model_instance: Node3D
var _anim_player: AnimationPlayer
var _skeleton: Skeleton3D
var _selector_bone_idx: int = -1
var _muzzle_point: Node3D
var _eject_point: Node3D
var _muzzle_flash_mesh: MeshInstance3D
var _muzzle_flash_light: OmniLight3D

var _att_optic_node: Node3D
var _att_muzzle_node: Node3D
var _att_mag_node: Node3D
var _att_laser_node: Node3D

var _current_data: WeaponData
var _current_stats: EffectiveWeaponStats
var _using_rigged_model: bool = false

var _ads_alpha: float = 0.0
var _shoulder_target: float = 1.0   # +1.0 = Right shoulder, -1.0 = Left shoulder
var _shoulder_blend: float = 1.0    # Smoothly interpolated [-1.0, +1.0]
var _selector_target_deg: float = 0.0
var _selector_current_deg: float = 0.0
var _selector_nudge: float = 0.0
var _kick_offset_z: float = 0.0
var _kick_pitch_deg: float = 0.0
var _sway_offset: Vector2 = Vector2.ZERO
var _bob_time: float = 0.0
var _muzzle_flash_timer: float = 0.0
var _reload_anim_alpha: float = 0.0
var _equip_anim_alpha: float = 0.0


func _ready() -> void:
	_weapon_root = Node3D.new()
	_weapon_root.name = "WeaponMeshRoot"
	add_child(_weapon_root)

	_muzzle_point = Marker3D.new()
	_muzzle_point.name = "MuzzlePoint"
	_weapon_root.add_child(_muzzle_point)

	_eject_point = Marker3D.new()
	_eject_point.name = "EjectPoint"
	_weapon_root.add_child(_eject_point)

	_build_muzzle_flash()


func configure_weapon(weapon: WeaponInstance) -> void:
	if weapon == null or weapon.data == null:
		return
	_current_data = weapon.data
	_current_stats = weapon.stats
	_clear_current_model()

	if weapon.data.viewmodel_scene != null:
		_mount_rigged_scene(weapon.data.viewmodel_scene)
	else:
		_using_rigged_model = false
		_rebuild_procedural_geometry(weapon.data)

	update_attachments(weapon)
	set_fire_mode_visual(weapon.get_current_fire_mode(), true)
	var hip := weapon.data.hip_position
	position = Vector3(hip.x * _shoulder_blend, hip.y, hip.z)
	rotation_degrees = Vector3.ZERO
	_kick_offset_z = 0.0
	_kick_pitch_deg = 0.0
	play_idle()


func set_shoulder_side(side: float, immediate: bool = false) -> void:
	_shoulder_target = 1.0 if side >= 0.0 else -1.0
	if immediate:
		_shoulder_blend = _shoulder_target


func get_shoulder_blend() -> float:
	return _shoulder_blend


func set_fire_mode_visual(mode: WeaponData.FireMode, immediate: bool = false) -> void:
	match mode:
		WeaponData.FireMode.SAFE:
			_selector_target_deg = 18.0
		WeaponData.FireMode.SEMI:
			_selector_target_deg = -16.0
		_:
			_selector_target_deg = 0.0
	if immediate:
		_selector_current_deg = _selector_target_deg
	else:
		_selector_nudge = 1.0


func update_attachments(weapon: WeaponInstance) -> void:
	if weapon == null:
		return
	_current_stats = weapon.stats
	if _att_optic_node != null:
		_att_optic_node.visible = weapon.has_attachment_in_slot(AttachmentData.Slot.OPTIC)
	if _att_muzzle_node != null:
		_att_muzzle_node.visible = weapon.has_attachment_in_slot(AttachmentData.Slot.MUZZLE)
	if _att_mag_node != null:
		_att_mag_node.visible = weapon.has_attachment_in_slot(AttachmentData.Slot.MAGAZINE)
	if _att_laser_node != null:
		_att_laser_node.visible = weapon.has_attachment_in_slot(AttachmentData.Slot.UNDERBARREL)


func play_idle() -> void:
	_play_rig_anim("idle", 1.0, 0.12, true)


func play_fire() -> void:
	_play_rig_anim("fire", 1.0, 0.02, false)


func play_bolt_action(target_duration: float) -> void:
	if _has_anim("bolt_action"):
		_play_rig_anim_to_duration("bolt_action", target_duration, 0.05)
	elif _has_anim("bolt"):
		_play_rig_anim_to_duration("bolt", target_duration, 0.05)


func get_hand_anchors() -> Dictionary:
	var anchors: Dictionary = {}
	if _model_instance == null:
		return anchors
	for marker_name in ["GripPrimary", "GripSupport", "MagInteract", "BoltInteract", "ShellPort", "ADSRef"]:
		var n := _find_node_by_name(_model_instance, marker_name)
		if n is Node3D:
			anchors[marker_name] = (n as Node3D).position
	return anchors


func play_reload_magazine(target_duration: float) -> void:
	_play_rig_anim_to_duration("reload", target_duration, 0.08)


func play_shell_start(target_duration: float) -> void:
	_play_rig_anim_to_duration("shell_start", target_duration, 0.06)


func play_shell_insert(target_duration: float) -> void:
	_play_rig_anim_to_duration("shell_insert", target_duration, 0.03)


func play_shell_end(target_duration: float) -> void:
	_play_rig_anim_to_duration("shell_end", target_duration, 0.05)


func play_reload_interrupt() -> void:
	if _has_anim("reload_interrupt"):
		_play_rig_anim("reload_interrupt", 1.2, 0.04, false)
	else:
		# Snap cleanly back to idle rest pose so no magazine or shell remains detached
		_play_rig_anim("idle", 1.0, 0.06, true)


func play_equip(target_duration: float) -> void:
	_play_rig_anim_to_duration("equip", target_duration, 0.04)


func play_unequip(target_duration: float) -> void:
	_play_rig_anim_to_duration("unequip", target_duration, 0.04)


func get_animation_names() -> PackedStringArray:
	if _anim_player == null:
		return PackedStringArray()
	return _anim_player.get_animation_list()


func get_current_animation() -> String:
	if _anim_player == null:
		return ""
	return _anim_player.current_animation


func trigger_fire_kick() -> void:
	if _current_data == null:
		return
	var kick_scale := 0.55 if _using_rigged_model else 1.0
	_kick_offset_z = minf(_kick_offset_z + _current_data.viewmodel_kickback_z * kick_scale, _current_data.viewmodel_kickback_z * 2.0)
	_kick_pitch_deg = minf(_kick_pitch_deg + _current_data.viewmodel_kick_pitch_deg * kick_scale, _current_data.viewmodel_kick_pitch_deg * 2.0)
	_muzzle_flash_timer = 0.045
	if _muzzle_flash_mesh != null:
		_muzzle_flash_mesh.visible = true
		_muzzle_flash_mesh.rotation.z = randf_range(0.0, TAU)
		var f_scale := 1.45 if _current_data.visual_preset == WeaponData.VisualPreset.SHOTGUN else (1.25 if _current_data.visual_preset == WeaponData.VisualPreset.PRECISION_RIFLE else 1.0)
		_muzzle_flash_mesh.scale = Vector3.ONE * f_scale
	if _muzzle_flash_light != null:
		_muzzle_flash_light.visible = true
		_muzzle_flash_light.light_energy = 3.8 if _current_data.visual_preset == WeaponData.VisualPreset.SHOTGUN else 2.8
	play_fire()


func add_look_sway(mouse_delta: Vector2) -> void:
	_sway_offset.x = clampf(_sway_offset.x - mouse_delta.x * 0.00016, -0.022, 0.022)
	_sway_offset.y = clampf(_sway_offset.y + mouse_delta.y * 0.00016, -0.018, 0.018)


func update_transform(
	delta: float,
	ads_alpha: float,
	is_sprinting: bool,
	is_reloading: bool,
	is_equipping_or_unequipping: bool,
	move_ratio: float,
	is_grounded: bool,
	is_cycling_bolt: bool = false,
	lean_amount: float = 0.0
) -> void:
	if _current_data == null:
		return

	_ads_alpha = ads_alpha
	# Smooth shoulder-side transition (-1.0 Left <-> +1.0 Right) without negative scaling
	_shoulder_blend = lerpf(_shoulder_blend, _shoulder_target, 1.0 - exp(-10.5 * delta))
	if absf(_shoulder_blend - _shoulder_target) < 0.002:
		_shoulder_blend = _shoulder_target
	var shoulder_mid_arc := maxf(0.0, 1.0 - absf(_shoulder_blend)) # peaks at 1.0 mid-cross

	# Animate AK-47 physical selector lever bone smoothly when present
	_selector_current_deg = lerpf(_selector_current_deg, _selector_target_deg, 1.0 - exp(-18.0 * delta))
	_selector_nudge = lerpf(_selector_nudge, 0.0, 1.0 - exp(-14.0 * delta))
	if _skeleton != null and _selector_bone_idx >= 0:
		_skeleton.set_bone_pose_rotation(
			_selector_bone_idx,
			Quaternion.from_euler(Vector3(deg_to_rad(_selector_current_deg), 0.0, 0.0))
		)

	# Hide 3D sniper viewmodel at full scope-in so HUD mil-dot scope overlay provides clear sight picture,
	# but keep it visible while cycling the bolt so the right-hand bolt animation is clearly shown!
	if _current_data.visual_preset == WeaponData.VisualPreset.PRECISION_RIFLE:
		visible = (_ads_alpha < 0.78) or is_reloading or is_equipping_or_unequipping or is_cycling_bolt
	else:
		visible = true

	var kick_decay := 1.0 - exp(-18.0 * delta)
	_kick_offset_z = lerpf(_kick_offset_z, 0.0, kick_decay)
	_kick_pitch_deg = lerpf(_kick_pitch_deg, 0.0, kick_decay)
	_sway_offset = _sway_offset.lerp(Vector2.ZERO, 1.0 - exp(-10.0 * delta))

	# Procedural fallback weights (zeroed when rigged AnimationPlayer owns reload/equip)
	var reload_target := 0.0 if _using_rigged_model else (1.0 if is_reloading else 0.0)
	var equip_target := 0.0 if _using_rigged_model else (1.0 if is_equipping_or_unequipping else 0.0)
	_reload_anim_alpha = lerpf(_reload_anim_alpha, reload_target, 1.0 - exp(-10.0 * delta))
	_equip_anim_alpha = lerpf(_equip_anim_alpha, equip_target, 1.0 - exp(-12.0 * delta))

	if _muzzle_flash_timer > 0.0:
		_muzzle_flash_timer -= delta
		if _muzzle_flash_timer <= 0.0:
			if _muzzle_flash_mesh != null:
				_muzzle_flash_mesh.visible = false
			if _muzzle_flash_light != null:
				_muzzle_flash_light.visible = false

	# Keep rigged weapons returning smoothly to idle when non-looping anims end
	if _using_rigged_model and _anim_player != null and not _anim_player.is_playing() and not is_reloading and not is_equipping_or_unequipping and not is_cycling_bolt:
		play_idle()

	# Side-aware hip & sprint transforms (ADS always converges cleanly to X=0 center!)
	var hip_sided := Vector3(_current_data.hip_position.x * _shoulder_blend, _current_data.hip_position.y, _current_data.hip_position.z)
	var ads_pos := _current_stats.ads_position if _current_stats != null else _current_data.ads_position
	var base_pos := hip_sided.lerp(ads_pos, _ads_alpha)
	var base_rot := Vector3.ZERO

	# Subtle chest-dip arc during shoulder switch (reduced in ADS so sightline stays stable)
	var arc_weight := lerpf(1.0, 0.25, _ads_alpha)
	base_pos += Vector3(0.0, -0.045 * shoulder_mid_arc * arc_weight, 0.025 * shoulder_mid_arc * arc_weight)
	base_rot.z += -9.0 * shoulder_mid_arc * _shoulder_target * arc_weight

	# Subtle left-shoulder yaw cant (keeps weapon barrel converging cleanly toward crosshair center)
	base_rot.y += lerpf(1.8 * (1.0 - _shoulder_blend) * 0.5, 0.0, _ads_alpha)

	# Tactile selector switch roll nudge
	base_rot += Vector3(2.2, -3.5, 5.5) * _selector_nudge * lerpf(1.0, 0.25, _ads_alpha)

	# Subtle tactical lean stabilization roll (keeps weapon grounded while corner peeking)
	base_rot.z += -4.2 * lean_amount * lerpf(1.0, 0.2, _ads_alpha)

	if is_sprinting and _ads_alpha < 0.1 and not is_reloading and not is_equipping_or_unequipping:
		var sp := _current_data.sprint_position
		var sprint_sided := Vector3(sp.x * _shoulder_blend, sp.y, sp.z)
		base_pos = base_pos.lerp(sprint_sided, 0.85)
		var sr := _current_data.sprint_rotation_deg
		base_rot = Vector3(sr.x, sr.y * _shoulder_blend, sr.z * _shoulder_blend)

	var bob_offset := Vector3.ZERO
	if is_grounded and move_ratio > 0.08:
		_bob_time += delta * (9.5 if is_sprinting else 6.8)
		var bob_amp := lerpf(0.010, 0.0015, _ads_alpha) * minf(move_ratio, 1.2)
		bob_offset.x = cos(_bob_time * 0.5) * bob_amp
		bob_offset.y = absf(sin(_bob_time)) * bob_amp * 0.85

	var reload_pos := Vector3(0.0, -0.09, 0.03) * _reload_anim_alpha
	var reload_rot := Vector3(14.0, -18.0, 26.0) * _reload_anim_alpha
	var equip_pos := Vector3(0.0, -0.24, 0.05) * _equip_anim_alpha
	var equip_rot := Vector3(-32.0, 0.0, 0.0) * _equip_anim_alpha

	var sway_scale := lerpf(1.0, 0.18, _ads_alpha)
	var sway_vec := Vector3(_sway_offset.x * sway_scale, _sway_offset.y * sway_scale, 0.0)
	var kick_vec := Vector3(0.0, 0.0, _kick_offset_z)

	var target_pos := base_pos + bob_offset + sway_vec + kick_vec + reload_pos + equip_pos
	var target_rot := base_rot + reload_rot + equip_rot + Vector3(_kick_pitch_deg, 0.0, 0.0)

	var blend := 1.0 - exp(-22.0 * delta)
	position = position.lerp(target_pos, blend)
	rotation_degrees = rotation_degrees.lerp(target_rot, blend)


func get_muzzle_global_position() -> Vector3:
	if _muzzle_point != null:
		return _muzzle_point.global_position
	return global_position


func get_eject_global_transform() -> Transform3D:
	if _eject_point != null:
		return _eject_point.global_transform
	return global_transform


func _clear_current_model() -> void:
	_anim_player = null
	_skeleton = null
	_selector_bone_idx = -1
	_model_instance = null
	for child in _weapon_root.get_children():
		if child != _muzzle_point and child != _eject_point:
			child.queue_free()


func _mount_rigged_scene(scene: PackedScene) -> void:
	_model_instance = scene.instantiate() as Node3D
	if _model_instance == null:
		_using_rigged_model = false
		return

	_using_rigged_model = true
	_weapon_root.add_child(_model_instance)
	_disable_shadows_recursive(_model_instance)
	_anim_player = _find_animation_player(_model_instance)
	_skeleton = _find_skeleton(_model_instance)
	if _skeleton != null:
		_selector_bone_idx = _skeleton.find_bone("selector")

	# Anchor muzzle & eject points to imported Blender markers
	var m_node := _find_node_by_name(_model_instance, "MuzzlePoint")
	_muzzle_point.position = m_node.position if m_node is Node3D else Vector3(0.0, 0.02, -0.60)
	var e_node := _find_node_by_name(_model_instance, "EjectPoint")
	_eject_point.position = e_node.position if e_node is Node3D else Vector3(0.035, 0.03, -0.06)

	# Anchor attachment indicators to imported Blender mount markers
	var opt_pos := _get_marker_pos(_model_instance, "OpticMount", Vector3(0.0, 0.06, -0.04))
	var muz_pos := _get_marker_pos(_model_instance, "MuzzleMount", _muzzle_point.position)
	var mag_pos := _get_marker_pos(_model_instance, "MagMount", Vector3(0.0, -0.14, -0.10))
	var las_pos := _get_marker_pos(_model_instance, "LaserMount", Vector3(0.028, 0.01, -0.32))

	var att_accent := _make_mat(Color(0.18, 0.19, 0.21), 0.72, 0.34)
	var glow_mat := _make_mat(Color(0.15, 0.95, 0.45), 0.0, 0.2, true)
	_build_attachment_nodes(opt_pos, muz_pos, mag_pos, las_pos, att_accent, glow_mat)


func _get_marker_pos(root_node: Node, marker_name: String, fallback: Vector3) -> Vector3:
	var n := _find_node_by_name(root_node, marker_name)
	if n is Node3D:
		return (n as Node3D).position
	return fallback


func _disable_shadows_recursive(node: Node) -> void:
	if node is GeometryInstance3D:
		(node as GeometryInstance3D).cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	for child in node.get_children():
		_disable_shadows_recursive(child)


func _find_animation_player(node: Node) -> AnimationPlayer:
	if node is AnimationPlayer:
		return node as AnimationPlayer
	for child in node.get_children():
		var found := _find_animation_player(child)
		if found != null:
			return found
	return null


func _find_skeleton(node: Node) -> Skeleton3D:
	if node is Skeleton3D:
		return node as Skeleton3D
	for child in node.get_children():
		var found := _find_skeleton(child)
		if found != null:
			return found
	return null


func _find_node_by_name(node: Node, target_name: String) -> Node:
	if node.name == target_name:
		return node
	for child in node.get_children():
		var found := _find_node_by_name(child, target_name)
		if found != null:
			return found
	return null


func _has_anim(anim_name: String) -> bool:
	return _anim_player != null and _anim_player.has_animation(anim_name)


func _play_rig_anim(anim_name: String, speed: float, blend: float, loop: bool) -> void:
	if not _has_anim(anim_name):
		return
	var anim := _anim_player.get_animation(anim_name)
	if anim != null:
		anim.loop_mode = Animation.LOOP_LINEAR if loop else Animation.LOOP_NONE
	_anim_player.play(anim_name, blend, speed, false)
	if not loop:
		_anim_player.seek(0.0, true)


func _play_rig_anim_to_duration(anim_name: String, target_duration: float, blend: float) -> void:
	if not _has_anim(anim_name):
		return
	var anim := _anim_player.get_animation(anim_name)
	var speed := 1.0
	if anim != null and anim.length > 0.01 and target_duration > 0.05:
		speed = clampf(anim.length / target_duration, 0.4, 3.0)
	_play_rig_anim(anim_name, speed, blend, false)


func _build_muzzle_flash() -> void:
	# Multi-layered crossed star muzzle flash (crisp core + radial flame fins)
	_muzzle_flash_mesh = MeshInstance3D.new()
	var core := BoxMesh.new()
	core.size = Vector3(0.045, 0.045, 0.065)
	_muzzle_flash_mesh.mesh = core
	_muzzle_flash_mesh.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var mat := StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.albedo_color = Color(1.0, 0.90, 0.48, 0.92)
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	_muzzle_flash_mesh.material_override = mat

	for ang in [0.0, 60.0, 120.0]:
		var fin := MeshInstance3D.new()
		var fm := BoxMesh.new()
		fm.size = Vector3(0.14, 0.018, 0.045)
		fin.mesh = fm
		fin.material_override = mat
		fin.rotation_degrees.z = ang
		fin.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		_muzzle_flash_mesh.add_child(fin)

	_muzzle_flash_mesh.visible = false
	_muzzle_point.add_child(_muzzle_flash_mesh)

	_muzzle_flash_light = OmniLight3D.new()
	_muzzle_flash_light.light_color = Color(1.0, 0.80, 0.36)
	_muzzle_flash_light.light_energy = 2.8
	_muzzle_flash_light.omni_range = 5.0
	_muzzle_flash_light.visible = false
	_muzzle_point.add_child(_muzzle_flash_light)


func _rebuild_procedural_geometry(data: WeaponData) -> void:
	var body_mat := _make_mat(data.accent_color, 0.45, 0.42)
	var dark_mat := _make_mat(Color(0.11, 0.12, 0.14), 0.65, 0.38)
	var sight_mat := _make_mat(Color(0.15, 0.95, 0.45), 0.0, 0.2, true)
	var att_accent := _make_mat(Color(0.75, 0.56, 0.22), 0.55, 0.35)
	_add_box_to(_weapon_root, Vector3(0.06, 0.08, 0.45), Vector3(0.0, 0.0, -0.15), body_mat)
	_muzzle_point.position = Vector3(0.0, 0.01, -0.45)
	_eject_point.position = Vector3(0.04, 0.02, -0.04)
	_build_attachment_nodes(Vector3(0.0, 0.06, -0.04), Vector3(0.0, 0.01, -0.45), Vector3(0.0, -0.12, -0.12), Vector3(0.036, 0.0, -0.30), att_accent, sight_mat)


func _build_attachment_nodes(
	optic_pos: Vector3,
	muzzle_pos: Vector3,
	mag_pos: Vector3,
	laser_pos: Vector3,
	accent_mat: StandardMaterial3D,
	glow_mat: StandardMaterial3D
) -> void:
	_att_optic_node = Node3D.new()
	_att_optic_node.position = optic_pos
	_att_optic_node.visible = false
	_weapon_root.add_child(_att_optic_node)
	_add_box_to(_att_optic_node, Vector3(0.040, 0.010, 0.078), Vector3(0.0, 0.005, 0.0), accent_mat)
	_add_box_to(_att_optic_node, Vector3(0.006, 0.036, 0.056), Vector3(-0.018, 0.024, 0.0), accent_mat)
	_add_box_to(_att_optic_node, Vector3(0.006, 0.036, 0.056), Vector3(0.018, 0.024, 0.0), accent_mat)
	_add_box_to(_att_optic_node, Vector3(0.040, 0.006, 0.056), Vector3(0.0, 0.042, 0.0), accent_mat)
	var red_dot_mat := _make_mat(Color(1.0, 0.16, 0.16), 0.0, 0.2, true)
	_add_box_to(_att_optic_node, Vector3(0.004, 0.004, 0.004), Vector3(0.0, 0.024, -0.012), red_dot_mat)

	_att_muzzle_node = Node3D.new()
	_att_muzzle_node.position = muzzle_pos
	_att_muzzle_node.visible = false
	_weapon_root.add_child(_att_muzzle_node)
	_add_box_to(_att_muzzle_node, Vector3(0.032, 0.028, 0.088), Vector3(0.0, 0.0, -0.042), accent_mat)

	_att_mag_node = Node3D.new()
	_att_mag_node.position = mag_pos
	_att_mag_node.visible = false
	_weapon_root.add_child(_att_mag_node)
	_add_box_to(_att_mag_node, Vector3(0.036, 0.065, 0.068), Vector3.ZERO, accent_mat)

	_att_laser_node = Node3D.new()
	_att_laser_node.position = laser_pos
	_att_laser_node.visible = false
	_weapon_root.add_child(_att_laser_node)
	_add_box_to(_att_laser_node, Vector3(0.022, 0.022, 0.082), Vector3.ZERO, accent_mat)
	_add_box_to(_att_laser_node, Vector3(0.006, 0.006, 0.008), Vector3(0.0, 0.0, -0.044), glow_mat)


func _add_box_to(parent: Node3D, size: Vector3, pos: Vector3, mat: Material, rot_deg: Vector3 = Vector3.ZERO) -> void:
	var mi := MeshInstance3D.new()
	var mesh := BoxMesh.new()
	mesh.size = size
	mi.mesh = mesh
	mi.material_override = mat
	mi.position = pos
	mi.rotation_degrees = rot_deg
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	parent.add_child(mi)


func _make_mat(color: Color, metallic: float, roughness: float, unshaded: bool = false) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = color
	m.metallic = metallic
	m.roughness = roughness
	if unshaded:
		m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	return m
