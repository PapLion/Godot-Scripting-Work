class_name AttachmentData
extends Resource
## Reusable weapon attachment Resource that modifies effective weapon behavior.
## Multiple attachments across distinct slots compose cleanly via EffectiveWeaponStats.

enum Slot {
	OPTIC = 0,
	MUZZLE = 1,
	MAGAZINE = 2,
	UNDERBARREL = 3,
}

@export_group("Identity")
@export var attachment_id: StringName = &"attachment_default"
@export var display_name: String = "Attachment"
@export var slot: Slot = Slot.OPTIC
@export var short_description: String = ""

@export_group("Damage & Range")
@export var damage_multiplier: float = 1.0
@export var effective_range_multiplier: float = 1.0

@export_group("Recoil Modifiers")
@export var recoil_vertical_multiplier: float = 1.0
@export var recoil_horizontal_multiplier: float = 1.0

@export_group("Spread Modifiers")
@export var hip_spread_multiplier: float = 1.0
@export var ads_spread_multiplier: float = 1.0
@export var move_spread_multiplier: float = 1.0

@export_group("Magazine & Reload Modifiers")
@export var magazine_capacity_multiplier: float = 1.0
@export var magazine_capacity_bonus: int = 0
@export var reload_duration_multiplier: float = 1.0

@export_group("ADS Modifiers")
@export var ads_fov_offset: float = 0.0
@export var ads_speed_multiplier: float = 1.0
@export var ads_y_offset: float = 0.0


static func get_slot_name(s: Slot) -> String:
	match s:
		Slot.OPTIC:
			return "Optic"
		Slot.MUZZLE:
			return "Muzzle"
		Slot.MAGAZINE:
			return "Magazine"
		Slot.UNDERBARREL:
			return "Underbarrel"
		_:
			return "Slot"
