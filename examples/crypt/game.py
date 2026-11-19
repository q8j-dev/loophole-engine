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


@when_broadcast("touch")
def bitten():
    if alive == 1 and hurt == 0 and "rat" in last_touched:
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


@when_broadcast("game complete")
def won():
    controls = 0
    message = "You found the crypt's treasure!"
    wait(2)
    for i in range(50):
        fade = (i + 1) / 50 * 0.85
        wait(0.03)
    message = "Crypt Crawl  -  made with Loophole Engine"
