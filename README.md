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

All weapons are authored as reusable `.tres` resources under `data/weapons/`:

1. **`ar_m4_carbine.tres` — AR-47 Tactical (Assault Rifle)**
   - Fire modes: `AUTO` / `SEMI` (`700 RPM`), `28` base damage, `30`-round magazine (`+1` tactical chamber)
   - Moderate recoil accumulation, tight ADS spread, `56°` ADS FOV, tactical (`1.55s`) & empty (`2.05s`) reload
2. **`sg_m870_tactical.tres` — SG-870 Breacher (Shotgun)**
   - Fire mode: `SEMI` (`72 RPM`), `8` pellets × `18` damage, `6`-shell tube
   - **Shell-by-shell reload** (`start → insert → end`) with **instant fire interruption**, wide pellet cone, steep `14m–38m` falloff
3. **`sr_mk14_precision.tres` — SR-14 Marksman (Precision Rifle)**
   - Fire mode: `SEMI` (`85 RPM`), `85` base damage (`170` headshot), `10`-round magazine
   - High vertical recoil kick, `34°` high-zoom ADS FOV, `0.06°` ADS spread, `85m` effective range

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
- [Extending the Framework (Add Weapons, Targets, Attachments, Scenes)](docs/EXTENDING.md)
- [Portfolio Description (danipp.tech)](docs/PORTFOLIO_BLURB.md)

---

## Testing & Verification Summary

- **Static Validation (`validate_scripts`):** 24/24 GDScript files valid, 0 errors.
- **Automated Suite (`tests/run_tests.gd`):** **48/48 passed**, covering resource loading, distance falloff, attachment stat composition & ammo conservation, state-machine invariants, framerate-independent recoil/spread recovery (60 vs 120 FPS), armor/hitbox multipliers, tactical/empty/shell-by-shell reloads, fire-interrupt, weapon switching, and scene instantiation.
- **Live Engine Verification (Godot MCP `run_project` + `game_eval` + `game_screenshot`):** Verified zero runtime errors under Vulkan Forward+, real raycast headshots (`2.0x`), armor absorption (`50%` split), multi-pellet shotgun hits, high-zoom precision ADS, and live attachment toggling.

---

## Known Limitations & Intentional Exclusions

- **Single-player only:** No multiplayer replication, authoritative server reconciliation, or lag compensation (intentionally out of scope).
- **Hitscan ballistics:** Uses camera-based hitscan raycasting with effective range & falloff; physical projectile drop/travel time is intentionally excluded unless required by a specific game design.
- **Minimal visual assets:** Viewmodels, targets, and range geometry use clean primitives and synthesized procedural audio to keep focus on gameplay engineering.
- **No AI/parkour/inventory systems:** Advanced movement (wallrunning/vaulting) and enemy AI are reserved for separate Godot Systems Lab modules.
