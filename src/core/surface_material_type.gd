class_name SurfaceMaterialType
extends RefCounted
## Surface classification & configurable ballistic penetration profiles for impact VFX and penetration.

enum Type {
	GENERIC = 0,
	CONCRETE = 1,
	METAL = 2,
	WOOD = 3,
	FLESH = 4,
	GLASS = 5,
	DRYWALL = 6,
	GROUND = 7,
}


class PenetrationProfile extends RefCounted:
	var penetrable: bool = false
	var min_entry_cost: float = 1.0
	var resistance_per_meter: float = 10.0
	var damage_retention: float = 0.7
	var max_probe_thickness: float = 0.65

	func _init(p_pen: bool, p_entry: float, p_res: float, p_ret: float, p_max_t: float = 0.65) -> void:
		penetrable = p_pen
		min_entry_cost = p_entry
		resistance_per_meter = p_res
		damage_retention = p_ret
		max_probe_thickness = p_max_t


static func get_surface_name(surface: Type) -> String:
	match surface:
		Type.CONCRETE:
			return "Concrete"
		Type.METAL:
			return "Metal"
		Type.WOOD:
			return "Wood"
		Type.FLESH:
			return "Flesh"
		Type.GLASS:
			return "Glass"
		Type.DRYWALL:
			return "Drywall"
		Type.GROUND:
			return "Ground"
		_:
			return "Generic"


static func get_penetration_profile(surface: Type) -> PenetrationProfile:
	match surface:
		Type.GLASS:
			return PenetrationProfile.new(true, 0.12, 0.8, 0.90, 0.25)
		Type.DRYWALL:
			return PenetrationProfile.new(true, 0.22, 2.2, 0.82, 0.40)
		Type.WOOD:
			return PenetrationProfile.new(true, 0.35, 3.8, 0.72, 0.50)
		Type.CONCRETE:
			# Blocks ordinary shots; only high-power precision rounds punch very thin edges
			return PenetrationProfile.new(true, 2.20, 14.0, 0.42, 0.35)
		Type.METAL:
			# Heavy steel barriers block standard & rifle rounds
			return PenetrationProfile.new(false, 9.0, 26.0, 0.30, 0.25)
		Type.GROUND:
			return PenetrationProfile.new(false, 9.0, 24.0, 0.25, 0.20)
		_:
			return PenetrationProfile.new(false, 6.0, 18.0, 0.40, 0.25)


static func resolve_from_collider(collider: Object) -> Type:
	var tag := resolve_tag_from_collider(collider)
	if tag != null:
		return tag.surface_type
	if collider is Node:
		var node := collider as Node
		if node.has_meta("surface_type"):
			return int(node.get_meta("surface_type")) as Type
		if node.get_parent() != null and node.get_parent().has_meta("surface_type"):
			return int(node.get_parent().get_meta("surface_type")) as Type
	return Type.GENERIC


static func resolve_tag_from_collider(collider: Object) -> SurfaceTag:
	if collider is Node:
		var node := collider as Node
		for child in node.get_children():
			if child is SurfaceTag:
				return child as SurfaceTag
	return null
