class_name EffectiveWeaponStats
extends RefCounted
## Pure computed weapon stats produced by composing a base WeaponData with active AttachmentData.
## Deterministic and stateless so it can be unit-tested and recalculated instantaneously on attachment changes.

var base_damage: float = 0.0
var pellets_per_shot: int = 1
var fire_interval: float = 0.1
var effective_range: float = 40.0
var max_falloff_range: float = 100.0
var min_falloff_multiplier: float = 0.5
var max_ray_distance: float = 250.0
var impact_impulse: float = 4.0
var penetration_power: float = 2.0
var max_penetrations: int = 3

var magazine_capacity: int = 30
var tactical_reload_duration: float = 1.6
var empty_reload_duration: float = 2.0
var shell_reload_start_duration: float = 0.35
var shell_reload_insert_duration: float = 0.40
var shell_reload_end_duration: float = 0.30

var base_hip_spread_deg: float = 1.5
var base_ads_spread_deg: float = 0.2
var move_spread_penalty_deg: float = 1.5
var air_spread_penalty_deg: float = 3.0
var crouch_spread_multiplier: float = 0.75
var spread_per_shot_deg: float = 0.4
var max_bloom_spread_deg: float = 4.0
var spread_recovery_rate_deg: float = 6.0

var recoil_vertical_kick_deg: float = 1.0
var recoil_horizontal_spread_deg: float = 0.4
var recoil_ads_multiplier: float = 0.65
var recoil_crouch_multiplier: float = 0.8
var recoil_sustained_scale: float = 0.1
var recoil_max_pitch_deg: float = 14.0
var recoil_snap_speed: float = 18.0
var recoil_recovery_speed: float = 9.0
var recoil_recovery_delay: float = 0.09

var ads_fov: float = 55.0
var ads_transition_speed: float = 10.0
var ads_sensitivity_multiplier: float = 0.65
var ads_position: Vector3 = Vector3.ZERO


static func compute(base: WeaponData, attachments: Array[AttachmentData]) -> EffectiveWeaponStats:
	var stats := EffectiveWeaponStats.new()
	if base == null:
		return stats

	var dmg_mult := 1.0
	var range_mult := 1.0
	var rec_v_mult := 1.0
	var rec_h_mult := 1.0
	var hip_sp_mult := 1.0
	var ads_sp_mult := 1.0
	var move_sp_mult := 1.0
	var mag_mult := 1.0
	var mag_bonus := 0
	var reload_mult := 1.0
	var ads_fov_delta := 0.0
	var ads_spd_mult := 1.0
	var ads_y_delta := 0.0

	for att in attachments:
		if att == null:
			continue
		dmg_mult *= att.damage_multiplier
		range_mult *= att.effective_range_multiplier
		rec_v_mult *= att.recoil_vertical_multiplier
		rec_h_mult *= att.recoil_horizontal_multiplier
		hip_sp_mult *= att.hip_spread_multiplier
		ads_sp_mult *= att.ads_spread_multiplier
		move_sp_mult *= att.move_spread_multiplier
		mag_mult *= att.magazine_capacity_multiplier
		mag_bonus += att.magazine_capacity_bonus
		reload_mult *= att.reload_duration_multiplier
		ads_fov_delta += att.ads_fov_offset
		ads_spd_mult *= att.ads_speed_multiplier
		ads_y_delta += att.ads_y_offset

	stats.base_damage = maxf(1.0, base.base_damage * dmg_mult)
	stats.pellets_per_shot = maxi(1, base.pellets_per_shot)
	stats.fire_interval = base.get_fire_interval()
	stats.effective_range = maxf(2.0, base.effective_range * range_mult)
	stats.max_falloff_range = maxf(stats.effective_range + 5.0, base.max_falloff_range * range_mult)
	stats.min_falloff_multiplier = clampf(base.min_falloff_multiplier, 0.1, 1.0)
	stats.max_ray_distance = base.max_ray_distance
	stats.impact_impulse = base.impact_impulse
	stats.penetration_power = maxf(0.0, base.penetration_power)
	stats.max_penetrations = maxi(0, base.max_penetrations)

	stats.magazine_capacity = maxi(1, int(round(float(base.magazine_capacity) * mag_mult)) + mag_bonus)
	stats.tactical_reload_duration = maxf(0.25, base.tactical_reload_duration * reload_mult)
	stats.empty_reload_duration = maxf(0.25, base.empty_reload_duration * reload_mult)
	stats.shell_reload_start_duration = maxf(0.1, base.shell_reload_start_duration * reload_mult)
	stats.shell_reload_insert_duration = maxf(0.12, base.shell_reload_insert_duration * reload_mult)
	stats.shell_reload_end_duration = maxf(0.1, base.shell_reload_end_duration * reload_mult)

	stats.base_hip_spread_deg = maxf(0.02, base.base_hip_spread_deg * hip_sp_mult)
	stats.base_ads_spread_deg = maxf(0.01, base.base_ads_spread_deg * ads_sp_mult)
	stats.move_spread_penalty_deg = maxf(0.0, base.move_spread_penalty_deg * move_sp_mult)
	stats.air_spread_penalty_deg = base.air_spread_penalty_deg
	stats.crouch_spread_multiplier = base.crouch_spread_multiplier
	stats.spread_per_shot_deg = base.spread_per_shot_deg
	stats.max_bloom_spread_deg = base.max_bloom_spread_deg
	stats.spread_recovery_rate_deg = base.spread_recovery_rate_deg

	stats.recoil_vertical_kick_deg = maxf(0.05, base.recoil_vertical_kick_deg * rec_v_mult)
	stats.recoil_horizontal_spread_deg = maxf(0.0, base.recoil_horizontal_spread_deg * rec_h_mult)
	stats.recoil_ads_multiplier = base.recoil_ads_multiplier
	stats.recoil_crouch_multiplier = base.recoil_crouch_multiplier
	stats.recoil_sustained_scale = base.recoil_sustained_scale
	stats.recoil_max_pitch_deg = base.recoil_max_pitch_deg
	stats.recoil_snap_speed = base.recoil_snap_speed
	stats.recoil_recovery_speed = base.recoil_recovery_speed
	stats.recoil_recovery_delay = base.recoil_recovery_delay

	stats.ads_fov = clampf(base.ads_fov + ads_fov_delta, 18.0, 85.0)
	stats.ads_transition_speed = maxf(2.0, base.ads_transition_speed * ads_spd_mult)
	stats.ads_sensitivity_multiplier = base.ads_sensitivity_multiplier
	stats.ads_position = base.ads_position + Vector3(0.0, ads_y_delta, 0.0)

	return stats


func compute_damage_at_distance(distance: float) -> float:
	if distance <= effective_range:
		return base_damage
	if distance >= max_falloff_range:
		return base_damage * min_falloff_multiplier
	var t := (distance - effective_range) / maxf(0.001, max_falloff_range - effective_range)
	var mult := lerpf(1.0, min_falloff_multiplier, clampf(t, 0.0, 1.0))
	return base_damage * mult
