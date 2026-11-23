class_name FPSEvents
extends RefCounted
## Shared typed data payloads for decoupled weapon, ballistic, penetration, damage, VFX, and HUD communication.


class DamageInfo extends RefCounted:
	var raw_damage: float = 0.0
	var final_damage: float = 0.0
	var armor_absorbed: float = 0.0
	var hit_zone: int = 0 # Matches HitboxComponent.HitZone
	var is_critical: bool = false
	var hit_position: Vector3 = Vector3.ZERO
	var hit_normal: Vector3 = Vector3.UP
	var impulse_direction: Vector3 = Vector3.FORWARD
	var impulse_strength: float = 0.0
	var source_id: StringName = &""
	var instigator: Node = null


class HitResult extends RefCounted:
	var hit: bool = false
	var segment_start: Vector3 = Vector3.ZERO
	var position: Vector3 = Vector3.ZERO
	var normal: Vector3 = Vector3.UP
	var distance: float = 0.0
	var collider: Object = null
	var surface_type: SurfaceMaterialType.Type = SurfaceMaterialType.Type.GENERIC
	var damage_applied: float = 0.0
	var armor_absorbed: float = 0.0
	var is_critical: bool = false
	var killed_target: bool = false
	var hit_damageable: bool = false
	var is_exit: bool = false
	var penetrated: bool = false
	var remaining_penetration: float = 0.0
	var damage_multiplier_after_pen: float = 1.0


class ShotSummary extends RefCounted:
	var weapon_id: StringName = &""
	var visual_preset: int = 0
	var origin: Vector3 = Vector3.ZERO
	var muzzle_position: Vector3 = Vector3.ZERO
	var hits: Array[HitResult] = []
	var total_damage: float = 0.0
	var total_armor_absorbed: float = 0.0
	var penetration_count: int = 0
	var any_damageable_hit: bool = false
	var any_critical_hit: bool = false
	var any_kill: bool = false
