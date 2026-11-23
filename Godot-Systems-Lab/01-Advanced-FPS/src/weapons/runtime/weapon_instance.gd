class_name WeaponInstance
extends RefCounted
## Runtime instance state for a single weapon in a loadout.
## Holds current ammunition, active fire mode, equipped attachments, and recomputed EffectiveWeaponStats.
## Safely handles ammunition conservation during reload and magazine-capacity attachment swaps.

signal ammo_changed(current_mag: int, reserve_ammo: int, max_mag: int)
signal fire_mode_changed(new_mode: WeaponData.FireMode)
signal attachments_changed(active_attachments: Array[AttachmentData])

var data: WeaponData
var attachments: Dictionary = {} # AttachmentData.Slot -> AttachmentData
var stats: EffectiveWeaponStats

var current_mag: int = 0
var reserve_ammo: int = 0
var fire_mode_index: int = 0


func _init(weapon_data: WeaponData) -> void:
	data = weapon_data
	recompute_stats(false)
	if data != null:
		current_mag = stats.magazine_capacity
		reserve_ammo = clampi(data.starting_reserve_ammo, 0, data.max_reserve_ammo)
		fire_mode_index = 0


func get_active_attachments() -> Array[AttachmentData]:
	var list: Array[AttachmentData] = []
	for att in attachments.values():
		if att is AttachmentData:
			list.append(att)
	return list


func has_attachment_in_slot(slot: AttachmentData.Slot) -> bool:
	return attachments.has(slot) and attachments[slot] != null


func get_attachment_in_slot(slot: AttachmentData.Slot) -> AttachmentData:
	if attachments.has(slot):
		return attachments[slot] as AttachmentData
	return null


func equip_attachment(attachment: AttachmentData) -> void:
	if attachment == null:
		return
	attachments[attachment.slot] = attachment
	recompute_stats(true)
	attachments_changed.emit(get_active_attachments())


func remove_attachment(slot: AttachmentData.Slot) -> bool:
	if not attachments.has(slot):
		return false
	attachments.erase(slot)
	recompute_stats(true)
	attachments_changed.emit(get_active_attachments())
	return true


func toggle_attachment(attachment: AttachmentData) -> bool:
	if attachment == null:
		return false
	var current := get_attachment_in_slot(attachment.slot)
	if current != null and current.attachment_id == attachment.attachment_id:
		remove_attachment(attachment.slot)
		return false
	equip_attachment(attachment)
	return true


func recompute_stats(adjust_ammo: bool = true) -> void:
	var old_capacity := stats.magazine_capacity if stats != null else 0
	stats = EffectiveWeaponStats.compute(data, get_active_attachments())
	if adjust_ammo and old_capacity > 0:
		var max_allowed := get_max_magazine_capacity()
		if current_mag > max_allowed:
			# Conserve excess rounds by returning them to reserve (clamped to max_reserve_ammo)
			var overflow := current_mag - max_allowed
			current_mag = max_allowed
			reserve_ammo = mini(data.max_reserve_ammo, reserve_ammo + overflow)
		ammo_changed.emit(current_mag, reserve_ammo, stats.magazine_capacity)


func get_max_magazine_capacity() -> int:
	if data == null or stats == null:
		return 0
	var extra := 1 if (data.allow_tactical_plus_one and data.reload_type == WeaponData.ReloadType.MAGAZINE) else 0
	return stats.magazine_capacity + extra


func get_current_fire_mode() -> WeaponData.FireMode:
	if data == null or data.supported_fire_modes.is_empty():
		return WeaponData.FireMode.SEMI
	fire_mode_index = clampi(fire_mode_index, 0, data.supported_fire_modes.size() - 1)
	return data.supported_fire_modes[fire_mode_index]


func cycle_fire_mode() -> bool:
	if data == null or data.supported_fire_modes.size() <= 1:
		return false
	fire_mode_index = (fire_mode_index + 1) % data.supported_fire_modes.size()
	fire_mode_changed.emit(get_current_fire_mode())
	return true


func can_consume_round() -> bool:
	return current_mag > 0


func consume_round() -> bool:
	if current_mag <= 0:
		return false
	current_mag -= 1
	ammo_changed.emit(current_mag, reserve_ammo, stats.magazine_capacity)
	return true


func needs_reload() -> bool:
	if reserve_ammo <= 0:
		return false
	if data.reload_type == WeaponData.ReloadType.MAGAZINE and data.allow_tactical_plus_one and current_mag > 0:
		return current_mag < stats.magazine_capacity + 1
	return current_mag < stats.magazine_capacity


func is_empty_reload() -> bool:
	return current_mag <= 0


func complete_magazine_reload() -> int:
	if reserve_ammo <= 0:
		return 0
	var target_capacity := stats.magazine_capacity
	if data.allow_tactical_plus_one and current_mag > 0:
		target_capacity += 1
	var needed := maxi(0, target_capacity - current_mag)
	var loaded := mini(needed, reserve_ammo)
	current_mag += loaded
	reserve_ammo -= loaded
	ammo_changed.emit(current_mag, reserve_ammo, stats.magazine_capacity)
	return loaded


func insert_single_shell() -> bool:
	if reserve_ammo <= 0 or current_mag >= stats.magazine_capacity:
		return false
	current_mag += 1
	reserve_ammo -= 1
	ammo_changed.emit(current_mag, reserve_ammo, stats.magazine_capacity)
	return true


func refill_ammo() -> void:
	current_mag = stats.magazine_capacity
	reserve_ammo = clampi(data.starting_reserve_ammo, 0, data.max_reserve_ammo)
	ammo_changed.emit(current_mag, reserve_ammo, stats.magazine_capacity)
