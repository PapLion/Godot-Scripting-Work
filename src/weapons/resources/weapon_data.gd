class_name WeaponData
extends Resource
## Data-driven configuration Resource for any weapon in the FPS Framework.
## Creating a new weapon primarily requires authoring a .tres of this Resource.

enum FireMode {
	SEMI = 0,
	AUTO = 1,
	BURST = 2,
	BOLT_ACTION = 3,
}

enum ReloadType {
	MAGAZINE = 0,
	SHELL_BY_SHELL = 1,
}

enum VisualPreset {
	ASSAULT_RIFLE = 0,
	SHOTGUN = 1,
	PRECISION_RIFLE = 2,
}

@export_group("Identity")
@export var weapon_id: StringName = &"weapon_default"
@export var display_name: String = "Default Weapon"
@export var visual_preset: VisualPreset = VisualPreset.ASSAULT_RIFLE
@export var viewmodel_scene: PackedScene
@export var accent_color: Color = Color(0.22, 0.24, 0.28)

@export_group("Ballistics & Damage")
@export var base_damage: float = 28.0
@export var pellets_per_shot: int = 1
@export var fire_rate_rpm: float = 650.0
@export var supported_fire_modes: Array[FireMode] = [FireMode.AUTO, FireMode.SEMI]
@export var burst_count: int = 3
@export var effective_range: float = 45.0
@export var max_falloff_range: float = 110.0
@export_range(0.1, 1.0, 0.05) var min_falloff_multiplier: float = 0.55
@export var max_ray_distance: float = 250.0
@export var impact_impulse: float = 4.0

@export_group("Ammunition & Reload")
@export var magazine_capacity: int = 30
@export var starting_reserve_ammo: int = 120
@export var max_reserve_ammo: int = 180
@export var reload_type: ReloadType = ReloadType.MAGAZINE
@export var tactical_reload_duration: float = 1.65
@export var empty_reload_duration: float = 2.15
@export var shell_reload_start_duration: float = 0.35
@export var shell_reload_insert_duration: float = 0.42
@export var shell_reload_end_duration: float = 0.30
@export var allow_tactical_plus_one: bool = false

@export_group("Handling & Timing")
@export var equip_duration: float = 0.32
@export var unequip_duration: float = 0.22
@export var bolt_cycle_duration: float = 0.82

@export_group("Spread (Degrees)")
@export var base_hip_spread_deg: float = 1.6
@export var base_ads_spread_deg: float = 0.22
@export var move_spread_penalty_deg: float = 1.8
@export var air_spread_penalty_deg: float = 3.2
@export var crouch_spread_multiplier: float = 0.72
@export var spread_per_shot_deg: float = 0.45
@export var max_bloom_spread_deg: float = 4.2
@export var spread_recovery_rate_deg: float = 6.5

@export_group("Recoil (Degrees)")
@export var recoil_vertical_kick_deg: float = 1.15
@export var recoil_horizontal_spread_deg: float = 0.45
@export var recoil_ads_multiplier: float = 0.65
@export var recoil_crouch_multiplier: float = 0.8
@export var recoil_sustained_scale: float = 0.10
@export var recoil_max_pitch_deg: float = 14.0
@export var recoil_snap_speed: float = 18.0
@export var recoil_recovery_speed: float = 9.5
@export var recoil_recovery_delay: float = 0.09
@export var viewmodel_kickback_z: float = 0.045
@export var viewmodel_kick_pitch_deg: float = 3.2

@export_group("Aim Down Sights (ADS)")
@export var ads_fov: float = 55.0
@export var ads_transition_speed: float = 11.0
@export var ads_sensitivity_multiplier: float = 0.62
@export var hip_position: Vector3 = Vector3(0.24, -0.22, -0.44)
@export var ads_position: Vector3 = Vector3(0.0, -0.155, -0.34)
@export var sprint_position: Vector3 = Vector3(0.18, -0.29, -0.38)
@export var sprint_rotation_deg: Vector3 = Vector3(-16.0, 26.0, -8.0)

@export_group("Audio & Feedback")
@export var fire_sound_id: StringName = &"shot_ar"
@export var eject_shell_color: Color = Color(0.85, 0.68, 0.25)
@export var tracer_color: Color = Color(1.0, 0.88, 0.55)


func get_fire_interval() -> float:
	return 60.0 / maxf(1.0, fire_rate_rpm)


static func get_fire_mode_label(mode: FireMode) -> String:
	match mode:
		FireMode.SEMI:
			return "SEMI"
		FireMode.AUTO:
			return "AUTO"
		FireMode.BURST:
			return "BURST"
		FireMode.BOLT_ACTION:
			return "BOLT"
		_:
			return "SEMI"
