class_name SpreadController
extends RefCounted
## Coherent weapon spread model combining stance (hip/ADS/crouch), movement velocity,
## airborne penalty, and sustained-fire bloom with framerate-independent recovery.

var bloom_deg: float = 0.0
var current_spread_deg: float = 1.0
var _rng := RandomNumberGenerator.new()


func _init(seed_value: int = 0) -> void:
	if seed_value != 0:
		_rng.seed = seed_value
	else:
		_rng.randomize()


func reset() -> void:
	bloom_deg = 0.0


func add_shot_bloom(stats: EffectiveWeaponStats) -> void:
	if stats == null:
		return
	bloom_deg = minf(stats.max_bloom_spread_deg, bloom_deg + stats.spread_per_shot_deg)


func update(
	delta: float,
	stats: EffectiveWeaponStats,
	ads_alpha: float,
	move_ratio: float,
	is_crouching: bool,
	is_grounded: bool
) -> float:
	if stats == null:
		current_spread_deg = 0.0
		return 0.0

	if delta > 0.0 and bloom_deg > 0.0:
		bloom_deg = maxf(0.0, bloom_deg - stats.spread_recovery_rate_deg * delta)

	var base_spread := lerpf(stats.base_hip_spread_deg, stats.base_ads_spread_deg, clampf(ads_alpha, 0.0, 1.0))
	var move_penalty := stats.move_spread_penalty_deg * clampf(move_ratio, 0.0, 1.2) * lerpf(1.0, 0.45, ads_alpha)
	var air_penalty := 0.0 if is_grounded else stats.air_spread_penalty_deg
	var crouch_mult := stats.crouch_spread_multiplier if is_crouching else 1.0

	current_spread_deg = maxf(0.01, (base_spread + move_penalty + air_penalty + bloom_deg) * crouch_mult)
	return current_spread_deg


func sample_direction(forward: Vector3, right: Vector3, up: Vector3, spread_deg: float) -> Vector3:
	if spread_deg <= 0.001:
		return forward.normalized()

	var max_rad := deg_to_rad(spread_deg)
	# Uniform disk sampling via sqrt(u) prevents center-clumping bias
	var angle := _rng.randf_range(0.0, TAU)
	var radius := sqrt(_rng.randf()) * tan(max_rad)
	var dir := forward + right * (cos(angle) * radius) + up * (sin(angle) * radius)
	return dir.normalized()
