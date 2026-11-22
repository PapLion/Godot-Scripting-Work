class_name ShellCasing
extends RigidBody3D
## Lightweight physical ejected shell casing with automatic cleanup.

var lifetime: float = 2.4


func setup(color: Color, is_shotgun_shell: bool = false) -> void:
	collision_layer = 0
	collision_mask = 1 # Collide with world only
	mass = 0.02
	gravity_scale = 1.0

	var mesh_inst := MeshInstance3D.new()
	var cyl := CylinderMesh.new()
	if is_shotgun_shell:
		cyl.top_radius = 0.011
		cyl.bottom_radius = 0.011
		cyl.height = 0.058
	else:
		cyl.top_radius = 0.0055
		cyl.bottom_radius = 0.006
		cyl.height = 0.036
	mesh_inst.mesh = cyl
	mesh_inst.rotation_degrees.x = 90.0

	var mat := StandardMaterial3D.new()
	mat.albedo_color = color
	mat.metallic = 0.7 if not is_shotgun_shell else 0.2
	mat.roughness = 0.35
	mesh_inst.material_override = mat
	add_child(mesh_inst)

	var col := CollisionShape3D.new()
	var shape := CylinderShape3D.new()
	shape.radius = cyl.top_radius
	shape.height = cyl.height
	col.shape = shape
	col.rotation_degrees.x = 90.0
	add_child(col)


func _process(delta: float) -> void:
	lifetime -= delta
	if lifetime <= 0.0:
		queue_free()
