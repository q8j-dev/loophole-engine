# Roadmap

## The bar

Someone watches a 30-second clip and says "there's no way this is Scratch". A 12-year-old can make their own game with it in an afternoon. Nothing else on Scratch or TurboWarp comes close.

Status: `[ ]` not started, `[~]` in progress, `[x]` built and checked in a 1080p screenshot or a headless playthrough.

## How it fits together

- `world.py` describes the game in Python: rooms carved from boxes, materials, lights, props, objects, triggers, spawn and settings, over any number of levels.
- `loophole build` bakes each level (cached by content hash) and writes `<game>.sb3`. If the file exists, the build merges into it: the user's sprites, blocks, variables and costumes stay, and only the Engine sprite and the engine's data are replaced.
- Gameplay is plain Scratch blocks in TurboWarp. The engine exposes variables (`player x`), lists indexed by object (`obj x`, `obj visible`), broadcasts (`enter <trigger>`, `use <object>`), a sound queue and a camera override. Gameplay can also be written in the Python dialect and compiled to blocks.
- Rendering is Loophole's, made data-driven: vertex-pulled meshes from data textures, PBR materials, kit surface detailing, baked lightmaps with GI and directional data, ambient probes, soft dynamic shadows from any object, parallax-corrected env probe reflections, SSR, TAA, volumetric haze, bloom, ACES, sharpening and grain.

## Milestones

### 1. Core engine
- [ ] Package layout, `pyproject.toml`, `loophole` command (`new`, `build`, `bake`, `info`)
- [ ] World DSL: rooms, solids, paint, lights (point, spot, strip, panel, lamp), props, spawn, settings, multiple levels
- [ ] Bake cache keyed by level content
- [ ] Runtime stripped of chamber hacks (finale flood, `uRm`, portal-only uniforms, VO, ride, title)
- [ ] Generic dynamic shadow casters (object boxes plus the player capsule)
- [ ] Shipped prebuilt assets: material atlas, decor atlases, kit meshes, prop meshes and atlas, sound pack
- [ ] Starter template renders and plays in the headless harness

### 2. Scratch API
- [ ] Player variables, readable and writable (teleport by setting `player x`)
- [ ] Objects: model, transform, visible, solid, physics, carry, use, glow, shadow
- [ ] Triggers with `enter`/`leave` broadcasts, kill and goal zones
- [ ] Sound queue, camera override, fade and flash, level switching
- [ ] Switchable dynamic lights
- [ ] Merge-rebuild keeps user sprites and blocks (checked by an automated test)
- [ ] Python gameplay dialect compiled to a Game sprite

### 3. Proof
- [ ] Showcase game, several levels, built only from the public API
- [ ] Natural-input playthrough of the showcase in the harness
- [ ] 1080p screenshots, a GIF, README with a 5-minute guide
- [ ] `docs/`: world API, Scratch API, renderer

### 4. Reach
- [ ] OBJ and GLB import with a base colour texture
- [ ] Portals as an optional engine feature
- [ ] Moving platforms

### 5. Ship
- [ ] MIT license, CREDITS for CC0 assets
- [ ] Public repo on GitHub, pushed at each milestone
