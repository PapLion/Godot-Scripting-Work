# System Architecture — 01-Advanced-FPS

## Design Philosophy

1. **Data-Driven Configuration:** Weapons (`WeaponData`) and attachments (`AttachmentData`) are Godot `Resource` assets. Pure derived parameters are calculated via `EffectiveWeaponStats.compute(base, attachments)`.
2. **Explicit Multi-Dimensional State:** `WeaponStateMachine` models `ActionState`, `AimState`, and `SprintState` as orthogonal enums with automatic cross-dimension invariants (e.g. entering `RELOADING` or `SPRINTING` always forces `AimState.HIP`).
3. **Decoupled Combat Contracts:** Weapons never reference target classes, and `HealthComponent` / `HitboxComponent` never reference weapons. All ballistic hits pass through `FPSEvents.DamageInfo` and `HitboxComponent.receive_hit(...)`.
4. **Framerate Independence:** Firing intervals, reload timers, recoil recovery (`1 - exp(-k * delta)`), spread bloom decay, and ADS interpolation are all delta-normalized.

---

## Component Boundaries

```
FPSPlayer (CharacterBody3D)
 ├── FPSCameraRig (Node3D)
 │    └── Camera3D
 │         └── WeaponViewmodel (procedural 3D pose, sway, kick, muzzle flash)
 ├── WeaponManager (Node3D)
 │    ├── WeaponStateMachine (Action / Aim / Sprint)
 │    ├── RecoilController (pitch/yaw kick + sustained scaling + recovery)
 │    ├── SpreadController (hip/ADS/crouch/move/air + bloom)
 │    ├── WeaponInstance[] (per-weapon ammo, fire mode, active attachments)
 │    └── BallisticSolver (camera raycast, multi-pellet, falloff, surface tags)
 └── HealthComponent (player vitals)

TargetDummy / Any Damageable Entity
 ├── HealthComponent (HP, armor, absorption ratio, death & reset signals)
 └── HitboxComponent[] (Area3D on Layer 3: HEAD 2.0x / BODY 1.0x / LIMB 0.75x)
```

---

## Physics Layers

| Layer | Name | Used By |
| :--- | :--- | :--- |
| `1` | `World` | Floors, walls, cover, ballistic surface test panels |
| `2` | `Player` | `FPSPlayer` capsule (excluded from own ballistic rays via RID) |
| `3` | `Hitboxes` | `HitboxComponent` `Area3D` nodes |
| `4` | `Interactables` | Reserved for scene triggers/benches |

---

## Signal Flow

- `WeaponManager` emits `weapon_equipped`, `ammo_updated`, `fire_mode_updated`, `shot_fired`, `hit_confirmed`, `reload_started`, `reload_finished`, `state_changed`, `attachments_updated`.
- `FPSHud` subscribes strictly to `WeaponManager` and `HealthComponent` signals — zero polling of internal private fields.
- `HealthComponent` emits `damaged`, `health_changed`, `armor_changed`, `died`, `reset_completed`.
