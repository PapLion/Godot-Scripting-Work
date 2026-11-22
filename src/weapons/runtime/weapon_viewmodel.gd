class_name WeaponViewmodel
extends Node3D
## Procedural 3D first-person weapon viewmodel with distinct silhouettes per weapon preset,
## visible attachment indicators, ADS alignment, sway, recoil kick, reload motion, and muzzle flash.

var _weapon_root: Node3D
var _muzzle_point: Marker3D
var _eject_point: Marker3D
var _muzzle_flash_mesh: MeshInstance3D
var _muzzle_flash_light: OmniLight3D

var _att_optic_node: Node3D
var _att_muzzle_node: Node3D
var _att_mag_node: Node3D
var _att_laser_node: Node3D

var _current_data: WeaponData
var _current_stats: EffectiveWeaponStats

var _ads_alpha: float = 0.0
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
	_rebuild_geometry(weapon.data)
	update_attachments(weapon)
	position = weapon.data.hip_position
	rotation_degrees = Vector3.ZERO
	_kick_offset_z = 0.0
	_kick_pitch_deg = 0.0


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


func trigger_fire_kick() -> void:
	if _current_data == null:
		return
	_kick_offset_z = minf(_kick_offset_z + _current_data.viewmodel_kickback_z, _current_data.viewmodel_kickback_z * 2.2)
	_kick_pitch_deg = minf(_kick_pitch_deg + _current_data.viewmodel_kick_pitch_deg, _current_data.viewmodel_kick_pitch_deg * 2.4)
	_muzzle_flash_timer = 0.045
	if _muzzle_flash_mesh != null:
		_muzzle_flash_mesh.visible = true
		_muzzle_flash_mesh.rotation.z = randf_range(0.0, TAU)
	if _muzzle_flash_light != null:
		_muzzle_flash_light.visible = true


func add_look_sway(mouse_delta: Vector2) -> void:
	_sway_offset.x = clampf(_sway_offset.x - mouse_delta.x * 0.00018, -0.025, 0.025)
	_sway_offset.y = clampf(_sway_offset.y + mouse_delta.y * 0.00018, -0.02, 0.02)


func update_transform(
	delta: float,
	ads_alpha: float,
	is_sprinting: bool,
	is_reloading: bool,
	is_equipping_or_unequipping: bool,
	move_ratio: float,
	is_grounded: bool
) -> void:
	if _current_data == null:
		return

	_ads_alpha = ads_alpha

	# Decay recoil kick & sway
	var kick_decay := 1.0 - exp(-18.0 * delta)
	_kick_offset_z = lerpf(_kick_offset_z, 0.0, kick_decay)
	_kick_pitch_deg = lerpf(_kick_pitch_deg, 0.0, kick_decay)
	_sway_offset = _sway_offset.lerp(Vector2.ZERO, 1.0 - exp(-10.0 * delta))

	# Reload & equip procedural pose weights
	var reload_target := 1.0 if is_reloading else 0.0
	var equip_target := 1.0 if is_equipping_or_unequipping else 0.0
	_reload_anim_alpha = lerpf(_reload_anim_alpha, reload_target, 1.0 - exp(-10.0 * delta))
	_equip_anim_alpha = lerpf(_equip_anim_alpha, equip_target, 1.0 - exp(-12.0 * delta))

	# Muzzle flash auto-off
	if _muzzle_flash_timer > 0.0:
		_muzzle_flash_timer -= delta
		if _muzzle_flash_timer <= 0.0:
			if _muzzle_flash_mesh != null:
				_muzzle_flash_mesh.visible = false
			if _muzzle_flash_light != null:
				_muzzle_flash_light.visible = false

	# Base position: Hip <-> ADS <-> Sprint
	var ads_pos := _current_stats.ads_position if _current_stats != null else _current_data.ads_position
	var base_pos := _current_data.hip_position.lerp(ads_pos, _ads_alpha)
	var base_rot := Vector3.ZERO

	if is_sprinting and _ads_alpha < 0.1 and not is_reloading:
		base_pos = base_pos.lerp(_current_data.sprint_position, 0.85)
		base_rot = _current_data.sprint_rotation_deg

	# Procedural walk bob (reduced during ADS)
	var bob_offset := Vector3.ZERO
	if is_grounded and move_ratio > 0.08:
		_bob_time += delta * (9.5 if is_sprinting else 6.8)
		var bob_amp := lerpf(0.011, 0.0018, _ads_alpha) * minf(move_ratio, 1.2)
		bob_offset.x = cos(_bob_time * 0.5) * bob_amp
		bob_offset.y = absf(sin(_bob_time)) * bob_amp * 0.9

	# Reload tilt + dip
	var reload_pos := Vector3(0.0, -0.09, 0.03) * _reload_anim_alpha
	var reload_rot := Vector3(14.0, -18.0, 26.0) * _reload_anim_alpha

	# Equip/unequip dip
	var equip_pos := Vector3(0.0, -0.24, 0.05) * _equip_anim_alpha
	var equip_rot := Vector3(-32.0, 0.0, 0.0) * _equip_anim_alpha

	var sway_scale := lerpf(1.0, 0.2, _ads_alpha)
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


func _build_muzzle_flash() -> void:
	_muzzle_flash_mesh = MeshInstance3D.new()
	var prism := BoxMesh.new()
	prism.size = Vector3(0.09, 0.09, 0.02)
	_muzzle_flash_mesh.mesh = prism
	_muzzle_flash_mesh.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var mat := StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.albedo_color = Color(1.0, 0.86, 0.42)
	_muzzle_flash_mesh.material_override = mat
	_muzzle_flash_mesh.visible = false
	_muzzle_point.add_child(_muzzle_flash_mesh)

	_muzzle_flash_light = OmniLight3D.new()
	_muzzle_flash_light.light_color = Color(1.0, 0.78, 0.35)
	_muzzle_flash_light.light_energy = 2.6
	_muzzle_flash_light.omni_range = 4.5
	_muzzle_flash_light.visible = false
	_muzzle_point.add_child(_muzzle_flash_light)


func _rebuild_geometry(data: WeaponData) -> void:
	for child in _weapon_root.get_children():
		if child != _muzzle_point and child != _eject_point:
			child.queue_free()

	var body_mat := _make_mat(data.accent_color, 0.45, 0.42)
	var dark_mat := _make_mat(Color(0.11, 0.12, 0.14), 0.65, 0.38)
	var grip_mat := _make_mat(Color(0.16, 0.16, 0.18), 0.15, 0.78)
	var sight_mat := _make_mat(Color(0.15, 0.95, 0.45), 0.0, 0.2, true)
	var att_accent := _make_mat(Color(0.75, 0.56, 0.22), 0.55, 0.35)

	match data.visual_preset:
		WeaponData.VisualPreset.ASSAULT_RIFLE:
			# Receiver, handguard, barrel, stock, magazine, iron sights
			_add_box(Vector3(0.068, 0.082, 0.36), Vector3(0.0, 0.0, -0.02), body_mat)
			_add_box(Vector3(0.056, 0.062, 0.26), Vector3(0.0, 0.004, -0.32), dark_mat)
			_add_cyl(0.013, 0.24, Vector3(0.0, 0.008, -0.52), dark_mat)
			_add_box(Vector3(0.048, 0.095, 0.18), Vector3(0.0, -0.015, 0.22), grip_mat)
			_add_box(Vector3(0.036, 0.11, 0.055), Vector3(0.0, -0.09, 0.06), grip_mat, Vector3(-16.0, 0.0, 0.0))
			_add_box(Vector3(0.042, 0.14, 0.072), Vector3(0.0, -0.105, -0.12), dark_mat, Vector3(8.0, 0.0, 0.0))
			# Front & rear iron sights
			_add_box(Vector3(0.012, 0.032, 0.014), Vector3(0.0, 0.058, -0.42), dark_mat)
			_add_box(Vector3(0.008, 0.008, 0.008), Vector3(0.0, 0.072, -0.42), sight_mat)
			_muzzle_point.position = Vector3(0.0, 0.008, -0.65)
			_eject_point.position = Vector3(0.045, 0.02, -0.04)
			_build_attachment_nodes(Vector3(0.0, 0.065, -0.04), Vector3(0.0, 0.008, -0.65), Vector3(0.0, -0.165, -0.13), Vector3(0.036, -0.005, -0.36), att_accent, sight_mat)

		WeaponData.VisualPreset.SHOTGUN:
			# Thick receiver, dual barrel + underbarrel tube, pump forend, stock
			_add_box(Vector3(0.074, 0.088, 0.34), Vector3(0.0, 0.0, 0.0), body_mat)
			_add_cyl(0.019, 0.56, Vector3(0.0, 0.022, -0.42), dark_mat)
			_add_cyl(0.016, 0.46, Vector3(0.0, -0.014, -0.37), dark_mat)
			_add_box(Vector3(0.064, 0.056, 0.22), Vector3(0.0, -0.016, -0.34), grip_mat)
			_add_box(Vector3(0.052, 0.092, 0.24), Vector3(0.0, -0.028, 0.24), grip_mat, Vector3(-8.0, 0.0, 0.0))
			_add_box(Vector3(0.01, 0.018, 0.012), Vector3(0.0, 0.052, -0.66), sight_mat)
			_muzzle_point.position = Vector3(0.0, 0.022, -0.71)
			_eject_point.position = Vector3(0.048, 0.02, -0.02)
			_build_attachment_nodes(Vector3(0.0, 0.068, -0.02), Vector3(0.0, 0.022, -0.71), Vector3(0.0, -0.014, -0.64), Vector3(0.04, -0.015, -0.46), att_accent, sight_mat)

		WeaponData.VisualPreset.PRECISION_RIFLE:
			# Long precision chassis, fluted barrel, cheek-rest stock, integrated scope rail
			_add_box(Vector3(0.066, 0.084, 0.42), Vector3(0.0, 0.0, -0.04), body_mat)
			_add_box(Vector3(0.052, 0.055, 0.32), Vector3(0.0, 0.0, -0.38), dark_mat)
			_add_cyl(0.014, 0.42, Vector3(0.0, 0.012, -0.70), dark_mat)
			_add_box(Vector3(0.05, 0.10, 0.24), Vector3(0.0, -0.012, 0.26), grip_mat)
			_add_box(Vector3(0.036, 0.11, 0.055), Vector3(0.0, -0.095, 0.08), grip_mat, Vector3(-14.0, 0.0, 0.0))
			_add_box(Vector3(0.044, 0.11, 0.088), Vector3(0.0, -0.09, -0.14), dark_mat)
			# Built-in DMR scope tube
			_add_cyl(0.024, 0.26, Vector3(0.0, 0.078, -0.06), dark_mat)
			_add_box(Vector3(0.008, 0.008, 0.008), Vector3(0.0, 0.078, -0.19), sight_mat)
			_muzzle_point.position = Vector3(0.0, 0.012, -0.92)
			_eject_point.position = Vector3(0.046, 0.02, -0.06)
			_build_attachment_nodes(Vector3(0.0, 0.105, -0.06), Vector3(0.0, 0.012, -0.92), Vector3(0.0, -0.145, -0.14), Vector3(0.038, -0.005, -0.44), att_accent, sight_mat)


func _build_attachment_nodes(
	optic_pos: Vector3,
	muzzle_pos: Vector3,
	mag_pos: Vector3,
	laser_pos: Vector3,
	accent_mat: StandardMaterial3D,
	glow_mat: StandardMaterial3D
) -> void:
	# Optic (Holo sight frame + glowing dot)
	_att_optic_node = Node3D.new()
	_att_optic_node.position = optic_pos
	_att_optic_node.visible = false
	_weapon_root.add_child(_att_optic_node)
	_add_box_to(_att_optic_node, Vector3(0.046, 0.012, 0.09), Vector3(0.0, -0.015, 0.0), accent_mat)
	_add_box_to(_att_optic_node, Vector3(0.008, 0.044, 0.07), Vector3(-0.02, 0.012, 0.0), accent_mat)
	_add_box_to(_att_optic_node, Vector3(0.008, 0.044, 0.07), Vector3(0.02, 0.012, 0.0), accent_mat)
	_add_box_to(_att_optic_node, Vector3(0.046, 0.008, 0.07), Vector3(0.0, 0.032, 0.0), accent_mat)
	var red_dot_mat := _make_mat(Color(1.0, 0.18, 0.18), 0.0, 0.2, true)
	_add_box_to(_att_optic_node, Vector3(0.005, 0.005, 0.005), Vector3(0.0, 0.012, -0.02), red_dot_mat)

	# Muzzle Compensator
	_att_muzzle_node = Node3D.new()
	_att_muzzle_node.position = muzzle_pos
	_att_muzzle_node.visible = false
	_weapon_root.add_child(_att_muzzle_node)
	_add_box_to(_att_muzzle_node, Vector3(0.038, 0.034, 0.11), Vector3(0.0, 0.0, -0.04), accent_mat)

	# Extended Magazine extension
	_att_mag_node = Node3D.new()
	_att_mag_node.position = mag_pos
	_att_mag_node.visible = false
	_weapon_root.add_child(_att_mag_node)
	_add_box_to(_att_mag_node, Vector3(0.048, 0.075, 0.078), Vector3.ZERO, accent_mat)

	# Underbarrel Tactical Laser
	_att_laser_node = Node3D.new()
	_att_laser_node.position = laser_pos
	_att_laser_node.visible = false
	_weapon_root.add_child(_att_laser_node)
	_add_box_to(_att_laser_node, Vector3(0.028, 0.028, 0.095), Vector3.ZERO, accent_mat)
	_add_box_to(_att_laser_node, Vector3(0.008, 0.008, 0.01), Vector3(0.0, 0.0, -0.052), glow_mat)


func _add_box(size: Vector3, pos: Vector3, mat: Material, rot_deg: Vector3 = Vector3.ZERO) -> void:
	_add_box_to(_weapon_root, size, pos, mat, rot_deg)


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


func _add_cyl(radius: float, height: float, pos: Vector3, mat: Material) -> void:
	var mi := MeshInstance3D.new()
	var mesh := CylinderMesh.new()
	mesh.top_radius = radius
	mesh.bottom_radius = radius
	mesh.height = height
	mesh.radial_segments = 12
	mi.mesh = mesh
	mi.material_override = mat
	mi.position = pos
	mi.rotation_degrees = Vector3(90.0, 0.0, 0.0)
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_weapon_root.add_child(mi)


func _make_mat(color: Color, metallic: float, roughness: float, unshaded: bool = false) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = color
	m.metallic = metallic
	m.roughness = roughness
	if unshaded:
		m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	return m
