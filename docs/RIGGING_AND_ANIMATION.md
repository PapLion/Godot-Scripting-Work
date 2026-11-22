# 3D Weapon Rigging & Godot Animation Integration

This document details the Blender 5.3 asset pipeline, bone hierarchies, exported animation clips, and Godot 4.7.2 `AnimationPlayer` synchronization for the three rigged weapons integrated into `01-Advanced-FPS`.

---

## Asset Organization

| Weapon | Editable Blender Source | Exported Game Asset | PBR Textures |
| :--- | :--- | :--- | :--- |
| **AK-47** | `assets/weapons/ak47/source/ak47.blend` | `assets/weapons/ak47/ak47.glb` | `assets/weapons/textures/AK_*` |
| **SPAS-12** | `assets/weapons/spas12/source/spas12.blend` | `assets/weapons/spas12/spas12.glb` | `assets/weapons/textures/SPAS_*` |
| **AWP** | `assets/weapons/awp/source/awp.blend` | `assets/weapons/awp/awp.glb` | `assets/weapons/textures/AWP_*` |

Editable `.blend` sources are kept in `source/` subfolders with `.gdignore` so Godot imports only the optimized `.glb` packages cleanly. Reproducible Blender Python generator scripts live in `assets/blender_scripts/`.

---

## Coordinate & Rigid Rigging Standards

- **Orientation:** Modeled pointing along `+Y` in Blender → exported via glTF 2.0 (`export_yup=True`) to `-Z` forward in Godot 4.
- **Zero Unwanted Deformation:** Every moving mechanical component is bound to its bone via a **single-bone rigid vertex group (weight `1.0`)** and `Armature` modifier.
- **Import Markers:** Each rig includes `Empty` markers (`MuzzlePoint`, `EjectPoint`, `OpticMount`, `MuzzleMount`, `MagMount`, `LaserMount`) read automatically by `WeaponViewmodel` on weapon equip.

---

## Bone Hierarchies & Exported Animations

### 1. AK-47 (`AK47_Rig`)
```
weapon_root
 └── weapon_body          (receiver, dust cover, wood stock/handguards/grip, barrel, sights)
      ├── magazine        (curved 30-round steel magazine)
      ├── charging_handle (bolt carrier + right-side hooked handle)
      ├── trigger         (curved trigger)
      ├── selector        (right-side fire selector lever)
      └── mag_release     (paddle magazine latch)
```
**Animations:** `idle`, `fire`, `reload`, `reload_mag_out`, `reload_mag_in`, `equip`, `unequip`.

### 2. SPAS-12 (`SPAS12_Rig`)
```
weapon_root
 └── weapon_body          (curved receiver, barrel, mag tube, ventilated heatshield, pistol grip)
      ├── pump            (ribbed SPAS-12 forend + dual action bars)
      ├── bolt            (chrome reciprocating bolt)
      ├── loading_gate    (bottom shell lifter/gate)
      ├── shell           (12-gauge red/brass shell animated into loading port)
      ├── trigger         (curved trigger)
      └── stock           (folding skeletal metal stock)
```
**Animations:** `idle`, `fire`, `shell_start`, `shell_insert`, `shell_end`, `reload_interrupt`, `equip`, `unequip`.

### 3. AWP (`AWP_Rig`)
```
weapon_root
 └── weapon_body          (olive-drab thumbhole chassis, rubber buttpad, receiver, heavy barrel, brake)
      ├── bolt            (steel bolt body)
      │    └── bolt_handle (angled bolt handle + spherical knob for 4-stage lift/pull/push/lock)
      ├── magazine        (detachable 10-round steel box magazine)
      ├── trigger         (match trigger)
      ├── scope           (variable optic + dual rings + tinted lenses)
      └── bipod           (folding tactical bipod)
```
**Animations:** `idle`, `fire` (includes 4-stage bolt cycling), `bolt` (standalone bolt cycle), `reload`, `reload_mag_out`, `reload_mag_in`, `equip`, `unequip`.

---

## Godot State Synchronization (`WeaponManager` ↔ `WeaponViewmodel`)

`WeaponManager` drives `WeaponViewmodel` directly from `WeaponStateMachine` transitions:
- **Fire:** `trigger_fire_kick()` → `play_fire()` (synchronizes AK bolt carrier, SPAS-12 pump/bolt, and AWP 4-stage bolt cycling).
- **Magazine Reload:** `request_reload()` → `play_reload_magazine(duration)` scales playback speed to match `tactical_reload_duration` or `empty_reload_duration` (including Extended Mag modifiers).
- **Shell-by-Shell Reload (SPAS-12):** `STARTING` → `play_shell_start()`, each `INSERTING` loop → `play_shell_insert()`, `ENDING` → `play_shell_end()`.
- **Reload Interruption / Weapon Switch:** `_cancel_reload()` calls `play_reload_interrupt()`, snapping detached magazines/shells back to rest pose before `play_unequip()` or immediate firing.
- **AWP Scope ADS:** At full ADS (`ads_alpha >= 0.78`), `WeaponViewmodel` hides the 3D sniper mesh while `FPSHud` renders a crisp tactical Mil-Dot scope overlay.
