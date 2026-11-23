# 3D Weapon Rigging, Hard-Surface Overhaul & Godot Animation Integration

This document details the **v6 Blender 5.3 hard-surface asset pipeline**, single-root bone hierarchies, bone-skinned modular attachments, smooth Bezier bone-locked first-person hand animations, and Godot 4.7.2 `BoneAttachment3D` / `AnimationPlayer` architecture for `01-Advanced-FPS`.

---

## Asset Organization

| Asset | Editable Blender Source | Exported Game Asset | 512px PBR Maps (Albedo + Roughness + Normal) |
| :--- | :--- | :--- | :--- |
| **Reusable FP Arms Rig** | `assets/hands/source/fps_arms_rig.blend` | `assets/hands/fps_arms.glb` | `assets/weapons/textures/FP_*` |
| **AK-47 + FP Hands** | `assets/weapons/ak47/source/ak47_fp.blend` (+ `ak47.blend`) | `assets/weapons/ak47/ak47_fp.glb` | `assets/weapons/textures/AK_*`, `Att_*`, `FP_*` |
| **SPAS-12 + FP Hands** | `assets/weapons/spas12/source/spas12_fp.blend` (+ `spas12.blend`) | `assets/weapons/spas12/spas12_fp.glb` | `assets/weapons/textures/SPAS_*`, `Att_*`, `FP_*` |
| **AWP + FP Hands** | `assets/weapons/awp/source/awp_fp.blend` (+ `awp.blend`) | `assets/weapons/awp/awp_fp.glb` | `assets/weapons/textures/AWP_*`, `Att_*`, `FP_*` |

Editable `.blend` sources live inside `source/` subfolders with `.gdignore` so Godot imports only optimized `.glb` packages cleanly. Reproducible Blender 5.3 Python generators live in `assets/blender_scripts/` (`weapon_build_utils.py`, `build_ak47.py`, `build_spas12.py`, `build_awp.py`, `fps_arms_rig.py`, and `animate_weapons_with_hands.py`).

---

## Hard-Surface & PBR Material Overhaul (v6)

- **512px Procedural Tileable PBR Maps:** `weapon_build_utils.py` generates seamless Albedo, Roughness, and Tangent-Space Normal PNG maps packed directly into each `.blend` / `.glb` (`metal` horizontal machined brushing, `wood` laminated walnut grain, `polymer` fine micro-stipple, `fabric` tactical cordura/ripstop weave, `skin` subtle micro-pores, and tinted `glass`).
- **Sculpted Hard-Surface Silhouettes (No Boxy Primitives):**
  - **AK-47:** Vaulted arched stamped-steel dust cover with cross-ribs, low-profile MIL-STD Picatinny rail, lofted laminated walnut buttstock + palm-swell handguards + ergonomic pistol grip, and progressive lofted curved 30-round banana magazine.
  - **SPAS-12:** Multi-station vaulted receiver, arched ventilated U-channel barrel heatshield, sculpted oval ribbed pump forend, ergonomic pistol grip, flush skeletal folding stock, and glowing fiber-optic front sight.
  - **AWP:** Rich military olive-drab Accuracy International thumbhole chassis with smooth arched cutout, dark-steel chassis hex fasteners, elevated saddle cheek rest on twin pillars, genuine 8-flute precision free-float barrel, machined 3-port muzzle brake, and variable scope with knurled turrets and mount rings.

---

## Coherent Single-Root Hierarchy & Zero Floating Parts

A core architectural rule of the v6 overhaul is **strict bone ownership** — attachments and weapon markers are NEVER static siblings of `Skeleton3D`:

```text
WeaponViewmodel (Node3D — Godot owns lightweight outer runtime ADS, sway, bob, recoil, shoulder, lean)
 └── RuntimeOffsetPivot (Node3D — clean local identity isolator)
      └── <Imported GLB Scene> (Blender owns all artistic poses, reloads, bolt cycling, shell loading)
           └── Skeleton3D
                ├── Weapon Body / Magazine / Bolt / Pump / FP_Arm_L / FP_Arm_R
                ├── Att_Optic_Holo        (rigidly skinned to `weapon_body` — beveled Holo Reflex + glowing red dot)
                ├── Att_Muzzle_Comp       (rigidly skinned to `weapon_body` — machined multi-port compensator)
                ├── Att_Mag_Ext           (rigidly skinned to `magazine` on AK-47/AWP; tubular mag extension on SPAS-12)
                ├── Att_Underbarrel_Laser (rigidly skinned to `weapon_body` — FDE PEQ laser module + green emitter)
                └── WeaponBodyBoneAttachment (Godot BoneAttachment3D -> `weapon_body`)
                     ├── MuzzlePoint (MuzzleFlashMesh + MuzzleFlashLight)
                     └── EjectPoint  (Shell casing ejection transform)
```

- Because `Att_*` meshes are authored and rigidly skinned directly inside Blender (`weapon_body` / `magazine`), optics, compensators, extended magazines, and lasers stay **100% locked to the animated firearm** across recoil, reloads, ADS, weapon switching, shoulder transitions, and tactical leaning.
- Because `MuzzlePoint` and `EjectPoint` mount via Godot `BoneAttachment3D` bound to `"weapon_body"`, muzzle flashes and ejected brass/12ga shells always emit accurately from the live animated barrel and ejection port.

---

## Reusable First-Person Arms & Bone-Locked Bezier Animation Pipeline

- **Anatomical FP Arms & Gloves Rig:** Muscular tapered forearms, two-tier rolled combat sleeves, coaxial leather Velcro wrist cuffs, sleek olive ripstop tactical gloves, low-profile molded knuckle armor, and 5 articulated fingers per hand (38 clean deform bones + editable Blender IK/pole controls).
- **Mathematically Bone-Locked Hand Tracking:** During Blender baking (`animate_weapons_with_hands.py`), weapon mechanical bones are keyframed and Bezier-smoothed first (`AUTO_CLAMPED` F-curves). Both hands then evaluate the exact rigid-body bone delta matrix (`pb.matrix @ rest.matrix_local.inverted()`) at dense sample intervals so hands stay glued with zero drift to `weapon_body`, `magazine`, `pump`, `charging_handle`, `shell`, and `bolt_handle`, with quaternion sign continuity (`make_compatible`) preventing wrist flips.
- **Camera-Framed Action Choreography (70° FOV):**
  - **AK-47 (`idle`, `ads_idle`, `fire`, `reload`, `reload_empty`, `equip`, `unequip`):** Distinct tactical reload (curved banana mag rock-out & fresh mag seating cleanly centered in frame) vs. empty reload (mag swap + rifle roll left + underhand chrome charging-handle rack). `selector` bone is left unkeyframed so Godot's `Skeleton3D` rotates the physical selector lever cleanly between `SAFE`, `SEMI`, and `AUTO`.
  - **SPAS-12 (`idle`, `ads_idle`, `fire`, `shell_start`, `shell_insert`, `shell_end`, `reload_interrupt`, `equip`, `unequip`):** Genuine semi-auto `fire` (chrome bolt reciprocates without contradictory pumping). Shell-by-shell loading elevates and rolls the shotgun cleanly into upper-center frame so the gloved left hand visibly pushes bright red/brass 12-gauge shells into the chrome loading gate, finishing with a left-hand pump rack on `shell_end` (or instant snap-to-ready on `reload_interrupt`).
  - **AWP (`idle`, `ads_idle`, `fire`, `bolt_action`, `reload`, `reload_empty`, `equip`, `unequip`):** Firing enters `CYCLING_BOLT` (`0.82s`), exits full scope zoom, and elevates/cants the rifle above the HUD so the gloved right hand visibly lifts the spherical bolt knob 68°, pulls the fluted steel bolt back 9.2cm (synchronized with mid-pull `.338` brass casing ejection in `WeaponManager`), drives it forward, and locks it down before allowing the next shot.

---

## Godot State Synchronization (`WeaponManager` ↔ `WeaponViewmodel`)

- **Blender-First Ownership:** Godot no longer runs procedural reload dips or procedural equip drops on rigged weapons. `WeaponViewmodel` applies only lightweight outer runtime transforms (ADS lerp, smooth shoulder-side arc, subtle sway/bob damped during actions, compact recoil kickback, and tactical lean stabilization roll) while `AnimationPlayer` drives all authored mechanical and hand motion.
- **Automatic `idle` ↔ `ads_idle` Crossfade:** When aiming down sights (`ads_alpha >= 0.65`), `WeaponViewmodel` crossfades cleanly into the stabilized `ads_idle` cheek-weld pose.
- **Tactical vs. Empty Magazine Reload Selection:** `play_reload_magazine(duration, is_empty)` selects `reload_empty` when reloading from zero rounds and `reload` for tactical reloads, scaling playback speed cleanly to match `EffectiveWeaponStats` durations (including Extended Mag modifiers).
- **AWP Scope ADS:** At full scope-in (`ads_alpha >= 0.78`), `WeaponViewmodel` hides the 3D sniper mesh while `FPSHud` renders the tactical Mil-Dot scope overlay, automatically re-showing the 3D viewmodel during `CYCLING_BOLT`, reload, and switching.
