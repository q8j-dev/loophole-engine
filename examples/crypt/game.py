@when_broadcast("level start")
def begin():
    goblets = 0
    health = 3
    hurt = 0
    alive = 1
    controls = 1
    fade = 0
    message = "Find the 3 golden goblets"
    show_status()


def show_status():
    status = join(join(join("Health ", health), "     Goblets "), join(goblets, "/3"))


@when_broadcast("collect")
def got_goblet():
    goblets += 1
    show_status()
    if goblets == 3:
        message = "The statue sinks. The vault is open!"
        obj_open[index_of(obj_name, "gate")] = 1
    else:
        message = join(3 - goblets, " goblets left")


def chase(name):
    if alive == 1:
        obj_mode[index_of(obj_name, name)] = "follow"
        message = "A rat spotted you!"


def give_up(name):
    wait(2)
    rat_number = index_of(obj_name, name)
    if obj_mode[rat_number] == "follow" and obj_sees_player[rat_number] == 0:
        obj_mode[rat_number] = "patrol"


@when_broadcast("sees rat1")
def chase1():
    chase("rat1")


@when_broadcast("sees rat2")
def chase2():
    chase("rat2")


@when_broadcast("sees rat3")
def chase3():
    chase("rat3")


@when_broadcast("lost rat1")
def lost1():
    give_up("rat1")


@when_broadcast("lost rat2")
def lost2():
    give_up("rat2")


@when_broadcast("lost rat3")
def lost3():
    give_up("rat3")


@when_broadcast("touch")
def bitten():
    if alive == 1 and hurt == 0 and "rat" in last_touched:
        biter = index_of(obj_name, last_touched)
        obj_mode[biter] = "flee"
        hurt = 1
        health -= 1
        flash = 0.8
        show_status()
        if health <= 0:
            alive = 0
            controls = 0
            message = "The rats got you..."
            wait(1.5)
            for i in range(30):
                fade = (i + 1) / 30
                wait(0.02)
            go_to_level = 1
        else:
            message = "Ouch! A rat bit you"
            wait(1.2)
            hurt = 0
            obj_mode[biter] = "patrol"


@when_broadcast("game complete")
def won():
    controls = 0
    message = "You found the crypt's treasure!"
    wait(2)
    for i in range(50):
        fade = (i + 1) / 50 * 0.85
        wait(0.03)
    message = "Crypt Crawl  -  made with Loophole Engine"
