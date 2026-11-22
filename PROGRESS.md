# Progress Checkpoint — 01-Advanced-FPS

## Status: COMPLETE & READY FOR PORTFOLIO PUBLICATION (v5 — Penetration & Combat VFX Expansion)
- [x] v1: Core Advanced FPS Framework (`feat/advanced-fps-framework` @ `f810be7`)
- [x] v2: Detailed Rigged Weapons — AK-47, SPAS-12, AWP (`feat/realistic-weapon-models` @ `f70f0d2`)
- [x] v3: First-Person Arms & Tactical Gloves Rig + AWP `BOLT_ACTION` Sync (`feat/fp-hands-rig-integration` @ `6ef1521`)
- [x] v4: Final Tactical Mechanics — AK-47 Selector, `V` Shoulder Switch, `Q`/`E` Leaning (`feat/tactical-mechanics` @ `489a144`)
- [x] v5: Surface Penetration & Combat VFX Expansion (`feat/penetration-and-vfx`):
  - Configurable multi-surface bullet penetration (thickness probe, resistance budget, damage retention, entry/exit points, per-weapon penetration power, zero duplicate hits/loops)
  - Centralized `GPUParticles3D` Combat VFX Framework with quality levels (`LOW`/`MEDIUM`/`HIGH`), bounded decal/effect budgets, multi-layered muzzle flashes, muzzle/barrel smoke, surface-dependent entry/exit impacts (Metal, Concrete, Wood, Glass, Drywall), and armor/headshot/kill hit feedback
  - Training range penetration test bay (Thin Wood, Glass, Drywall, Thick Concrete + targets behind cover)
  - `87/87` automated tests passed, `27/27` scripts valid
  - Updated portfolio clips, screenshots, GIF preview, and documentation
