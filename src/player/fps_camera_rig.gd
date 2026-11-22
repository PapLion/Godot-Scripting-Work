class_name FPSCameraRig
extends Node3D
## First-person camera rig handling pitch clamping, ADS FOV interpolation,
## real weapon recoil pitch/yaw application, collision-aware Q/E tactical leaning,
## subtle shoulder-side eye offset, headbob, and landing camera impulse.

@export var base_fov: float = 70.0
@export var mouse_sensitivity: float = 0.14
@export var min_pitch_deg: float = -85.0
@export var max_pitch_deg: float = 85.0
@export var headbob_frequency: float = 8.5
@export var headbob_amplitude: float = 0.032

@export_group("Tactical Leaning & Shoulder Offset")
@export var max_lean_angle_deg: float = 13.5
@export var max_lean_offset_m: float = 0.44
@export var lean_drop_y_m: float = 0.045
@export var lean_speed: float = 11.0
@export var lean_wall_margin_m: float = 0.24
@export var shoulder_eye_offset_m: float = 0.075

@onready var camera: Camera3D = $Camera3D
@onready var viewmodel: WeaponViewmodel = $Camera3D/WeaponViewmodel

var base_pitch_deg: float = 0.0
var current_lean_ratio: float = 0.0    # Effective clamped lean in [-1.0, +1.0]
var current_lean_angle_deg: float = 0.0
var current_lateral_offset_m: float = 0.0
var last_lean_blocked: bool = false

var _recoil_offset_deg: Vector2 = Vector2.ZERO
var _landing_dip: float = 0.0
var _bob_phase: float = 0.0
var _base_local_y: float = 1.60


func _ready() -> void:
	_base_local_y = position.y
	if camera != null:
		camera.fov = base_fov


func apply_mouse_look(mouse_delta: Vector2, yaw_body: Node3D, ads_sens_mult: float) -> void:
	var sens := mouse_sensitivity * ads_sens_mult
	if yaw_body != null:
		yaw_body.rotate_y(deg_to_rad(-mouse_delta.x * sens))
	base_pitch_deg = clampf(base_pitch_deg - mouse_delta.y * sens, min_pitch_deg, max_pitch_deg)
	if viewmodel != null:
		viewmodel.add_look_sway(mouse_delta)


func add_landing_impulse(impact_speed: float) -> void:
	_landing_dip = clampf(_landing_dip - impact_speed * 0.016, -0.14, 0.0)


func compute_safe_lateral_displacement(
	space_state: PhysicsDirectSpaceState3D,
	body: Node3D,
	eye_height: float,
	desired_x: float,
	exclude_rids: Array[RID]
) -> float:
	## Collision-aware corner-peeking displacement check against World geometry (Layer 1).
	## Prevents the camera from entering solid walls or shooting through cover.
	last_lean_blocked = false
	if absf(desired_x) < 0.001 or space_state == null or body == null:
		return desired_x

	var side_sign := signf(desired_x)
	var dist_needed := absf(desired_x)
	var probe_dist := dist_needed + lean_wall_margin_m
	var right_dir := body.global_transform.basis.x.normalized() * side_sign
	var fwd_dir := -body.global_transform.basis.z.normalized()
	var origin_center := body.global_position + Vector3(0.0, eye_height, 0.0)

	# Multi-ray clearance probe (center + slightly forward near-plane check)
	var min_safe := dist_needed
	var offsets: PackedFloat32Array = PackedFloat32Array([0.0, 0.14])
	for fwd_off in offsets:
		var ray_from: Vector3 = origin_center + fwd_dir * fwd_off
		var ray_to: Vector3 = ray_from + right_dir * probe_dist
		var q := PhysicsRayQueryParameters3D.create(ray_from, ray_to, 1) # Layer 1: World
		q.collide_with_bodies = true
		q.collide_with_areas = false
		q.exclude = exclude_rids
		var hit := space_state.intersect_ray(q)
		if not hit.is_empty():
			var hit_pos: Vector3 = hit["position"]
			var hit_dist: float = ray_from.distance_to(hit_pos)
			var allowed := maxf(0.0, hit_dist - lean_wall_margin_m)
			if allowed < min_safe:
				min_safe = allowed
				last_lean_blocked = true

	return side_sign * min_safe


func update_rig(
	delta: float,
	eye_height: float,
	target_fov: float,
	recoil_deg: Vector2,
	move_ratio: float,
	is_grounded: bool,
	is_sprinting: bool,
	ads_alpha: float,
	lean_input: float = 0.0,
	shoulder_side: float = 1.0,
	space_state: PhysicsDirectSpaceState3D = null,
	owner_body: Node3D = null,
	exclude_rids: Array[RID] = []
) -> void:
	_recoil_offset_deg = recoil_deg
	_landing_dip = lerpf(_landing_dip, 0.0, 1.0 - exp(-12.0 * delta))

	# Collision-aware lateral peeking + subtle shoulder eye offset
	var desired_lean := clampf(lean_input, -1.0, 1.0)
	var desired_shoulder_x := shoulder_side * shoulder_eye_offset_m * lerpf(1.0, 0.5, ads_alpha)
	var desired_total_x := desired_lean * max_lean_offset_m + desired_shoulder_x

	var safe_x := compute_safe_lateral_displacement(space_state, owner_body, eye_height, desired_total_x, exclude_rids)

	# Scale roll proportionally to unobstructed lean clearance so camera never tilts into solid walls
	var clearance_scale := 1.0
	if absf(desired_total_x) > 0.01:
		clearance_scale = clampf(absf(safe_x) / absf(desired_total_x), 0.0, 1.0)
	var effective_lean_target := desired_lean * clearance_scale

	var lean_blend := 1.0 - exp(-lean_speed * delta)
	current_lateral_offset_m = lerpf(current_lateral_offset_m, safe_x, lean_blend)
	current_lean_ratio = lerpf(current_lean_ratio, effective_lean_target, lean_blend)
	if absf(current_lean_ratio) < 0.002 and absf(effective_lean_target) < 0.001:
		current_lean_ratio = 0.0
	current_lean_angle_deg = -current_lean_ratio * max_lean_angle_deg

	var bob_y := 0.0
	if is_grounded and move_ratio > 0.08:
		var freq := headbob_frequency * (1.3 if is_sprinting else 1.0)
		_bob_phase += delta * freq
		var amp := headbob_amplitude * lerpf(1.0, 0.2, ads_alpha) * minf(move_ratio, 1.2)
		bob_y = sin(_bob_phase) * amp

	var lean_drop := absf(current_lean_ratio) * lean_drop_y_m
	var target_y := eye_height - lean_drop + bob_y + _landing_dip
	position.x = current_lateral_offset_m
	position.y = lerpf(position.y, target_y, 1.0 - exp(-16.0 * delta))

	# Apply base pitch + real weapon recoil pitch/yaw + smooth tactical lean Z-roll
	var final_pitch := clampf(base_pitch_deg + _recoil_offset_deg.x, min_pitch_deg, max_pitch_deg)
	rotation_degrees.x = final_pitch
	rotation_degrees.y = _recoil_offset_deg.y
	rotation_degrees.z = current_lean_angle_deg

	if camera != null:
		camera.fov = lerpf(camera.fov, target_fov, 1.0 - exp(-16.0 * delta))
