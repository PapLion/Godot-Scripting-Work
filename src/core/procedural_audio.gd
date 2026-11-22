class_name ProceduralAudio
extends RefCounted
## Deterministic procedural AudioStreamWAV generator for FPS sound effects.
## Eliminates external licensing dependencies while providing crisp, distinct audio feedback.

const SAMPLE_RATE := 22050

static var _cache: Dictionary = {}


static func clear_cache() -> void:
	_cache.clear()


static func get_sound(sound_id: StringName) -> AudioStreamWAV:
	if _cache.has(sound_id):
		return _cache[sound_id] as AudioStreamWAV

	var stream: AudioStreamWAV
	match sound_id:
		&"shot_ar":
			stream = _synth_gunshot(0.16, 175.0, 55.0, 0.72, 18.0, 101)
		&"shot_shotgun":
			stream = _synth_gunshot(0.28, 120.0, 34.0, 0.92, 11.0, 202)
		&"shot_precision":
			stream = _synth_gunshot(0.24, 240.0, 48.0, 0.85, 13.0, 303)
		&"dry_fire":
			stream = _synth_click(0.035, 1450.0, 0.45)
		&"reload_mag_out":
			stream = _synth_click(0.08, 620.0, 0.5)
		&"reload_mag_in":
			stream = _synth_click(0.09, 980.0, 0.58)
		&"reload_shell":
			stream = _synth_click(0.075, 1180.0, 0.52)
		&"equip":
			stream = _synth_click(0.06, 520.0, 0.35)
		&"fire_mode":
			stream = _synth_click(0.03, 1800.0, 0.35)
		&"hit_body":
			stream = _synth_tone_burst(0.055, 1250.0, 900.0, 0.48)
		&"hit_head":
			stream = _synth_tone_burst(0.095, 2200.0, 1650.0, 0.65)
		&"hit_kill":
			stream = _synth_double_chime(0.14, 1400.0, 2100.0, 0.6)
		&"impact_concrete":
			stream = _synth_gunshot(0.07, 130.0, 60.0, 0.38, 34.0, 404)
		&"impact_metal":
			stream = _synth_tone_burst(0.11, 2600.0, 1950.0, 0.45)
		&"impact_wood":
			stream = _synth_gunshot(0.065, 220.0, 95.0, 0.35, 36.0, 505)
		&"footstep":
			stream = _synth_gunshot(0.05, 95.0, 45.0, 0.22, 42.0, 606)
		_:
			stream = _synth_click(0.04, 1000.0, 0.35)

	_cache[sound_id] = stream
	return stream


static func _build_wav(samples: PackedFloat32Array) -> AudioStreamWAV:
	var pcm := PackedByteArray()
	pcm.resize(samples.size() * 2)
	for i in samples.size():
		var clamped := clampf(samples[i], -1.0, 1.0)
		var s16 := int(round(clamped * 32767.0))
		pcm[i * 2] = s16 & 0xFF
		pcm[i * 2 + 1] = (s16 >> 8) & 0xFF

	var wav := AudioStreamWAV.new()
	wav.format = AudioStreamWAV.FORMAT_16_BITS
	wav.mix_rate = SAMPLE_RATE
	wav.stereo = false
	wav.data = pcm
	return wav


static func _synth_gunshot(
	duration: float,
	start_freq: float,
	end_freq: float,
	noise_mix: float,
	decay: float,
	seed_val: int
) -> AudioStreamWAV:
	var count := int(SAMPLE_RATE * duration)
	var samples := PackedFloat32Array()
	samples.resize(count)

	var rng := RandomNumberGenerator.new()
	rng.seed = seed_val
	var phase := 0.0
	var lp := 0.0

	for i in count:
		var t := float(i) / float(SAMPLE_RATE)
		var norm := t / duration
		var env := exp(-decay * t)
		var attack := minf(1.0, t / 0.0025)
		var freq := lerpf(start_freq, end_freq, minf(1.0, norm * 2.4))
		phase += TAU * freq / float(SAMPLE_RATE)
		var body := sin(phase) * exp(-decay * 0.7 * t)
		var raw_noise := rng.randf_range(-1.0, 1.0)
		lp = lerpf(lp, raw_noise, 0.45)
		var crack := raw_noise * exp(-decay * 2.2 * t)
		var sample := ((1.0 - noise_mix) * body + noise_mix * (lp * 0.65 + crack * 0.65)) * env * attack
		samples[i] = clampf(sample * 1.45, -1.0, 1.0)

	return _build_wav(samples)


static func _synth_click(duration: float, freq: float, gain: float) -> AudioStreamWAV:
	var count := int(SAMPLE_RATE * duration)
	var samples := PackedFloat32Array()
	samples.resize(count)
	var rng := RandomNumberGenerator.new()
	rng.seed = int(freq)
	for i in count:
		var t := float(i) / float(SAMPLE_RATE)
		var env := exp(-48.0 * t)
		var tone := sin(TAU * freq * t) * 0.7 + rng.randf_range(-0.3, 0.3)
		samples[i] = tone * env * gain
	return _build_wav(samples)


static func _synth_tone_burst(duration: float, f0: float, f1: float, gain: float) -> AudioStreamWAV:
	var count := int(SAMPLE_RATE * duration)
	var samples := PackedFloat32Array()
	samples.resize(count)
	var phase := 0.0
	for i in count:
		var t := float(i) / float(SAMPLE_RATE)
		var norm := t / duration
		var freq := lerpf(f0, f1, norm)
		phase += TAU * freq / float(SAMPLE_RATE)
		var env := exp(-22.0 * t) * minf(1.0, t / 0.002)
		samples[i] = (sin(phase) * 0.75 + sin(phase * 2.0) * 0.25) * env * gain
	return _build_wav(samples)


static func _synth_double_chime(duration: float, f0: float, f1: float, gain: float) -> AudioStreamWAV:
	var count := int(SAMPLE_RATE * duration)
	var samples := PackedFloat32Array()
	samples.resize(count)
	var split := duration * 0.42
	for i in count:
		var t := float(i) / float(SAMPLE_RATE)
		var f := f0 if t < split else f1
		var local_t := t if t < split else (t - split)
		var env := exp(-24.0 * local_t) * minf(1.0, local_t / 0.002)
		samples[i] = sin(TAU * f * local_t) * env * gain
	return _build_wav(samples)
