@when_broadcast("level start")
def begin():
    message = "Left and right click make portals. Bring the cube across the slime."
    status = ""


@when_broadcast("press button")
def opened():
    message = "The exit is open"


@when_broadcast("game complete")
def done():
    message = "Portal Lab complete"
