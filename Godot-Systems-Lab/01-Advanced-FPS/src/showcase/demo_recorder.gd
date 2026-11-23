class_name DemoRecorder
extends Node
## Reproducible scripted showcase controller for portfolio video/screenshot capture.
## Drives REAL FPSPlayer and WeaponManager methods (never faked animations).
## Activated only when launched with `-- --demo-mode=<main|clip1|clip2|clip3|clip4|shots>`.

var _range: RangeController
var _player: FPSPlayer
var _wm: WeaponManager
var _mode: String = ""
var _elapsed: float = 0.0
var _step_idx: int = 0
var _aim_target: Vector3 = Vector3(0.0, 1.2, -6.0)
var _smooth_aim: Vector3 = Vector3(0.0, 1.2, -6.0)
var _shot_dir: String = ""


func setup(range_ctrl: RangeController, mode: String) -> void:
	_range = range_ctrl
	_player = range_ctrl.player
	_wm = _player.weapon_manager
	_mode = mode
	_shot_dir = ProjectSettings.globalize_path("res://portfolio_media/screenshots")
	DirAccess.make_dir_recursive_absolute(_shot_dir)

	_player.scripted_control = true
	Input.set_mouse_mode(Input.MOUSE_MODE_VISIBLE)
	_smooth_aim = _get_target_point("TargetArmored12m", "BodyHitbox")
	_aim_target = _smooth_aim


func _physics_process(delta: float) -> void:
	if _player == null or _wm == null:
		return
	_elapsed += delta
	_smooth_aim = _smooth_aim.lerp(_aim_target, 1.0 - exp(-9.0 * delta))
	_player.look_at_world_point(_smooth_aim)

	match _mode:
		"main":
			_run_main_showcase()
		"clip1":
			_run_clip1_ar_ads_recoil()
		"clip2":
			_run_clip2_shotgun_shells()
		"clip3":
			_run_clip3_precision_hitboxes()
		"clip4":
			_run_clip4_attachments_switching()
		"tactical_selector":
			_run_clip5_fire_selector()
		"tactical_shoulder":
			_run_clip6_shoulder_switching()
		"tactical_lean":
			_run_clip7_tactical_lean()
		"tactical_shots":
			_run_tactical_screenshots()
		"penetration_demo":
			_run_clip8_surface_penetration()
		"vfx_surfaces_demo":
			_run_clip9_combat_vfx_surfaces()
		"pen_vfx_shots":
			_run_pen_vfx_screenshots()
		"shots":
			_run_screenshots_only()


func _get_target_point(target_name: String, hitbox_name: String) -> Vector3:
	var t := _range.targets_root.get_node_or_null(target_name)
	if t == null:
		return Vector3(0.0, 1.2, -10.0)
	var hb := t.get_node_or_null("Pivot/" + hitbox_name)
	if hb is Node3D:
		return (hb as Node3D).global_position
	return t.global_position + Vector3(0.0, 1.2, 0.0)


func _save_shot(filename: String) -> void:
	var img := get_viewport().get_texture().get_image()
	if img != null:
		img.save_png(_shot_dir.path_join(filename))
		print("[DemoRecorder] Saved screenshot: ", filename)


func _run_main_showcase() -> void:
	# 38-second comprehensive real gameplay showcase covering all 10 required demonstrations
	var t := _elapsed

	# 0-4s: Strafe movement & aiming across range
	if t < 1.8:
		_player.scripted_move_input = Vector2(0.85, -0.2)
		_aim_target = _get_target_point("TargetArmored12m", "BodyHitbox")
	elif t < 3.6:
		_player.scripted_move_input = Vector2(-0.85, 0.1)
		_aim_target = _get_target_point("TargetClose10m", "HeadHitbox")
	elif t < 4.5:
		_player.scripted_move_input = Vector2.ZERO
		_aim_target = _get_target_point("TargetArmored12m", "BodyHitbox")

	# 4.5-8.5s: AR-47 AUTO sustained fire (recoil + armor drain) -> recoil recovery
	if t >= 4.5 and t < 5.7:
		_wm.set_aim_requested(true)
		_wm.set_trigger_held(t >= 4.9 and t < 5.65)
	elif t >= 5.7 and t < 7.2:
		_wm.set_trigger_held(false)
		_wm.set_aim_requested(false)

	# 7.2-10.5s: Cycle to SEMI, crisp headshot on TargetClose10m, then tactical reload
	if _step_idx == 0 and t >= 7.2:
		_step_idx = 1
		_wm.request_cycle_fire_mode()
		_aim_target = _get_target_point("TargetClose10m", "HeadHitbox")
		_wm.set_aim_requested(true)
	if _step_idx == 1 and t >= 8.0:
		_step_idx = 2
		_wm.set_trigger_held(true)
	if _step_idx == 2 and t >= 8.2:
		_step_idx = 3
		_wm.set_trigger_held(false)
	if _step_idx == 3 and t >= 8.7:
		_step_idx = 4
		_wm.set_trigger_held(true)
	if _step_idx == 4 and t >= 8.9:
		_step_idx = 5
		_wm.set_trigger_held(false)
		_wm.set_aim_requested(false)
		_wm.request_reload()

	# 11.2-16.5s: Attachments showcase (Holo Optic, Compensator, Extended Mag, Laser) + AUTO burst on Moving Target
	if _step_idx == 5 and t >= 11.4:
		_step_idx = 6
		_wm.request_cycle_fire_mode() # back to AUTO
		_wm.toggle_attachment_by_slot(AttachmentData.Slot.OPTIC)
		_wm.toggle_attachment_by_slot(AttachmentData.Slot.MUZZLE)
	if _step_idx == 6 and t >= 12.2:
		_step_idx = 7
		_wm.toggle_attachment_by_slot(AttachmentData.Slot.MAGAZINE)
		_wm.toggle_attachment_by_slot(AttachmentData.Slot.UNDERBARREL)
		_wm.request_reload()
	if t >= 14.2 and t < 16.5:
		_aim_target = _get_target_point("TargetMoving20m", "BodyHitbox")
		_wm.set_aim_requested(true)
		_wm.set_trigger_held(t >= 14.6 and t < 15.8)

	# 16.5-24.5s: Switch to Shotgun (SG-870), fire 3 blasts (close target + steel plate), shell-by-shell reload + fire interrupt!
	if _step_idx == 7 and t >= 16.5:
		_step_idx = 8
		_wm.set_trigger_held(false)
		_wm.set_aim_requested(false)
		_wm.request_switch_slot(1)
		_aim_target = _get_target_point("TargetArmored12m", "BodyHitbox")
	if _step_idx == 8 and t >= 17.5:
		_step_idx = 9
		_wm.set_trigger_held(true)
	if _step_idx == 9 and t >= 17.7:
		_step_idx = 10
		_wm.set_trigger_held(false)
		_aim_target = Vector3(11.3, 1.4, -2.0) # Steel plate surface impact!
	if _step_idx == 10 and t >= 18.6:
		_step_idx = 11
		_wm.set_trigger_held(true)
	if _step_idx == 11 and t >= 18.8:
		_step_idx = 12
		_wm.set_trigger_held(false)
		_aim_target = _get_target_point("TargetClose10m", "BodyHitbox")
	if _step_idx == 12 and t >= 19.6:
		_step_idx = 13
		_wm.set_trigger_held(true)
	if _step_idx == 13 and t >= 19.8:
		_step_idx = 14
		_wm.set_trigger_held(false)
		_wm.request_reload() # Start shell-by-shell reload
	if _step_idx == 14 and t >= 21.5:
		_step_idx = 15
		# Interrupt shell-by-shell reload mid-load by firing!
		_wm.set_trigger_held(true)
	if _step_idx == 15 and t >= 21.7:
		_step_idx = 16
		_wm.set_trigger_held(false)

	# 23.0-34.0s: Switch to Precision Rifle (SR-14), high-zoom ADS, headshot 45m & 25m armored target
	if _step_idx == 16 and t >= 23.0:
		_step_idx = 17
		_range.reset_all_targets()
		_wm.request_switch_slot(2)
		_aim_target = _get_target_point("TargetLong45m", "HeadHitbox")
	if _step_idx == 17 and t >= 24.4:
		_step_idx = 18
		_wm.set_aim_requested(true)
	if _step_idx == 18 and t >= 25.5:
		_step_idx = 19
		_wm.set_trigger_held(true)
	if _step_idx == 19 and t >= 25.7:
		_step_idx = 20
		_wm.set_trigger_held(false)
		_aim_target = _get_target_point("TargetMid25m", "HeadHitbox")
	if _step_idx == 20 and t >= 27.3:
		_step_idx = 21
		_wm.set_trigger_held(true)
	if _step_idx == 21 and t >= 27.5:
		_step_idx = 22
		_wm.set_trigger_held(false)
	if _step_idx == 22 and t >= 28.8:
		_step_idx = 23
		_wm.set_trigger_held(true)
	if _step_idx == 23 and t >= 29.0:
		_step_idx = 24
		_wm.set_trigger_held(false)
		_wm.set_aim_requested(false)
		_wm.request_reload()

	# 32.0-38.0s: Switch back to AR, demonstrate Left-shoulder switch + Q/E corner peek around PeekPillarCenter!
	if _step_idx == 24 and t >= 32.0:
		_step_idx = 25
		_wm.request_switch_slot(0)
		_wm.toggle_shoulder_side() # Switch to Left shoulder
		_player.global_position = Vector3(-1.35, 0.2, 4.45)
		_aim_target = _get_target_point("TargetArmored12m", "BodyHitbox")
	if t >= 33.4 and t < 35.6:
		_player.scripted_lean = 1.0 # Lean right around cover pillar
		_wm.set_aim_requested(true)
		_wm.set_trigger_held(t >= 34.0 and t < 35.0)
	elif t >= 35.6 and t < 37.2:
		_wm.set_trigger_held(false)
		_player.scripted_lean = -1.0 # Lean left around cover pillar
		_aim_target = _get_target_point("TargetClose10m", "HeadHitbox")
		_wm.set_trigger_held(t >= 36.1 and t < 36.8)
	elif t >= 37.2:
		_wm.set_trigger_held(false)
		_wm.set_aim_requested(false)
		_player.scripted_lean = 0.0

	if t >= 38.0:
		get_tree().quit(0)


func _run_clip1_ar_ads_recoil() -> void:
	# 9s clip: AR-47 ADS, sustained recoil + recovery, tactical reload
	var t := _elapsed
	_aim_target = _get_target_point("TargetArmored12m", "BodyHitbox")
	if t >= 0.8 and t < 3.6:
		_wm.set_aim_requested(true)
		_wm.set_trigger_held(t >= 1.3 and t < 2.5)
	elif t >= 3.6 and t < 5.0:
		_wm.set_trigger_held(false)
		_wm.set_aim_requested(false)
	if _step_idx == 0 and t >= 4.2:
		_step_idx = 1
		_wm.request_reload()
	if _step_idx == 1 and t >= 6.5:
		_step_idx = 2
		_aim_target = _get_target_point("TargetClose10m", "HeadHitbox")
		_wm.set_aim_requested(true)
	if _step_idx == 2 and t >= 7.2:
		_step_idx = 3
		_wm.set_trigger_held(true)
	if _step_idx == 3 and t >= 7.7:
		_step_idx = 4
		_wm.set_trigger_held(false)
	if t >= 9.0:
		get_tree().quit(0)


func _run_clip2_shotgun_shells() -> void:
	# 9s clip: Shotgun multi-pellet blast, shell-by-shell reload, fire interrupt
	var t := _elapsed
	if _step_idx == 0:
		_step_idx = 1
		_wm._equip_slot_immediate(1)
		_aim_target = _get_target_point("TargetClose10m", "BodyHitbox")
	if _step_idx == 1 and t >= 1.0:
		_step_idx = 2
		_wm.set_trigger_held(true)
	if _step_idx == 2 and t >= 1.2:
		_step_idx = 3
		_wm.set_trigger_held(false)
		_aim_target = _get_target_point("TargetArmored12m", "BodyHitbox")
	if _step_idx == 3 and t >= 2.2:
		_step_idx = 4
		_wm.set_trigger_held(true)
	if _step_idx == 4 and t >= 2.4:
		_step_idx = 5
		_wm.set_trigger_held(false)
	if _step_idx == 5 and t >= 3.3:
		_step_idx = 6
		_wm.set_trigger_held(true)
	if _step_idx == 6 and t >= 3.5:
		_step_idx = 7
		_wm.set_trigger_held(false)
		_wm.request_reload()
	if _step_idx == 7 and t >= 5.6:
		_step_idx = 8
		_wm.set_trigger_held(true) # Interrupt shell reload!
	if _step_idx == 8 and t >= 5.8:
		_step_idx = 9
		_wm.set_trigger_held(false)
	if t >= 8.5:
		get_tree().quit(0)


func _run_clip3_precision_hitboxes() -> void:
	# 10s clip: AWP high-zoom scope ADS, 45m headshot -> visible right-hand BOLT_ACTION cycle -> 25m shot -> full reload!
	var t := _elapsed
	if _step_idx == 0:
		_step_idx = 1
		_wm._equip_slot_immediate(2)
		_aim_target = _get_target_point("TargetLong45m", "HeadHitbox")
	if _step_idx == 1 and t >= 0.8:
		_step_idx = 2
		_wm.set_aim_requested(true)
	if _step_idx == 2 and t >= 1.9:
		_step_idx = 3
		_wm.set_trigger_held(true)
	if _step_idx == 3 and t >= 2.05:
		_step_idx = 4
		_wm.set_trigger_held(false)
		# Drop ADS briefly so right-hand bolt-action cycling is clearly showcased!
		_wm.set_aim_requested(false)
		_aim_target = _get_target_point("TargetMid25m", "HeadHitbox")
	if _step_idx == 4 and t >= 3.3:
		_step_idx = 5
		_wm.set_aim_requested(true)
	if _step_idx == 5 and t >= 4.2:
		_step_idx = 6
		_wm.set_trigger_held(true)
	if _step_idx == 6 and t >= 4.35:
		_step_idx = 7
		_wm.set_trigger_held(false)
		_wm.set_aim_requested(false)
	if _step_idx == 7 and t >= 5.6:
		_step_idx = 8
		_wm.request_reload()
	if t >= 9.0:
		get_tree().quit(0)


func _run_clip4_attachments_switching() -> void:
	# 9s clip: Attachment toggling (Optic, Compensator, Extended Mag, Laser) + Weapon switching
	var t := _elapsed
	_aim_target = _get_target_point("TargetArmored12m", "BodyHitbox")
	if _step_idx == 0 and t >= 0.8:
		_step_idx = 1
		_wm.toggle_attachment_by_slot(AttachmentData.Slot.OPTIC)
	if _step_idx == 1 and t >= 1.6:
		_step_idx = 2
		_wm.toggle_attachment_by_slot(AttachmentData.Slot.MUZZLE)
	if _step_idx == 2 and t >= 2.4:
		_step_idx = 3
		_wm.toggle_attachment_by_slot(AttachmentData.Slot.MAGAZINE)
		_wm.toggle_attachment_by_slot(AttachmentData.Slot.UNDERBARREL)
		_wm.request_reload()
	if _step_idx == 3 and t >= 4.5:
		_step_idx = 4
		_wm.set_aim_requested(true)
		_wm.set_trigger_held(true)
	if _step_idx == 4 and t >= 5.4:
		_step_idx = 5
		_wm.set_trigger_held(false)
		_wm.set_aim_requested(false)
		_wm.request_switch_slot(1)
	if _step_idx == 5 and t >= 6.8:
		_step_idx = 6
		_wm.request_switch_slot(2)
	if t >= 8.5:
		get_tree().quit(0)


func _run_screenshots_only() -> void:
	var t := _elapsed
	# 01: Clean overview of training range & AR-47
	if _step_idx == 0 and t >= 0.5:
		_step_idx = 1
		_save_shot("01_training_range_overview.png")
		_wm.toggle_attachment_by_slot(AttachmentData.Slot.OPTIC)
		_wm.toggle_attachment_by_slot(AttachmentData.Slot.MUZZLE)
		_wm.toggle_attachment_by_slot(AttachmentData.Slot.MAGAZINE)
		_wm.toggle_attachment_by_slot(AttachmentData.Slot.UNDERBARREL)
		_wm.set_aim_requested(true)
		_aim_target = _get_target_point("TargetArmored12m", "HeadHitbox")

	# 02: AR-47 ADS with attachments equipped
	if _step_idx == 1 and t >= 1.6:
		_step_idx = 2
		_wm.set_trigger_held(true)
	if _step_idx == 2 and t >= 1.72:
		_step_idx = 3
		_wm.set_trigger_held(false)
		_save_shot("02_ar_ads_attachments_hit.png")
		_wm.set_aim_requested(false)
		_wm._equip_slot_immediate(1)
		_aim_target = _get_target_point("TargetClose10m", "BodyHitbox")

	# 03: Shotgun close-range combat blast + multi-pellet hit feedback
	if _step_idx == 3 and t >= 2.7:
		_step_idx = 4
		_wm.set_trigger_held(true)
	if _step_idx == 4 and t >= 2.75:
		_step_idx = 5
		_wm.set_trigger_held(false)
		_save_shot("03_shotgun_multi_pellet.png")
		_wm._equip_slot_immediate(2)
		_aim_target = _get_target_point("TargetLong45m", "HeadHitbox")
		_wm.set_aim_requested(true)

	# 04: Precision rifle high-zoom ADS mil-dot scope + 06: AWP olive-drab 3D hip view
	if _step_idx == 5 and t >= 4.0:
		_step_idx = 6
		_save_shot("04_awp_scope_ads.png")
		_wm.set_aim_requested(false)
	if _step_idx == 6 and t >= 4.6:
		_step_idx = 7
		_save_shot("06_awp_hip_viewmodel.png")
		_wm._equip_slot_immediate(0)
		_aim_target = Vector3(11.3, 1.4, -2.0)

	# 05: Multi-surface ballistic impact test wall (Concrete / Steel / Timber)
	if _step_idx == 7 and t >= 5.3:
		_step_idx = 8
		_wm.set_trigger_held(true)
	if _step_idx == 8 and t >= 5.65:
		_step_idx = 9
		_wm.set_trigger_held(false)
		_save_shot("05_surface_impacts_and_telemetry.png")
		get_tree().quit(0)


func _run_clip5_fire_selector() -> void:
	# 9.5s clip: AK-47 Fire Selector: SAFE (disabled) -> AUTO (burst) -> SEMI (single shots) -> SAFE mid-fire!
	var t := _elapsed
	_aim_target = _get_target_point("TargetArmored12m", "BodyHitbox")
	if _step_idx == 0 and t >= 0.4:
		_step_idx = 1
		# Cycle AUTO -> SEMI -> SAFE to start demonstration cleanly on SAFE
		_wm.request_cycle_fire_mode()
		_wm.request_cycle_fire_mode()
	if _step_idx == 1 and t >= 1.2:
		_step_idx = 2
		_wm.set_trigger_held(true) # SAFE: must not fire!
	if _step_idx == 2 and t >= 1.9:
		_step_idx = 3
		_wm.set_trigger_held(false)
		_wm.request_cycle_fire_mode() # SAFE -> AUTO
		_wm.request_cycle_fire_mode() # AUTO -> SEMI
	if _step_idx == 3 and t >= 2.7:
		_step_idx = 4
		_wm.set_aim_requested(true)
		_wm.set_trigger_held(true) # SEMI shot 1 (held -> fires strictly 1 round!)
	if _step_idx == 4 and t >= 3.4:
		_step_idx = 5
		_wm.set_trigger_held(false)
	if _step_idx == 5 and t >= 3.8:
		_step_idx = 6
		_wm.set_trigger_held(true) # SEMI shot 2
	if _step_idx == 6 and t >= 4.2:
		_step_idx = 7
		_wm.set_trigger_held(false)
		_wm.request_cycle_fire_mode() # SEMI -> SAFE
		_wm.request_cycle_fire_mode() # SAFE -> AUTO
	if _step_idx == 7 and t >= 5.2:
		_step_idx = 8
		_wm.set_trigger_held(true) # AUTO sustained burst!
	if _step_idx == 8 and t >= 6.4:
		_step_idx = 9
		# Switch to SAFE mid-AUTO -> stops firing immediately!
		_wm.request_cycle_fire_mode()
		_wm.request_cycle_fire_mode()
	if _step_idx == 9 and t >= 7.6:
		_step_idx = 10
		_wm.set_trigger_held(false)
		_wm.set_aim_requested(false)
	if t >= 9.0:
		get_tree().quit(0)


func _run_clip6_shoulder_switching() -> void:
	# 9.5s clip: Smooth Right <-> Left shoulder switching (V) across AK-47 (with ADS), SPAS-12, and AWP!
	var t := _elapsed
	_aim_target = _get_target_point("TargetArmored12m", "BodyHitbox")
	if _step_idx == 0 and t >= 0.8:
		_step_idx = 1
		_wm.toggle_shoulder_side() # Right -> Left (AK-47)
	if _step_idx == 1 and t >= 2.0:
		_step_idx = 2
		_wm.set_aim_requested(true) # ADS from Left shoulder -> exact center!
	if _step_idx == 2 and t >= 2.7:
		_step_idx = 3
		_wm.set_trigger_held(true)
	if _step_idx == 3 and t >= 3.2:
		_step_idx = 4
		_wm.set_trigger_held(false)
		_wm.set_aim_requested(false)
		_wm.request_switch_slot(1) # SPAS-12 on Left shoulder
	if _step_idx == 4 and t >= 4.8:
		_step_idx = 5
		_wm.toggle_shoulder_side() # Left -> Right (SPAS-12)
	if _step_idx == 5 and t >= 6.0:
		_step_idx = 6
		_wm.request_switch_slot(2) # AWP on Right shoulder
	if _step_idx == 6 and t >= 7.2:
		_step_idx = 7
		_wm.toggle_shoulder_side() # Right -> Left (AWP)
	if t >= 9.0:
		get_tree().quit(0)


func _run_clip7_tactical_lean() -> void:
	# 9.5s clip: Q/E Tactical Leaning behind PeekPillarCenter — corner peek right (ADS + fire), return, peek left (ADS + fire)!
	var t := _elapsed
	if _step_idx == 0:
		_step_idx = 1
		_player.global_position = Vector3(-1.35, 0.2, 4.45)
		_aim_target = _get_target_point("TargetArmored12m", "BodyHitbox")
		_smooth_aim = _aim_target
	if t >= 0.8 and t < 3.6:
		_player.scripted_lean = 1.0 # Lean Right (E) around pillar
		_wm.set_aim_requested(t >= 1.3)
		_wm.set_trigger_held(t >= 1.9 and t < 2.9)
	elif t >= 3.6 and t < 4.5:
		_wm.set_trigger_held(false)
		_wm.set_aim_requested(false)
		_player.scripted_lean = 0.0 # Return behind cover
		_aim_target = _get_target_point("TargetClose10m", "HeadHitbox")
	elif t >= 4.5 and t < 7.6:
		_player.scripted_lean = -1.0 # Lean Left (Q) around pillar
		_wm.set_aim_requested(t >= 5.0)
		_wm.set_trigger_held(t >= 5.6 and t < 6.4)
	else:
		_wm.set_trigger_held(false)
		_wm.set_aim_requested(false)
		_player.scripted_lean = 0.0
	if t >= 9.0:
		get_tree().quit(0)


func _run_tactical_screenshots() -> void:
	var t := _elapsed
	if _step_idx == 0:
		_step_idx = 1
		_wm.toggle_shoulder_side() # Left shoulder
		_aim_target = _get_target_point("TargetArmored12m", "BodyHitbox")
		_smooth_aim = _aim_target
	if _step_idx == 1 and t >= 0.8:
		_step_idx = 2
		_save_shot("07_shoulder_left_viewmodel.png")
		_wm.toggle_shoulder_side() # Back to Right shoulder
		_player.global_position = Vector3(-1.35, 0.2, 4.45)
		_player.scripted_lean = 1.0
		_wm.set_aim_requested(true)
	if _step_idx == 2 and t >= 1.8:
		_step_idx = 3
		_save_shot("08_tactical_lean_corner_peek.png")
		get_tree().quit(0)


func _run_clip8_surface_penetration() -> void:
	# 10s clip: Surface Penetration comparison — Thick Concrete (blocked) vs Thin Wood (penetrates) vs Glass (shatters & penetrates) vs Drywall!
	var t := _elapsed
	if _step_idx == 0:
		_step_idx = 1
		_player.global_position = Vector3(-8.2, 0.2, 3.6)
		_aim_target = Vector3(-5.4, 1.05, -2.2) # Thick Concrete
		_smooth_aim = _aim_target
	# 0.8-2.4s: Shoot Thick Concrete (blocks shots, concrete dust/debris)
	if t >= 0.8 and t < 2.2:
		_wm.set_aim_requested(true)
		_wm.set_trigger_held(t >= 1.1 and t < 1.9)
	# 2.4-5.2s: Pan to Thin Wood (penetrates -> entry/exit splinters + damages TargetBehindWood!)
	elif t >= 2.2 and t < 5.0:
		_aim_target = Vector3(-7.6, 1.0, -4.6)
		_wm.set_trigger_held(t >= 3.0 and t < 4.3)
	# 5.0-7.6s: Pan to Glass (shattering glass shards + high-retention penetration on TargetBehindGlass!)
	elif t >= 5.0 and t < 7.6:
		_aim_target = Vector3(-9.8, 1.0, -4.6)
		_wm.set_trigger_held(t >= 5.7 and t < 6.9)
	# 7.6-9.5s: Pan to Drywall (plaster dust clouds)
	elif t >= 7.6 and t < 9.5:
		_aim_target = Vector3(-11.8, 1.05, -2.2)
		_wm.set_trigger_held(t >= 8.2 and t < 9.0)
	else:
		_wm.set_trigger_held(false)
		_wm.set_aim_requested(false)
	if t >= 9.6:
		get_tree().quit(0)


func _run_clip9_combat_vfx_surfaces() -> void:
	# 9s clip: Combat VFX Showcase — Steel Plate sparks, Concrete dust, Timber splinters + Muzzle flash/smoke/shells (AK-47 & SPAS-12)
	var t := _elapsed
	if _step_idx == 0:
		_step_idx = 1
		_player.global_position = Vector3(4.5, 0.2, 0.5)
		_aim_target = Vector3(11.3, 1.35, 0.6) # Concrete
		_smooth_aim = _aim_target
	if t >= 0.6 and t < 2.4:
		_wm.set_trigger_held(t >= 0.8 and t < 1.8)
	elif t >= 2.4 and t < 4.6:
		_aim_target = Vector3(11.3, 1.35, -2.0) # Steel Plate (golden spark shower!)
		_wm.set_trigger_held(t >= 2.9 and t < 4.2)
	elif t >= 4.6 and t < 6.2:
		_wm.set_trigger_held(false)
		if _step_idx == 1:
			_step_idx = 2
			_wm.request_switch_slot(1) # SPAS-12 shotgun blast smoke & muzzle flash!
		_aim_target = Vector3(11.3, 1.35, -4.6) # Timber
	elif t >= 6.2 and t < 8.5:
		if _step_idx == 2 and t >= 6.4:
			_step_idx = 3
			_wm.set_trigger_held(true)
		elif _step_idx == 3 and t >= 6.6:
			_step_idx = 4
			_wm.set_trigger_held(false)
			_aim_target = Vector3(11.3, 1.35, -2.0) # Steel blast
		elif _step_idx == 4 and t >= 7.5:
			_step_idx = 5
			_wm.set_trigger_held(true)
		elif _step_idx == 5 and t >= 7.7:
			_step_idx = 6
			_wm.set_trigger_held(false)
	if t >= 8.8:
		get_tree().quit(0)


func _run_pen_vfx_screenshots() -> void:
	var t := _elapsed
	if _step_idx == 0:
		_step_idx = 1
		_player.global_position = Vector3(-8.4, 0.2, 3.2)
		_aim_target = Vector3(-7.6, 1.05, -4.6) # Shoot through Thin Wood into TargetBehindWood
		_smooth_aim = _aim_target
	if _step_idx == 1 and t >= 0.45:
		_step_idx = 2
		_wm.set_trigger_held(true)
	if _step_idx == 2 and t >= 0.72:
		_step_idx = 3
		_wm.set_trigger_held(false)
		_save_shot("09_penetration_wood_glass.png")
		_player.global_position = Vector3(5.0, 0.2, -1.5)
		_aim_target = Vector3(11.3, 1.35, -2.0) # Steel Plate sparks + star muzzle flash
		_smooth_aim = _aim_target
	if _step_idx == 3 and t >= 1.25:
		_step_idx = 4
		_wm.set_trigger_held(true)
	if _step_idx == 4 and t >= 1.52:
		_step_idx = 5
		_wm.set_trigger_held(false)
		_save_shot("10_vfx_metal_sparks_muzzle.png")
		get_tree().quit(0)
