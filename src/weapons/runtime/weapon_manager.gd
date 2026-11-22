class_name WeaponManager
extends Node3D
## Core orchestrator for weapon loadout, state machine, firing modes, recoil, spread,
## ADS transitions, magazine/shell-by-shell reloading, attachments, and weapon switching.

signal weapon_equipped(weapon: WeaponInstance, slot_index: int)
signal ammo_updated(current_mag: int, reserve_ammo: int, max_mag: int)
signal fire_mode_updated(mode: WeaponData.FireMode)
signal shot_fired(summary: FPSEvents.ShotSummary)
signal hit_confirmed(is_critical: bool, is_kill: bool, total_damage: float)
signal reload_started(is_empty: bool, is_shell_by_shell: bool)
signal reload_finished(was_interrupted: bool)
signal state_changed(action_state: WeaponStateMachine.ActionState, aim_state: WeaponStateMachine.AimState)
signal attachments_updated(active_attachments: Array[AttachmentData])

enum ShellReloadStage {
	NONE = 0,
	STARTING = 1,
	INSERTING = 2,
	ENDING = 3,
}

@export var starting_weapons: Array[WeaponData] = []
@export var available_attachments: Array[AttachmentData] = []
@export var eject_shells_enabled: bool = true

var state_machine := WeaponStateMachine.new()
var recoil_controller := RecoilController.new()
var spread_controller := SpreadController.new()

var loadout: Array[WeaponInstance] = []
var current_slot: int = -1
var ads_alpha: float = 0.0

var _camera: Camera3D
var _viewmodel: WeaponViewmodel
var _fx_manager: ImpactFXManager
var _instigator: Node
var _exclude_rids: Array[RID] = []

var _fire_cooldown: float = 0.0
var _dry_fire_cooldown: float = 0.0
var _action_timer: float = 0.0
var _pending_slot: int = -1
var _shell_stage: ShellReloadStage = ShellReloadStage.NONE
var _burst_remaining: int = 0
var _trigger_held: bool = false
var _trigger_consumed_semi: bool = false
var _aim_requested: bool = false
var _sprint_requested: bool = false

var _audio_weapon: AudioStreamPlayer
var _audio_feedback: AudioStreamPlayer


func _ready() -> void:
	_audio_weapon = AudioStreamPlayer.new()
	_audio_weapon.name = "WeaponAudio"
	_audio_weapon.volume_db = -5.0
	add_child(_audio_weapon)

	_audio_feedback = AudioStreamPlayer.new()
	_audio_feedback.name = "HitFeedbackAudio"
	_audio_feedback.volume_db = -4.0
	add_child(_audio_feedback)

	state_machine.action_state_changed.connect(_on_state_machine_changed)
	state_machine.aim_state_changed.connect(_on_aim_state_changed)


func initialize(
	camera: Camera3D,
	viewmodel: WeaponViewmodel,
	fx_manager: ImpactFXManager,
	instigator: Node,
	exclude_rids: Array[RID]
) -> void:
	_camera = camera
	_viewmodel = viewmodel
	_fx_manager = fx_manager
	_instigator = instigator
	_exclude_rids = exclude_rids

	loadout.clear()
	for w_data in starting_weapons:
		if w_data != null:
			loadout.append(WeaponInstance.new(w_data))

	if not loadout.is_empty():
		_equip_slot_immediate(0)


func get_current_weapon() -> WeaponInstance:
	if current_slot < 0 or current_slot >= loadout.size():
		return null
	return loadout[current_slot]


func set_trigger_held(held: bool) -> void:
	if held and not _trigger_held:
		_trigger_consumed_semi = false
		_try_trigger_pressed()
	elif not held:
		_trigger_consumed_semi = false
	_trigger_held = held


func set_aim_requested(aiming: bool) -> void:
	_aim_requested = aiming
	if aiming and state_machine.can_aim():
		state_machine.set_aim_state(WeaponStateMachine.AimState.AIMING)
	elif not aiming:
		state_machine.set_aim_state(WeaponStateMachine.AimState.HIP)


func set_sprint_requested(sprinting: bool) -> void:
	_sprint_requested = sprinting
	if sprinting and state_machine.can_sprint() and not _trigger_held:
		state_machine.set_sprint_state(WeaponStateMachine.SprintState.SPRINTING)
	else:
		state_machine.set_sprint_state(WeaponStateMachine.SprintState.NORMAL)


func request_reload() -> bool:
	var weapon := get_current_weapon()
	if weapon == null:
		return false
	if not state_machine.can_reload():
		return false
	if not weapon.needs_reload():
		return false

	_burst_remaining = 0
	var is_empty := weapon.is_empty_reload()
	var is_shell := (weapon.data.reload_type == WeaponData.ReloadType.SHELL_BY_SHELL)

	state_machine.set_action_state(WeaponStateMachine.ActionState.RELOADING)
	if is_shell:
		_shell_stage = ShellReloadStage.STARTING
		_action_timer = weapon.stats.shell_reload_start_duration
	else:
		_shell_stage = ShellReloadStage.NONE
		_action_timer = weapon.stats.empty_reload_duration if is_empty else weapon.stats.tactical_reload_duration

	_play_weapon_sound(&"reload_mag_out")
	reload_started.emit(is_empty, is_shell)
	return true


func request_cycle_fire_mode() -> bool:
	var weapon := get_current_weapon()
	if weapon == null:
		return false
	if state_machine.action_state in [WeaponStateMachine.ActionState.EQUIPPING, WeaponStateMachine.ActionState.UNEQUIPPING]:
		return false
	if weapon.cycle_fire_mode():
		_play_weapon_sound(&"fire_mode")
		fire_mode_updated.emit(weapon.get_current_fire_mode())
		return true
	return false


func request_switch_slot(slot_index: int) -> bool:
	if slot_index < 0 or slot_index >= loadout.size():
		return false
	if slot_index == current_slot and _pending_slot == -1:
		return false
	if not state_machine.can_switch_weapon():
		_pending_slot = slot_index
		return true

	# Cancel active reload cleanly without duplicating ammo
	if state_machine.is_reloading():
		_cancel_reload(true)

	_pending_slot = slot_index
	_burst_remaining = 0
	var current := get_current_weapon()
	_action_timer = current.data.unequip_duration if current != null else 0.15
	state_machine.set_action_state(WeaponStateMachine.ActionState.UNEQUIPPING)
	return true


func request_switch_relative(delta_slot: int) -> bool:
	if loadout.size() <= 1:
		return false
	var target := wrapi(current_slot + delta_slot, 0, loadout.size())
	return request_switch_slot(target)


func toggle_attachment_by_slot(slot: AttachmentData.Slot) -> bool:
	var weapon := get_current_weapon()
	if weapon == null:
		return false
	var candidate := _find_available_attachment(slot)
	if candidate == null:
		return false

	# If toggling magazine while reloading, cancel reload safely to keep ammo consistent
	if slot == AttachmentData.Slot.MAGAZINE and state_machine.is_reloading():
		_cancel_reload(true)

	var equipped := weapon.toggle_attachment(candidate)
	if _viewmodel != null:
		_viewmodel.update_attachments(weapon)
	_play_weapon_sound(&"fire_mode")
	ammo_updated.emit(weapon.current_mag, weapon.reserve_ammo, weapon.stats.magazine_capacity)
	attachments_updated.emit(weapon.get_active_attachments())
	return equipped


func equip_attachment(attachment: AttachmentData) -> void:
	var weapon := get_current_weapon()
	if weapon == null or attachment == null:
		return
	if attachment.slot == AttachmentData.Slot.MAGAZINE and state_machine.is_reloading():
		_cancel_reload(true)
	weapon.equip_attachment(attachment)
	if _viewmodel != null:
		_viewmodel.update_attachments(weapon)
	ammo_updated.emit(weapon.current_mag, weapon.reserve_ammo, weapon.stats.magazine_capacity)
	attachments_updated.emit(weapon.get_active_attachments())


func refill_all_ammo() -> void:
	for w in loadout:
		w.refill_ammo()
	var current := get_current_weapon()
	if current != null:
		ammo_updated.emit(current.current_mag, current.reserve_ammo, current.stats.magazine_capacity)


func step(
	delta: float,
	move_ratio: float,
	is_crouching: bool,
	is_grounded: bool
) -> void:
	var weapon := get_current_weapon()
	if weapon == null:
		return

	if _fire_cooldown > 0.0:
		_fire_cooldown = maxf(0.0, _fire_cooldown - delta)
	if _dry_fire_cooldown > 0.0:
		_dry_fire_cooldown = maxf(0.0, _dry_fire_cooldown - delta)

	# Action state timers (Reload, Equip, Unequip)
	_step_action_timers(delta, weapon)

	# Re-evaluate ADS & Sprint intentions if state now allows them
	if _aim_requested and state_machine.can_aim() and not state_machine.is_aiming():
		state_machine.set_aim_state(WeaponStateMachine.AimState.AIMING)
	elif not _aim_requested and state_machine.is_aiming():
		state_machine.set_aim_state(WeaponStateMachine.AimState.HIP)

	if _sprint_requested and state_machine.can_sprint() and not _trigger_held and not _aim_requested:
		state_machine.set_sprint_state(WeaponStateMachine.SprintState.SPRINTING)
	elif (not _sprint_requested or _trigger_held or _aim_requested) and state_machine.is_sprinting():
		state_machine.set_sprint_state(WeaponStateMachine.SprintState.NORMAL)

	# Smooth ADS interpolation
	var ads_target := 1.0 if state_machine.is_aiming() else 0.0
	var ads_blend := 1.0 - exp(-weapon.stats.ads_transition_speed * delta)
	ads_alpha = lerpf(ads_alpha, ads_target, ads_blend)
	if absf(ads_alpha - ads_target) < 0.002:
		ads_alpha = ads_target

	# Continuous fire (AUTO / BURST)
	_step_firing(weapon, is_crouching)

	# Update Recoil & Spread
	recoil_controller.update(delta, weapon.stats)
	spread_controller.update(delta, weapon.stats, ads_alpha, move_ratio, is_crouching, is_grounded)

	# Return FIRING -> IDLE once cooldown completes and trigger is not actively firing
	if state_machine.action_state == WeaponStateMachine.ActionState.FIRING and _fire_cooldown <= 0.0 and _burst_remaining <= 0:
		if not _trigger_held or weapon.get_current_fire_mode() == WeaponData.FireMode.SEMI or weapon.current_mag <= 0:
			state_machine.set_action_state(WeaponStateMachine.ActionState.IDLE)

	# Update Viewmodel transform
	if _viewmodel != null:
		var is_equip_transition := state_machine.action_state in [
			WeaponStateMachine.ActionState.EQUIPPING,
			WeaponStateMachine.ActionState.UNEQUIPPING,
		]
		_viewmodel.update_transform(
			delta,
			ads_alpha,
			state_machine.is_sprinting(),
			state_machine.is_reloading(),
			is_equip_transition,
			move_ratio,
			is_grounded
		)


func get_current_spread_deg() -> float:
	return spread_controller.current_spread_deg


func get_current_recoil_deg() -> Vector2:
	return recoil_controller.current_offset_deg


func get_ads_sensitivity_multiplier() -> float:
	var weapon := get_current_weapon()
	if weapon == null:
		return 1.0
	return lerpf(1.0, weapon.stats.ads_sensitivity_multiplier, ads_alpha)


func get_target_fov(base_fov: float) -> float:
	var weapon := get_current_weapon()
	if weapon == null:
		return base_fov
	return lerpf(base_fov, weapon.stats.ads_fov, ads_alpha)


func _try_trigger_pressed() -> void:
	var weapon := get_current_weapon()
	if weapon == null:
		return

	# Interruptible shell-by-shell reload on fire press
	if state_machine.is_reloading() and _can_interrupt_shell_reload(weapon):
		_cancel_reload(true)

	if not state_machine.can_fire(false):
		return

	if not weapon.can_consume_round():
		_play_dry_fire()
		return

	if weapon.get_current_fire_mode() == WeaponData.FireMode.BURST and _burst_remaining <= 0:
		_burst_remaining = weapon.data.burst_count


func _step_firing(weapon: WeaponInstance, is_crouching: bool) -> void:
	if _fire_cooldown > 0.0:
		return

	var should_fire := false
	var mode := weapon.get_current_fire_mode()

	if _burst_remaining > 0:
		should_fire = true
	elif _trigger_held:
		match mode:
			WeaponData.FireMode.AUTO:
				should_fire = true
			WeaponData.FireMode.SEMI:
				if not _trigger_consumed_semi:
					should_fire = true
			WeaponData.FireMode.BURST:
				if not _trigger_consumed_semi:
					_burst_remaining = weapon.data.burst_count
					should_fire = true

	if not should_fire:
		return

	if state_machine.is_reloading() and _can_interrupt_shell_reload(weapon):
		_cancel_reload(true)

	if not state_machine.can_fire(false):
		return

	if not weapon.can_consume_round():
		_burst_remaining = 0
		if not _trigger_consumed_semi:
			_play_dry_fire()
			_trigger_consumed_semi = true
		return

	_execute_shot(weapon, is_crouching)
	if mode == WeaponData.FireMode.SEMI or mode == WeaponData.FireMode.BURST:
		_trigger_consumed_semi = true
	if _burst_remaining > 0:
		_burst_remaining -= 1


func _execute_shot(weapon: WeaponInstance, is_crouching: bool) -> void:
	if not weapon.consume_round():
		return

	state_machine.set_action_state(WeaponStateMachine.ActionState.FIRING)
	_fire_cooldown = weapon.stats.fire_interval
	ammo_updated.emit(weapon.current_mag, weapon.reserve_ammo, weapon.stats.magazine_capacity)

	# Fire ballistics from camera center (with real recoil & spread)
	var summary := FPSEvents.ShotSummary.new()
	summary.weapon_id = weapon.data.weapon_id
	if _camera != null and is_inside_tree():
		var muzzle_pos := _viewmodel.get_muzzle_global_position() if _viewmodel != null else _camera.global_position
		summary = BallisticSolver.fire_shot(
			_camera.get_world_3d().direct_space_state,
			_camera.global_transform,
			muzzle_pos,
			weapon.data.weapon_id,
			weapon.stats,
			spread_controller,
			spread_controller.current_spread_deg,
			_exclude_rids,
			_instigator
		)

	# Apply recoil kick & spread bloom
	recoil_controller.add_shot_kick(weapon.stats, state_machine.is_aiming(), is_crouching)
	spread_controller.add_shot_bloom(weapon.stats)

	# Viewmodel kick, muzzle flash, audio, FX, shell ejection
	if _viewmodel != null:
		_viewmodel.trigger_fire_kick()
	_play_weapon_sound(weapon.data.fire_sound_id)

	if _fx_manager != null:
		_fx_manager.spawn_shot_fx(summary, weapon.data.tracer_color)

	if eject_shells_enabled and _viewmodel != null and is_inside_tree():
		_spawn_ejected_shell(weapon.data)

	shot_fired.emit(summary)

	if summary.any_damageable_hit:
		if summary.any_kill:
			_play_feedback_sound(&"hit_kill")
		elif summary.any_critical_hit:
			_play_feedback_sound(&"hit_head")
		else:
			_play_feedback_sound(&"hit_body")
		hit_confirmed.emit(summary.any_critical_hit, summary.any_kill, summary.total_damage)


func _step_action_timers(delta: float, weapon: WeaponInstance) -> void:
	match state_machine.action_state:
		WeaponStateMachine.ActionState.RELOADING:
			_action_timer -= delta
			if _action_timer > 0.0:
				return
			if weapon.data.reload_type == WeaponData.ReloadType.SHELL_BY_SHELL:
				_advance_shell_reload(weapon)
			else:
				weapon.complete_magazine_reload()
				ammo_updated.emit(weapon.current_mag, weapon.reserve_ammo, weapon.stats.magazine_capacity)
				_play_weapon_sound(&"reload_mag_in")
				state_machine.set_action_state(WeaponStateMachine.ActionState.IDLE)
				reload_finished.emit(false)

		WeaponStateMachine.ActionState.UNEQUIPPING:
			_action_timer -= delta
			if _action_timer <= 0.0:
				var next_slot := _pending_slot
				_pending_slot = -1
				if next_slot >= 0 and next_slot < loadout.size():
					_equip_slot_with_transition(next_slot)
				else:
					state_machine.set_action_state(WeaponStateMachine.ActionState.IDLE)

		WeaponStateMachine.ActionState.EQUIPPING:
			_action_timer -= delta
			if _action_timer <= 0.0:
				state_machine.set_action_state(WeaponStateMachine.ActionState.IDLE)
				if _pending_slot >= 0 and _pending_slot != current_slot:
					request_switch_slot(_pending_slot)


func _advance_shell_reload(weapon: WeaponInstance) -> void:
	match _shell_stage:
		ShellReloadStage.STARTING:
			_shell_stage = ShellReloadStage.INSERTING
			_action_timer = weapon.stats.shell_reload_insert_duration

		ShellReloadStage.INSERTING:
			var inserted := weapon.insert_single_shell()
			if inserted:
				_play_weapon_sound(&"reload_shell")
				ammo_updated.emit(weapon.current_mag, weapon.reserve_ammo, weapon.stats.magazine_capacity)
			if weapon.current_mag >= weapon.stats.magazine_capacity or weapon.reserve_ammo <= 0:
				_shell_stage = ShellReloadStage.ENDING
				_action_timer = weapon.stats.shell_reload_end_duration
			else:
				_action_timer = weapon.stats.shell_reload_insert_duration

		ShellReloadStage.ENDING:
			_shell_stage = ShellReloadStage.NONE
			_play_weapon_sound(&"equip")
			state_machine.set_action_state(WeaponStateMachine.ActionState.IDLE)
			reload_finished.emit(false)


func _can_interrupt_shell_reload(weapon: WeaponInstance) -> bool:
	return (
		weapon.data.reload_type == WeaponData.ReloadType.SHELL_BY_SHELL
		and weapon.current_mag > 0
	)


func _cancel_reload(was_interrupted: bool) -> void:
	_shell_stage = ShellReloadStage.NONE
	_action_timer = 0.0
	if state_machine.is_reloading():
		state_machine.set_action_state(WeaponStateMachine.ActionState.IDLE)
		reload_finished.emit(was_interrupted)


func _equip_slot_immediate(slot_index: int) -> void:
	current_slot = slot_index
	var weapon := get_current_weapon()
	recoil_controller.reset()
	spread_controller.reset()
	ads_alpha = 0.0
	_fire_cooldown = 0.0
	_burst_remaining = 0
	state_machine.reset_to_idle()
	if _viewmodel != null and weapon != null:
		_viewmodel.configure_weapon(weapon)
	_emit_current_weapon_signals()


func _equip_slot_with_transition(slot_index: int) -> void:
	current_slot = slot_index
	var weapon := get_current_weapon()
	recoil_controller.reset()
	spread_controller.reset()
	ads_alpha = 0.0
	_fire_cooldown = 0.0
	_burst_remaining = 0
	_action_timer = weapon.data.equip_duration if weapon != null else 0.25
	state_machine.set_action_state(WeaponStateMachine.ActionState.EQUIPPING)
	if _viewmodel != null and weapon != null:
		_viewmodel.configure_weapon(weapon)
	_play_weapon_sound(&"equip")
	_emit_current_weapon_signals()


func _emit_current_weapon_signals() -> void:
	var weapon := get_current_weapon()
	if weapon == null:
		return
	weapon_equipped.emit(weapon, current_slot)
	ammo_updated.emit(weapon.current_mag, weapon.reserve_ammo, weapon.stats.magazine_capacity)
	fire_mode_updated.emit(weapon.get_current_fire_mode())
	attachments_updated.emit(weapon.get_active_attachments())


func _spawn_ejected_shell(data: WeaponData) -> void:
	var shell := ShellCasing.new()
	var is_shotgun := (data.visual_preset == WeaponData.VisualPreset.SHOTGUN)
	shell.setup(data.eject_shell_color, is_shotgun)
	var parent := get_tree().current_scene
	if parent == null:
		return
	parent.add_child(shell)
	var xf := _viewmodel.get_eject_global_transform()
	shell.global_transform = xf
	var right_dir := xf.basis.x.normalized()
	var up_dir := xf.basis.y.normalized()
	shell.linear_velocity = right_dir * randf_range(1.4, 2.2) + up_dir * randf_range(0.8, 1.4)
	shell.angular_velocity = Vector3(randf_range(-10.0, 10.0), randf_range(-10.0, 10.0), randf_range(-10.0, 10.0))


func _find_available_attachment(slot: AttachmentData.Slot) -> AttachmentData:
	for att in available_attachments:
		if att != null and att.slot == slot:
			return att
	return null


func _play_dry_fire() -> void:
	if _dry_fire_cooldown > 0.0:
		return
	_dry_fire_cooldown = 0.22
	_play_weapon_sound(&"dry_fire")


func _play_weapon_sound(sound_id: StringName) -> void:
	if _audio_weapon == null:
		return
	_audio_weapon.stream = ProceduralAudio.get_sound(sound_id)
	_audio_weapon.pitch_scale = randf_range(0.96, 1.04)
	_audio_weapon.play()


func _play_feedback_sound(sound_id: StringName) -> void:
	if _audio_feedback == null:
		return
	_audio_feedback.stream = ProceduralAudio.get_sound(sound_id)
	_audio_feedback.pitch_scale = 1.0
	_audio_feedback.play()


func _on_state_machine_changed(_prev: WeaponStateMachine.ActionState, next_state: WeaponStateMachine.ActionState) -> void:
	state_changed.emit(next_state, state_machine.aim_state)


func _on_aim_state_changed(_prev: WeaponStateMachine.AimState, next_state: WeaponStateMachine.AimState) -> void:
	state_changed.emit(state_machine.action_state, next_state)
