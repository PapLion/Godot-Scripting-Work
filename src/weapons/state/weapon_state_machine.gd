class_name WeaponStateMachine
extends RefCounted
## Explicit multi-dimensional weapon state machine.
## Separates Action, Aim, and Sprint dimensions to eliminate contradictory booleans
## and enforce safe transitions across firing, reloading, ADS, sprinting, and switching.

signal action_state_changed(previous_state: ActionState, new_state: ActionState)
signal aim_state_changed(previous_state: AimState, new_state: AimState)
signal sprint_state_changed(previous_state: SprintState, new_state: SprintState)

enum ActionState {
	IDLE = 0,
	FIRING = 1,
	RELOADING = 2,
	EQUIPPING = 3,
	UNEQUIPPING = 4,
}

enum AimState {
	HIP = 0,
	AIMING = 1,
}

enum SprintState {
	NORMAL = 0,
	SPRINTING = 1,
}

var action_state: ActionState = ActionState.IDLE
var aim_state: AimState = AimState.HIP
var sprint_state: SprintState = SprintState.NORMAL


func set_action_state(next_state: ActionState) -> bool:
	if next_state == action_state:
		return false
	var prev := action_state
	action_state = next_state

	# Enforce cross-dimension invariants
	if next_state in [ActionState.RELOADING, ActionState.EQUIPPING, ActionState.UNEQUIPPING]:
		set_aim_state(AimState.HIP)
	if next_state == ActionState.FIRING:
		set_sprint_state(SprintState.NORMAL)

	action_state_changed.emit(prev, next_state)
	return true


func set_aim_state(next_state: AimState) -> bool:
	if next_state == AimState.AIMING and not can_aim():
		next_state = AimState.HIP
	if next_state == aim_state:
		return false
	var prev := aim_state
	aim_state = next_state
	if next_state == AimState.AIMING:
		set_sprint_state(SprintState.NORMAL)
	aim_state_changed.emit(prev, next_state)
	return true


func set_sprint_state(next_state: SprintState) -> bool:
	if next_state == SprintState.SPRINTING and not can_sprint():
		next_state = SprintState.NORMAL
	if next_state == sprint_state:
		return false
	var prev := sprint_state
	sprint_state = next_state
	if next_state == SprintState.SPRINTING:
		set_aim_state(AimState.HIP)
	sprint_state_changed.emit(prev, next_state)
	return true


func can_fire(allow_reload_interrupt: bool = false) -> bool:
	match action_state:
		ActionState.IDLE, ActionState.FIRING:
			return true
		ActionState.RELOADING:
			return allow_reload_interrupt
		_:
			return false


func can_reload() -> bool:
	return action_state in [ActionState.IDLE, ActionState.FIRING]


func can_aim() -> bool:
	return action_state in [ActionState.IDLE, ActionState.FIRING]


func can_sprint() -> bool:
	return action_state in [ActionState.IDLE, ActionState.RELOADING, ActionState.EQUIPPING]


func can_switch_weapon() -> bool:
	return action_state != ActionState.UNEQUIPPING


func is_aiming() -> bool:
	return aim_state == AimState.AIMING


func is_sprinting() -> bool:
	return sprint_state == SprintState.SPRINTING


func is_reloading() -> bool:
	return action_state == ActionState.RELOADING


func reset_to_idle() -> void:
	set_aim_state(AimState.HIP)
	set_sprint_state(SprintState.NORMAL)
	set_action_state(ActionState.IDLE)


static func get_action_name(s: ActionState) -> String:
	match s:
		ActionState.IDLE:
			return "IDLE"
		ActionState.FIRING:
			return "FIRING"
		ActionState.RELOADING:
			return "RELOADING"
		ActionState.EQUIPPING:
			return "EQUIPPING"
		ActionState.UNEQUIPPING:
			return "UNEQUIPPING"
		_:
			return "UNKNOWN"
