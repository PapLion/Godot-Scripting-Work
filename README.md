# Godot Systems Lab — 01: Advanced FPS Framework

A modular, reusable, commission-grade **First-Person Shooter Gameplay Framework** built in **Godot 4.7.2 (GDScript)**.

> **The scripting is the product.** Every weapon model, first-person arm rig, animation, synthesized audio cue, and range target exists to demonstrate and verify the underlying commission-grade Godot 4 gameplay architecture.

---

## Overview

This project is a standalone, single-player FPS gameplay architecture designed so a client or team can drop its weapon, ballistics, recoil, spread, ADS, reload, damage/hitbox, and attachment modules directly into another Godot 4 project without rewriting core logic.

### Implemented Systems

| System | Key Scripts | Capabilities |
| :--- | :--- | :--- |
| **Data-Driven Weapons** | `WeaponData`, `WeaponInstance`, `EffectiveWeaponStats` | Resource-driven weapon definitions, pure stat composition, safe ammo conservation, `AUTO`/`SEMI`/`SAFE`/`BOLT` fire modes |
| **Multi-Dimensional State Machine** | `WeaponStateMachine` | Orthogonal `ActionState` (incl. `CYCLING_BOLT`), `AimState`, and `SprintState` dimensions — zero contradictory booleans |
| **Tactical Mechanics** | `FPSCameraRig`, `WeaponManager`, `WeaponViewmodel` | AK-47 `SAFE`/`SEMI`/`AUTO` selector (`B`, animated `selector` bone), smooth Right/Left shoulder switching (`V`), collision-aware `Q`/`E` corner peeking |
| **Gunplay & Ballistics** | `BallisticSolver`, `RecoilController`, `SpreadController` | Camera-based hitscan & multi-pellet shotgun solver, distance falloff, **configurable multi-surface penetration** (thickness + resistance budget + damage retention + entry/exit points), real camera recoil + recovery, stance/movement/bloom spread |
| **Combat VFX Framework** | `ImpactFXManager`, `WeaponViewmodel`, `ShellCasing` | Centralized quality-scalable (`LOW`/`MEDIUM`/`HIGH`) `GPUParticles3D` + decal framework: multi-layered star muzzle flashes, muzzle/barrel smoke, surface-dependent entry/exit impacts (Metal sparks, Concrete dust/debris, Wood splinters, Glass shards, Drywall plaster), armor/headshot/kill bursts, strict bounded budgets |
| **Reload Mechanics** | `WeaponManager` | Tactical (+1 chamber) & empty magazine reloads, shell-by-shell shotgun loading with immediate fire-interrupt, safe switch cancellation |
| **Attachments & Modifiers** | `AttachmentData`, `EffectiveWeaponStats`, `WeaponViewmodel` | 4 slots (Optic, Muzzle, Magazine, Underbarrel) with live stat recalculation, ammo conservation, and **bone-skinned Blender hard-surface attachment meshes** (`Att_*`) that never detach or float during animations |
| **Decoupled Damage & Hitboxes** | `HealthComponent`, `HitboxComponent`, `TargetDummy` | Head/Body/Limb hit zones with configurable multipliers, armor absorption & drain, death/reset signals, static/armored/moving targets |
| **FPS Controller & Camera Rig** | `FPSPlayer`, `FPSCameraRig` | Walk, sprint, jump, smooth crouch with ceiling raycast check, ADS sensitivity scaling, FOV interpolation, landing impulse |
| **Viewmodels, Feedback & Audio** | `WeaponViewmodel`, `ImpactFXManager`, `ProceduralAudio`, `FPSHud` | Sculpted hard-surface Blender 5.3 weapons (512px PBR Albedo+Roughness+Normal), anatomical gloved FP arms, bone-locked Bezier animations (`idle`, `ads_idle`, `reload`, `reload_empty`, `shell_*`, `bolt_action`), `BoneAttachment3D` muzzle/eject points, synthesized WAV audio, dynamic crosshair & hitmarkers |

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
| `B` | Cycle Fire Selector (`AUTO` / `SEMI` / `SAFE` on AK-47) |
| `V` | Switch Dominant Weapon Shoulder (`[R]` ↔ `[L]`) |
| `Q` / `E` | Collision-Aware Tactical Lean & Corner Peek (Left / Right) |
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

### Run Automated Deterministic Test Suite (106 Assertions)
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
- **Automated Suite (`tests/run_tests.gd`):** **106/106 passed (0 errors, 0 leaks)**, covering resource loading, distance falloff, attachment stat composition & ammo conservation, state-machine invariants, framerate-independent recoil/spread recovery (60 vs 120 FPS), armor/hitbox multipliers, tactical/empty/shell-by-shell reloads, fire-interrupt, weapon switching, scene instantiation, rigged GLB weapon+hand animations (`idle`, `ads_idle`, `fire`, `reload`, `reload_empty`, `shell_*`, `bolt_action`, `equip`, `unequip`), `BoneAttachment3D` dynamic muzzle/eject transform inheritance, bone-skinned `Skeleton3D` modular attachment visibility & hierarchy, AWP `BOLT_ACTION` / `CYCLING_BOLT` readiness enforcement, AK-47 `SAFE`/`SEMI`/`AUTO` fire selector, smooth Right/Left shoulder switching, collision-aware `Q`/`E` tactical leaning, multi-surface bullet penetration (wood/glass/drywall vs thick concrete/metal), and bounded VFX lifecycle budgets.
- **Live Engine Verification (Godot MCP `run_project` + `game_eval` + `game_screenshot`):** Verified zero runtime errors under Vulkan Forward+, real raycast headshots (`2.0x`), armor absorption (`50%` split), multi-pellet shotgun hits, high-zoom precision ADS, and live attachment toggling.

---

## Known Limitations & Intentional Exclusions

- **Single-player only:** No multiplayer replication, authoritative server reconciliation, or lag compensation (intentionally out of scope).
- **Hitscan ballistics:** Uses camera-based hitscan raycasting with effective range & falloff; physical projectile drop/travel time is intentionally excluded unless required by a specific game design.
- **Focused environment art:** The training range and targets use clean color-coded blocks and synthesized procedural audio so visual attention stays on the hard-surface weapons, first-person animations, and gameplay systems.
- **No AI/parkour/inventory systems:** Advanced movement (wallrunning/vaulting) and enemy AI are reserved for separate Godot Systems Lab modules.
