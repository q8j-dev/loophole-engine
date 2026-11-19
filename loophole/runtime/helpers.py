@block("move object %s to x %s y %s z %s")
def move_object(name, x, y, z):
    """Moves an object from world.py, like the cube or a door, to a new spot. Objects are listed in the obj name list."""
    k = index_of(obj_name, name)
    if k > 0:
        obj_x[k] = x
        obj_y[k] = y
        obj_z[k] = z


@block("turn object %s to %s degrees")
def turn_object(name, angle):
    k = index_of(obj_name, name)
    if k > 0:
        obj_yaw[k] = angle


@block("show object %s")
def show_object(name):
    k = index_of(obj_name, name)
    if k > 0:
        obj_visible[k] = 1


@block("hide object %s")
def hide_object(name):
    k = index_of(obj_name, name)
    if k > 0:
        obj_visible[k] = 0


@block("open %s")
def open_object(name):
    """Opens a door or anything else that slides. close does the opposite."""
    k = index_of(obj_name, name)
    if k > 0:
        obj_open[k] = 1


@block("close %s")
def close_object(name):
    k = index_of(obj_name, name)
    if k > 0:
        obj_open[k] = 0


@block("play sound %s")
def play_sound(name):
    """Plays one of the engine's sounds: alarm, arrive, boost, button, click, door_close, door_open, fail, hum, impact, jump, land, pickup, release, rumble, success, unpress, whoosh."""
    sound_queue.append(name)


@block("show message %s")
def show_message(text):
    """Shows big text near the bottom of the screen. Show an empty message to hide it."""
    message = text


@block("show message %s for %s seconds")
def show_message_for(text, secs):
    message = text
    wait(secs)
    if message == text:
        message = ""


@block("set status %s")
def set_status(text):
    """Small text in the top left corner, good for score, health or time."""
    status = text


@block("teleport player to x %s y %s z %s")
def teleport_player(x, y, z):
    player_x = x
    player_y = y
    player_z = z


@block("switch light %s to %s")
def switch_light(name, power):
    """Turns a named light on (1), off (0) or anything in between. Name a light in world.py with name="lamp1"."""
    k = index_of(light_name, name)
    if k > 0:
        light_power[k] = power


@block("start weather %s")
def start_weather(kind):
    """clear, rain, snow or fog. It fades in over a few seconds."""
    weather = kind


@block("go to level %s")
def change_level(n):
    go_to_level = n


@block("fade to black in %s seconds")
def fade_out(secs):
    for i in range(20):
        fade = (i + 1) / 20
        wait(secs / 20)


@block("fade in from black in %s seconds")
def fade_in(secs):
    for i in range(20):
        fade = 1 - (i + 1) / 20
        wait(secs / 20)


@block("fly camera to x %s y %s z %s turn %s tilt %s in %s seconds")
def fly_camera(x, y, z, yaw, pitch, secs):
    """Glides a free camera to a point, turned and tilted in degrees. Use camera back to player when you are done."""
    if camera_mode != 1:
        camera_x = player_x
        camera_y = player_y + 1.6
        camera_z = player_z
        camera_yaw = player_yaw
        camera_pitch = player_pitch
        camera_mode = 1
    fx = camera_x
    fy = camera_y
    fz = camera_z
    fyaw = camera_yaw
    fpitch = camera_pitch
    fstart = timer()
    fk = 0
    while fk < 1:
        fk = min(1, (timer() - fstart) / max(secs, 0.01))
        fe = fk * fk * (3 - 2 * fk)
        camera_x = fx + (x - fx) * fe
        camera_y = fy + (y - fy) * fe
        camera_z = fz + (z - fz) * fe
        camera_yaw = fyaw + (yaw - fyaw) * fe
        camera_pitch = fpitch + (pitch - fpitch) * fe
        wait(0)


@block("camera back to player")
def camera_back():
    camera_mode = 0
    controls = 1


@when_broadcast("press button")
def door_example():
    """Example: a button that opens a door.

In world.py the button already opens the door with opens="door". This script adds a message and a sound when it goes down. Use the name of your own button in the hat block: press <name>."""
    play_sound("door_open")
    show_message_for("The door is open! Keep something heavy on the button.", 3)


@when_broadcast("level start")
def coins_reset():
    """Example: counting collectibles. Every level starts at 0."""
    coins = 0


@when_broadcast("collect")
def coins_example():
    """Every pickup the player touches sends collect. Add pickups in world.py, or with the Collectible tool in Studio, and this keeps score in the corner."""
    coins += 1
    set_status(join("Coins: ", coins))


@when_broadcast("level start")
def enemy_example():
    """Example: an enemy that walks back and forth.

Add an object called enemy in world.py, for example:
lab.object("enemy", "rat", 3, 0, 7, scale=6, solid=False)
It paces 3 metres either side of where it starts."""
    ek = index_of(obj_name, "enemy")
    if ek > 0:
        ex = obj_x[ek]
        elv = level
        while level == elv:
            obj_x[ek] = ex + 3 * sin(level_time * 60)
            if cos(level_time * 60) > 0:
                obj_yaw[ek] = 0
            else:
                obj_yaw[ek] = 180
            wait(0)


@when_broadcast("touch enemy")
def enemy_touch():
    """Touching the enemy flashes the screen and starts the level again."""
    flash = 0.6
    show_message("Caught! Try again.")
    wait(1)
    change_level(level)


@when_key("c")
def flythrough_example():
    """Example: press C for a camera fly-through of the starter lab.

The player can't move while it plays. Change the numbers to points in your own level: x, y, z, then turn and tilt in degrees."""
    controls = 0
    fly_camera(6, 5, 13, 0, -15, 2)
    fly_camera(1.5, 3, 3, -50, -12, 2.5)
    fly_camera(10, 4, 1.5, 60, -20, 2.5)
    fly_camera(6, 2, -2, 0, 0, 2)
    camera_back()
