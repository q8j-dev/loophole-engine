@when_broadcast("press button")
def door_example():
    """Example: a button that opens a door.

In world.py the button already opens the door with opens="door". This script adds a sound and a message when the button goes down. For your own button, change the hat to press and its name."""
    play_sound("door_open")
    show_message_for("The door is open! Keep something heavy on the button.", 3)


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


@when_broadcast("collect")
def coins_example():
    """Example: counting collectibles.

Every pickup the player touches sends collect. Add pickups in world.py, or with the Collectible tool in Studio, and this keeps score in the corner."""
    coins += 1
    set_status(join("Coins: ", coins))


@when_broadcast("level start")
def coins_reset():
    """Every level starts with 0 coins."""
    coins = 0


@when_broadcast("level start")
def enemy_example():
    """Example: an enemy that walks back and forth.

Add an object called enemy in world.py, for example:
lab.object("enemy", "rat", 3, 0, 7, scale=6, solid=False)
It paces 3 metres either side of where it starts."""
    enemy_number = index_of(obj_name, "enemy")
    if enemy_number > 0:
        enemy_start = obj_x[enemy_number]
        this_level = level
        while level == this_level:
            obj_x[enemy_number] = enemy_start + 3 * sin(level_time * 60)
            if cos(level_time * 60) > 0:
                obj_yaw[enemy_number] = 0
            else:
                obj_yaw[enemy_number] = 180
            wait(0)


@when_broadcast("touch enemy")
def enemy_touch():
    """Touching the enemy flashes the screen and starts the level again."""
    flash = 0.6
    show_message("Caught! Try again.")
    wait(1)
    change_level(level)


@block("move object %s to x %s y %s z %s")
def move_object(name, x, y, z):
    """Moves an object from world.py, like the cube or a door. Objects are listed in the obj name list."""
    number = index_of(obj_name, name)
    if number > 0:
        obj_x[number] = x
        obj_y[number] = y
        obj_z[number] = z


@block("push %s by x %s y %s z %s")
def push_object(name, x, y, z):
    """Shoves an object that has physics, like a cube. The numbers are speeds in metres per second, so y 6 throws it up."""
    number = index_of(obj_name, name)
    if number > 0:
        obj_vx[number] = obj_vx[number] + x
        obj_vy[number] = obj_vy[number] + y
        obj_vz[number] = obj_vz[number] + z


@block("turn object %s to %s degrees")
def turn_object(name, angle):
    number = index_of(obj_name, name)
    if number > 0:
        obj_yaw[number] = angle


@block("show object %s")
def show_object(name):
    number = index_of(obj_name, name)
    if number > 0:
        obj_visible[number] = 1


@block("hide object %s")
def hide_object(name):
    number = index_of(obj_name, name)
    if number > 0:
        obj_visible[number] = 0


@block("open %s")
def open_object(name):
    """Opens a door or anything else that slides."""
    number = index_of(obj_name, name)
    if number > 0:
        obj_open[number] = 1


@block("close %s")
def close_object(name):
    number = index_of(obj_name, name)
    if number > 0:
        obj_open[number] = 0


@block("make %s follow the player")
def npc_follow(name):
    """Characters find their way around walls on their own. When one sees the player it sends sees and its name."""
    set_npc_mode(name, "follow")


@block("make %s wander")
def npc_wander(name):
    set_npc_mode(name, "wander")


@block("make %s patrol its path")
def npc_patrol(name):
    set_npc_mode(name, "patrol")


@block("make %s run away from the player")
def npc_flee(name):
    set_npc_mode(name, "flee")


@block("make %s walk to x %s z %s")
def npc_goto(name, x, z):
    number = index_of(obj_name, name)
    if number > 0:
        obj_goal_x[number] = x
        obj_goal_z[number] = z
        obj_mode[number] = "goto"


@block("make %s stop")
def npc_stop(name):
    set_npc_mode(name, "stop")


@block("set mode of %s to %s")
def set_npc_mode(name, mode):
    number = index_of(obj_name, name)
    if number > 0:
        obj_mode[number] = mode


@block("play sound %s")
def play_sound(name):
    """Sounds: alarm, arrive, boost, button, click, door_close, door_open, fail, hum, impact, jump, land, pickup, release, rumble, success, unpress, whoosh."""
    sound_queue.append(name)


@block("play sound %s at x %s y %s z %s")
def play_sound_at(name, x, y, z):
    """Plays a sound from a spot in the level. It is louder close by and comes from the left or right."""
    away_x = x - camera_x
    away_z = z - camera_z
    distance = sqrt(away_x * away_x + (y - camera_y) * (y - camera_y) + away_z * away_z)
    loudness = 1 - distance / 25
    if loudness < 0:
        loudness = 0
    set_volume(loudness * loudness * 100)
    if distance > 0.1:
        set_pan((away_x * cos(camera_yaw) + away_z * sin(camera_yaw)) / distance * 90)
    else:
        set_pan(0)
    play(name)


@block("rumble controller %s for %s seconds")
def rumble_controller(strength, seconds):
    """Shakes a connected game controller. Strength goes from 0 to 1."""
    rumble(strength, strength, seconds)


@block("show message %s")
def show_message(text):
    """Big text near the bottom of the screen. Show an empty message to hide it."""
    message = text


@block("show message %s for %s seconds")
def show_message_for(text, seconds):
    message = text
    wait(seconds)
    if message == text:
        message = ""


@block("set status %s")
def set_status(text):
    """Small text in the top left corner, for score, health or time."""
    status = text


@block("teleport player to x %s y %s z %s")
def teleport_player(x, y, z):
    player_x = x
    player_y = y
    player_z = z


@block("switch light %s to %s")
def switch_light(name, power):
    """1 is on and 0 is off. Name a light in world.py with name="lamp1"."""
    number = index_of(light_name, name)
    if number > 0:
        light_power[number] = power


@block("start weather %s")
def start_weather(kind):
    """clear, rain, snow or fog."""
    weather = kind


@block("go to level %s")
def change_level(number):
    go_to_level = number


@block("fade to black in %s seconds")
def fade_out(seconds):
    for step in range(20):
        fade = (step + 1) / 20
        wait(seconds / 20)


@block("fade in from black in %s seconds")
def fade_in(seconds):
    for step in range(20):
        fade = 1 - (step + 1) / 20
        wait(seconds / 20)


@block("fly camera to x %s y %s z %s turn %s tilt %s in %s seconds")
def fly_camera(x, y, z, turn, tilt, seconds):
    """Glides a free camera, for cutscenes. Use camera back to player at the end."""
    if camera_mode != 1:
        camera_x = player_x
        camera_y = player_y + 1.6
        camera_z = player_z
        camera_yaw = player_yaw
        camera_pitch = player_pitch
        camera_mode = 1
    start_x = camera_x
    start_y = camera_y
    start_z = camera_z
    start_turn = camera_yaw
    start_tilt = camera_pitch
    start_time = timer()
    progress = 0
    while progress < 1:
        progress = (timer() - start_time) / seconds
        if progress > 1:
            progress = 1
        eased = progress * progress * (3 - 2 * progress)
        camera_x = start_x + (x - start_x) * eased
        camera_y = start_y + (y - start_y) * eased
        camera_z = start_z + (z - start_z) * eased
        camera_yaw = start_turn + (turn - start_turn) * eased
        camera_pitch = start_tilt + (tilt - start_tilt) * eased
        wait(0)


@block("camera back to player")
def camera_back():
    camera_mode = 0
    controls = 1


@block("save game to slot %s")
def save_slot(slot):
    """Saves the level, where the player is, the checkpoint, which things are collected or open, and everything in the save data list. It stays in this browser, even after closing it."""
    make_save_text()
    store_ns(GAME_ID)
    store_set(join("slot ", slot), save_text)
    show_message_for("Game saved", 1.5)


@block("load game from slot %s")
def load_slot(slot):
    """Puts the player back where the save was made. Sets save found to 0 if the slot is empty."""
    store_ns(GAME_ID)
    save_text = store_get(join("slot ", slot))
    use_save_text()


@block("delete save slot %s")
def delete_slot(slot):
    store_ns(GAME_ID)
    store_remove(join("slot ", slot))


@block("make save code")
def make_save_code():
    """Puts the whole save into save code as digits only, so it fits in a cloud variable or can be written down."""
    make_save_text()
    encode_save()


@block("load save code %s")
def load_save_code(code):
    decode_save(code)
    use_save_text()


@warp
@block("add %s to save text")
def save_field(value):
    save_text = join(join(save_text, value), ";")


@warp
@block("make save text")
def make_save_text():
    save_text = "LH1;"
    save_field(level)
    save_field(round(player_x * 100) / 100)
    save_field(round(player_y * 100) / 100)
    save_field(round(player_z * 100) / 100)
    save_field(round(player_yaw))
    save_field(checkpoint_x)
    save_field(checkpoint_y)
    save_field(checkpoint_z)
    save_field(checkpoint_yaw)
    flags = ""
    for item in range(len(obj_visible)):
        flags = join(flags, obj_visible[item + 1])
    save_field(flags)
    flags = ""
    for item in range(len(obj_open)):
        flags = join(flags, round(obj_open[item + 1]))
    save_field(flags)
    for item in range(len(save_data)):
        save_text = join(join(save_text, save_data[item + 1]), "|")


@warp
@block("split save text")
def split_save_text():
    save_fields.clear()
    piece = ""
    for item in range(strlen(save_text)):
        character = letter(item + 1, save_text)
        if character == ";":
            save_fields.append(piece)
            piece = ""
        else:
            piece = join(piece, character)
    save_fields.append(piece)


@block("use save text")
def use_save_text():
    split_save_text()
    if save_fields[1] != "LH1":
        save_found = 0
    else:
        save_found = 1
        if level != save_fields[2]:
            go_to_level = save_fields[2]
            while level != save_fields[2]:
                wait(0)
            wait(1)
        apply_save_text()


@warp
@block("apply save text")
def apply_save_text():
    player_x = save_fields[3]
    player_y = save_fields[4]
    player_z = save_fields[5]
    player_yaw = save_fields[6]
    checkpoint_x = save_fields[7]
    checkpoint_y = save_fields[8]
    checkpoint_z = save_fields[9]
    checkpoint_yaw = save_fields[10]
    if strlen(save_fields[11]) == len(obj_visible):
        for item in range(len(obj_visible)):
            obj_visible[item + 1] = letter(item + 1, save_fields[11])
    if strlen(save_fields[12]) == len(obj_open):
        for item in range(len(obj_open)):
            obj_open[item + 1] = letter(item + 1, save_fields[12])
    save_data.clear()
    piece = ""
    for item in range(strlen(save_fields[13])):
        character = letter(item + 1, save_fields[13])
        if character == "|":
            save_data.append(piece)
            piece = ""
        else:
            piece = join(piece, character)


@warp
@block("encode save text")
def encode_save():
    save_code = ""
    for item in range(strlen(save_text)):
        character = letter(item + 1, save_text)
        position = 1
        while position < 64 and letter(position, CODE_CHARS) != character:
            position += 1
        save_code = join(save_code, position + 10)


@warp
@block("decode save code %s")
def decode_save(code):
    save_text = ""
    for item in range(floor(strlen(code) / 2)):
        position = join(letter(item * 2 + 1, code), letter(item * 2 + 2, code)) - 10
        save_text = join(save_text, letter(position, CODE_CHARS))
