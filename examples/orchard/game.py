@when_broadcast("level start")
def begin():
    apples = 0
    time_left = 75
    playing = 1
    controls = 1
    fade = 0
    message = "Grab all 12 apples before sunset. Watch for rats!"
    show_status()
    while playing == 1:
        wait(1)
        if playing == 1:
            time_left -= 1
            show_status()
            if time_left == 60:
                message = ""
            if time_left <= 0:
                playing = 0
                lose()


def show_status():
    status = join(join(join("Apples ", apples), "/12     Time "), time_left)


@when_broadcast("collect")
def got_apple():
    if playing == 1:
        apples += 1
        show_status()
        if apples == 12:
            playing = 0
            controls = 0
            message = join(join("Orchard cleared with ", time_left), " seconds to spare!")
            broadcast("game complete")


@when_broadcast("touch")
def bumped():
    if playing == 1 and "rat" in last_touched:
        time_left -= 5
        flash = 0.6
        message = "A rat bit you! -5 seconds"
        show_status()


def lose():
    controls = 0
    message = "Out of time! Trying again..."
    wait(2)
    for i in range(30):
        fade = (i + 1) / 30
        wait(0.02)
    go_to_level = 1
