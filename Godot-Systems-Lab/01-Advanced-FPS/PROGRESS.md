# Progress Checkpoint — 01-Advanced-FPS

## Status: COMPLETE & READY FOR PORTFOLIO PUBLICATION (v6 — Complete Blender Viewmodel & Animation Overhaul)
- [x] v1: Core Advanced FPS Framework (`feat/advanced-fps-framework` @ `f810be7`)
- [x] v2: Detailed Rigged Weapons — AK-47, SPAS-12, AWP (`feat/realistic-weapon-models` @ `f70f0d2`)
- [x] v3: First-Person Arms & Tactical Gloves Rig + AWP `BOLT_ACTION` Sync (`feat/fp-hands-rig-integration` @ `6ef1521`)
- [x] v4: Final Tactical Mechanics — AK-47 Selector, `V` Shoulder Switch, `Q`/`E` Leaning (`feat/tactical-mechanics` @ `489a144`)
- [x] v5: Surface Penetration & Combat VFX Expansion (`feat/penetration-and-vfx` @ `dac8a9a`)
- [x] v6: Complete Blender Viewmodel & Animation Overhaul (`feat/viewmodel-animation-overhaul`):
  - Rebuilt AK-47, SPAS-12, and AWP with sculpted hard-surface silhouettes (vaulted arched receivers, palm-swell walnut furniture, arched thumbhole OD AWP chassis with hex bolts, 8-flute barrel, machined brakes, 512px tileable Albedo+Roughness+Normal PBR maps)
  - Eliminated disconnected/floating attachments & markers permanently by skinning detailed modular hard-surface attachments (`Att_Optic_Holo`, `Att_Muzzle_Comp`, `Att_Mag_Ext`, `Att_Underbarrel_Laser`) directly to `weapon_body` / `magazine` bones in Blender and mounting `MuzzlePoint` / `EjectPoint` via Godot `BoneAttachment3D`
  - Upgraded anatomical FP arms & tactical gloves rig and authored smooth `AUTO_CLAMPED` Bezier, mathematically bone-locked, 70° camera-framed weapon+hand animations (`idle`, `ads_idle`, `fire`, `reload`, `reload_empty`, `shell_start/insert/end`, `reload_interrupt`, `bolt_action`, `equip`, `unequip`)
  - Refactored `WeaponViewmodel` to clean Blender-first animation ownership (removing competing GDScript procedural reload/equip routines and crude `BoxMesh` attachments) + synchronized AWP mid-bolt-pull brass shell ejection in `WeaponManager`
  - `106/106` automated tests passed (0 errors, 0 leaks), `27/27` GDScript files valid
  - Re-recorded and visually inspected updated studio renders, rig previews, live Godot screenshots, and 10 gameplay MP4 clips (with v5 media preserved in `portfolio_media/v5_penetration_vfx/`)
