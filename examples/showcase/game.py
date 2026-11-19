@when_flag
def start():
    viewmodel = "device"
    controls = 1
    fade = 0
    lanterns = 0
    finished = 0
    message = "Carry the cube to the button  (E to grab)"
    status = ""


@when_broadcast("level start")
def arrive():
    if level == 2:
        viewmodel = "lantern"
        message = "Find the 3 lost lanterns"
        status = "Lanterns 0/3"


@when_broadcast("press button")
def pressed():
    message = "The door is open"


@when_broadcast("release button")
def released():
    if level == 1:
        message = "Something has to stay on the button"


@when_broadcast("collect")
def found():
    lanterns += 1
    status = join(join("Lanterns ", lanterns), "/3")
    light_power[index_of(light_name, join("beacon", lanterns))] = 1
    flash = 0.35
    if lanterns == 3:
        message = "The house is lit. Head home."
    else:
        message = join(3 - lanterns, " lanterns still out there")


@when_broadcast("enter home")
def home():
    if lanterns == 3 and finished == 0:
        finished = 1
        controls = 0
        message = "Welcome home"
        status = ""
        wait(2.5)
        for i in range(60):
            fade = (i + 1) / 60
            wait(0.03)
        message = "Afterglow  -  made with Loophole Engine"
        broadcast("game complete")
