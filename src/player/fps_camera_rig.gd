class_name FPSCameraRig
extends Node3D
## First-person camera rig handling pitch clamping, ADS FOV interpolation,
## real weapon recoil pitch/yaw application, headbob, and landing camera impulse.

@export var base_fov: float = 70.0
@export var mouse_sensitivity: float = 0.14
@export var min_pitch_deg: float = -85.0
@export var max_pitch_deg: float = 85.0
@export var headbob_frequency: float = 8.5
@export var headbob_amplitude: float = 0.032

@onready var camera: Camera3D = $Camera3D
@onready var viewmodel: WeaponViewmodel = $Camera3D/WeaponViewmodel

var base_pitch_deg: float = 0.0
var _recoil_offset_deg: Vector2 = Vector2.ZERO
var _landing_dip: float = 0.0
var _bob_phase: float = 0.0
var _base_local_y: float = 1.62


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


func update_rig(
	delta: float,
	eye_height: float,
	target_fov: float,
	recoil_deg: Vector2,
	move_ratio: float,
	is_grounded: bool,
	is_sprinting: bool,
	ads_alpha: float
) -> void:
	_recoil_offset_deg = recoil_deg
	_landing_dip = lerpf(_landing_dip, 0.0, 1.0 - exp(-12.0 * delta))

	var bob_y := 0.0
	if is_grounded and move_ratio > 0.08:
		var freq := headbob_frequency * (1.3 if is_sprinting else 1.0)
		_bob_phase += delta * freq
		var amp := headbob_amplitude * lerpf(1.0, 0.2, ads_alpha) * minf(move_ratio, 1.2)
		bob_y = sin(_bob_phase) * amp

	var target_y := eye_height + bob_y + _landing_dip
	position.y = lerpf(position.y, target_y, 1.0 - exp(-16.0 * delta))

	# Apply base pitch + real weapon recoil pitch/yaw directly to camera transform
	var final_pitch := clampf(base_pitch_deg + _recoil_offset_deg.x, min_pitch_deg, max_pitch_deg)
	rotation_degrees.x = final_pitch
	rotation_degrees.y = _recoil_offset_deg.y

	if camera != null:
		camera.fov = lerpf(camera.fov, target_fov, 1.0 - exp(-16.0 * delta))
