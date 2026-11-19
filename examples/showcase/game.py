@when_flag
def start():
    viewmodel = "device"
    lanterns = 0
    message = "Put the cube on the button"
    status = ""


@when_broadcast("level start")
def arrive():
    if level == 2:
        viewmodel = "lantern"
        message = "Find the 3 lanterns"
        status = "Lanterns 0/3"


@when_broadcast("collect")
def found():
    lanterns += 1
    status = join(join("Lanterns ", lanterns), "/3")
    light_power[index_of(light_name, join("beacon", lanterns))] = 1
    if lanterns == 3:
        message = "Go home"
    else:
        message = join(3 - lanterns, " more lanterns")


@when_broadcast("enter home")
def home():
    if lanterns == 3:
        message = "Welcome home"
        broadcast("game complete")
