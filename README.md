# Godot Systems Lab — 01: Advanced FPS Framework

A modular, reusable, commission-grade **First-Person Shooter Gameplay Framework** built in **Godot 4.7.2 (GDScript)**.

> **The scripting is the product.** Everything else — geometric viewmodels, synthesized audio, and the minimal firing range — exists to verify and demonstrate the underlying gameplay systems.

---

## Overview

This project is a standalone, single-player FPS gameplay architecture designed so a client or team can drop its weapon, ballistics, recoil, spread, ADS, reload, damage/hitbox, and attachment modules directly into another Godot 4 project without rewriting core logic.

### Implemented Systems

| System | Key Scripts | Capabilities |
| :--- | :--- | :--- |
| **Data-Driven Weapons** | `WeaponData`, `WeaponInstance`, `EffectiveWeaponStats` | Resource-driven weapon definitions, pure stat composition, safe ammo conservation |
| **Multi-Dimensional State Machine** | `WeaponStateMachine` | Orthogonal `ActionState`, `AimState`, and `SprintState` dimensions — zero contradictory booleans |
| **Gunplay & Ballistics** | `BallisticSolver`, `RecoilController`, `SpreadController` | Camera-based hitscan & multi-pellet shotgun solver, distance falloff, real camera recoil + recovery, stance/movement/bloom spread |
| **Reload Mechanics** | `WeaponManager` | Tactical (+1 chamber) & empty magazine reloads, shell-by-shell shotgun loading with immediate fire-interrupt, safe switch cancellation |
| **Attachments & Modifiers** | `AttachmentData`, `EffectiveWeaponStats` | 4 slots (Optic, Muzzle, Magazine, Underbarrel) with live stat recalculation, ammo conservation, and visual viewmodel indicators |
| **Decoupled Damage & Hitboxes** | `HealthComponent`, `HitboxComponent`, `TargetDummy` | Head/Body/Limb hit zones with configurable multipliers, armor absorption & drain, death/reset signals, static/armored/moving targets |
| **FPS Controller & Camera Rig** | `FPSPlayer`, `FPSCameraRig` | Walk, sprint, jump, smooth crouch with ceiling raycast check, ADS sensitivity scaling, FOV interpolation, landing impulse |
| **Feedback, Audio & Range** | `WeaponViewmodel`, `ImpactFXManager`, `ProceduralAudio`, `FPSHud` | Procedural 3D viewmodels, muzzle flash, tracers, shell casings, surface-dependent impacts (Concrete/Metal/Wood/Flesh), synthesized WAV audio, dynamic spread crosshair & hitmarkers |

---

## Engine & Environment

- **Engine:** Godot `4.7.2.stable` (Forward+)
- **Language:** Typed GDScript
- **Scope:** Single-player FPS gameplay framework (no multiplayer/netcode, campaign, or inventory UI)

---

## Included Weapon Configurations

All weapons are authored as reusable `.tres` resources under `data/weapons/`, backed by rigged, PBR-textured, animated `.glb` models built in **Blender 5.3** (`assets/weapons/`):

1. **`ar_m4_carbine.tres` — AK-47 (Assault Rifle)**
   - Fire modes: `AUTO` / `SEMI` (`700 RPM`), `28` base damage, `30`-round magazine (`+1` tactical chamber)
   - Synchronized first-person gloved hands + rigged curved steel magazine, reciprocating charging handle, fire selector, mag release, and trigger (`ak47_fp.glb`)
2. **`sg_m870_tactical.tres` — SPAS-12 (Shotgun)**
   - Fire mode: `SEMI` (`72 RPM`), `8` pellets × `18` damage, `6`-shell tube
   - Synchronized first-person hands + ribbed forend, ventilated heatshield, folding stock, chrome bolt, loading gate, and animated left-hand 12ga shell loading & reload interruption (`spas12_fp.glb`)
3. **`sr_mk14_precision.tres` — AWP (Precision Rifle)**
   - Fire mode: `BOLT_ACTION` (`[BOLT]`, `0.82s` bolt cycle), `85` base damage (`170` headshot), `10`-round magazine
   - Synchronized first-person hands + olive-drab thumbhole chassis, right-hand 4-stage bolt-action cycling (`CYCLING_BOLT` blocks firing until cycle completes), box magazine reload, variable scope + tactical Mil-Dot ADS overlay, and folding bipod (`awp_fp.glb`)

### Included Attachments (`data/attachments/`)

- **`optic_holo_sight.tres` (`[5]`)** — Holo Reflex: `-8°` ADS FOV, `+25%` ADS speed, `-20%` ADS spread
- **`muzzle_compensator.tres` (`[6]`)** — Compensator: `-32%` vertical recoil, `-25%` horizontal recoil, `+8%` effective range
- **`mag_extended.tres` (`[7]`)** — Extended Mag: `+40%` magazine capacity, `+15%` reload duration (safely returns overflow rounds to reserve on unequip)
- **`underbarrel_laser.tres` (`[8]`)** — Tactical Laser: `-35%` hipfire spread, `-25%` movement spread penalty

---

## Controls (Training Range)

| Input | Action |
| :--- | :--- |
| `W / A / S / D` | Move |
| `Shift` | Sprint |
| `Ctrl` / `C` | Crouch (with ceiling check) |
| `Space` | Jump |
| `Left Click` | Fire (interrupts shotgun shell reload) |
| `Right Click` | Aim Down Sights (ADS) |
| `R` | Reload |
| `B` | Cycle Fire Mode (`AUTO` / `SEMI`) |
| `1 / 2 / 3` or `Mouse Wheel` | Switch Weapon |
| `5 / 6 / 7 / 8` | Toggle Optic / Muzzle / Extended Mag / Tactical Laser |
| `T` | Reset All Range Targets & Refill Ammo |
| `F3` | Toggle Live Framework Telemetry Panel |
| `Esc` | Release / Recapture Mouse Cursor |

---

## Running the Project & Tests

### Play the Training Range
Open `project.godot` in Godot 4.7.2 and press **F5** (main scene: `res://src/showcase/training_range.tscn`), or run from CLI:

```powershell
Godot_v4.7.2-stable_win64_console.exe --path .
```

### Run Automated Deterministic Test Suite (48 Assertions)
```powershell
Godot_v4.7.2-stable_win64_console.exe --headless --path . --script res://tests/run_tests.gd
```

---

## Documentation Index

- [Architecture & System Boundaries](docs/ARCHITECTURE.md)
- [3D Weapon Rigging & Godot Animation Integration](docs/RIGGING_AND_ANIMATION.md)
- [Extending the Framework (Add Weapons, Targets, Attachments, Scenes)](docs/EXTENDING.md)
- [Portfolio Description (danipp.tech)](docs/PORTFOLIO_BLURB.md)

---

## Testing & Verification Summary

- **Static Validation (`validate_scripts`):** 27/27 GDScript files valid, 0 errors.
- **Automated Suite (`tests/run_tests.gd`):** **62/62 passed**, covering resource loading, distance falloff, attachment stat composition & ammo conservation, state-machine invariants, framerate-independent recoil/spread recovery (60 vs 120 FPS), armor/hitbox multipliers, tactical/empty/shell-by-shell reloads, fire-interrupt, weapon switching, scene instantiation, rigged GLB weapon+hand animations, configurable hand attachment markers, and AWP `BOLT_ACTION` / `CYCLING_BOLT` readiness enforcement.
- **Live Engine Verification (Godot MCP `run_project` + `game_eval` + `game_screenshot`):** Verified zero runtime errors under Vulkan Forward+, real raycast headshots (`2.0x`), armor absorption (`50%` split), multi-pellet shotgun hits, high-zoom precision ADS, and live attachment toggling.

---

## Known Limitations & Intentional Exclusions

- **Single-player only:** No multiplayer replication, authoritative server reconciliation, or lag compensation (intentionally out of scope).
- **Hitscan ballistics:** Uses camera-based hitscan raycasting with effective range & falloff; physical projectile drop/travel time is intentionally excluded unless required by a specific game design.
- **Minimal visual assets:** Viewmodels, targets, and range geometry use clean primitives and synthesized procedural audio to keep focus on gameplay engineering.
- **No AI/parkour/inventory systems:** Advanced movement (wallrunning/vaulting) and enemy AI are reserved for separate Godot Systems Lab modules.
