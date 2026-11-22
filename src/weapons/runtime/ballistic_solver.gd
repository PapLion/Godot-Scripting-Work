class_name BallisticSolver
extends RefCounted
## Camera-based hitscan ballistic solver supporting single rounds, multi-pellet shotguns,
## and configurable multi-surface penetration with thickness evaluation, resistance budgets,
## entry/exit point resolution, damage reduction, and duplicate-hit prevention.

const COLLISION_MASK_WORLD_AND_HITBOXES := (1 << 0) | (1 << 2) # Layer 1 (World) + Layer 3 (Hitboxes)
const MAX_HARD_ITERATIONS := 8
const STEP_EPSILON := 0.025


static func fire_shot(
	space_state: PhysicsDirectSpaceState3D,
	camera_transform: Transform3D,
	muzzle_position: Vector3,
	weapon_id: StringName,
	stats: EffectiveWeaponStats,
	spread_controller: SpreadController,
	spread_deg: float,
	exclude_rids: Array[RID],
	instigator: Node
) -> FPSEvents.ShotSummary:
	var summary := FPSEvents.ShotSummary.new()
	summary.weapon_id = weapon_id
	summary.origin = camera_transform.origin
	summary.muzzle_position = muzzle_position

	if space_state == null or stats == null:
		return summary

	var forward := -camera_transform.basis.z.normalized()
	var right := camera_transform.basis.x.normalized()
	var up := camera_transform.basis.y.normalized()
	var pellets := maxi(1, stats.pellets_per_shot)

	for _i in pellets:
		var dir: Vector3
		if spread_controller != null:
			dir = spread_controller.sample_direction(forward, right, up, spread_deg)
		else:
			dir = forward

		_trace_pellet_with_penetration(
			space_state,
			camera_transform.origin,
			muzzle_position,
			dir,
			weapon_id,
			stats,
			exclude_rids,
			instigator,
			summary
		)

	return summary


static func _trace_pellet_with_penetration(
	space_state: PhysicsDirectSpaceState3D,
	origin: Vector3,
	muzzle_position: Vector3,
	dir: Vector3,
	weapon_id: StringName,
	stats: EffectiveWeaponStats,
	base_excludes: Array[RID],
	instigator: Node,
	summary: FPSEvents.ShotSummary
) -> void:
	var cursor := origin
	var visual_seg_start := muzzle_position
	var remaining_dist := stats.max_ray_distance
	var remaining_power := stats.penetration_power
	var damage_mult := 1.0
	var penetrations_done := 0
	var max_pen := mini(stats.max_penetrations, MAX_HARD_ITERATIONS)

	# Prevent registering the same pellet repeatedly against one damageable target
	var damaged_health_ids: Dictionary = {}
	var iter := 0

	while remaining_dist > 0.05 and iter < MAX_HARD_ITERATIONS:
		iter += 1
		var ray_to := cursor + dir * remaining_dist
		var query := PhysicsRayQueryParameters3D.create(cursor, ray_to, COLLISION_MASK_WORLD_AND_HITBOXES)
		query.collide_with_areas = true
		query.collide_with_bodies = true
		query.hit_from_inside = false
		query.exclude = base_excludes

		var result := space_state.intersect_ray(query)
		if result.is_empty():
			var miss := FPSEvents.HitResult.new()
			miss.hit = false
			miss.segment_start = visual_seg_start
			miss.position = ray_to
			miss.normal = -dir
			miss.distance = origin.distance_to(ray_to)
			miss.damage_multiplier_after_pen = damage_mult
			summary.hits.append(miss)
			return

		var hit_pos: Vector3 = result["position"]
		var hit_normal: Vector3 = result["normal"]
		var collider: Object = result["collider"]
		var total_dist := origin.distance_to(hit_pos)
		var surface := SurfaceMaterialType.resolve_from_collider(collider)

		var entry_res := FPSEvents.HitResult.new()
		entry_res.hit = true
		entry_res.segment_start = visual_seg_start
		entry_res.position = hit_pos
		entry_res.normal = hit_normal
		entry_res.collider = collider
		entry_res.distance = total_dist
		entry_res.surface_type = surface
		entry_res.is_exit = false
		entry_res.damage_multiplier_after_pen = damage_mult

		# Case A: Hit a damageable HitboxComponent
		if collider is HitboxComponent:
			var hitbox := collider as HitboxComponent
			var hp_id := hitbox.health_component.get_instance_id() if hitbox.health_component != null else hitbox.get_instance_id()
			if not damaged_health_ids.has(hp_id):
				damaged_health_ids[hp_id] = true
				var was_dead := hitbox.is_target_dead()
				var falloff_damage := stats.compute_damage_at_distance(total_dist) * damage_mult
				var dmg_info := hitbox.receive_hit(
					falloff_damage,
					hit_pos,
					hit_normal,
					dir,
					stats.impact_impulse * damage_mult,
					weapon_id,
					instigator
				)
				entry_res.hit_damageable = true
				entry_res.damage_applied = dmg_info.final_damage
				entry_res.armor_absorbed = dmg_info.armor_absorbed
				entry_res.is_critical = dmg_info.is_critical
				entry_res.killed_target = (not was_dead) and hitbox.is_target_dead()

				summary.total_damage += dmg_info.final_damage
				summary.total_armor_absorbed += dmg_info.armor_absorbed
				summary.any_damageable_hit = true
				if dmg_info.is_critical:
					summary.any_critical_hit = true
				if entry_res.killed_target:
					summary.any_kill = true

			summary.hits.append(entry_res)
			return

		# Case B: Hit solid World geometry — evaluate configurable surface penetration
		var profile := SurfaceMaterialType.get_penetration_profile(surface)
		var tag := SurfaceMaterialType.resolve_tag_from_collider(collider)
		var can_pen := profile.penetrable
		var res_mult := 1.0
		if tag != null:
			if tag.override_penetration:
				can_pen = tag.allow_penetration
			res_mult = maxf(0.1, tag.resistance_multiplier)

		var entry_cost := profile.min_entry_cost * res_mult
		if not can_pen or penetrations_done >= max_pen or remaining_power <= entry_cost:
			entry_res.penetrated = false
			entry_res.remaining_penetration = remaining_power
			summary.hits.append(entry_res)
			return

		# Probe backward from beyond the obstacle to find exact exit point & wall thickness
		var exit_info := _probe_exit_point(space_state, hit_pos, dir, collider, profile.max_probe_thickness, base_excludes)
		if exit_info.is_empty():
			# Obstacle thicker than max_probe_thickness -> blocked
			entry_res.penetrated = false
			entry_res.remaining_penetration = remaining_power
			summary.hits.append(entry_res)
			return

		var exit_pos: Vector3 = exit_info["position"]
		var exit_normal: Vector3 = exit_info["normal"]
		var thickness := hit_pos.distance_to(exit_pos)
		var total_cost := entry_cost + thickness * profile.resistance_per_meter * res_mult

		if total_cost > remaining_power:
			entry_res.penetrated = false
			entry_res.remaining_penetration = remaining_power
			summary.hits.append(entry_res)
			return

		# Penetration succeeds! Consume penetration budget & reduce remaining damage
		remaining_power = maxf(0.0, remaining_power - total_cost)
		var thickness_atten := clampf(1.0 - thickness * 0.45, 0.35, 1.0)
		damage_mult *= clampf(profile.damage_retention * thickness_atten, 0.20, 0.95)
		penetrations_done += 1
		summary.penetration_count += 1

		entry_res.penetrated = true
		entry_res.remaining_penetration = remaining_power
		entry_res.damage_multiplier_after_pen = damage_mult
		summary.hits.append(entry_res)

		# Record distinct EXIT impact for exit splinters/dust/shards VFX
		var exit_res := FPSEvents.HitResult.new()
		exit_res.hit = true
		exit_res.segment_start = hit_pos
		exit_res.position = exit_pos
		exit_res.normal = exit_normal
		exit_res.collider = collider
		exit_res.distance = origin.distance_to(exit_pos)
		exit_res.surface_type = surface
		exit_res.is_exit = true
		exit_res.penetrated = true
		exit_res.remaining_penetration = remaining_power
		exit_res.damage_multiplier_after_pen = damage_mult
		summary.hits.append(exit_res)

		# Advance cursor cleanly past exit face
		var next_cursor := exit_pos + dir * STEP_EPSILON
		var traveled := cursor.distance_to(next_cursor)
		remaining_dist = maxf(0.0, remaining_dist - traveled)
		cursor = next_cursor
		visual_seg_start = exit_pos


static func _probe_exit_point(
	space_state: PhysicsDirectSpaceState3D,
	entry_pos: Vector3,
	dir: Vector3,
	target_collider: Object,
	max_thickness: float,
	base_excludes: Array[RID]
) -> Dictionary:
	## Casts a reverse ray from `entry_pos + dir * max_thickness` back toward `entry_pos`
	## to measure the exact exit face and obstacle thickness.
	var probe_start := entry_pos + dir * max_thickness
	var probe_end := entry_pos + dir * 0.004
	var q := PhysicsRayQueryParameters3D.create(probe_start, probe_end, 1) # Layer 1: World
	q.collide_with_bodies = true
	q.collide_with_areas = false
	q.hit_from_inside = false
	q.exclude = base_excludes
	var back_hit := space_state.intersect_ray(q)
	if back_hit.is_empty():
		return {}
	if back_hit["collider"] != target_collider:
		# Another wall sat behind the target; retry slightly closer to isolate target thickness
		var mid_start := entry_pos + dir * (max_thickness * 0.45)
		var q2 := PhysicsRayQueryParameters3D.create(mid_start, probe_end, 1)
		q2.collide_with_bodies = true
		q2.collide_with_areas = false
		q2.hit_from_inside = false
		q2.exclude = base_excludes
		back_hit = space_state.intersect_ray(q2)
		if back_hit.is_empty() or back_hit["collider"] != target_collider:
			return {}
	return back_hit
