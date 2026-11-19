# Scratch API

A built game talks to your scripts through normal Scratch variables, lists and broadcasts on the Stage. You use them with the usual blocks: "set [variable] to", "change [variable] by", "item (1) of [list]", "replace item (1) of [list] with", "when I receive [message]" and so on. There are no custom blocks to learn.

Your own sprites, scripts and variables survive `loophole build`. The build replaces only the Engine sprite and, if you use `game.script`, the Game sprite.

## Variables

Variables marked "read" are updated by the engine every frame. Variables marked "set" are yours to change, and the engine reads them every frame.

### Player

| Variable | Use | Meaning |
| --- | --- | --- |
| `player x`, `player y`, `player z` | read, set | Feet position in metres. Set all three to teleport. |
| `player yaw` | read, set | Facing in degrees. 0 looks toward -z, 90 toward +x. |
| `player pitch` | read, set | Looking up (positive) or down (negative), in degrees. |
| `player speed` | read | Horizontal speed in metres per second. |
| `player on ground` | read | 1 when standing on something, 0 in the air. |
| `walk speed` | set | Running speed. Default 6. |
| `jump power` | set | Jump speed. Default 7. |
| `gravity` | set | Default 20. |
| `controls` | set | 1 lets the player move and look. 0 freezes them, for cutscenes and endings. |

### Looking and holding

| Variable | Use | Meaning |
| --- | --- | --- |
| `looking at` | read | Number of the object under the crosshair (its position in the `obj name` list), or 0. |
| `looking distance` | read | Distance to that object. |
| `holding` | read, set | Number of the object being carried, or 0. Set it to 0 to drop it. |
| `used object` | read | Number of the last object the player pressed E on (objects made with `use=True`). |
| `last touched` | read | Name of the last object the player walked into. |
| `last collected` | read | Name of the last pickup collected. |
| `last trigger` | read | Name of the last trigger entered or left. |

### Camera

| Variable | Use | Meaning |
| --- | --- | --- |
| `camera mode` | set | 0 first person, 1 free camera, 2 third person, 3 top down. |
| `camera distance` | set | Distance behind or above the player in modes 2 and 3. |
| `camera yaw`, `camera pitch` | read, set | Orbit angles in modes 2 and 3. In mode 1 they aim the free camera. |
| `camera x`, `camera y`, `camera z` | read, set | Camera position. Set them in mode 1 to place a free camera. |
| `field of view` | set | Vertical field of view in degrees. |
| `viewmodel` | set | What the player holds in first person: `none`, `arms`, `device`, or any name listed in `Game(viewmodels=...)`. |

### Screen

| Variable | Use | Meaning |
| --- | --- | --- |
| `message` | set | Large text near the bottom of the screen. It fades in when it changes. Set it to empty to hide it. |
| `status` | set | Smaller text in the top left corner, for score, health or time. |
| `fade` | set | 0 is normal and 1 is black. Count it up in a loop for a fade-out. |
| `flash` | set | Set to about 0.5 for a white flash when the player is hurt. It fades back by itself. |
| `exposure` | set | Brightness multiplier. Default 1. |

### Game flow

| Variable | Use | Meaning |
| --- | --- | --- |
| `level` | read | Current level number, starting at 1. |
| `level name` | read | Name given in `game.level("...")`. |
| `level time` | read | Seconds since the level started. |
| `go to level` | set | Set it to a level number to load that level. The engine sets it back to 0. |
| `paused` | read, set | 1 while paused. Set it to 1 to pause, 0 to resume. |
| `mouse locked` | read | 1 while the mouse is captured for looking around. |
| `fps` | read | Frames per second. |

## Lists

Each object in the current level has one item in every `obj` list, in the order the objects appear in `world.py`. Find an object's number with "item # of [rat1] in [obj name]".

| List | Use | Meaning |
| --- | --- | --- |
| `obj name` | read | Object names. |
| `obj x`, `obj y`, `obj z` | read, set | Positions. |
| `obj yaw`, `obj pitch`, `obj roll` | read, set | Rotation in degrees. |
| `obj scale` | read, set | Size multiplier. |
| `obj visible` | read, set | 1 shown, 0 hidden. Hidden objects do not collide or send touch events. |
| `obj solid` | read, set | 1 blocks the player. |
| `obj glow` | read, set | Brightness of the object's glowing parts. |
| `obj open` | read, set | For doors and sliding objects, 1 opens and 0 closes. Buttons set it for you. |
| `obj touching` | read | 1 while the player touches the object. |
| `light name` | read | Names of the level's lights. Unnamed lights are called light1, light2 and so on. |
| `light power` | read, set | Brightness of each light. Named lights switch on with 1 and off with 0. |
| `trigger name` | read | Names of the level's triggers and goals. |
| `trigger inside` | read | 1 while the player is inside that trigger. |
| `sound queue` | add | Add a sound name and the engine plays it: `alarm`, `arrive`, `boost`, `button`, `click`, `door_close`, `door_open`, `fail`, `hum`, `impact`, `jump`, `land`, `pickup`, `release`, `rumble`, `success`, `unpress`, `whoosh`. |

Example: switch on a light called `beacon1` when the player collects something.

```
when I receive [collect]
replace item (item # of [beacon1] in [light name]) of [light power] with (1)
```

## Broadcasts

The engine sends these. Use them with "when I receive".

| Broadcast | When |
| --- | --- |
| `level start` | A level has loaded and faded in, including the first one. |
| `collect` and `collect <name>` | The player collected a pickup. `last collected` holds the name. |
| `touch` and `touch <name>` | The player started touching an object. `last touched` holds the name. |
| `enter` and `enter <name>` | The player walked into a trigger or goal. `last trigger` holds the name. |
| `leave` and `leave <name>` | The player walked out of a trigger. |
| `press <name>` | A button went down. |
| `release <name>` | A button came back up. |
| `use <name>` | The player pressed E while looking at an object made with `use=True`. |
| `player died` | The player hit a hazard and is respawning. |
| `paused`, `resumed` | The game paused or resumed. |
| `game complete` | The player reached the goal of the last level. |
| `portal` | The player placed a portal (only with `Game(portals=True)`). |

Use the plain broadcast (`touch`) when you want one script for many objects and check `last touched`. Use the named one (`touch rat1`) when only one object matters.

Example: lose health when any rat touches the player.

```
when I receive [touch]
if <(last touched) contains [rat]> then
  change [health] by (-1)
  set [flash] to (0.6)
end
```

## Controls

| Input | Action |
| --- | --- |
| Click the stage | Capture the mouse and start playing. |
| W A S D | Move. In third person and top down, movement is relative to the camera. |
| Mouse or arrow keys | Look around, or orbit the camera. |
| Space | Jump. |
| Shift or C | Crouch. |
| E | Pick up, drop or use the object under the crosshair. |
| R | Restart from the spawn point. |
| Left and right click | Place the blue and orange portals, when portals are on. |
| P or Escape | Pause. |

## Python gameplay scripts

`game.script("game.py")` compiles a Python file into Scratch blocks inside a sprite called Game. You can open that sprite in TurboWarp and read or change the blocks it made. Engine variables use underscores in place of spaces: `player_x`, `camera_mode`, `last_touched`, `light_power`, `obj_open`, `go_to_level`.

```python
@when_broadcast("level start")
def begin():
    score = 0
    status = "Score 0"


@when_broadcast("collect")
def got():
    score += 1
    status = join("Score ", score)
    if score == 10:
        message = "You win!"
        controls = 0
```

Supported:

- Hats: `@when_flag`, `@when_broadcast("name")`, `@when_clone`. Plain functions become custom blocks.
- Control flow: `if`, `elif`, `else`, `while`, and `for i in range(n)` or `range(a, b)`.
- Waiting and messages: `wait(seconds)`, `broadcast("name")`, `broadcast_wait("name")`.
- Lists: `my_list[i]` (indexes start at 1, as in Scratch), `.append()`, `.insert()`, `.pop()`, `.clear()`, `len(list)`, `item in list`, `index_of(list, item)`.
- Text: `join(a, b)`, `letter(i, text)`, `strlen(text)`, `"rat" in text`.
- Maths: `+ - * / %`, comparisons, `and`, `or`, `not`, `abs`, `sqrt`, `sin`, `cos`, `floor`, `round`, `min`, `max`, `random(a, b)`.
- Input: `key("space")`, `mouse_x()`, `mouse_y()`, `mouse_down()`, `timer()`.
- Sound: `sound_queue.append("pickup")` plays one of the engine's sounds.

New variable names become variables on the Game sprite, and names from `game.variable` are shared on the Stage.
