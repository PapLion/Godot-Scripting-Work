class_name SurfaceMaterialType
extends RefCounted
## Surface classification for ballistic impact feedback (particles, decals, audio).

enum Type {
	GENERIC = 0,
	CONCRETE = 1,
	METAL = 2,
	WOOD = 3,
	FLESH = 4,
	GLASS = 5,
}


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
		_:
			return "Generic"


static func resolve_from_collider(collider: Object) -> Type:
	if collider == null:
		return Type.GENERIC

	if collider is Node:
		var node := collider as Node
		if node.has_meta("surface_type"):
			return int(node.get_meta("surface_type")) as Type
		for child in node.get_children():
			if child is SurfaceTag:
				return (child as SurfaceTag).surface_type
		if node.get_parent() != null and node.get_parent().has_meta("surface_type"):
			return int(node.get_parent().get_meta("surface_type")) as Type

	return Type.GENERIC
