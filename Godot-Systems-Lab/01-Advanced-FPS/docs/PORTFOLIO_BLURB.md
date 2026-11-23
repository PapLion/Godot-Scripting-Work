# Portfolio Description — Advanced FPS Framework (Godot 4.7)

**Title:** Advanced FPS Gameplay Framework (Godot 4 / GDScript)

**Short Summary (for danipp.tech):**
A modular, commission-grade First-Person Shooter gameplay framework engineered in Godot 4.7.2 and typed GDScript. Built as a reusable foundation rather than a one-off game, the framework separates data-driven weapon configuration (`WeaponData`, `AttachmentData`, `EffectiveWeaponStats`) from an explicit multi-dimensional weapon state machine (`Action`, `Aim`, and `Sprint` states). It implements camera-based hitscan and multi-pellet shotgun ballistics with distance damage falloff, framerate-independent recoil and spread models, smooth ADS transitions, tactical and interruptible shell-by-shell reloading, live attachment modifiers with ammo conservation, and a decoupled hitbox/armor damage architecture—verified through 48 automated engine assertions and live runtime testing in an interactive firing range.

**Key Technical Highlights:**
- Data-driven `WeaponData` & `AttachmentData` resources with pure `EffectiveWeaponStats` composition
- Multi-dimensional `WeaponStateMachine` preventing contradictory states across firing, reloading, ADS, sprinting, and switching
- Real camera-applied recoil accumulation/recovery and stance-aware dynamic spread
- Tactical/empty magazine reload + interruptible shell-by-shell shotgun loading with zero ammo duplication
- Decoupled `HealthComponent` + `HitboxComponent` (head/body multipliers, armor absorption)
- Verified with 48 automated headless Godot tests and live engine runtime validation
