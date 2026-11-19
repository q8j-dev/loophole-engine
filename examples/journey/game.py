@when_broadcast("level start")
def begin():
    if level == 1:
        found = 0
        message = "Gather the 3 golden apples along the path"
        status = "Apples 0/3"
    elif level == 2:
        message = "Find the relic on the far shore. You can swim across."
        status = ""
    else:
        message = "Climb to the cabin before the storm"
        status = ""


@when_broadcast("collect")
def got():
    if level == 1:
        found += 1
        status = join(join("Apples ", found), "/3")
        if found == 3:
            message = "Follow the path out of the woods"
    else:
        message = "Relic found. The path continues south."


@when_broadcast("game complete")
def done():
    controls = 0
    message = "Home, warm by the fire"
    wait(2)
    for i in range(50):
        fade = (i + 1) / 50 * 0.85
        wait(0.03)
    message = "The Long Walk  -  made with Loophole Engine"
