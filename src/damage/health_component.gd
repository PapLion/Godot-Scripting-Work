class_name HealthComponent
extends Node
## Reusable health, armor, and death-state component for any damageable entity.
## Completely decoupled from weapon implementations.

signal damaged(info: FPSEvents.DamageInfo)
signal health_changed(current_health: float, max_health: float)
signal armor_changed(current_armor: float, max_armor: float)
signal died(killing_blow: FPSEvents.DamageInfo)
signal reset_completed()

@export var max_health: float = 100.0
@export var max_armor: float = 0.0
@export_range(0.0, 0.9, 0.05) var armor_absorption_ratio: float = 0.5
@export var start_with_full_armor: bool = true

var current_health: float = 100.0
var current_armor: float = 0.0
var is_dead: bool = false


func _ready() -> void:
	reset_health()


func reset_health() -> void:
	is_dead = false
	current_health = maxf(1.0, max_health)
	current_armor = maxf(0.0, max_armor) if start_with_full_armor else 0.0
	health_changed.emit(current_health, max_health)
	armor_changed.emit(current_armor, max_armor)
	reset_completed.emit()


func apply_damage(info: FPSEvents.DamageInfo) -> FPSEvents.DamageInfo:
	if info == null or is_dead or info.raw_damage <= 0.0:
		if info != null:
			info.final_damage = 0.0
			info.armor_absorbed = 0.0
		return info

	var incoming := info.raw_damage
	var absorbed := 0.0

	if current_armor > 0.0 and armor_absorption_ratio > 0.0:
		var desired_absorb := incoming * armor_absorption_ratio
		absorbed = minf(current_armor, desired_absorb)
		current_armor = maxf(0.0, current_armor - absorbed)
		armor_changed.emit(current_armor, max_armor)

	var health_damage := maxf(0.0, incoming - absorbed)
	info.armor_absorbed = absorbed
	info.final_damage = health_damage

	current_health = maxf(0.0, current_health - health_damage)
	health_changed.emit(current_health, max_health)
	damaged.emit(info)

	if current_health <= 0.0 and not is_dead:
		is_dead = true
		died.emit(info)

	return info


func heal(amount: float) -> void:
	if is_dead or amount <= 0.0:
		return
	current_health = minf(max_health, current_health + amount)
	health_changed.emit(current_health, max_health)


func get_health_ratio() -> float:
	return current_health / maxf(1.0, max_health)


func get_armor_ratio() -> float:
	if max_armor <= 0.0:
		return 0.0
	return current_armor / max_armor
