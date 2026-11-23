class_name SurfaceTag
extends Node
## Attach as a child of any CollisionObject3D to declare its ballistic surface material
## and optional per-object penetration overrides.

@export var surface_type: SurfaceMaterialType.Type = SurfaceMaterialType.Type.CONCRETE
@export var override_penetration: bool = false
@export var allow_penetration: bool = true
@export var resistance_multiplier: float = 1.0
