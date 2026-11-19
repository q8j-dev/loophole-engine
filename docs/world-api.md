# World API

A game is a Python file, usually `world.py`, that creates one `Game` and adds levels to it. `loophole build` runs the file, bakes the lighting and writes the `.sb3`.

```python
from loophole import Game

game = Game("My Game")
lab = game.level("Lab")
lab.room(0, 0, 0, 12, 6, 14)
lab.spawn(6, 0, 12)
```

## Units and directions

- One unit is one metre. The player is 1.75 m tall and steps up ledges up to 0.55 m.
- `y` is up. Level geometry snaps to a 0.5 m grid.
- `yaw` is in degrees. A yaw of 0 looks toward `-z`, and 90 looks toward `+x`.
- A `facing` is one of `"+x"`, `"-x"`, `"+y"`, `"-y"`, `"+z"`, `"-z"`, or a direction tuple such as `(1, 0, 1)`.
- Colours are names (`white`, `warm`, `cool`, `red`, `orange`, `amber`, `green`, `blue`, `cyan`, `purple`, `pink`, `yellow`, `sodium`, `daylight`, `gold`), `"#rrggbb"` strings, or `(r, g, b)` tuples from 0 to 1.

## Game

```python
Game(title="My Game", viewmodel="none", viewmodels=None, hand_color="cyan", quality=3, fov=72, start_level=1,
     camera="first person", camera_distance=4.0, camera_pitch=None, walk_speed=6.0, jump_power=7.0,
     textures="normal", viewmodel_arms=False, player_model="suit", portals=False)
```

| Argument | Meaning |
| --- | --- |
| `title` | Project name. The output file is named after it. |
| `viewmodel` | What the player holds in first person: `"none"`, `"arms"`, `"device"`, or the name of any prop or imported model. |
| `viewmodels` | Extra viewmodels a script can switch to by setting the `viewmodel` variable. |
| `hand_color` | Glow colour of the device. |
| `quality` | Starting render resolution from 1 (fastest) to 4 (sharpest). |
| `auto_quality` | On by default. Steps `quality` down to 2 when the frame rate stays under 50, and to 1 under 36, so games stay smooth on slower computers. |
| `fov` | Vertical field of view in degrees. |
| `start_level` | Level number to start on. |
| `camera` | `"first person"`, `"third person"`, `"top down"` or `"free"`. Scripts can change it with `camera mode`. |
| `camera_distance` | Distance from the player for third person and top down. |
| `camera_pitch` | Downward angle in degrees. Defaults to 20 for third person and 60 for top down. |
| `walk_speed`, `jump_power` | Movement in metres per second. Scripts can change them at run time. |
| `textures` | `"normal"` uses 512-pixel textures and keeps games small. `"high"` uses 1024 pixels and makes files about twice as large. |
| `viewmodel_arms` | Draw the suit arms holding prop viewmodels. |
| `portals` | Same as calling `game.portals(True)`. Turns on the portal gun in first person. Left click places the blue portal and right click the orange one, on any `white`, `concrete`, `floor`, `plaster`, `tiles` or `marble` surface big enough to hold it. Walking into one portal brings you out of the other, and you can see through them. |
| `player_model` | Character shown in third person and top down: `"suit"`, `"knight"`, `"mage"`, `"rogue"`, `"barbarian"`, or a name added with `game.character`. |

| Method | What it does |
| --- | --- |
| `game.portals(on=True, colors=("cyan", "magenta"))` | Turns the portal gun on or off and sets the two portal colours. Portals can't be placed over props, signs, windows or objects. |
| `game.level(name)` | Adds a level and returns it. Levels are numbered from 1 in the order you add them. |
| `game.script(path)` | Compiles a Python gameplay file into Scratch blocks in a sprite called Game. See [scratch-api.md](scratch-api.md#python-gameplay-scripts). |
| `game.variable(name, show=False)` | Adds a Stage variable. With `show=True` it appears as a Scratch monitor. |
| `game.model(name, path, scale=1.0, texture=1024, up="y")` | Imports an `.obj`, `.gltf` or `.glb` file as a prop. Use `up="z"` for files exported Z-up. |
| `game.character(name, path, height=1.8, keep=None, facing="+z")` | Imports a rigged `.glb` or `.gltf` character. It needs a skeleton and an idle or walk animation. Clips named like Idle, Walk, Run and Jump are used automatically. Meshes attached to hand bones are hidden unless you list their node names in `keep`. Up to 32 bones. |

## Level geometry

Indoor levels start as solid rock. You carve rooms out of it.

| Method | What it does |
| --- | --- |
| `room(x0, y0, z0, x1, y1, z1, floor=None, walls=None, ceiling=None)` | Carves a box-shaped room. Rooms that touch or overlap join up, so a doorway is a small room between two big ones. |
| `hole(...)` | Same as `room` with default materials. |
| `solid(x0, y0, z0, x1, y1, z1, material=None)` | Fills a box back in. Use it for pillars, crates of stone and ledges. |
| `platform(x0, z0, x1, z1, height, y=0, material=None)` | A solid block from `y` to `height`. |
| `stairs(x0, z0, x1, z1, height, direction="+z", step=0.5)` | Steps that rise toward `direction`. |
| `paint(material, x0, y0, z0, x1, y1, z1, facing=None)` | Changes the material of surfaces inside a box. `facing="walls"` paints only walls. |
| `materials(floor=None, walls=None, ceiling=None)` | Default materials for this level. |
| `style(name)` | A preset look: `"lab"`, `"house"`, `"dungeon"`, `"outdoor"` or `"plain"`. It sets default materials, haze and trim. |
| `pool(material, x0, z0, x1, z1, y=0, depth=1.5)` | A sunken pool of `water`, `slime`, `lava` or another liquid. |
| `window(x0, y0, z0, x1, y1, z1, facing)` | A window panel on a wall. |
| `sign(text, x, y, z, facing="+z", height=1.6)` | Letters, digits and punctuation cut into a wall. |
| `cutaway(height=2.4)` | For top-down levels. Everything higher than `height` above the player's feet is hidden, and wall cross-sections draw black, so you can see into rooms with ceilings. |

Materials: `white`, `metal`, `floor`, `ceiling`, `dark`, `panel`, `grate`, `rust`, `shutter`, `concrete`, `plate`, `hazard`, `stripes`, `grass`, `rock`, `sand`, `dirt`, `brick`, `wood`, `planks`, `plaster`, `tiles`, `stone`, `cobble`, `bark`, `asphalt`, `snow`, `cliff`, `gravel`, `roof`, `marble`, `paint`, `fabric`, `gold`, `glass`, `water`, `slime`, `lava`, `exit`, `boost`, `light`. Common synonyms work too, for example `bricks`, `cobblestone`, `floorboards` and `road`.

## Outdoor levels

```python
v = game.level("Valley")
v.outdoor(sky="sunset", sun=(-0.7, 0.32, -0.45))
v.terrain(-45, -45, 45, 45, hills=8.0, seed=11)
v.flatten(-16, -14, 18, 14)
v.path((4, -1), (-2, 8), (-20, 13), width=2.4)
v.building(-2, -10, 9, -2, door=("+z", 3.5), windows=[("+z", 7.0)])
```

| Method | What it does |
| --- | --- |
| `outdoor(sky="day", sun=(0.4, 0.75, 0.3), sun_color=None, fog=0.0035, clouds=0.45, shafts=0.6)` | Opens the level to the sky. Skies: `day`, `sunset`, `dusk`, `night`, `overcast`. `sun` points toward the sun. `shafts` sets how strongly sunbeams show through gaps in trees when you look toward the sun. |
| `terrain(x0, z0, x1, z1, hills=4.0, seed=1, height=None, grass=1.0, grass_style="lawn", material="terrain")` | Rolling ground with grass, dirt and rock on slopes. The hills continue to the horizon. `grass_style` is `"lawn"` (short, green), `"meadow"` (tall, with wildflowers), `"dry"` (golden) or `"forest"` (sparse, with leaf litter and moss under trees). `grass` scales the density. Pass a 2D `height` array to sculpt the ground yourself. |
| `wind(direction=(1, 0.35), strength=1.0)` | Wind for the level. Gusts roll across grass in waves and sway trees, bushes and clumps of leaves together. `strength=0` stops it. |
| `flatten(x0, z0, x1, z1, height=0, falloff=6)` | Levels an area, blending back into the hills over `falloff` metres. |
| `path(*points, width=2.0, material="gravel")` | A smooth path through the points. Use `"dirt"` or `"gravel"`. |
| `building(x0, z0, x1, z1, height=3, walls="brick", inside="plaster", floor="wood", roof="roof", roof_shape="gable", door=None, windows=(), ...)` | A house with a foundation, a gabled or flat roof, framed glass windows, a door frame and trim. `door` and each window are `(side, position along the wall)`. The ground under it is flattened. |

## Forests in one line

```python
v.forest(-40, -40, 40, 20)
v.forest(-40, 20, 0, 50, kind="pine", density=0.8)
v.scatter(["boulder", "rock"], -30, -30, 30, 30, spacing=8)
```

| Method | What it does |
| --- | --- |
| `forest(x0, z0, x1, z1, kind="mixed", density=1.0, undergrowth=True, seed=1)` | Fills the area with trees spaced like a real forest, plus bushes, ferns, grass, fallen logs and rocks underneath. Kinds: `"mixed"`, `"broadleaf"`, `"pine"`, `"birch"`, `"autumn"`. Paths, buildings, objects and the spawn point stay clear. |
| `scatter(kinds, x0, z0, x1, z1, spacing=3.0, scale=(0.8, 1.2), seed=0)` | Places props randomly with at least `spacing` metres between them, with random size and rotation. `kinds` is a prop name, a list of names, or a list of `(name, weight)` pairs. |

Big forests stay fast: leaves far from the camera are thinned out and replaced by fewer, larger clusters, and parts of the level behind the camera are skipped.

On a level with terrain, `y` means height above the ground for spawns, props, lights, objects and triggers. `y=0` stands on the hillside wherever you are.

## Lights

The bake lights the level from these, with soft shadows and bounced light.

| Method | What it does |
| --- | --- |
| `light(x, y, z, color="white", power=8, fixture="cage", facing="-y", haze=0, name=None, dynamic=False, on=True, flicker=0)` | A point light. `fixture=None` hides the cage. |
| `spot(x, y, z, target, color="white", power=40, cone=(18, 32), haze=1.0)` | A spotlight aimed at `target`, with a visible beam when `haze` is above 0. |
| `strip(x0, y0, z0, x1, y1, z1, color="cool", power=8)` | A fluorescent tube light. |
| `ceiling_light(x, y, z, width=1.5, depth=1.5, power=4.6)` | A flat ceiling panel. |

Give a light a `name` to control it from Scratch through the `light power` list. A named light is dynamic: it is not baked, so it can switch on and off. `on=False` starts it off. `flicker` from 0 to 1 makes a torch flicker.

## Props

```python
v.prop("oak", 12, 0, -8, yaw=40, scale=1.1)
v.prop("lantern", 3.5, 0.55, -6)
v.wall_prop("sconce", 8.3, 1.8, -4.5, facing="-x")
```

`prop(kind, x, y, z, yaw=0, scale=1, solid=None, light=True, name=None, on=True, flicker=0)` places a prop. Lamps, candles and fires add their own light unless `light=False`. Large props are solid by default.

| Group | Props |
| --- | --- |
| Trees | `oak`, `birch`, `maple` (autumn colours), `willow`, `pine`, `spruce` |
| Nature | `bush`, `grass`, `fern`, `log`, `boulder`, `rock`, `mossrock`, `stump` |
| House | `table`, `chair`, `armchair`, `sofa`, `bed`, `bookshelf`, `cabinet`, `nightstand`, `picture`, `chandelier`, `sconce`, `lantern`, `candlestick`, `oillamp` |
| Village | `woodbarrel`, `winebarrel`, `woodcrate`, `bench`, `firepit`, `streetlamp`, `walllamp`, `toolcart`, `bucket` |
| Treasure | `apple`, `goblet`, `treasure`, `statue`, `catstatue`, `rat` |
| Lab | `crate`, `barrel`, `machine`, `tank`, `rack`, `terminal`, `trolley`, `reel`, `toolbox`, `pipe`, `valve`, `duct`, `jbox`, `fan`, `panel`, `tray`, `ramp`, `drain` |
| Characters | `knight`, `mage`, `rogue`, `barbarian` |

Lab helpers: `pipe(*points, radius=1)`, `catwalk(x0, y, z0, x1, z1, rails="both")`, `column(x, z, y0, y1)`, `vent(x0, z0, x1, z1)` and `sparks(x, y, z)`.

## Objects

Objects move, react and appear in the Scratch lists, so scripts can change them.

```python
lab.cube("cube", 9, 0, 9)
lab.button("button", 3, 0, 4, opens="door")
lab.door("door", 6, 0, -0.6, facing="+z", width=2, height=3)
v.pickup("apple1", "apple", 5, 0.4, 2, scale=3)
v.object("rat1", "rat", -20, 0, 1, scale=6, solid=False, path=[(-20, 0, 1), (20, 0, 1)], speed=3)
```

| Method | What it does |
| --- | --- |
| `object(name, model, x, y, z, **options)` | Any prop, imported model or `cube`, `door`, `button` as an object. Names must be unique in a level. |
| `cube(name, x, y, z)` | A physics cube the player can carry with E. |
| `button(name, x, y, z, opens=None)` | A floor button. Standing on it or putting something heavy on it opens the object named in `opens`. |
| `door(name, x, y, z, facing="+z", width=2, height=3)` | A sliding door. It opens when its button is pressed or a script sets its `obj open` item to 1. |
| `pickup(name, model, x, y, z)` | A collectible that spins, bobs and glows gold. Touching it hides it and sends `collect`. |

Options for any object: `yaw`, `pitch`, `roll`, `scale`, `visible`, `solid`, `physics`, `carry`, `use` (E sends `used object`), `shadow`, `glow`, `glow_color`, `collect`, `spin` (degrees per second), `bob` (metres), `highlight` (rim glow colour), `path` (list of points to walk), `speed`, `loop`, `face_path`, `slide` and `open_speed` (for doors; any object with `kind=1` slides by `slide` metres when opened, and negative values sink it).

## Zones

| Method | What it does |
| --- | --- |
| `spawn(x, y, z, yaw=0, pitch=0)` | Where the player starts and respawns. |
| `trigger(name, x0, y0, z0, x1, y1, z1)` | Sends `enter <name>` and `leave <name>` when the player crosses it. |
| `goal(x0, y0, z0, x1, y1, z1, to=None)` | Ends the level. It goes to level `to`, or the next level, or sends `game complete` on the last level. |
| `hazard(x0, y0, z0, x1, y1, z1)` | Kills the player, who respawns. |

## Look

`grade(r=1, g=1, b=1, saturation=1, exposure=None, auto_exposure=None)` tints the final image. `exposure` brightens or darkens the level. `auto_exposure` from 0 to 1 sets how strongly the camera adapts to dark and bright areas, and a low value keeps dark places dark.
