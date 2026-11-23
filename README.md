# Godot Scripting Work

A collection of modular, commission-grade **Godot 4** gameplay systems and reusable engineering frameworks built in typed **GDScript**.

> **The scripting is the product.** Each project is structured so its core gameplay architecture can be inspected, tested, and integrated into real production projects.

---

## Repository Structure

```text
Godot-Scripting-Work/
├── Godot-Systems-Lab/
│   └── 01-Advanced-FPS/   # Modular Godot 4.7.2 First-Person Shooter Framework
├── .gitattributes
├── .gitignore
└── README.md
```

---

## Projects

### [01 — Advanced FPS Framework](./Godot-Systems-Lab/01-Advanced-FPS/)

A complete single-player First-Person Shooter gameplay framework built in **Godot 4.7.2 (Forward+)** with typed GDScript, custom Blender 5.3 rigged weapon/arm viewmodels, and an automated deterministic test suite.

- **Core Systems:** Data-driven `WeaponData` / `WeaponInstance` / `EffectiveWeaponStats`, orthogonal `WeaponStateMachine` (`ActionState`, `AimState`, `SprintState`), hitscan & multi-pellet `BallisticSolver` with distance falloff and configurable multi-surface penetration, camera recoil & spread recovery, tactical/empty magazine & interruptible shell-by-shell reloads, 4-slot attachment modifiers, decoupled `HitboxComponent` / `HealthComponent` with armor absorption, `SAFE`/`SEMI`/`AUTO` fire selector, shoulder switching, collision-aware `Q`/`E` leaning, and centralized `GPUParticles3D` `ImpactFXManager`.
- **Verification:** 106/106 automated headless test assertions passing (`tests/run_tests.gd`).
- **Documentation:** [README](./Godot-Systems-Lab/01-Advanced-FPS/README.md) · [Architecture](./Godot-Systems-Lab/01-Advanced-FPS/docs/ARCHITECTURE.md) · [Extending](./Godot-Systems-Lab/01-Advanced-FPS/docs/EXTENDING.md) · [Rigging & Animation](./Godot-Systems-Lab/01-Advanced-FPS/docs/RIGGING_AND_ANIMATION.md)

---

## Links

- **Portfolio:** [danipp.tech/game-dev](https://danipp.tech/game-dev)
- **GitHub:** [@PapLion](https://github.com/PapLion)
