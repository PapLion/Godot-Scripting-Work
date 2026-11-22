class_name HitboxComponent
extends Area3D
## Reusable hit-region component (Head, Body, Limb) with configurable damage multiplier.
## Routes hits to an assigned HealthComponent without knowing anything about weapon classes.

signal hit_received(info: FPSEvents.DamageInfo)

enum HitZone {
	BODY = 0,
	HEAD = 1,
	LIMB = 2,
}

@export var hit_zone: HitZone = HitZone.BODY
@export var damage_multiplier: float = 1.0
@export var health_component: HealthComponent
@export var surface_type: SurfaceMaterialType.Type = SurfaceMaterialType.Type.FLESH


func _ready() -> void:
	# Default to Layer 3 (Hitboxes) so ballistic rays can query hitboxes cleanly
	if collision_layer == 1:
		collision_layer = 1 << 2
	collision_mask = 0
	set_meta("surface_type", surface_type)


func receive_hit(
	base_damage: float,
	hit_pos: Vector3,
	hit_normal: Vector3,
	direction: Vector3,
	impulse: float,
	source_id: StringName,
	instigator: Node
) -> FPSEvents.DamageInfo:
	var info := FPSEvents.DamageInfo.new()
	info.raw_damage = maxf(0.0, base_damage * damage_multiplier)
	info.hit_zone = hit_zone
	info.is_critical = (hit_zone == HitZone.HEAD)
	info.hit_position = hit_pos
	info.hit_normal = hit_normal
	info.impulse_direction = direction.normalized()
	info.impulse_strength = impulse
	info.source_id = source_id
	info.instigator = instigator

	if health_component != null:
		health_component.apply_damage(info)
	else:
		info.final_damage = info.raw_damage

	hit_received.emit(info)
	return info


func is_target_dead() -> bool:
	return health_component != null and health_component.is_dead
