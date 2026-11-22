# Extending the FPS Framework

This guide documents how to reuse and extend `01-Advanced-FPS` in another Godot 4.7+ project.

---

## 1. Adding a New Weapon

1. Create a new `WeaponData` resource (`.tres`) in `data/weapons/` (or duplicate `ar_m4_carbine.tres`).
2. Configure identity, ballistics (`base_damage`, `pellets_per_shot`, `fire_rate_rpm`, `supported_fire_modes`, `effective_range`, `max_falloff_range`), ammunition (`reload_type`: `MAGAZINE` or `SHELL_BY_SHELL`), recoil, spread, and ADS parameters.
3. Add the `.tres` to `WeaponManager.starting_weapons` in `fps_player.tscn` (or append a `WeaponInstance.new(your_data)` at runtime).

No weapon script duplication is required unless the weapon introduces a fundamentally new mechanic.

---

## 2. Adding a New Attachment

1. Create a new `AttachmentData` resource (`.tres`) in `data/attachments/`.
2. Assign its `slot` (`OPTIC`, `MUZZLE`, `MAGAZINE`, or `UNDERBARREL`) and desired multiplicative/additive modifiers.
3. Add it to `WeaponManager.available_attachments` or equip it directly via `weapon_manager.equip_attachment(your_attachment)`.

`EffectiveWeaponStats.compute()` recalculates all affected stats immediately, and `WeaponInstance` automatically conserves excess magazine rounds if capacity decreases.

---

## 3. Making Any Object Damageable

1. Add a `HealthComponent` node as a child of your entity and configure `max_health`, `max_armor`, and `armor_absorption_ratio`.
2. Add one or more `HitboxComponent` (`Area3D`) nodes on **Collision Layer 3 (`Hitboxes`)** with collision shapes.
3. Assign each `HitboxComponent.health_component` to your `HealthComponent`, and set `hit_zone` (`BODY`, `HEAD`, `LIMB`) and `damage_multiplier`.
4. Connect to `HealthComponent.damaged` and `HealthComponent.died` for custom reactions.

No weapon code needs to know your entity exists.

---

## 4. Tagging Custom Impact Surfaces

Attach a `SurfaceTag` node as a child of any `StaticBody3D` / `CollisionObject3D` and set `surface_type` (`CONCRETE`, `METAL`, `WOOD`, `FLESH`, `GLASS`). `BallisticSolver` and `ImpactFXManager` automatically adapt impact sparks, marks, and audio.

---

## 5. Reusing the Framework in Another Scene

1. Instance `res://src/player/fps_player.tscn`, `res://src/effects/impact_fx_manager.tscn` (or a `Node3D` with `impact_fx_manager.gd`), and `res://src/ui/fps_hud.tscn` into your level scene.
2. Ensure level geometry uses **Collision Layer 1 (`World`)**.
3. Call in your level's `_ready()`:
   ```gdscript
   player.initialize_combat(fx_manager)
   hud.bind_player(player)
   ```
4. Copy the `[input]` and `[layer_names]` sections from `project.godot` if migrating into a fresh Godot project.
