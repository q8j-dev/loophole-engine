# Roadmap

## The bar

Someone watches a 30-second clip and says "there's no way this is Scratch". A 12-year-old can make their own game with it in an afternoon. Nothing else on Scratch or TurboWarp comes close.

Status: `[ ]` not started, `[~]` works but has known gaps, `[x]` built and checked in a 1080p screenshot or a scripted playthrough in `tools/harness`.

## How it fits together

- `world.py` describes the game in Python: rooms carved from boxes, terrain, buildings, materials, lights, props, objects, triggers and settings, over any number of levels.
- `loophole build` bakes each level (cached by content hash) and writes `<game>.sb3`. If the file exists, the build merges into it: the user's sprites, blocks, variables and costumes stay, and only the Engine sprite, the Game sprite and the engine's data are replaced.
- Gameplay is plain Scratch blocks in TurboWarp, or Python compiled to blocks. The engine exposes variables, per-object lists, broadcasts, a sound queue, camera control and on-screen text. [docs/scratch-api.md](docs/scratch-api.md) lists all of them.
- The renderer is Loophole's, made data-driven. [docs/renderer.md](docs/renderer.md) explains it.

## Milestones

### 1. Core engine
- [x] Package layout, `pyproject.toml`, `loophole` command (`new`, `build`, `info`). Baking happens inside `build`, so there is no separate `bake` command.
- [x] World DSL: rooms, solids, paint, lights (point, spot, strip, panel, prop lamps), props, spawn, settings, multiple levels
- [x] Bake cache keyed by level content and prop meshes
- [x] Runtime stripped of Loophole's chamber-specific code
- [x] Generic dynamic shadow casters (object boxes plus the player capsule)
- [x] Prebuilt assets in the package: material atlases, kit and prop meshes, decor tiles, characters, fonts, sound pack
- [x] Per-game texture packing: only the materials and props a game uses, 512-pixel textures by default. The showcase went from 63 MB to 23 MB.
- [x] Starter template renders in the harness at about 60 fps
- [x] Automatic quality: render resolution steps down when the frame rate stays low (checked with 8x CPU throttling: 14 fps, quality 3 to 1 in about 6 seconds), and scripts can read or set `quality`

### 2. Scratch API
- [x] Player variables, readable and writable (teleport by setting `player x`)
- [x] Objects: model, transform, visible, solid, physics, carry, use, glow, highlight, bob, shadow, paths
- [x] Triggers with `enter`/`leave` broadcasts, hazard and goal zones, generic `collect`/`touch`/`enter`/`leave` broadcasts with `last ...` variables
- [x] Sound queue, camera control, fade and flash, level switching, `controls` to freeze the player
- [x] Switchable and flickering lights
- [x] On-screen `message` and `status` text drawn by the engine
- [x] Merge-rebuild keeps user sprites and blocks (`tests/test_merge.py`)
- [x] Python gameplay dialect compiled to a Game sprite, including `range` loops, `in` checks and `index_of`

### 3. Proof
- [x] Showcase game (Afterglow): a first-person lab puzzle, then a dusk valley with a lantern hunt and an ending, built only from the public API
- [x] Natural-input playthrough of the showcase from start to finish (`tools/harness/runs/showcase.txt`)
- [x] README with real 1080p captures, a GIF and a 5-minute guide, checked by following it in a fresh virtual environment from a fresh clone
- [x] `docs/`: world API, Scratch API, renderer

### 4. Outdoor
- [x] Sun baked into lightmaps with soft shadows, sky light from rays that escape the level. The showcase valley bakes in about 35 seconds.
- [x] Sky with day, sunset, dusk, night and overcast presets, sun disc and clouds
- [x] Heightmap terrain with its own lightmap, grass cards, dirt and rock blending, paths, and hills out to the horizon
- [x] Open levels without boundary walls, with height fog
- [x] Buildings with roofs, framed glass windows and doors that let daylight into interiors
- [x] Showcase has an indoor level and an outdoor level
- [x] On terrain, `y` is measured from the ground for spawns, props, objects and triggers

### 4b. Look library
- [x] Second and third material atlases from Poly Haven CC0 sets
- [x] Level styles: lab, house, dungeon, outdoor, plain
- [x] Viewmodel is data-driven: none, arms, device, or any prop or model, switchable from the `viewmodel` variable
- [x] Prop library made in Blender from Poly Haven models (32 props) plus generated foliage with alpha-cut leaves and wind sway
- [x] Signs with letters, digits and punctuation

### 5. Game variety
- [x] Camera modes: first person, free, third person orbit, top down with a cutaway for indoor levels
- [x] Objects that follow paths, spin, bob and fire `touch` and `collect` broadcasts
- [x] Example games in different genres, each with a natural-input playthrough: Afterglow (first-person puzzle and exploration), Orchard Dash (third-person timed collectathon), Crypt Crawl (top-down dungeon), Portal Lab (portal puzzle with a cube, a ledge and a momentum fling)
- [x] Player characters: suit, knight, mage, rogue, barbarian, or any rigged glTF with idle, walk, run and jump clips

### 6. Reach
- [x] OBJ, glTF and GLB import with base colour, normal and roughness textures
- [x] Portals as an optional engine feature (`game.portals(True, colors=...)`): recursive see-through views (3 levels), walk-through with momentum, floor-portal funnelling, carried and dropped cubes pass through, placement refuses props, signs, windows and non-portal surfaces. Ported from Loophole's verified `tele_check`, `tele_dir`, `portal_pass` and funnelling code.
- [~] Moving platforms: the player rides objects that move along paths, but no example uses it and no playthrough checks it

### 7. Ship
- [x] MIT license, CREDITS for every third-party asset
- [x] Public repo on GitHub (https://github.com/q8j-dev/loophole-engine), pushed at each milestone
- [x] Clean clone builds and plays from a fresh path, with only numpy and Pillow

## Known gaps

- Tree canopies seen from very close still break into ragged leaf cards, and the temporal anti-aliasing smears foliage during fast camera turns.
- Distant hills beyond the playable area are low in detail.
- Portals work only in first person, and portal views render at half resolution.
- The Portal Lab playthrough is timing-sensitive in the harness: it passes as written in `tools/harness/runs/portals.txt`, but removing the extra `log` steps after the first teleport has made the walk west along the ledge stall in some runs. The cause is not yet found.
- Characters use rigid skinning (each vertex follows one bone) with a limit of 32 bones, so very smooth organic rigs crease at the joints.
- Games need TurboWarp because they use the Pen+ extension. They don't run on scratch.mit.edu.
- A clone of the repo is about 150 MB, half of it git history from earlier texture versions.
