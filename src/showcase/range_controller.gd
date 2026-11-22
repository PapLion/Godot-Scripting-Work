class_name RangeController
extends Node3D
## Builds and orchestrates the minimal FPS Training Range showcase scene.
## Provides distance lanes, static/armored/moving targets, cover, multi-surface ballistic test panels,
## and a target/ammo reset mechanism.

@onready var player: FPSPlayer = $FPSPlayer
@onready var fx_manager: ImpactFXManager = $ImpactFXManager
@onready var hud: FPSHud = $FPSHud
@onready var geometry_root: Node3D = $RangeGeometry
@onready var targets_root: Node3D = $Targets

const TARGET_SCENE: PackedScene = preload("res://src/damage/target_dummy.tscn")


func _ready() -> void:
	_build_range_environment()
	_spawn_range_targets()

	if player != null:
		player.initialize_combat(fx_manager)
	if hud != null and player != null:
		hud.bind_player(player)

	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--demo-mode="):
			var mode := arg.trim_prefix("--demo-mode=")
			var rec := DemoRecorder.new()
			rec.name = "DemoRecorder"
			add_child(rec)
			rec.setup(self, mode)
			break


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("reset_targets"):
		reset_all_targets()


func reset_all_targets() -> void:
	for node in get_tree().get_nodes_in_group("range_targets"):
		if node is TargetDummy:
			(node as TargetDummy).reset_target()
	if player != null and player.weapon_manager != null:
		player.weapon_manager.refill_all_ammo()


func _build_range_environment() -> void:
	var floor_mat := _make_mat(Color(0.28, 0.30, 0.34), 0.1, 0.85)
	var wall_mat := _make_mat(Color(0.36, 0.39, 0.44), 0.1, 0.82)
	var accent_mat := _make_mat(Color(0.86, 0.56, 0.16), 0.2, 0.55)
	var cover_mat := _make_mat(Color(0.24, 0.27, 0.32), 0.2, 0.72)
	var metal_mat := _make_mat(Color(0.52, 0.56, 0.62), 0.78, 0.32)
	var wood_mat := _make_mat(Color(0.52, 0.35, 0.20), 0.05, 0.82)
	var concrete_mat := _make_mat(Color(0.54, 0.55, 0.54), 0.05, 0.92)

	# Main range floor (30m wide x 96m long)
	_add_static_box("Floor", Vector3(30.0, 0.5, 96.0), Vector3(0.0, -0.25, -34.0), floor_mat, SurfaceMaterialType.Type.CONCRETE)

	# Perimeter walls (backstop, left, right, rear)
	_add_static_box("BackstopWall", Vector3(30.0, 8.0, 1.0), Vector3(0.0, 4.0, -82.0), wall_mat, SurfaceMaterialType.Type.CONCRETE)
	_add_static_box("RearWall", Vector3(30.0, 6.0, 1.0), Vector3(0.0, 3.0, 14.0), wall_mat, SurfaceMaterialType.Type.CONCRETE)
	_add_static_box("LeftWall", Vector3(1.0, 6.0, 96.0), Vector3(-15.0, 3.0, -34.0), wall_mat, SurfaceMaterialType.Type.CONCRETE)
	_add_static_box("RightWall", Vector3(1.0, 6.0, 96.0), Vector3(15.0, 3.0, -34.0), wall_mat, SurfaceMaterialType.Type.CONCRETE)

	# Firing line accent stripe at Z = +2
	_add_visual_box("FiringLineStripe", Vector3(28.0, 0.02, 0.25), Vector3(0.0, 0.01, 2.0), accent_mat)

	# Tactical cover blocks near firing deck (standing + crouching cover + tall corner-peek pillar)
	_add_static_box("CoverLeft", Vector3(2.6, 1.15, 0.55), Vector3(-4.2, 0.575, 0.8), cover_mat, SurfaceMaterialType.Type.CONCRETE)
	_add_static_box("CoverRight", Vector3(2.6, 1.15, 0.55), Vector3(4.2, 0.575, 0.8), cover_mat, SurfaceMaterialType.Type.CONCRETE)
	_add_static_box("PeekPillarCenter", Vector3(1.15, 2.35, 0.55), Vector3(-1.35, 1.175, 3.0), cover_mat, SurfaceMaterialType.Type.CONCRETE)
	_add_label("Q/E PEEK COVER", Vector3(-1.35, 2.60, 3.30), 26)

	# Low crouch-clearance beam on the far left for testing crouch ceiling detection
	_add_static_box("CrouchTunnelRoof", Vector3(3.6, 0.35, 3.2), Vector3(-10.5, 1.52, 4.5), cover_mat, SurfaceMaterialType.Type.METAL)
	_add_label("CROUCH CHECK", Vector3(-10.5, 2.05, 6.2), 32)

	# Distance lane stripes & 3D markers (measured from spawn at Z = +6)
	var distances := [10, 25, 45, 70]
	for d in distances:
		var z_pos := 6.0 - float(d)
		_add_visual_box("LaneStripe_%dm" % d, Vector3(28.0, 0.02, 0.14), Vector3(0.0, 0.01, z_pos), accent_mat)
		_add_label("%dm" % d, Vector3(-13.8, 1.4, z_pos), 46, Vector3(0.0, 90.0, 0.0))
		_add_label("%dm" % d, Vector3(13.8, 1.4, z_pos), 46, Vector3(0.0, -90.0, 0.0))

	# Multi-surface ballistic impact test wall on the right lane
	var panel_z := -2.0
	_add_static_box("SurfaceConcrete", Vector3(0.35, 2.6, 2.4), Vector3(11.5, 1.3, panel_z + 2.8), concrete_mat, SurfaceMaterialType.Type.CONCRETE)
	_add_label("CONCRETE", Vector3(11.2, 2.9, panel_z + 2.8), 32, Vector3(0.0, -90.0, 0.0))

	_add_static_box("SurfaceMetal", Vector3(0.35, 2.6, 2.4), Vector3(11.5, 1.3, panel_z), metal_mat, SurfaceMaterialType.Type.METAL)
	_add_label("STEEL PLATE", Vector3(11.2, 2.9, panel_z), 32, Vector3(0.0, -90.0, 0.0))

	_add_static_box("SurfaceWood", Vector3(0.35, 2.6, 2.4), Vector3(11.5, 1.3, panel_z - 2.8), wood_mat, SurfaceMaterialType.Type.WOOD)
	_add_label("TIMBER", Vector3(11.2, 2.9, panel_z - 2.8), 32, Vector3(0.0, -90.0, 0.0))

	# Range signage on backstop
	_add_label("GODOT SYSTEMS LAB  //  01-ADVANCED-FPS RANGE", Vector3(0.0, 6.2, -81.2), 72)


func _spawn_range_targets() -> void:
	# 1. Close static target (10m) — ideal for shotgun & headshot multiplier demo
	_add_target("TargetClose10m", "STATIC 10m", Vector3(-3.6, 0.0, -4.0), 100.0, 0.0, false, 0.0, 0.0)

	# 2. Armored close-mid target (12m) — demonstrates armor absorption & armor drain
	_add_target("TargetArmored12m", "ARMORED 12m", Vector3(0.0, 0.0, -6.0), 100.0, 80.0, false, 0.0, 0.0)

	# 3. Moving mid-range target (20m) — demonstrates tracking & recoil control
	_add_target("TargetMoving20m", "MOVING 20m", Vector3(0.0, 0.0, -14.0), 100.0, 0.0, true, 4.2, 1.8)

	# 4. Mid-range armored target (25m)
	_add_target("TargetMid25m", "ARMORED 25m", Vector3(4.2, 0.0, -19.0), 120.0, 60.0, false, 0.0, 0.0)

	# 5. Long-range precision target (45m)
	_add_target("TargetLong45m", "PRECISION 45m", Vector3(-2.5, 0.0, -39.0), 100.0, 0.0, false, 0.0, 0.0)

	# 6. Long-range moving target (65m)
	_add_target("TargetLongMoving65m", "MOVING 65m", Vector3(2.2, 0.0, -59.0), 100.0, 0.0, true, 5.0, 1.4)


func _add_target(
	node_name: String,
	label_text: String,
	pos: Vector3,
	hp: float,
	armor: float,
	moving: bool,
	move_dist: float,
	move_spd: float
) -> TargetDummy:
	var target := TARGET_SCENE.instantiate() as TargetDummy
	target.name = node_name
	target.target_label = label_text
	target.position = pos
	target.max_health = hp
	target.max_armor = armor
	target.move_enabled = moving
	target.move_distance = move_dist
	target.move_speed = move_spd
	targets_root.add_child(target)
	return target


func _add_static_box(
	node_name: String,
	size: Vector3,
	pos: Vector3,
	mat: Material,
	surface: SurfaceMaterialType.Type
) -> StaticBody3D:
	var body := StaticBody3D.new()
	body.name = node_name
	body.position = pos
	body.collision_layer = 1 # Layer 1: World
	body.collision_mask = 0

	var tag := SurfaceTag.new()
	tag.surface_type = surface
	body.add_child(tag)

	var mesh_inst := MeshInstance3D.new()
	var box := BoxMesh.new()
	box.size = size
	mesh_inst.mesh = box
	mesh_inst.material_override = mat
	body.add_child(mesh_inst)

	var col := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = size
	col.shape = shape
	body.add_child(col)

	geometry_root.add_child(body)
	return body


func _add_visual_box(node_name: String, size: Vector3, pos: Vector3, mat: Material) -> void:
	var mesh_inst := MeshInstance3D.new()
	mesh_inst.name = node_name
	var box := BoxMesh.new()
	box.size = size
	mesh_inst.mesh = box
	mesh_inst.material_override = mat
	mesh_inst.position = pos
	mesh_inst.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	geometry_root.add_child(mesh_inst)


func _add_label(text: String, pos: Vector3, size: int = 36, rot_deg: Vector3 = Vector3.ZERO) -> void:
	var lbl := Label3D.new()
	lbl.text = text
	lbl.position = pos
	lbl.rotation_degrees = rot_deg
	lbl.font_size = size
	lbl.outline_size = 8
	lbl.modulate = Color(0.95, 0.96, 0.98)
	geometry_root.add_child(lbl)


func _make_mat(color: Color, metallic: float, roughness: float) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = color
	m.metallic = metallic
	m.roughness = roughness
	return m
