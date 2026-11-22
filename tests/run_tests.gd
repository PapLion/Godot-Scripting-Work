extends SceneTree
## Automated deterministic test suite for Godot Systems Lab — 01-Advanced-FPS.
## Run with: godot --headless --path <project_path> --script res://tests/run_tests.gd

var _passed: int = 0
var _failed: int = 0


func _initialize() -> void:
	call_deferred("_run_all")


func _run_all() -> void:
	await process_frame
	print("=== 01-Advanced-FPS Automated Test Suite ===")
	_test_weapon_resources_and_falloff()
	_test_attachment_modifiers_and_ammo_conservation()
	_test_weapon_state_machine_invariants()
	_test_recoil_and_spread_framerate_independence()
	_test_damage_hitboxes_and_armor()
	_test_weapon_manager_firing_reloads_and_switching()
	await _test_training_range_scene_instantiation()
	await _test_rigged_weapon_models_and_animations()

	print("--------------------------------------------")
	print("TOTAL: %d passed, %d failed" % [_passed, _failed])
	ProceduralAudio.clear_cache()
	quit(0 if _failed == 0 else 1)


func _assert(cond: bool, msg: String) -> void:
	if cond:
		_passed += 1
		print("[PASS] %s" % msg)
	else:
		_failed += 1
		printerr("[FAIL] %s" % msg)


func _test_weapon_resources_and_falloff() -> void:
	var ar := load("res://data/weapons/ar_m4_carbine.tres") as WeaponData
	var sg := load("res://data/weapons/sg_m870_tactical.tres") as WeaponData
	var sr := load("res://data/weapons/sr_mk14_precision.tres") as WeaponData
	_assert(ar != null and sg != null and sr != null, "All 3 weapon WeaponData resources load")
	_assert(ar.supported_fire_modes.size() == 2, "AR supports AUTO and SEMI fire modes")
	_assert(sg.pellets_per_shot == 8 and sg.reload_type == WeaponData.ReloadType.SHELL_BY_SHELL, "Shotgun has 8 pellets and shell-by-shell reload")
	_assert(sr.base_damage > ar.base_damage and sr.ads_fov < ar.ads_fov, "Precision rifle has higher damage and stronger ADS zoom")

	var ar_stats := EffectiveWeaponStats.compute(ar, [])
	_assert(is_equal_approx(ar_stats.compute_damage_at_distance(10.0), ar.base_damage), "Full damage within effective range")
	var mid_dist := (ar_stats.effective_range + ar_stats.max_falloff_range) * 0.5
	var expected_mid := ar.base_damage * ((1.0 + ar_stats.min_falloff_multiplier) * 0.5)
	_assert(absf(ar_stats.compute_damage_at_distance(mid_dist) - expected_mid) < 0.05, "Linear damage falloff at mid-falloff distance")
	_assert(is_equal_approx(ar_stats.compute_damage_at_distance(500.0), ar.base_damage * ar_stats.min_falloff_multiplier), "Damage falloff clamps at min_falloff_multiplier")


func _test_attachment_modifiers_and_ammo_conservation() -> void:
	var ar := load("res://data/weapons/ar_m4_carbine.tres") as WeaponData
	var optic := load("res://data/attachments/optic_holo_sight.tres") as AttachmentData
	var comp := load("res://data/attachments/muzzle_compensator.tres") as AttachmentData
	var ext_mag := load("res://data/attachments/mag_extended.tres") as AttachmentData
	var laser := load("res://data/attachments/underbarrel_laser.tres") as AttachmentData

	var wi := WeaponInstance.new(ar)
	var base_recoil := wi.stats.recoil_vertical_kick_deg
	var base_mag := wi.stats.magazine_capacity
	var base_fov := wi.stats.ads_fov
	var base_hip := wi.stats.base_hip_spread_deg

	wi.equip_attachment(comp)
	_assert(wi.stats.recoil_vertical_kick_deg < base_recoil * 0.75, "Compensator reduces vertical recoil")

	wi.equip_attachment(optic)
	_assert(wi.stats.ads_fov < base_fov, "Holo optic narrows ADS FOV")

	wi.equip_attachment(laser)
	_assert(wi.stats.base_hip_spread_deg < base_hip * 0.70, "Laser reduces hipfire spread")

	wi.equip_attachment(ext_mag)
	_assert(wi.stats.magazine_capacity > base_mag, "Extended mag increases magazine capacity (%d -> %d)" % [base_mag, wi.stats.magazine_capacity])

	# Fill extended mag, then remove extended mag and verify zero ammo loss/duplication
	wi.current_mag = wi.stats.magazine_capacity
	wi.reserve_ammo = 100
	var total_before := wi.current_mag + wi.reserve_ammo
	wi.remove_attachment(AttachmentData.Slot.MAGAZINE)
	var total_after := wi.current_mag + wi.reserve_ammo
	_assert(wi.current_mag <= wi.get_max_magazine_capacity(), "Removing extended mag clamps current_mag to max allowed")
	_assert(total_before == total_after, "Removing extended mag conserves exact total ammunition (%d == %d)" % [total_before, total_after])


func _test_weapon_state_machine_invariants() -> void:
	var sm := WeaponStateMachine.new()
	sm.set_aim_state(WeaponStateMachine.AimState.AIMING)
	_assert(sm.is_aiming(), "Can enter AIMING from IDLE")

	sm.set_action_state(WeaponStateMachine.ActionState.RELOADING)
	_assert(not sm.is_aiming(), "Entering RELOADING cancels AIMING")
	_assert(not sm.can_fire(false), "Cannot fire during non-interruptible RELOADING")
	_assert(sm.can_fire(true), "Can fire during interruptible shell RELOADING")
	_assert(not sm.can_reload(), "Cannot start duplicate reload while RELOADING")

	sm.set_action_state(WeaponStateMachine.ActionState.IDLE)
	sm.set_sprint_state(WeaponStateMachine.SprintState.SPRINTING)
	_assert(sm.is_sprinting(), "Can enter SPRINTING from IDLE")
	sm.set_aim_state(WeaponStateMachine.AimState.AIMING)
	_assert(sm.is_aiming() and not sm.is_sprinting(), "Entering AIMING cancels SPRINTING")
	sm.set_sprint_state(WeaponStateMachine.SprintState.SPRINTING)
	_assert(sm.is_sprinting() and not sm.is_aiming(), "Entering SPRINTING cancels AIMING")


func _test_recoil_and_spread_framerate_independence() -> void:
	var ar := load("res://data/weapons/ar_m4_carbine.tres") as WeaponData
	var stats := EffectiveWeaponStats.compute(ar, [])

	# Recoil accumulation & recovery
	var r60 := RecoilController.new(12345)
	var r120 := RecoilController.new(12345)
	for _i in 4:
		r60.add_shot_kick(stats, false, false)
		r120.add_shot_kick(stats, false, false)
	_assert(r60.target_offset_deg.x > stats.recoil_vertical_kick_deg * 3.0, "Recoil accumulates across sustained shots")

	# Simulate 0.6s at 60 FPS vs 120 FPS
	for _i in 36:
		r60.update(1.0 / 60.0, stats)
	for _i in 72:
		r120.update(1.0 / 120.0, stats)
	_assert(absf(r60.current_offset_deg.x - r120.current_offset_deg.x) < 0.08, "Recoil recovery is framerate-independent (60 vs 120 FPS)")

	# Complete recovery
	for _i in 120:
		r60.update(1.0 / 60.0, stats)
	_assert(r60.current_offset_deg.length() < 0.01 and r60.get_sustained_shot_count() == 0, "Recoil fully recovers to zero")

	# Spread stance hierarchy
	var sc := SpreadController.new(99)
	var spread_ads := sc.update(0.0, stats, 1.0, 0.0, false, true)
	var spread_hip_crouch := sc.update(0.0, stats, 0.0, 0.0, true, true)
	var spread_hip_stand := sc.update(0.0, stats, 0.0, 0.0, false, true)
	var spread_hip_move := sc.update(0.0, stats, 0.0, 1.0, false, true)
	var spread_air := sc.update(0.0, stats, 0.0, 0.5, false, false)
	_assert(spread_ads < spread_hip_crouch and spread_hip_crouch < spread_hip_stand, "Spread ordering: ADS < Crouch < Standing")
	_assert(spread_hip_stand < spread_hip_move and spread_hip_move < spread_air, "Spread ordering: Standing < Moving < Airborne")


func _test_damage_hitboxes_and_armor() -> void:
	var hp := HealthComponent.new()
	hp.max_health = 100.0
	hp.max_armor = 50.0
	hp.armor_absorption_ratio = 0.5
	hp.reset_health()

	var body_hb := HitboxComponent.new()
	body_hb.hit_zone = HitboxComponent.HitZone.BODY
	body_hb.damage_multiplier = 1.0
	body_hb.health_component = hp

	var head_hb := HitboxComponent.new()
	head_hb.hit_zone = HitboxComponent.HitZone.HEAD
	head_hb.damage_multiplier = 2.0
	head_hb.health_component = hp

	# Body hit of 40 with 50 armor (50% absorption) -> 20 armor absorbed, 20 health damage
	var d1 := body_hb.receive_hit(40.0, Vector3.ZERO, Vector3.UP, Vector3.FORWARD, 1.0, &"test", null)
	_assert(is_equal_approx(d1.armor_absorbed, 20.0) and is_equal_approx(d1.final_damage, 20.0), "Armor absorbs 50% of incoming damage")
	_assert(is_equal_approx(hp.current_armor, 30.0) and is_equal_approx(hp.current_health, 80.0), "Health & armor pools update accurately")

	# Headshot of 50 raw -> 100 after 2.0x mult; 50% desire = 50, capped by 30 remaining armor -> 70 health damage
	var d2 := head_hb.receive_hit(50.0, Vector3.ZERO, Vector3.UP, Vector3.FORWARD, 1.0, &"test", null)
	_assert(d2.is_critical and is_equal_approx(d2.armor_absorbed, 30.0) and is_equal_approx(d2.final_damage, 70.0), "Headshot 2x multiplier + partial armor drain")
	_assert(is_equal_approx(hp.current_armor, 0.0) and is_equal_approx(hp.current_health, 10.0), "Armor depleted cleanly, 10 HP remaining")

	# Lethal hit + post-death immunity
	var d3 := body_hb.receive_hit(25.0, Vector3.ZERO, Vector3.UP, Vector3.FORWARD, 1.0, &"test", null)
	_assert(hp.is_dead and is_equal_approx(hp.current_health, 0.0) and d3.final_damage > 0.0, "Target dies on lethal hit")
	var d4 := body_hb.receive_hit(25.0, Vector3.ZERO, Vector3.UP, Vector3.FORWARD, 1.0, &"test", null)
	_assert(is_equal_approx(d4.final_damage, 0.0), "Dead target ignores subsequent damage")

	hp.reset_health()
	_assert(not hp.is_dead and is_equal_approx(hp.current_health, 100.0) and is_equal_approx(hp.current_armor, 50.0), "HealthComponent resets cleanly")

	body_hb.free()
	head_hb.free()
	hp.free()


func _test_weapon_manager_firing_reloads_and_switching() -> void:
	var wm := WeaponManager.new()
	wm.eject_shells_enabled = false
	wm.starting_weapons = [
		load("res://data/weapons/ar_m4_carbine.tres"),
		load("res://data/weapons/sg_m870_tactical.tres"),
		load("res://data/weapons/sr_mk14_precision.tres"),
	]
	wm.available_attachments = [
		load("res://data/attachments/optic_holo_sight.tres"),
		load("res://data/attachments/muzzle_compensator.tres"),
		load("res://data/attachments/mag_extended.tres"),
		load("res://data/attachments/underbarrel_laser.tres"),
	]
	root.add_child(wm)
	wm.initialize(null, null, null, null, [])

	var ar := wm.get_current_weapon()
	_assert(ar.data.weapon_id == &"ar_m4_carbine", "WeaponManager equips slot 0 (AR) on init")

	# Auto fire 5 rounds
	wm.set_trigger_held(true)
	for _i in 30:
		wm.step(0.02, 0.0, false, true)
	wm.set_trigger_held(false)
	_assert(ar.current_mag < 30 and ar.current_mag > 20, "AUTO fire consumes multiple rounds smoothly (mag=%d)" % ar.current_mag)

	# Switch to SEMI and verify single shot per trigger hold
	var switched_mode := wm.request_cycle_fire_mode()
	_assert(switched_mode and ar.get_current_fire_mode() == WeaponData.FireMode.SEMI, "AR cycles to SEMI mode")
	var mag_before_semi := ar.current_mag
	wm.set_trigger_held(true)
	for _i in 20:
		wm.step(0.02, 0.0, false, true)
	wm.set_trigger_held(false)
	_assert(ar.current_mag == mag_before_semi - 1, "SEMI mode fires exactly 1 round while trigger held")

	# Start tactical reload and interrupt via weapon switch -> no ammo duplication!
	var total_ar_before := ar.current_mag + ar.reserve_ammo
	var started_reload := wm.request_reload()
	_assert(started_reload and wm.state_machine.is_reloading(), "Tactical reload starts cleanly")
	var dup_reload := wm.request_reload()
	_assert(not dup_reload, "Duplicate reload request rejected")
	wm.step(0.3, 0.0, false, true)
	wm.request_switch_slot(1)
	for _i in 40:
		wm.step(0.02, 0.0, false, true)
	_assert(ar.current_mag + ar.reserve_ammo == total_ar_before, "Weapon switch during mag reload conserves exact AR ammo")

	# Verify Shotgun shell-by-shell reload + fire interruption!
	var sg := wm.get_current_weapon()
	_assert(sg.data.weapon_id == &"sg_m870_tactical" and wm.state_machine.action_state == WeaponStateMachine.ActionState.IDLE, "Switched to Shotgun cleanly")
	sg.current_mag = 2
	sg.reserve_ammo = 20
	wm.request_reload()
	# Step past start (0.30s) + 2 shell inserts (0.76s) = 1.15s -> should have 4 shells now, still reloading
	for _i in 58:
		wm.step(0.02, 0.0, false, true)
	_assert(sg.current_mag == 4 and wm.state_machine.is_reloading(), "Shotgun loads shells incrementally (mag=%d)" % sg.current_mag)

	# Interrupt shell reload by pressing fire!
	wm.set_trigger_held(true)
	wm.step(0.02, 0.0, false, true)
	wm.set_trigger_held(false)
	_assert(not wm.state_machine.is_reloading() and sg.current_mag == 3, "Firing interrupts shotgun shell reload and fires immediately (mag=%d)" % sg.current_mag)

	wm.queue_free()


func _test_training_range_scene_instantiation() -> void:
	var scene := load("res://src/showcase/training_range.tscn") as PackedScene
	_assert(scene != null, "training_range.tscn loads as PackedScene")
	var inst := scene.instantiate() as RangeController
	root.add_child(inst)
	await process_frame
	_assert(inst.player != null and inst.player.weapon_manager != null, "TrainingRange instantiates FPSPlayer & WeaponManager")
	_assert(inst.player.weapon_manager.loadout.size() == 3, "Player loadout contains all 3 configured weapons")
	_assert(inst.player.weapon_manager.available_attachments.size() == 4, "Player has all 4 configured attachments available")
	var targets := get_nodes_in_group("range_targets")
	_assert(targets.size() == 6, "TrainingRange spawns all 6 practice targets (static, armored, moving)")
	inst.queue_free()
	await process_frame


func _test_rigged_weapon_models_and_animations() -> void:
	var scene := load("res://src/showcase/training_range.tscn") as PackedScene
	var inst := scene.instantiate() as RangeController
	root.add_child(inst)
	await process_frame

	var vm := inst.player.camera_rig.viewmodel
	var wm := inst.player.weapon_manager

	# 1. AK-47 rigged animations
	var ak_anims := vm.get_animation_names()
	_assert(
		ak_anims.has("idle") and ak_anims.has("fire") and ak_anims.has("reload") and ak_anims.has("equip") and ak_anims.has("unequip"),
		"AK-47 GLB imports with required animations (%s)" % [", ".join(ak_anims)]
	)
	wm.get_current_weapon().current_mag = 10
	wm.request_reload()
	_assert(vm.get_current_animation() == "reload", "AK-47 plays 'reload' animation on reload start")
	wm.request_switch_slot(1)
	_assert(vm.get_current_animation() == "unequip", "Weapon switch interrupts AK-47 reload and plays 'unequip'")

	# 2. SPAS-12 rigged animations + shell-by-shell sync
	wm._equip_slot_immediate(1)
	var spas_anims := vm.get_animation_names()
	_assert(
		spas_anims.has("idle") and spas_anims.has("fire") and spas_anims.has("shell_start") and spas_anims.has("shell_insert") and spas_anims.has("shell_end") and spas_anims.has("reload_interrupt"),
		"SPAS-12 GLB imports with shell-by-shell & interrupt animations (%s)" % [", ".join(spas_anims)]
	)
	wm.get_current_weapon().current_mag = 2
	wm.request_reload()
	_assert(vm.get_current_animation() == "shell_start", "SPAS-12 plays 'shell_start' on shell reload start")

	# 3. AWP rigged animations + bolt-action cycle
	wm._equip_slot_immediate(2)
	var awp_anims := vm.get_animation_names()
	_assert(
		awp_anims.has("idle") and awp_anims.has("fire") and (awp_anims.has("bolt") or awp_anims.has("bolt_cycle")) and awp_anims.has("reload") and awp_anims.has("equip"),
		"AWP GLB imports with bolt-action & reload animations (%s)" % [", ".join(awp_anims)]
	)

	inst.queue_free()
	await process_frame
