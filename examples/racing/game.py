LAPS = 3
CHECKPOINTS = 3


@when_broadcast("level start")
def begin():
    store_ns("kart-cup")
    best = store_get("best lap")
    if best == "":
        best = 0
    lap = 0
    racing = 0
    next_checkpoint = 1
    message = "Walk up to a kart and press E to drive"
    show_status()


def show_status():
    if best > 0:
        status = join(join(join("Lap ", lap), join("/", LAPS)), join("     Best lap ", join(round((best) * 10) / 10, " s")))
    else:
        status = join(join("Lap ", lap), join("/", LAPS))


@when_broadcast("enter vehicle")
def got_in():
    if racing == 0:
        message = "Drive through the start gate. W to go, A and D to steer, space to drift"


@when_broadcast("exit vehicle")
def got_out():
    if racing == 1:
        message = "Press E near the kart to get back in"


def checkpoint(number):
    if driving != "" and racing == 1 and next_checkpoint == number:
        next_checkpoint = number + 1
        sound_queue.append("pickup")


@when_broadcast("enter cp1")
def cp1():
    checkpoint(1)


@when_broadcast("enter cp2")
def cp2():
    checkpoint(2)


@when_broadcast("enter cp3")
def cp3():
    checkpoint(3)


@when_broadcast("enter start")
def crossed_start():
    if driving == "":
        return
    if racing == 0:
        racing = 1
        lap = 1
        next_checkpoint = 1
        lap_start = level_time
        message = "Go!"
        sound_queue.append("arrive")
        show_status()
    elif next_checkpoint > CHECKPOINTS:
        lap_time = level_time - lap_start
        lap_start = level_time
        next_checkpoint = 1
        if best == 0 or lap_time < best:
            best = lap_time
            store_set("best lap", best)
            message = join("New best lap! ", join(round((lap_time) * 10) / 10, " s"))
            sound_queue.append("success")
        else:
            message = join("Lap time ", join(round((lap_time) * 10) / 10, " s"))
            sound_queue.append("pickup")
        if lap == LAPS:
            racing = 2
            message = join("Race finished! Best lap ", join(round((best) * 10) / 10, " s"))
            sound_queue.append("success")
        else:
            lap += 1
        show_status()


@when_flag
def clock():
    while True:
        if racing == 1:
            status = join(join(join("Lap ", lap), join("/", LAPS)), join("     ", join(round((level_time - lap_start) * 10) / 10, " s")))
            if best > 0:
                status = join(status, join("     Best ", join(round((best) * 10) / 10, " s")))
        wait(0.1)
