class_name RecoilController
extends RefCounted
## Configurable weapon recoil controller with vertical kick, horizontal variance,
## sustained-fire accumulation, ADS/crouch scaling, and smooth automatic recovery.
## Outputs real pitch/yaw angles (degrees) applied directly to the camera & shot ray.

var current_offset_deg: Vector2 = Vector2.ZERO # x = pitch (+up), y = yaw (+left / -right)
var target_offset_deg: Vector2 = Vector2.ZERO

var _sustained_shots: int = 0
var _recovery_delay_timer: float = 0.0
var _rng := RandomNumberGenerator.new()


func _init(seed_value: int = 0) -> void:
	if seed_value != 0:
		_rng.seed = seed_value
	else:
		_rng.randomize()


func reset() -> void:
	current_offset_deg = Vector2.ZERO
	target_offset_deg = Vector2.ZERO
	_sustained_shots = 0
	_recovery_delay_timer = 0.0


func add_shot_kick(stats: EffectiveWeaponStats, is_aiming: bool, is_crouching: bool) -> Vector2:
	if stats == null:
		return Vector2.ZERO

	var mult := 1.0
	if is_aiming:
		mult *= stats.recoil_ads_multiplier
	if is_crouching:
		mult *= stats.recoil_crouch_multiplier

	# Sustained-fire accumulation factor (capped to keep recoil controllable)
	var sustained_factor := 1.0 + minf(float(_sustained_shots) * stats.recoil_sustained_scale, 0.85)
	_sustained_shots += 1

	var vertical := stats.recoil_vertical_kick_deg * mult * sustained_factor
	var horizontal := _rng.randf_range(
		-stats.recoil_horizontal_spread_deg,
		stats.recoil_horizontal_spread_deg
	) * mult * sustained_factor

	target_offset_deg.x = clampf(target_offset_deg.x + vertical, 0.0, stats.recoil_max_pitch_deg)
	target_offset_deg.y = clampf(target_offset_deg.y + horizontal, -stats.recoil_max_pitch_deg * 0.6, stats.recoil_max_pitch_deg * 0.6)
	_recovery_delay_timer = stats.recoil_recovery_delay

	return Vector2(vertical, horizontal)


func update(delta: float, stats: EffectiveWeaponStats) -> Vector2:
	if stats == null or delta <= 0.0:
		return current_offset_deg

	if _recovery_delay_timer > 0.0:
		_recovery_delay_timer = maxf(0.0, _recovery_delay_timer - delta)
	else:
		var rec_alpha := 1.0 - exp(-stats.recoil_recovery_speed * delta)
		target_offset_deg = target_offset_deg.lerp(Vector2.ZERO, rec_alpha)
		if target_offset_deg.length() < 0.01:
			target_offset_deg = Vector2.ZERO
			_sustained_shots = 0

	var snap_alpha := 1.0 - exp(-stats.recoil_snap_speed * delta)
	current_offset_deg = current_offset_deg.lerp(target_offset_deg, snap_alpha)
	if current_offset_deg.length() < 0.005 and target_offset_deg == Vector2.ZERO:
		current_offset_deg = Vector2.ZERO

	return current_offset_deg


func get_sustained_shot_count() -> int:
	return _sustained_shots
