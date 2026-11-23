class_name WeaponViewmodel
extends Node3D
## First-person weapon viewmodel with strict single-root hierarchy and Blender-first animation ownership.
##
## Architecture:
##   WeaponViewmodel (Node3D)
##     └── RuntimeOffsetPivot (Node3D: Godot owns lightweight ADS, sway, bob, kick, shoulder, lean)
##           └── <Imported GLB Scene> (Blender owns all poses, reloads, bolt cycling, shell loading)
##                 └── Skeleton3D
##                       ├── Att_Optic_Holo / Att_Muzzle_Comp / Att_Mag_Ext / Att_Underbarrel_Laser
##                       │     (rigidly skinned to weapon_body / magazine bones -> zero floating parts!)
##                       └── WeaponBodyBoneAttachment (BoneAttachment3D -> "weapon_body")
##                             ├── MuzzlePoint (MuzzleFlashMesh + MuzzleFlashLight)
##                             └── EjectPoint

var _runtime_pivot: Node3D
var _model_instance: Node3D
var _anim_player: AnimationPlayer
var _skeleton: Skeleton3D
var _body_bone_attachment: BoneAttachment3D
var _selector_bone_idx: int = -1
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
var _fallback_reload_alpha: float = 0.0
var _fallback_equip_alpha: float = 0.0


func _ready() -> void:
	_runtime_pivot = Node3D.new()
	_runtime_pivot.name = "RuntimeOffsetPivot"
	add_child(_runtime_pivot)

	_muzzle_point = Marker3D.new()
	_muzzle_point.name = "MuzzlePoint"
	_runtime_pivot.add_child(_muzzle_point)

	_eject_point = Marker3D.new()
	_eject_point.name = "EjectPoint"
	_runtime_pivot.add_child(_eject_point)

	_build_muzzle_flash()


func configure_weapon(weapon: WeaponInstance) -> void:
	if weapon == null or weapon.data == null:
		return
	_ensure_initialized()
	_current_data = weapon.data
	_current_stats = weapon.stats
	_clear_current_model()

	if weapon.data.viewmodel_scene != null:
		_mount_rigged_scene(weapon.data.viewmodel_scene)
	else:
		_using_rigged_model = false
		_rebuild_procedural_fallback(weapon.data)

	update_attachments(weapon)
	set_fire_mode_visual(weapon.get_current_fire_mode(), true)

	var hip := weapon.data.hip_position
	position = Vector3(hip.x * _shoulder_blend, hip.y, hip.z)
	rotation_degrees = Vector3.ZERO
	_runtime_pivot.position = Vector3.ZERO
	_runtime_pivot.rotation_degrees = Vector3.ZERO
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
	var target_anim := "ads_idle" if (_ads_alpha >= 0.65 and _has_anim("ads_idle")) else "idle"
	_play_rig_anim(target_anim, 1.0, 0.14, true)


func play_fire() -> void:
	_play_rig_anim("fire", 1.0, 0.02, false)


func play_bolt_action(target_duration: float) -> void:
	if _has_anim("bolt_action"):
		_play_rig_anim_to_duration("bolt_action", target_duration, 0.06)
	elif _has_anim("bolt"):
		_play_rig_anim_to_duration("bolt", target_duration, 0.06)


func play_reload_magazine(target_duration: float, is_empty: bool = false) -> void:
	if is_empty and _has_anim("reload_empty"):
		_play_rig_anim_to_duration("reload_empty", target_duration, 0.08)
	else:
		_play_rig_anim_to_duration("reload", target_duration, 0.08)


func play_shell_start(target_duration: float) -> void:
	_play_rig_anim_to_duration("shell_start", target_duration, 0.06)


func play_shell_insert(target_duration: float) -> void:
	_play_rig_anim_to_duration("shell_insert", target_duration, 0.03)


func play_shell_end(target_duration: float) -> void:
	_play_rig_anim_to_duration("shell_end", target_duration, 0.06)


func play_reload_interrupt() -> void:
	if _has_anim("reload_interrupt"):
		_play_rig_anim("reload_interrupt", 1.15, 0.04, false)
	else:
		_play_rig_anim("idle", 1.0, 0.08, true)


func play_equip(target_duration: float) -> void:
	_play_rig_anim_to_duration("equip", target_duration, 0.04)


func play_unequip(target_duration: float) -> void:
	_play_rig_anim_to_duration("unequip", target_duration, 0.05)


func get_animation_names() -> PackedStringArray:
	if _anim_player == null:
		return PackedStringArray()
	return _anim_player.get_animation_list()


func get_current_animation() -> String:
	if _anim_player == null:
		return ""
	return _anim_player.current_animation


func get_skeleton() -> Skeleton3D:
	return _skeleton


func get_body_bone_attachment() -> BoneAttachment3D:
	return _body_bone_attachment


func get_runtime_pivot() -> Node3D:
	return _runtime_pivot


func get_attachment_nodes() -> Dictionary:
	return {
		"optic": _att_optic_node,
		"muzzle": _att_muzzle_node,
		"magazine": _att_mag_node,
		"underbarrel": _att_laser_node,
	}


func get_hand_anchors() -> Dictionary:
	var anchors: Dictionary = {}
	if _model_instance == null:
		return anchors
	for marker_name in ["GripPrimary", "GripSupport", "MagInteract", "BoltInteract", "ShellPort", "ADSRef"]:
		var n := _find_node_by_name(_model_instance, marker_name)
		if n is Node3D:
			var skel_xf := _get_transform_relative_to_skeleton(n as Node3D)
			anchors[marker_name] = skel_xf.origin
	return anchors


func trigger_fire_kick() -> void:
	if _current_data == null:
		return
	# Compact outer runtime kickback complements Blender's authored fire animation without double-kicking
	var kick_scale := 0.42 if _using_rigged_model else 1.0
	_kick_offset_z = minf(_kick_offset_z + _current_data.viewmodel_kickback_z * kick_scale, _current_data.viewmodel_kickback_z * 1.65)
	_kick_pitch_deg = minf(_kick_pitch_deg + _current_data.viewmodel_kick_pitch_deg * kick_scale, _current_data.viewmodel_kick_pitch_deg * 1.65)
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
	_sway_offset.x = clampf(_sway_offset.x - mouse_delta.x * 0.00014, -0.020, 0.020)
	_sway_offset.y = clampf(_sway_offset.y + mouse_delta.y * 0.00014, -0.016, 0.016)


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
	if _current_data == null or _runtime_pivot == null:
		return

	_ads_alpha = ads_alpha

	# Smooth shoulder-side transition (-1.0 Left <-> +1.0 Right) without negative scaling
	_shoulder_blend = lerpf(_shoulder_blend, _shoulder_target, 1.0 - exp(-10.5 * delta))
	if absf(_shoulder_blend - _shoulder_target) < 0.002:
		_shoulder_blend = _shoulder_target
	var shoulder_mid_arc := maxf(0.0, 1.0 - absf(_shoulder_blend))

	# Smoothly rotate physical AK-47 selector lever bone (not keyframed in Blender actions)
	_selector_current_deg = lerpf(_selector_current_deg, _selector_target_deg, 1.0 - exp(-18.0 * delta))
	_selector_nudge = lerpf(_selector_nudge, 0.0, 1.0 - exp(-14.0 * delta))
	if _skeleton != null and _selector_bone_idx >= 0:
		_skeleton.set_bone_pose_rotation(
			_selector_bone_idx,
			Quaternion.from_euler(Vector3(deg_to_rad(_selector_current_deg), 0.0, 0.0))
		)

	# Hide 3D sniper viewmodel at full scope-in so HUD mil-dot scope overlay provides clear sight picture,
	# while keeping it visible during reload, equip, and bolt cycling!
	if _current_data.visual_preset == WeaponData.VisualPreset.PRECISION_RIFLE:
		visible = (_ads_alpha < 0.78) or is_reloading or is_equipping_or_unequipping or is_cycling_bolt
	else:
		visible = true

	var kick_decay := 1.0 - exp(-19.0 * delta)
	_kick_offset_z = lerpf(_kick_offset_z, 0.0, kick_decay)
	_kick_pitch_deg = lerpf(_kick_pitch_deg, 0.0, kick_decay)
	_sway_offset = _sway_offset.lerp(Vector2.ZERO, 1.0 - exp(-11.0 * delta))

	if _muzzle_flash_timer > 0.0:
		_muzzle_flash_timer -= delta
		if _muzzle_flash_timer <= 0.0:
			if _muzzle_flash_mesh != null:
				_muzzle_flash_mesh.visible = false
			if _muzzle_flash_light != null:
				_muzzle_flash_light.visible = false

	# Keep rigged weapons cleanly in idle / ads_idle when authored non-looping clips finish
	if _using_rigged_model and _anim_player != null and not is_reloading and not is_equipping_or_unequipping and not is_cycling_bolt:
		var desired_idle := "ads_idle" if (_ads_alpha >= 0.65 and _has_anim("ads_idle")) else "idle"
		if not _anim_player.is_playing():
			_play_rig_anim(desired_idle, 1.0, 0.14, true)
		elif _anim_player.current_animation in ["idle", "ads_idle"] and _anim_player.current_animation != desired_idle:
			_play_rig_anim(desired_idle, 1.0, 0.14, true)

	# Outer runtime positioning on RuntimeOffsetPivot (never competes with imported Skeleton3D bone animations!)
	var hip_sided := Vector3(_current_data.hip_position.x * _shoulder_blend, _current_data.hip_position.y, _current_data.hip_position.z)
	var ads_pos := _current_stats.ads_position if _current_stats != null else _current_data.ads_position
	var base_pos := hip_sided.lerp(ads_pos, _ads_alpha)
	var base_rot := Vector3.ZERO

	# Subtle chest-dip arc during shoulder switch (suppressed during ADS so sightline stays stable)
	var arc_weight := lerpf(1.0, 0.22, _ads_alpha)
	base_pos += Vector3(0.0, -0.042 * shoulder_mid_arc * arc_weight, 0.022 * shoulder_mid_arc * arc_weight)
	base_rot.z += -8.0 * shoulder_mid_arc * _shoulder_target * arc_weight

	# Subtle left-shoulder yaw convergence toward crosshair
	base_rot.y += lerpf(1.6 * (1.0 - _shoulder_blend) * 0.5, 0.0, _ads_alpha)

	# Tactile selector lever nudge
	base_rot += Vector3(1.8, -2.8, 4.5) * _selector_nudge * lerpf(1.0, 0.20, _ads_alpha)

	# Subtle tactical lean stabilization counter-roll
	base_rot.z += -3.8 * lean_amount * lerpf(1.0, 0.18, _ads_alpha)

	# Dampen outer procedural motion when an authored Blender reload/bolt/equip clip is active
	var action_quiet := 0.35 if (is_reloading or is_cycling_bolt or is_equipping_or_unequipping) else 1.0

	if is_sprinting and _ads_alpha < 0.1 and not is_reloading and not is_equipping_or_unequipping and not is_cycling_bolt:
		var sp := _current_data.sprint_position
		var sprint_sided := Vector3(sp.x * _shoulder_blend, sp.y, sp.z)
		base_pos = base_pos.lerp(sprint_sided, 0.85)
		var sr := _current_data.sprint_rotation_deg
		base_rot = Vector3(sr.x, sr.y * _shoulder_blend, sr.z * _shoulder_blend)

	var bob_offset := Vector3.ZERO
	if is_grounded and move_ratio > 0.08:
		_bob_time += delta * (9.2 if is_sprinting else 6.6)
		var bob_amp := lerpf(0.0085, 0.0012, _ads_alpha) * minf(move_ratio, 1.2) * action_quiet
		bob_offset.x = cos(_bob_time * 0.5) * bob_amp
		bob_offset.y = absf(sin(_bob_time)) * bob_amp * 0.80

	var sway_scale := lerpf(1.0, 0.16, _ads_alpha) * action_quiet
	var sway_vec := Vector3(_sway_offset.x * sway_scale, _sway_offset.y * sway_scale, 0.0)
	var kick_vec := Vector3(0.0, 0.0, _kick_offset_z)

	var target_pos := base_pos + bob_offset + sway_vec + kick_vec
	var target_rot := base_rot + Vector3(_kick_pitch_deg, 0.0, 0.0)

	# Non-rigged fallback only (zeroed for all Blender rigged weapons!)
	if not _using_rigged_model:
		_fallback_reload_alpha = lerpf(_fallback_reload_alpha, 1.0 if is_reloading else 0.0, 1.0 - exp(-10.0 * delta))
		_fallback_equip_alpha = lerpf(_fallback_equip_alpha, 1.0 if is_equipping_or_unequipping else 0.0, 1.0 - exp(-12.0 * delta))
		target_pos += Vector3(0.0, -0.09, 0.03) * _fallback_reload_alpha + Vector3(0.0, -0.24, 0.05) * _fallback_equip_alpha
		target_rot += Vector3(14.0, -18.0, 26.0) * _fallback_reload_alpha + Vector3(-32.0, 0.0, 0.0) * _fallback_equip_alpha

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


func _ensure_initialized() -> void:
	if _runtime_pivot != null:
		return
	_runtime_pivot = Node3D.new()
	_runtime_pivot.name = "RuntimeOffsetPivot"
	add_child(_runtime_pivot)

	_muzzle_point = Marker3D.new()
	_muzzle_point.name = "MuzzlePoint"
	_runtime_pivot.add_child(_muzzle_point)

	_eject_point = Marker3D.new()
	_eject_point.name = "EjectPoint"
	_runtime_pivot.add_child(_eject_point)

	_build_muzzle_flash()


func _reparent_marker_cleanly(marker: Node3D, new_parent: Node) -> void:
	if marker == null or new_parent == null or marker.get_parent() == new_parent:
		return
	if marker.get_parent() != null:
		marker.get_parent().remove_child(marker)
	new_parent.add_child(marker)


func _clear_current_model() -> void:
	# Detach reusable MuzzlePoint & EjectPoint BEFORE freeing old model/BoneAttachment3D!
	_reparent_marker_cleanly(_muzzle_point, _runtime_pivot)
	_reparent_marker_cleanly(_eject_point, _runtime_pivot)
	if _muzzle_point != null:
		_muzzle_point.transform = Transform3D.IDENTITY
	if _eject_point != null:
		_eject_point.transform = Transform3D.IDENTITY

	_anim_player = null
	_skeleton = null
	_body_bone_attachment = null
	_selector_bone_idx = -1
	_model_instance = null
	_att_optic_node = null
	_att_muzzle_node = null
	_att_mag_node = null
	_att_laser_node = null

	for child in _runtime_pivot.get_children():
		if child != _muzzle_point and child != _eject_point:
			child.queue_free()


func _mount_rigged_scene(scene: PackedScene) -> void:
	_model_instance = scene.instantiate() as Node3D
	if _model_instance == null:
		_using_rigged_model = false
		return

	_using_rigged_model = true
	_runtime_pivot.add_child(_model_instance)
	_disable_shadows_recursive(_model_instance)
	_anim_player = _find_animation_player(_model_instance)
	_skeleton = _find_skeleton(_model_instance)

	# Resolve Blender-authored bone-skinned modular attachment meshes (zero floating parts!)
	_att_optic_node = _find_node_by_name(_model_instance, "Att_Optic_Holo") as Node3D
	_att_muzzle_node = _find_node_by_name(_model_instance, "Att_Muzzle_Comp") as Node3D
	_att_mag_node = _find_node_by_name(_model_instance, "Att_Mag_Ext") as Node3D
	_att_laser_node = _find_node_by_name(_model_instance, "Att_Underbarrel_Laser") as Node3D
	for att_n in [_att_optic_node, _att_muzzle_node, _att_mag_node, _att_laser_node]:
		if att_n != null:
			att_n.visible = false

	# Bind MuzzlePoint & EjectPoint directly onto Skeleton3D's `weapon_body` via BoneAttachment3D!
	if _skeleton != null:
		_selector_bone_idx = _skeleton.find_bone("selector")
		var body_bone_idx := _skeleton.find_bone("weapon_body")
		if body_bone_idx >= 0:
			_body_bone_attachment = BoneAttachment3D.new()
			_body_bone_attachment.name = "WeaponBodyBoneAttachment"
			_body_bone_attachment.bone_name = "weapon_body"
			_skeleton.add_child(_body_bone_attachment)

			var rest_xf: Transform3D = _skeleton.get_bone_global_rest(body_bone_idx)
			var rest_inv: Transform3D = rest_xf.affine_inverse()

			var m_node := _find_node_by_name(_model_instance, "MuzzlePoint")
			var muzzle_skel_xf := _get_transform_relative_to_skeleton(m_node as Node3D) if m_node is Node3D else Transform3D(Basis.IDENTITY, Vector3(0.0, 0.02, -0.60))
			_reparent_marker_cleanly(_muzzle_point, _body_bone_attachment)
			_muzzle_point.transform = rest_inv * muzzle_skel_xf

			var e_node := _find_node_by_name(_model_instance, "EjectPoint")
			var eject_skel_xf := _get_transform_relative_to_skeleton(e_node as Node3D) if e_node is Node3D else Transform3D(Basis.IDENTITY, Vector3(0.035, 0.03, -0.06))
			_reparent_marker_cleanly(_eject_point, _body_bone_attachment)
			_eject_point.transform = rest_inv * eject_skel_xf
			return

	# Fallback if a custom GLB lacks a weapon_body bone
	var fallback_m := _find_node_by_name(_model_instance, "MuzzlePoint")
	_muzzle_point.position = (fallback_m as Node3D).position if fallback_m is Node3D else Vector3(0.0, 0.02, -0.60)
	var fallback_e := _find_node_by_name(_model_instance, "EjectPoint")
	_eject_point.position = (fallback_e as Node3D).position if fallback_e is Node3D else Vector3(0.035, 0.03, -0.06)


func _get_transform_relative_to_skeleton(node: Node3D) -> Transform3D:
	if node == null:
		return Transform3D.IDENTITY
	var xf := Transform3D.IDENTITY
	var cur: Node = node
	while cur != null and cur != _skeleton and cur != _model_instance:
		if cur is BoneAttachment3D and _skeleton != null:
			var ba := cur as BoneAttachment3D
			var b_idx := _skeleton.find_bone(ba.bone_name)
			if b_idx >= 0:
				xf = _skeleton.get_bone_global_rest(b_idx) * xf
			else:
				xf = ba.transform * xf
		elif cur is Node3D:
			xf = (cur as Node3D).transform * xf
		cur = cur.get_parent()
	return xf


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
	_muzzle_flash_mesh = MeshInstance3D.new()
	var core := BoxMesh.new()
	core.size = Vector3(0.042, 0.042, 0.062)
	_muzzle_flash_mesh.mesh = core
	_muzzle_flash_mesh.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var mat := StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.albedo_color = Color(1.0, 0.90, 0.48, 0.92)
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	_muzzle_flash_mesh.material_override = mat

	var fin_angles := PackedFloat32Array([0.0, 60.0, 120.0])
	for ang in fin_angles:
		var fin := MeshInstance3D.new()
		var fm := BoxMesh.new()
		fm.size = Vector3(0.135, 0.016, 0.042)
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


func _rebuild_procedural_fallback(data: WeaponData) -> void:
	var body_mat := StandardMaterial3D.new()
	body_mat.albedo_color = data.accent_color
	body_mat.metallic = 0.45
	body_mat.roughness = 0.42
	var mi := MeshInstance3D.new()
	var mesh := BoxMesh.new()
	mesh.size = Vector3(0.06, 0.08, 0.45)
	mi.mesh = mesh
	mi.material_override = body_mat
	mi.position = Vector3(0.0, 0.0, -0.15)
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_runtime_pivot.add_child(mi)
	_muzzle_point.position = Vector3(0.0, 0.01, -0.45)
	_eject_point.position = Vector3(0.04, 0.02, -0.04)
