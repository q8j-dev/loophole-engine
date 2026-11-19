@when_broadcast("level start")
def begin():
    message = "Left click and right click make portals"
    status = ""


@when_broadcast("portal")
def placed():
    message = "Walk through one portal to come out of the other"


@when_broadcast("game complete")
def done():
    message = "You reached the ledge!"
