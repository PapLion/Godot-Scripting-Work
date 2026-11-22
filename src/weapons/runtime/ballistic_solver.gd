class_name BallisticSolver
extends RefCounted
## Camera-based hitscan ballistic solver supporting single rounds and multi-pellet shotguns.
## Handles collision exclusions, effective range, damage falloff, hitbox resolution, and surface types.

const COLLISION_MASK_WORLD_AND_HITBOXES := (1 << 0) | (1 << 2) # Layer 1 (World) + Layer 3 (Hitboxes)


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

	for i in pellets:
		var pellet_spread := spread_deg
		var dir: Vector3
		if spread_controller != null:
			dir = spread_controller.sample_direction(forward, right, up, pellet_spread)
		else:
			dir = forward

		var ray_from := camera_transform.origin
		var ray_to := ray_from + dir * stats.max_ray_distance

		var query := PhysicsRayQueryParameters3D.create(ray_from, ray_to, COLLISION_MASK_WORLD_AND_HITBOXES)
		query.collide_with_areas = true
		query.collide_with_bodies = true
		query.hit_from_inside = false
		query.exclude = exclude_rids

		var result := space_state.intersect_ray(query)
		var hit_res := FPSEvents.HitResult.new()

		if result.is_empty():
			hit_res.hit = false
			hit_res.position = ray_to
			hit_res.normal = -dir
			hit_res.distance = stats.max_ray_distance
			summary.hits.append(hit_res)
			continue

		hit_res.hit = true
		hit_res.position = result["position"]
		hit_res.normal = result["normal"]
		hit_res.collider = result["collider"]
		hit_res.distance = ray_from.distance_to(hit_res.position)
		hit_res.surface_type = SurfaceMaterialType.resolve_from_collider(hit_res.collider)

		var falloff_damage := stats.compute_damage_at_distance(hit_res.distance)

		if hit_res.collider is HitboxComponent:
			var hitbox := hit_res.collider as HitboxComponent
			var was_dead := hitbox.is_target_dead()
			var dmg_info := hitbox.receive_hit(
				falloff_damage,
				hit_res.position,
				hit_res.normal,
				dir,
				stats.impact_impulse,
				weapon_id,
				instigator
			)
			hit_res.hit_damageable = true
			hit_res.damage_applied = dmg_info.final_damage
			hit_res.is_critical = dmg_info.is_critical
			hit_res.killed_target = (not was_dead) and hitbox.is_target_dead()

			summary.total_damage += dmg_info.final_damage
			summary.any_damageable_hit = true
			if dmg_info.is_critical:
				summary.any_critical_hit = true
			if hit_res.killed_target:
				summary.any_kill = true

		summary.hits.append(hit_res)

	return summary
