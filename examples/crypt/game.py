@when_broadcast("level start")
def begin():
    goblets = 0
    beaten = 0
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
    obj_mode[index_of(obj_name, name)] = "follow"
    message = "A skeleton spotted you! Press F to fight"


def give_up(name):
    wait(3)
    number = index_of(obj_name, name)
    if obj_mode[number] == "follow" and obj_sees_player[number] == 0 and obj_health[number] > 0:
        obj_mode[number] = "patrol"


@when_broadcast("sees skeleton1")
def chase1():
    chase("skeleton1")


@when_broadcast("sees skeleton2")
def chase2():
    chase("skeleton2")


@when_broadcast("sees skeleton3")
def chase3():
    chase("skeleton3")


@when_broadcast("lost skeleton1")
def lost1():
    give_up("skeleton1")


@when_broadcast("lost skeleton2")
def lost2():
    give_up("skeleton2")


@when_broadcast("lost skeleton3")
def lost3():
    give_up("skeleton3")


@when_broadcast("player hurt")
def hurt():
    show_status()
    if health > 0:
        message = "Ouch!"


@when_broadcast("defeated")
def beat_one():
    beaten += 1
    message = join(join("Skeletons beaten: ", beaten), "/3")


@when_broadcast("player died")
def died():
    message = "The skeletons got you..."
    wait(2)
    show_status()


@when_broadcast("game complete")
def won():
    controls = 0
    message = "You found the crypt's treasure!"
    wait(2)
    for i in range(50):
        fade = (i + 1) / 50 * 0.85
        wait(0.03)
    message = "Crypt Crawl  -  made with Loophole Engine"
