class_name FPSPlayer
extends CharacterBody3D
## Responsive first-person controller built specifically to showcase and integrate FPS combat systems.
## Supports walk, sprint, crouch (with ceiling clearance check), jump, mouse look, and weapon integration.

@export_group("Movement")
@export var walk_speed: float = 5.2
@export var sprint_speed: float = 7.8
@export var crouch_speed: float = 2.9
@export var jump_velocity: float = 5.2
@export var ground_acceleration: float = 14.0
@export var ground_friction: float = 12.0
@export var air_acceleration: float = 4.5
@export var gravity_scale: float = 1.35

@export_group("Stance")
@export var standing_height: float = 1.80
@export var crouch_height: float = 1.12
@export var standing_eye_height: float = 1.60
@export var crouch_eye_height: float = 0.96

@export_group("Controls")
@export var capture_mouse_on_ready: bool = true

@onready var collision_shape: CollisionShape3D = $CollisionShape3D
@onready var ceiling_ray: RayCast3D = $CeilingCheckRay
@onready var camera_rig: FPSCameraRig = $CameraRig
@onready var weapon_manager: WeaponManager = $WeaponManager
@onready var health_component: HealthComponent = $HealthComponent

var is_crouching: bool = false
var is_sprinting: bool = false
var scripted_control: bool = false
var scripted_move_input: Vector2 = Vector2.ZERO
var scripted_sprint: bool = false
var scripted_crouch: bool = false

var _was_on_floor: bool = true
var _last_y_velocity: float = 0.0
var _footstep_timer: float = 0.0
var _footstep_audio: AudioStreamPlayer
var _gravity: float = ProjectSettings.get_setting("physics/3d/default_gravity", 9.8)


func _ready() -> void:
	collision_layer = 1 << 1 # Layer 2: Player
	collision_mask = 1 << 0  # Layer 1: World

	_footstep_audio = AudioStreamPlayer.new()
	_footstep_audio.name = "FootstepAudio"
	_footstep_audio.volume_db = -14.0
	add_child(_footstep_audio)

	if capture_mouse_on_ready and not DisplayServer.get_name().to_lower().contains("headless"):
		Input.set_mouse_mode(Input.MOUSE_MODE_CAPTURED)


func initialize_combat(fx_manager: ImpactFXManager) -> void:
	var excludes: Array[RID] = [get_rid()]
	if weapon_manager != null and camera_rig != null:
		weapon_manager.initialize(
			camera_rig.camera,
			camera_rig.viewmodel,
			fx_manager,
			self,
			excludes
		)


func _unhandled_input(event: InputEvent) -> void:
	if scripted_control:
		return

	if event is InputEventMouseMotion and Input.get_mouse_mode() == Input.MOUSE_MODE_CAPTURED:
		var mm := event as InputEventMouseMotion
		var ads_mult := weapon_manager.get_ads_sensitivity_multiplier() if weapon_manager != null else 1.0
		camera_rig.apply_mouse_look(mm.relative, self, ads_mult)
		return

	if event is InputEventKey and event.pressed and not event.echo:
		var ke := event as InputEventKey
		if ke.keycode == KEY_ESCAPE:
			if Input.get_mouse_mode() == Input.MOUSE_MODE_CAPTURED:
				Input.set_mouse_mode(Input.MOUSE_MODE_VISIBLE)
			else:
				Input.set_mouse_mode(Input.MOUSE_MODE_CAPTURED)
			return

	if event is InputEventMouseButton and event.pressed:
		if Input.get_mouse_mode() != Input.MOUSE_MODE_CAPTURED:
			Input.set_mouse_mode(Input.MOUSE_MODE_CAPTURED)
			return

	if weapon_manager == null:
		return

	if event.is_action_pressed("reload"):
		weapon_manager.request_reload()
	elif event.is_action_pressed("fire_mode"):
		weapon_manager.request_cycle_fire_mode()
	elif event.is_action_pressed("weapon_1"):
		weapon_manager.request_switch_slot(0)
	elif event.is_action_pressed("weapon_2"):
		weapon_manager.request_switch_slot(1)
	elif event.is_action_pressed("weapon_3"):
		weapon_manager.request_switch_slot(2)
	elif event.is_action_pressed("weapon_next"):
		weapon_manager.request_switch_relative(1)
	elif event.is_action_pressed("weapon_prev"):
		weapon_manager.request_switch_relative(-1)
	elif event.is_action_pressed("toggle_attachment_optic"):
		weapon_manager.toggle_attachment_by_slot(AttachmentData.Slot.OPTIC)
	elif event.is_action_pressed("toggle_attachment_muzzle"):
		weapon_manager.toggle_attachment_by_slot(AttachmentData.Slot.MUZZLE)
	elif event.is_action_pressed("toggle_attachment_mag"):
		weapon_manager.toggle_attachment_by_slot(AttachmentData.Slot.MAGAZINE)
	elif event.is_action_pressed("toggle_attachment_laser"):
		weapon_manager.toggle_attachment_by_slot(AttachmentData.Slot.UNDERBARREL)


func _physics_process(delta: float) -> void:
	var input_dir := _read_move_input()
	var want_crouch := scripted_crouch if scripted_control else Input.is_action_pressed("crouch")
	var want_sprint := scripted_sprint if scripted_control else Input.is_action_pressed("sprint")

	# Crouch with ceiling check when attempting to stand
	if want_crouch:
		is_crouching = true
	elif is_crouching and _can_stand_up():
		is_crouching = false

	_update_capsule_height(delta)

	var aiming := weapon_manager != null and weapon_manager.state_machine.is_aiming()
	var moving_forward := input_dir.y < -0.1
	is_sprinting = want_sprint and moving_forward and not is_crouching and not aiming and is_on_floor()

	# Horizontal movement
	var wish_dir := (transform.basis * Vector3(input_dir.x, 0.0, input_dir.y)).normalized()
	var target_speed := crouch_speed if is_crouching else (sprint_speed if is_sprinting else walk_speed)
	if aiming and not is_crouching:
		target_speed *= 0.68

	var horiz_vel := Vector3(velocity.x, 0.0, velocity.z)
	if is_on_floor():
		if wish_dir.length_squared() > 0.001:
			horiz_vel = horiz_vel.lerp(wish_dir * target_speed, 1.0 - exp(-ground_acceleration * delta))
		else:
			horiz_vel = horiz_vel.lerp(Vector3.ZERO, 1.0 - exp(-ground_friction * delta))
	else:
		if wish_dir.length_squared() > 0.001:
			horiz_vel = horiz_vel.lerp(wish_dir * target_speed, 1.0 - exp(-air_acceleration * delta))

	velocity.x = horiz_vel.x
	velocity.z = horiz_vel.z

	# Gravity & Jump
	if not is_on_floor():
		velocity.y -= _gravity * gravity_scale * delta
	else:
		if not scripted_control and Input.is_action_just_pressed("jump") and not is_crouching:
			velocity.y = jump_velocity

	_last_y_velocity = velocity.y
	move_and_slide()

	# Landing impulse feedback
	if is_on_floor() and not _was_on_floor and _last_y_velocity < -2.2:
		camera_rig.add_landing_impulse(absf(_last_y_velocity))
	_was_on_floor = is_on_floor()

	var move_ratio := Vector2(velocity.x, velocity.z).length() / maxf(0.1, walk_speed)
	_step_footsteps(delta, move_ratio)

	# Weapon input & step
	if weapon_manager != null:
		if not scripted_control:
			weapon_manager.set_trigger_held(Input.is_action_pressed("fire"))
			weapon_manager.set_aim_requested(Input.is_action_pressed("aim"))
		weapon_manager.set_sprint_requested(is_sprinting)
		weapon_manager.step(delta, move_ratio, is_crouching, is_on_floor())

	# Camera rig update (FOV, recoil pitch/yaw, eye height, headbob)
	if camera_rig != null:
		var eye_h := crouch_eye_height if is_crouching else standing_eye_height
		var target_fov := weapon_manager.get_target_fov(camera_rig.base_fov) if weapon_manager != null else camera_rig.base_fov
		var recoil := weapon_manager.get_current_recoil_deg() if weapon_manager != null else Vector2.ZERO
		var ads_a := weapon_manager.ads_alpha if weapon_manager != null else 0.0
		camera_rig.update_rig(delta, eye_h, target_fov, recoil, move_ratio, is_on_floor(), is_sprinting, ads_a)


func look_at_world_point(world_point: Vector3) -> void:
	## Deterministic aiming helper for scripted tests and portfolio capture sequences.
	if camera_rig == null:
		return
	var eye_pos := global_position + Vector3(0.0, camera_rig.position.y, 0.0)
	var to_target := (world_point - eye_pos).normalized()
	var yaw := atan2(-to_target.x, -to_target.z)
	var horiz_len := Vector2(to_target.x, to_target.z).length()
	var pitch_deg := rad_to_deg(atan2(to_target.y, maxf(0.0001, horiz_len)))
	rotation.y = yaw
	camera_rig.base_pitch_deg = clampf(pitch_deg, camera_rig.min_pitch_deg, camera_rig.max_pitch_deg)


func _read_move_input() -> Vector2:
	if scripted_control:
		return scripted_move_input
	return Input.get_vector("move_left", "move_right", "move_forward", "move_backward")


func _can_stand_up() -> bool:
	if ceiling_ray == null:
		return true
	ceiling_ray.force_raycast_update()
	return not ceiling_ray.is_colliding()


func _update_capsule_height(delta: float) -> void:
	if collision_shape == null or not (collision_shape.shape is CapsuleShape3D):
		return
	var cap := collision_shape.shape as CapsuleShape3D
	var target_h := crouch_height if is_crouching else standing_height
	cap.height = lerpf(cap.height, target_h, 1.0 - exp(-14.0 * delta))
	collision_shape.position.y = cap.height * 0.5


func _step_footsteps(delta: float, move_ratio: float) -> void:
	if not is_on_floor() or move_ratio < 0.2:
		_footstep_timer = 0.08
		return
	_footstep_timer -= delta
	if _footstep_timer <= 0.0:
		_footstep_timer = 0.32 if is_sprinting else (0.58 if is_crouching else 0.44)
		if _footstep_audio != null:
			_footstep_audio.stream = ProceduralAudio.get_sound(&"footstep")
			_footstep_audio.pitch_scale = randf_range(0.88, 1.12)
			_footstep_audio.play()
