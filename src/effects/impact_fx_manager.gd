class_name ImpactFXManager
extends Node3D
## Centralized, event-driven Combat VFX Framework using native Godot GPUParticles3D,
## procedural emissive/translucent materials, surface-oriented decals, and bounded lifecycle budgets.
## Supports surface-dependent entry/exit impacts, armor/headshot/kill feedback, tracers, and muzzle smoke.

enum VFXQuality {
	LOW = 0,
	MEDIUM = 1,
	HIGH = 2,
}

@export var quality: VFXQuality = VFXQuality.HIGH

var _decals: Array[Node3D] = []
var _active_effects: Array[Node3D] = []
var _shared_meshes: Dictionary = {}
var _shared_materials: Dictionary = {}


func get_max_decals() -> int:
	match quality:
		VFXQuality.LOW:
			return 20
		VFXQuality.MEDIUM:
			return 40
		_:
			return 64


func get_max_effects() -> int:
	match quality:
		VFXQuality.LOW:
			return 20
		VFXQuality.MEDIUM:
			return 36
		_:
			return 56


func get_active_decal_count() -> int:
	_prune_invalid(_decals)
	return _decals.size()


func get_active_effect_count() -> int:
	_prune_invalid(_active_effects)
	return _active_effects.size()


func spawn_shot_fx(summary: FPSEvents.ShotSummary, tracer_color: Color) -> void:
	if summary == null or not is_inside_tree():
		return

	var played_impact_audio := false
	for hit_res in summary.hits:
		var seg_start := hit_res.segment_start if hit_res.segment_start != Vector3.ZERO else summary.muzzle_position
		var end_pos := hit_res.position
		if not hit_res.is_exit and seg_start.distance_squared_to(end_pos) > 0.20:
			var t_col := tracer_color
			if hit_res.damage_multiplier_after_pen < 0.99:
				t_col = Color(tracer_color.r, tracer_color.g * 0.85, tracer_color.b * 0.75, 0.72)
			_spawn_tracer(seg_start, end_pos, t_col)

		if not hit_res.hit:
			continue

		if hit_res.hit_damageable:
			_spawn_hit_feedback_vfx(hit_res)
		else:
			_spawn_surface_impact_vfx(hit_res)
			_spawn_impact_mark(hit_res.position, hit_res.normal, hit_res.surface_type, hit_res.is_exit)
			if not played_impact_audio and not hit_res.is_exit:
				_play_impact_audio(hit_res.position, hit_res.surface_type)
				played_impact_audio = true


func spawn_muzzle_smoke(
	muzzle_pos: Vector3,
	forward: Vector3,
	preset: int,
	barrel_heat: float
) -> void:
	if not is_inside_tree():
		return
	var is_shotgun := (preset == WeaponData.VisualPreset.SHOTGUN)
	var is_sniper := (preset == WeaponData.VisualPreset.PRECISION_RIFLE)
	var count := _scale_count(10 if is_shotgun else (7 if is_sniper else 5))
	if barrel_heat > 0.45:
		count += _scale_count(3)

	var p := _create_gpu_burst(
		muzzle_pos,
		forward.normalized(),
		count,
		0.45 if is_shotgun else 0.34,
		Color(0.82, 0.84, 0.86, 0.38 if is_shotgun else 0.24),
		0.35 if is_shotgun else 0.22,
		1.4 if is_shotgun else 0.9,
		Vector3(0.0, 0.9, 0.0), # gentle upward thermal drift
		0.055 if is_shotgun else 0.036,
		28.0 if is_shotgun else 18.0,
		false
	)
	_register_effect(p, 0.65)


func _spawn_surface_impact_vfx(hit_res: FPSEvents.HitResult) -> void:
	var pos := hit_res.position
	var normal := hit_res.normal.normalized()
	var surface := hit_res.surface_type
	var exit_boost := 1.35 if hit_res.is_exit else 1.0

	match surface:
		SurfaceMaterialType.Type.METAL:
			# Bright glowing golden-white ricochet sparks + subtle dark smoke
			var sparks := _create_gpu_burst(
				pos + normal * 0.015, normal, _scale_count(14), 0.32,
				Color(1.0, 0.86, 0.36, 1.0), 2.8, 6.2, Vector3(0.0, -9.8, 0.0),
				0.022, 42.0, true
			)
			_register_effect(sparks, 0.45)

		SurfaceMaterialType.Type.WOOD:
			# Directional tan wooden splinters + sawdust cloud (stronger blowout on exit!)
			var splinters := _create_gpu_burst(
				pos + normal * 0.015, normal, _scale_count(int(10 * exit_boost)), 0.38,
				Color(0.68, 0.46, 0.24, 1.0), 1.6 * exit_boost, 4.2 * exit_boost, Vector3(0.0, -7.5, 0.0),
				0.032, 34.0 if hit_res.is_exit else 26.0, false
			)
			_register_effect(splinters, 0.50)
			var dust := _create_gpu_burst(
				pos + normal * 0.02, normal, _scale_count(5), 0.42,
				Color(0.76, 0.62, 0.44, 0.45), 0.4, 1.3, Vector3(0.0, 0.35, 0.0),
				0.065, 38.0, false
			)
			_register_effect(dust, 0.55)

		SurfaceMaterialType.Type.GLASS:
			# Sparkling translucent cyan-white glass shards spraying outward
			var shards := _create_gpu_burst(
				pos + normal * 0.015, normal, _scale_count(int(14 * exit_boost)), 0.44,
				Color(0.76, 0.94, 1.0, 0.85), 1.8 * exit_boost, 5.0 * exit_boost, Vector3(0.0, -8.8, 0.0),
				0.028, 46.0, true
			)
			_register_effect(shards, 0.55)

		SurfaceMaterialType.Type.DRYWALL:
			# White plaster powder cloud + fine chips
			var cloud := _create_gpu_burst(
				pos + normal * 0.02, normal, _scale_count(int(9 * exit_boost)), 0.48,
				Color(0.92, 0.92, 0.90, 0.55), 0.5, 1.8, Vector3(0.0, 0.25, 0.0),
				0.078, 40.0, false
			)
			_register_effect(cloud, 0.60)

		SurfaceMaterialType.Type.CONCRETE, SurfaceMaterialType.Type.GROUND:
			# Concrete dust puff + angular dark debris chunks
			var chunks := _create_gpu_burst(
				pos + normal * 0.015, normal, _scale_count(9), 0.36,
				Color(0.45, 0.46, 0.48, 1.0), 1.5, 4.0, Vector3(0.0, -9.8, 0.0),
				0.028, 36.0, false
			)
			_register_effect(chunks, 0.48)
			var puff := _create_gpu_burst(
				pos + normal * 0.02, normal, _scale_count(6), 0.46,
				Color(0.75, 0.76, 0.74, 0.48), 0.45, 1.4, Vector3(0.0, 0.45, 0.0),
				0.075, 42.0, false
			)
			_register_effect(puff, 0.58)

		_:
			var generic := _create_gpu_burst(
				pos + normal * 0.015, normal, _scale_count(7), 0.30,
				Color(0.82, 0.82, 0.80, 0.9), 1.4, 3.2, Vector3(0.0, -6.0, 0.0),
				0.026, 35.0, false
			)
			_register_effect(generic, 0.42)


func _spawn_hit_feedback_vfx(hit_res: FPSEvents.HitResult) -> void:
	var pos := hit_res.position
	var normal := hit_res.normal.normalized()

	# Armor deflection sparks (cyan-blue metallic burst)
	if hit_res.armor_absorbed > 0.5:
		var arm_sparks := _create_gpu_burst(
			pos + normal * 0.02, normal, _scale_count(10), 0.28,
			Color(0.40, 0.85, 1.0, 1.0), 2.2, 5.2, Vector3(0.0, -7.5, 0.0),
			0.024, 48.0, true
		)
		_register_effect(arm_sparks, 0.40)

	# Headshot / critical burst vs standard readable body hit
	var hit_col := Color(1.0, 0.24, 0.18, 1.0) if hit_res.is_critical else Color(1.0, 0.52, 0.22, 0.95)
	var hit_cnt := _scale_count(12 if hit_res.is_critical else 7)
	var hit_burst := _create_gpu_burst(
		pos + normal * 0.02, normal, hit_cnt, 0.26 if not hit_res.is_critical else 0.34,
		hit_col, 1.6, 4.4 if hit_res.is_critical else 3.0, Vector3(0.0, -6.5, 0.0),
		0.030 if hit_res.is_critical else 0.022, 44.0, true
	)
	_register_effect(hit_burst, 0.44)

	# Target destruction burst
	if hit_res.killed_target:
		var kill_burst := _create_gpu_burst(
			pos + normal * 0.03, Vector3.UP, _scale_count(14), 0.45,
			Color(1.0, 0.82, 0.28, 1.0), 2.0, 5.5, Vector3(0.0, -8.0, 0.0),
			0.036, 75.0, true
		)
		_register_effect(kill_burst, 0.58)


func _create_gpu_burst(
	world_pos: Vector3,
	direction: Vector3,
	amount: int,
	lifetime: float,
	color: Color,
	vel_min: float,
	vel_max: float,
	gravity: Vector3,
	particle_size: float,
	spread_deg: float,
	unshaded: bool
) -> GPUParticles3D:
	var p := GPUParticles3D.new()
	p.one_shot = true
	p.explosiveness = 0.92
	p.amount = maxi(2, amount)
	p.lifetime = lifetime
	p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF

	var proc := ParticleProcessMaterial.new()
	proc.direction = direction.normalized()
	proc.spread = spread_deg
	proc.initial_velocity_min = vel_min
	proc.initial_velocity_max = vel_max
	proc.gravity = gravity
	proc.damping_min = 1.2
	proc.damping_max = 2.6
	proc.scale_min = 0.55
	proc.scale_max = 1.25

	# Smooth fade-out color ramp
	var grad := Gradient.new()
	grad.set_color(0, color)
	grad.set_color(1, Color(color.r, color.g, color.b, 0.0))
	var grad_tex := GradientTexture1D.new()
	grad_tex.gradient = grad
	proc.color_ramp = grad_tex
	p.process_material = proc

	var mesh := BoxMesh.new()
	mesh.size = Vector3.ONE * particle_size
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color.WHITE
	mat.vertex_color_use_as_albedo = true
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.roughness = 0.6
	if unshaded:
		mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mesh.material = mat
	p.draw_pass_1 = mesh

	add_child(p)
	p.global_position = world_pos
	p.emitting = true
	return p


func _register_effect(node: Node3D, cleanup_sec: float) -> void:
	_prune_invalid(_active_effects)
	_active_effects.append(node)
	var max_fx := get_max_effects()
	while _active_effects.size() > max_fx:
		var oldest := _active_effects.pop_front() as Node3D
		if is_instance_valid(oldest):
			oldest.queue_free()

	var tw := create_tween()
	tw.tween_interval(cleanup_sec)
	tw.tween_callback(func() -> void:
		if is_instance_valid(node):
			node.queue_free()
	)


func _spawn_tracer(from_pos: Vector3, to_pos: Vector3, color: Color) -> void:
	var dist := from_pos.distance_to(to_pos)
	if dist < 0.2:
		return
	var visual_dist := minf(dist, 95.0)
	var mid := from_pos.lerp(to_pos, 0.5)

	var tracer := MeshInstance3D.new()
	var cyl := CylinderMesh.new()
	cyl.top_radius = 0.0038
	cyl.bottom_radius = 0.0038
	cyl.height = visual_dist
	cyl.radial_segments = 6
	tracer.mesh = cyl
	tracer.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF

	var mat := StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.albedo_color = color
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	tracer.material_override = mat

	add_child(tracer)
	tracer.global_position = mid
	var dir := (to_pos - from_pos).normalized()
	var up := Vector3.UP if absf(dir.dot(Vector3.UP)) < 0.98 else Vector3.RIGHT
	tracer.look_at(to_pos, up)
	tracer.rotate_object_local(Vector3.RIGHT, PI * 0.5)

	var tween := create_tween()
	tween.tween_property(mat, "albedo_color:a", 0.0, 0.068)
	tween.tween_callback(tracer.queue_free)


func _spawn_impact_mark(pos: Vector3, normal: Vector3, surface: SurfaceMaterialType.Type, is_exit: bool) -> void:
	var mark := MeshInstance3D.new()
	var quad := QuadMesh.new()
	var sz := 0.115 if is_exit else 0.082
	if surface == SurfaceMaterialType.Type.GLASS:
		sz = 0.16
	quad.size = Vector2(sz, sz)
	mark.mesh = quad
	mark.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF

	var mat := StandardMaterial3D.new()
	mat.albedo_color = _get_surface_mark_color(surface, is_exit)
	mat.roughness = 0.85
	if surface == SurfaceMaterialType.Type.GLASS:
		mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mark.material_override = mat

	add_child(mark)
	mark.global_position = pos + normal * 0.009
	var up := Vector3.UP if absf(normal.dot(Vector3.UP)) < 0.98 else Vector3.RIGHT
	mark.look_at(pos + normal * 2.0, up)
	mark.rotate_object_local(Vector3.FORWARD, randf_range(0.0, TAU))

	_prune_invalid(_decals)
	_decals.append(mark)
	var max_decals := get_max_decals()
	while _decals.size() > max_decals:
		var old := _decals.pop_front() as Node3D
		if is_instance_valid(old):
			old.queue_free()


func _play_impact_audio(pos: Vector3, surface: SurfaceMaterialType.Type) -> void:
	var sound_id := &"impact_concrete"
	match surface:
		SurfaceMaterialType.Type.METAL:
			sound_id = &"impact_metal"
		SurfaceMaterialType.Type.WOOD:
			sound_id = &"impact_wood"
		SurfaceMaterialType.Type.GLASS:
			sound_id = &"impact_glass"
		SurfaceMaterialType.Type.DRYWALL:
			sound_id = &"impact_drywall"
		SurfaceMaterialType.Type.FLESH:
			return

	var audio := AudioStreamPlayer3D.new()
	audio.stream = ProceduralAudio.get_sound(sound_id)
	audio.volume_db = -7.0
	audio.max_distance = 45.0
	add_child(audio)
	audio.global_position = pos
	audio.finished.connect(audio.queue_free)
	audio.play()


func _get_surface_mark_color(surface: SurfaceMaterialType.Type, is_exit: bool) -> Color:
	match surface:
		SurfaceMaterialType.Type.METAL:
			return Color(0.10, 0.11, 0.13)
		SurfaceMaterialType.Type.WOOD:
			return Color(0.28, 0.18, 0.10) if is_exit else Color(0.18, 0.11, 0.06)
		SurfaceMaterialType.Type.GLASS:
			return Color(0.84, 0.96, 1.0, 0.55)
		SurfaceMaterialType.Type.DRYWALL:
			return Color(0.72, 0.72, 0.70) if is_exit else Color(0.26, 0.26, 0.27)
		_:
			return Color(0.11, 0.11, 0.12)


func _scale_count(base_count: int) -> int:
	match quality:
		VFXQuality.LOW:
			return maxi(2, int(round(base_count * 0.45)))
		VFXQuality.MEDIUM:
			return maxi(3, int(round(base_count * 0.75)))
		_:
			return base_count


func _prune_invalid(arr: Array[Node3D]) -> void:
	var i := arr.size() - 1
	while i >= 0:
		if not is_instance_valid(arr[i]):
			arr.remove_at(i)
		i -= 1
