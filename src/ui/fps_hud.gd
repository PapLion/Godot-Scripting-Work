class_name FPSHud
extends CanvasLayer
## Minimal tactical HUD displaying dynamic spread crosshair, hitmarkers, ammo/weapon info,
## health/armor, active attachments, subtle controls hints, and an optional F3 telemetry panel.

var _player: FPSPlayer
var _weapon_manager: WeaponManager
var _health_component: HealthComponent

var _crosshair_control: Control
var _weapon_label: Label
var _ammo_label: Label
var _fire_mode_label: Label
var _state_badge_label: Label
var _slots_label: Label
var _attachments_label: Label
var _health_bar: ProgressBar
var _armor_bar: ProgressBar
var _health_value_label: Label
var _debug_panel: PanelContainer
var _debug_label: Label

var _hitmarker_timer: float = 0.0
var _hitmarker_color: Color = Color.WHITE
var _hitmarker_scale: float = 1.0
var _spread_pixels: float = 10.0
var _crosshair_alpha: float = 1.0


func _ready() -> void:
	_build_ui()


func bind_player(player: FPSPlayer) -> void:
	_player = player
	if _player == null:
		return
	_weapon_manager = _player.weapon_manager
	_health_component = _player.health_component

	if _weapon_manager != null:
		_weapon_manager.weapon_equipped.connect(_on_weapon_equipped)
		_weapon_manager.ammo_updated.connect(_on_ammo_updated)
		_weapon_manager.fire_mode_updated.connect(_on_fire_mode_updated)
		_weapon_manager.hit_confirmed.connect(_on_hit_confirmed)
		_weapon_manager.state_changed.connect(_on_state_changed)
		_weapon_manager.attachments_updated.connect(_on_attachments_updated)
		var current := _weapon_manager.get_current_weapon()
		if current != null:
			_on_weapon_equipped(current, _weapon_manager.current_slot)
			_on_ammo_updated(current.current_mag, current.reserve_ammo, current.stats.magazine_capacity)
			_on_fire_mode_updated(current.get_current_fire_mode())
			_on_attachments_updated(current.get_active_attachments())

	if _health_component != null:
		_health_component.health_changed.connect(_on_health_changed)
		_health_component.armor_changed.connect(_on_armor_changed)
		_on_health_changed(_health_component.current_health, _health_component.max_health)
		_on_armor_changed(_health_component.current_armor, _health_component.max_armor)


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("toggle_debug") and _debug_panel != null:
		_debug_panel.visible = not _debug_panel.visible


func _process(delta: float) -> void:
	if _hitmarker_timer > 0.0:
		_hitmarker_timer = maxf(0.0, _hitmarker_timer - delta)

	if _weapon_manager != null:
		var spread_deg := _weapon_manager.get_current_spread_deg()
		_spread_pixels = clampf(5.0 + spread_deg * 8.5, 5.0, 72.0)
		_crosshair_alpha = lerpf(0.92, 0.22, _weapon_manager.ads_alpha)

	if _crosshair_control != null:
		_crosshair_control.queue_redraw()

	if _debug_panel != null and _debug_panel.visible:
		_update_debug_telemetry()


func _on_weapon_equipped(weapon: WeaponInstance, slot_index: int) -> void:
	if _weapon_label != null and weapon != null:
		_weapon_label.text = weapon.data.display_name
	_refresh_slot_strip(slot_index)


func _on_ammo_updated(current_mag: int, reserve_ammo: int, max_mag: int) -> void:
	if _ammo_label == null:
		return
	_ammo_label.text = "%d / %d" % [current_mag, reserve_ammo]
	if current_mag == 0:
		_ammo_label.modulate = Color(1.0, 0.35, 0.32)
	elif current_mag <= maxi(1, int(max_mag * 0.25)):
		_ammo_label.modulate = Color(1.0, 0.80, 0.30)
	else:
		_ammo_label.modulate = Color(0.95, 0.97, 1.0)


func _on_fire_mode_updated(mode: WeaponData.FireMode) -> void:
	if _fire_mode_label != null:
		_fire_mode_label.text = "[%s]" % WeaponData.get_fire_mode_label(mode)


func _on_hit_confirmed(is_critical: bool, is_kill: bool, _total_damage: float) -> void:
	_hitmarker_timer = 0.20 if is_kill else 0.14
	if is_kill:
		_hitmarker_color = Color(1.0, 0.82, 0.22)
		_hitmarker_scale = 1.35
	elif is_critical:
		_hitmarker_color = Color(1.0, 0.24, 0.22)
		_hitmarker_scale = 1.18
	else:
		_hitmarker_color = Color(0.98, 0.98, 1.0)
		_hitmarker_scale = 1.0


func _on_state_changed(action_state: WeaponStateMachine.ActionState, aim_state: WeaponStateMachine.AimState) -> void:
	if _state_badge_label == null:
		return
	if action_state == WeaponStateMachine.ActionState.RELOADING:
		_state_badge_label.text = "RELOADING..."
		_state_badge_label.modulate = Color(1.0, 0.82, 0.32)
	elif action_state in [WeaponStateMachine.ActionState.EQUIPPING, WeaponStateMachine.ActionState.UNEQUIPPING]:
		_state_badge_label.text = "SWITCHING"
		_state_badge_label.modulate = Color(0.75, 0.85, 0.95)
	elif aim_state == WeaponStateMachine.AimState.AIMING:
		_state_badge_label.text = "ADS"
		_state_badge_label.modulate = Color(0.45, 0.92, 0.72)
	else:
		_state_badge_label.text = ""


func _on_attachments_updated(active_attachments: Array[AttachmentData]) -> void:
	if _attachments_label == null:
		return
	var active_slots := {}
	for att in active_attachments:
		active_slots[att.slot] = att.display_name

	var parts: PackedStringArray = [
		"[5] %s" % (active_slots.get(AttachmentData.Slot.OPTIC, "Optic:--")),
		"[6] %s" % (active_slots.get(AttachmentData.Slot.MUZZLE, "Muzzle:--")),
		"[7] %s" % (active_slots.get(AttachmentData.Slot.MAGAZINE, "Mag:--")),
		"[8] %s" % (active_slots.get(AttachmentData.Slot.UNDERBARREL, "Laser:--")),
	]
	_attachments_label.text = "  |  ".join(parts)


func _on_health_changed(current: float, max_val: float) -> void:
	if _health_bar != null:
		_health_bar.max_value = max_val
		_health_bar.value = current
	_refresh_vitals_text()


func _on_armor_changed(current: float, max_val: float) -> void:
	if _armor_bar != null:
		_armor_bar.max_value = maxf(1.0, max_val)
		_armor_bar.value = current
	_refresh_vitals_text()


func _refresh_vitals_text() -> void:
	if _health_value_label == null or _health_component == null:
		return
	_health_value_label.text = "HP %.0f   ARM %.0f" % [
		_health_component.current_health,
		_health_component.current_armor,
	]


func _refresh_slot_strip(active_slot: int) -> void:
	if _slots_label == null or _weapon_manager == null:
		return
	var entries: PackedStringArray = []
	for i in _weapon_manager.loadout.size():
		var w := _weapon_manager.loadout[i]
		var prefix := ">" if i == active_slot else " "
		entries.append("%s[%d] %s" % [prefix, i + 1, w.data.display_name])
	_slots_label.text = "   ".join(entries)


func _update_debug_telemetry() -> void:
	if _debug_label == null or _weapon_manager == null:
		return
	var w := _weapon_manager.get_current_weapon()
	if w == null:
		return
	var sm := _weapon_manager.state_machine
	var rec := _weapon_manager.get_current_recoil_deg()
	var fov := _player.camera_rig.camera.fov if (_player != null and _player.camera_rig != null) else 75.0
	_debug_label.text = (
		"TELEMETRY (F3)\n"
		+ "State: %s | Aim: %s | Sprint: %s\n" % [
			WeaponStateMachine.get_action_name(sm.action_state),
			"ADS" if sm.is_aiming() else "HIP",
			"YES" if sm.is_sprinting() else "NO",
		]
		+ "Spread: %.2f deg | Recoil: P %.2f / Y %.2f\n" % [
			_weapon_manager.get_current_spread_deg(), rec.x, rec.y
		]
		+ "FOV: %.1f | ADS Alpha: %.2f\n" % [fov, _weapon_manager.ads_alpha]
		+ "Eff. Stats: DMG %.1f x%d | Mag %d | Range %.0fm" % [
			w.stats.base_damage, w.stats.pellets_per_shot, w.stats.magazine_capacity, w.stats.effective_range
		]
	)


func _build_ui() -> void:
	# Center Crosshair & Hitmarker Canvas
	_crosshair_control = Control.new()
	_crosshair_control.set_anchors_preset(Control.PRESET_FULL_RECT)
	_crosshair_control.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_crosshair_control.draw.connect(_draw_crosshair)
	add_child(_crosshair_control)

	# Top-Left Controls Hint
	var hint_panel := _make_panel()
	hint_panel.set_anchors_preset(Control.PRESET_TOP_LEFT)
	hint_panel.offset_left = 18
	hint_panel.offset_top = 14
	add_child(hint_panel)
	var hint_lbl := Label.new()
	hint_lbl.text = "WASD Move | Shift Sprint | C Crouch | LMB Fire | RMB ADS | R Reload | B Mode | 1-3 Weapons | T Reset | F3 Info"
	hint_lbl.add_theme_font_size_override("font_size", 11)
	hint_lbl.modulate = Color(0.82, 0.87, 0.92, 0.9)
	hint_panel.add_child(hint_lbl)

	# Top-Right Attachments Strip
	var att_panel := _make_panel()
	att_panel.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	att_panel.offset_left = -450
	att_panel.offset_right = -18
	att_panel.offset_top = 14
	add_child(att_panel)
	_attachments_label = Label.new()
	_attachments_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	_attachments_label.add_theme_font_size_override("font_size", 11)
	_attachments_label.modulate = Color(0.92, 0.85, 0.62)
	att_panel.add_child(_attachments_label)

	# Bottom-Left Vitals (Health & Armor)
	var vitals_panel := _make_panel()
	vitals_panel.set_anchors_preset(Control.PRESET_BOTTOM_LEFT)
	vitals_panel.offset_left = 18
	vitals_panel.offset_top = -94
	vitals_panel.offset_right = 268
	vitals_panel.offset_bottom = -18
	add_child(vitals_panel)

	var v_box := VBoxContainer.new()
	vitals_panel.add_child(v_box)
	_health_value_label = Label.new()
	_health_value_label.text = "HP 100   ARM 50"
	_health_value_label.add_theme_font_size_override("font_size", 14)
	v_box.add_child(_health_value_label)

	_health_bar = ProgressBar.new()
	_health_bar.custom_minimum_size = Vector2(220, 12)
	_health_bar.show_percentage = false
	_health_bar.modulate = Color(0.32, 0.85, 0.48)
	v_box.add_child(_health_bar)

	_armor_bar = ProgressBar.new()
	_armor_bar.custom_minimum_size = Vector2(220, 8)
	_armor_bar.show_percentage = false
	_armor_bar.modulate = Color(0.35, 0.72, 0.98)
	v_box.add_child(_armor_bar)

	# Bottom-Right Weapon & Ammo Panel
	var weapon_panel := _make_panel()
	weapon_panel.set_anchors_preset(Control.PRESET_BOTTOM_RIGHT)
	weapon_panel.offset_left = -360
	weapon_panel.offset_top = -126
	weapon_panel.offset_right = -18
	weapon_panel.offset_bottom = -18
	add_child(weapon_panel)

	var w_box := VBoxContainer.new()
	weapon_panel.add_child(w_box)

	var top_row := HBoxContainer.new()
	w_box.add_child(top_row)

	_weapon_label = Label.new()
	_weapon_label.text = "AR-47 Tactical"
	_weapon_label.add_theme_font_size_override("font_size", 18)
	_weapon_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	top_row.add_child(_weapon_label)

	_fire_mode_label = Label.new()
	_fire_mode_label.text = "[AUTO]"
	_fire_mode_label.add_theme_font_size_override("font_size", 14)
	_fire_mode_label.modulate = Color(0.75, 0.88, 1.0)
	top_row.add_child(_fire_mode_label)

	var mid_row := HBoxContainer.new()
	w_box.add_child(mid_row)

	_ammo_label = Label.new()
	_ammo_label.text = "30 / 150"
	_ammo_label.add_theme_font_size_override("font_size", 28)
	_ammo_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	mid_row.add_child(_ammo_label)

	_state_badge_label = Label.new()
	_state_badge_label.text = ""
	_state_badge_label.add_theme_font_size_override("font_size", 14)
	_state_badge_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	mid_row.add_child(_state_badge_label)

	_slots_label = Label.new()
	_slots_label.text = ""
	_slots_label.add_theme_font_size_override("font_size", 11)
	_slots_label.modulate = Color(0.74, 0.78, 0.84)
	w_box.add_child(_slots_label)

	# Optional Debug Telemetry Panel (F3 — hidden by default)
	_debug_panel = _make_panel()
	_debug_panel.set_anchors_preset(Control.PRESET_TOP_LEFT)
	_debug_panel.offset_left = 18
	_debug_panel.offset_top = 52
	_debug_panel.visible = false
	add_child(_debug_panel)

	_debug_label = Label.new()
	_debug_label.add_theme_font_size_override("font_size", 12)
	_debug_label.modulate = Color(0.72, 0.96, 0.82)
	_debug_panel.add_child(_debug_label)


func _make_panel() -> PanelContainer:
	var panel := PanelContainer.new()
	var style := StyleBoxFlat.new()
	style.bg_color = Color(0.06, 0.08, 0.11, 0.72)
	style.border_width_left = 1
	style.border_width_right = 1
	style.border_width_top = 1
	style.border_width_bottom = 1
	style.border_color = Color(0.28, 0.36, 0.46, 0.55)
	style.corner_radius_top_left = 4
	style.corner_radius_top_right = 4
	style.corner_radius_bottom_left = 4
	style.corner_radius_bottom_right = 4
	style.content_margin_left = 12
	style.content_margin_right = 12
	style.content_margin_top = 6
	style.content_margin_bottom = 6
	panel.add_theme_stylebox_override("panel", style)
	return panel


func _draw_crosshair() -> void:
	var center := _crosshair_control.size * 0.5
	var col := Color(0.95, 0.98, 1.0, _crosshair_alpha)
	var gap := _spread_pixels
	var length := 8.0
	var width := 2.0

	# 4 dynamic spread ticks + subtle center dot
	_crosshair_control.draw_line(center + Vector2(-gap - length, 0), center + Vector2(-gap, 0), col, width)
	_crosshair_control.draw_line(center + Vector2(gap, 0), center + Vector2(gap + length, 0), col, width)
	_crosshair_control.draw_line(center + Vector2(0, -gap - length), center + Vector2(0, -gap), col, width)
	_crosshair_control.draw_line(center + Vector2(0, gap), center + Vector2(0, gap + length), col, width)
	_crosshair_control.draw_circle(center, 1.6, Color(0.95, 0.98, 1.0, maxf(0.45, _crosshair_alpha)))

	# Hitmarker diagonal X-ticks
	if _hitmarker_timer > 0.0:
		var hm_alpha := clampf(_hitmarker_timer / 0.14, 0.0, 1.0)
		var hm_col := Color(_hitmarker_color.r, _hitmarker_color.g, _hitmarker_color.b, hm_alpha)
		var inner := 5.0 * _hitmarker_scale
		var outer := 13.0 * _hitmarker_scale
		for dir in [Vector2(-1, -1), Vector2(1, -1), Vector2(-1, 1), Vector2(1, 1)]:
			_crosshair_control.draw_line(center + dir * inner, center + dir * outer, hm_col, 2.4)
