class_name ImpactFXManager
extends Node3D
## Spawns surface-dependent ballistic impact effects, bullet tracers, and impact audio.
## Keeps all temporary FX self-cleaning with bounded lifetimes.

const MAX_ACTIVE_DECALS := 48
var _decals: Array[Node3D] = []


func spawn_shot_fx(summary: FPSEvents.ShotSummary, tracer_color: Color) -> void:
	if summary == null:
		return

	var played_impact_audio := false
	for hit_res in summary.hits:
		var start_pos := summary.muzzle_position
		var end_pos := hit_res.position
		if start_pos.distance_squared_to(end_pos) > 0.25:
			_spawn_tracer(start_pos, end_pos, tracer_color)

		if hit_res.hit:
			_spawn_impact_burst(hit_res.position, hit_res.normal, hit_res.surface_type, hit_res.is_critical)
			if not hit_res.hit_damageable:
				_spawn_impact_mark(hit_res.position, hit_res.normal, hit_res.surface_type)
			if not played_impact_audio:
				_play_impact_audio(hit_res.position, hit_res.surface_type)
				played_impact_audio = true


func _spawn_tracer(from_pos: Vector3, to_pos: Vector3, color: Color) -> void:
	var dist := from_pos.distance_to(to_pos)
	if dist < 0.2:
		return
	var visual_dist := minf(dist, 90.0)
	var mid := from_pos.lerp(to_pos, 0.5)

	var tracer := MeshInstance3D.new()
	var cyl := CylinderMesh.new()
	cyl.top_radius = 0.004
	cyl.bottom_radius = 0.004
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
	tween.tween_property(mat, "albedo_color:a", 0.0, 0.065)
	tween.tween_callback(tracer.queue_free)


func _spawn_impact_burst(pos: Vector3, normal: Vector3, surface: SurfaceMaterialType.Type, is_crit: bool) -> void:
	var color := _get_surface_spark_color(surface, is_crit)
	var count := 6 if surface == SurfaceMaterialType.Type.METAL else 4

	var root := Node3D.new()
	add_child(root)
	root.global_position = pos + normal * 0.015

	var mat := StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.albedo_color = color
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA

	var box := BoxMesh.new()
	box.size = Vector3.ONE * (0.045 if is_crit else 0.032)

	var rng := RandomNumberGenerator.new()
	rng.randomize()

	var tween := create_tween()
	tween.set_parallel(true)
	for i in count:
		var spark := MeshInstance3D.new()
		spark.mesh = box
		spark.material_override = mat
		spark.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		root.add_child(spark)

		var scatter := (normal + Vector3(
			rng.randf_range(-0.85, 0.85),
			rng.randf_range(-0.5, 0.95),
			rng.randf_range(-0.85, 0.85)
		)).normalized()
		var dist := rng.randf_range(0.18, 0.55)
		tween.tween_property(spark, "position", scatter * dist, 0.22).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
		tween.tween_property(spark, "scale", Vector3.ONE * 0.05, 0.22)

	tween.tween_property(mat, "albedo_color:a", 0.0, 0.24)
	tween.chain().tween_callback(root.queue_free)


func _spawn_impact_mark(pos: Vector3, normal: Vector3, surface: SurfaceMaterialType.Type) -> void:
	var mark := MeshInstance3D.new()
	var quad := QuadMesh.new()
	quad.size = Vector2(0.085, 0.085)
	mark.mesh = quad
	mark.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF

	var mat := StandardMaterial3D.new()
	mat.albedo_color = _get_surface_mark_color(surface)
	mat.roughness = 0.9
	mark.material_override = mat

	add_child(mark)
	mark.global_position = pos + normal * 0.008
	var up := Vector3.UP if absf(normal.dot(Vector3.UP)) < 0.98 else Vector3.RIGHT
	mark.look_at(pos + normal * 2.0, up)

	_decals.append(mark)
	while _decals.size() > MAX_ACTIVE_DECALS:
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
		SurfaceMaterialType.Type.FLESH:
			return # Hitmarker audio handles target hits cleanly

	var audio := AudioStreamPlayer3D.new()
	audio.stream = ProceduralAudio.get_sound(sound_id)
	audio.volume_db = -8.0
	audio.max_distance = 40.0
	add_child(audio)
	audio.global_position = pos
	audio.finished.connect(audio.queue_free)
	audio.play()


func _get_surface_spark_color(surface: SurfaceMaterialType.Type, is_crit: bool) -> Color:
	if is_crit:
		return Color(1.0, 0.25, 0.2, 1.0)
	match surface:
		SurfaceMaterialType.Type.METAL:
			return Color(1.0, 0.85, 0.35, 1.0)
		SurfaceMaterialType.Type.WOOD:
			return Color(0.76, 0.56, 0.32, 1.0)
		SurfaceMaterialType.Type.FLESH:
			return Color(0.95, 0.42, 0.22, 1.0)
		_:
			return Color(0.82, 0.82, 0.80, 1.0)


func _get_surface_mark_color(surface: SurfaceMaterialType.Type) -> Color:
	match surface:
		SurfaceMaterialType.Type.METAL:
			return Color(0.16, 0.18, 0.22)
		SurfaceMaterialType.Type.WOOD:
			return Color(0.24, 0.16, 0.10)
		_:
			return Color(0.12, 0.12, 0.13)
