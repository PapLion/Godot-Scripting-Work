class_name TargetDummy
extends Node3D
## Reusable FPS practice target with separate Head (2.0x) and Body (1.0x) HitboxComponents,
## optional armor, optional lateral movement rail, hit flash, knock-down death, and reset/respawn.

signal target_damaged(info: FPSEvents.DamageInfo)
signal target_killed(target: TargetDummy)
signal target_reset(target: TargetDummy)

@export_group("Health & Armor")
@export var target_label: String = "TARGET"
@export var max_health: float = 100.0
@export var max_armor: float = 0.0
@export_range(0.0, 0.9, 0.05) var armor_absorption_ratio: float = 0.5
@export var auto_respawn: bool = true
@export var respawn_delay: float = 3.5

@export_group("Movement Rail")
@export var move_enabled: bool = false
@export var move_distance: float = 3.5
@export var move_speed: float = 2.2

@export_group("Visuals")
@export var body_color: Color = Color(0.24, 0.44, 0.66)
@export var head_color: Color = Color(0.86, 0.34, 0.24)
@export var armor_tint_color: Color = Color(0.22, 0.52, 0.42)

@onready var health_component: HealthComponent = $HealthComponent
@onready var pivot: Node3D = $Pivot
@onready var body_mesh: MeshInstance3D = $Pivot/BodyMesh
@onready var head_mesh: MeshInstance3D = $Pivot/HeadMesh
@onready var body_hitbox: HitboxComponent = $Pivot/BodyHitbox
@onready var head_hitbox: HitboxComponent = $Pivot/HeadHitbox
@onready var status_label: Label3D = $Pivot/StatusLabel
@onready var damage_popup_label: Label3D = $Pivot/DamagePopupLabel

var _origin_position: Vector3 = Vector3.ZERO
var _move_time: float = 0.0
var _respawn_timer: float = 0.0
var _flash_timer: float = 0.0
var _popup_timer: float = 0.0
var _body_mat: StandardMaterial3D
var _head_mat: StandardMaterial3D


func _ready() -> void:
	_origin_position = position
	add_to_group("range_targets")

	health_component.max_health = max_health
	health_component.max_armor = max_armor
	health_component.armor_absorption_ratio = armor_absorption_ratio
	health_component.reset_health()

	body_hitbox.health_component = health_component
	head_hitbox.health_component = health_component

	health_component.damaged.connect(_on_damaged)
	health_component.died.connect(_on_died)

	_setup_materials()
	_refresh_status_label()
	if damage_popup_label != null:
		damage_popup_label.text = ""


func _process(delta: float) -> void:
	if move_enabled and not health_component.is_dead:
		_move_time += delta * move_speed
		position = _origin_position + transform.basis.x * (sin(_move_time) * move_distance)

	if _flash_timer > 0.0:
		_flash_timer -= delta
		if _flash_timer <= 0.0:
			_apply_idle_colors()

	if _popup_timer > 0.0:
		_popup_timer -= delta
		if damage_popup_label != null:
			damage_popup_label.position.y += delta * 0.45
			if _popup_timer <= 0.0:
				damage_popup_label.text = ""

	if health_component.is_dead and auto_respawn:
		_respawn_timer -= delta
		if _respawn_timer <= 0.0:
			reset_target()


func reset_target() -> void:
	_respawn_timer = 0.0
	_flash_timer = 0.0
	health_component.reset_health()
	if body_hitbox != null:
		body_hitbox.set_deferred("monitorable", true)
		body_hitbox.collision_layer = 1 << 2
	if head_hitbox != null:
		head_hitbox.set_deferred("monitorable", true)
		head_hitbox.collision_layer = 1 << 2
	var tw := create_tween()
	tw.tween_property(pivot, "rotation_degrees:x", 0.0, 0.22).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	_apply_idle_colors()
	_refresh_status_label()
	target_reset.emit(self)


func _on_damaged(info: FPSEvents.DamageInfo) -> void:
	_flash_timer = 0.11
	if info.is_critical and _head_mat != null:
		_head_mat.albedo_color = Color(1.0, 0.92, 0.35)
		_head_mat.emission_enabled = true
		_head_mat.emission = Color(1.0, 0.35, 0.15)
	elif _body_mat != null:
		_body_mat.albedo_color = Color(1.0, 0.92, 0.72)

	if damage_popup_label != null:
		var suffix := " CRIT!" if info.is_critical else ""
		var armor_txt := (" (-%.0f ARM)" % info.armor_absorbed) if info.armor_absorbed > 0.5 else ""
		damage_popup_label.text = "-%.0f%s%s" % [info.final_damage, suffix, armor_txt]
		damage_popup_label.modulate = Color(1.0, 0.28, 0.22) if info.is_critical else Color(1.0, 0.94, 0.55)
		damage_popup_label.position = Vector3(0.0, 2.28, 0.0)
		_popup_timer = 0.85

	# Subtle knockback wobble
	if not health_component.is_dead:
		var tw := create_tween()
		tw.tween_property(pivot, "rotation_degrees:x", -10.0, 0.05)
		tw.tween_property(pivot, "rotation_degrees:x", 0.0, 0.14).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)

	_refresh_status_label()
	target_damaged.emit(info)


func _on_died(_killing_blow: FPSEvents.DamageInfo) -> void:
	_respawn_timer = respawn_delay
	if body_hitbox != null:
		body_hitbox.collision_layer = 0
	if head_hitbox != null:
		head_hitbox.collision_layer = 0

	var tw := create_tween()
	tw.tween_property(pivot, "rotation_degrees:x", -88.0, 0.28).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)
	_refresh_status_label()
	target_killed.emit(self)


func _setup_materials() -> void:
	_body_mat = StandardMaterial3D.new()
	_body_mat.roughness = 0.55
	_head_mat = StandardMaterial3D.new()
	_head_mat.roughness = 0.45
	if body_mesh != null:
		body_mesh.material_override = _body_mat
	if head_mesh != null:
		head_mesh.material_override = _head_mat
	_apply_idle_colors()


func _apply_idle_colors() -> void:
	if _body_mat != null:
		_body_mat.albedo_color = armor_tint_color if health_component.current_armor > 0.0 else body_color
	if _head_mat != null:
		_head_mat.albedo_color = head_color
		_head_mat.emission_enabled = false


func _refresh_status_label() -> void:
	if status_label == null:
		return
	if health_component.is_dead:
		status_label.text = "%s\nDOWN" % target_label
		status_label.modulate = Color(0.85, 0.35, 0.35)
		return

	if max_armor > 0.0:
		status_label.text = "%s\nHP %.0f | ARM %.0f" % [
			target_label,
			health_component.current_health,
			health_component.current_armor,
		]
	else:
		status_label.text = "%s\nHP %.0f / %.0f" % [
			target_label,
			health_component.current_health,
			health_component.max_health,
		]
	status_label.modulate = Color(0.95, 0.97, 1.0)
