import math
import random

from loophole import Game

game = Game("Afterglow", viewmodel="device", viewmodels=["lantern"], fov=74)
game.script("game.py")

lab = game.level("Intake")
lab.room(0, 0, 0, 16, 8, 20)
lab.room(7, 0, -8, 9, 3, 0)
lab.platform(0, 2, 4, 12, 3)
lab.stairs(0, 12, 4, 18, 3, direction="-z")
lab.paint("metal", 0, 3, 2, 4, 3, 12, facing="+y")
lab.spawn(11, 0, 17, yaw=-20)

for z in (3, 5, 7, 9, 11):
    lab.deco("railing", (4.4, 3, z), (0, 0, 1), (0, 1, 0), (1, 1, 1))
lab.strip(5, 7.95, 1, 5, 7.95, 19, power=22)
lab.strip(11, 7.95, 1, 11, 7.95, 19, power=22)
lab.spot(8, 7.4, 4, target=(11, 0, 6), color="warm", power=60, cone=(16, 28), haze=0.35)
lab.spot(2, 7.4, 8, target=(2, 3, 4), color="cool", power=30, cone=(18, 30), haze=0.25)
lab.window(16, 4, 6, 16, 7, 14, facing="-x")
lab.sign("INTAKE 07", 12.0, 4.4, 0, facing="+z", height=1.0)
lab.sign("EXIT", 8, 3.3, 0, facing="+z", height=0.45)
lab.pipe((15.6, 6.6, 0.4), (15.6, 6.6, 19.6))
lab.pipe((15.2, 7.2, 0.4), (15.2, 7.2, 19.6), radius=0.7)
lab.pipe((0.4, 7.0, 19.6), (15.6, 7.0, 19.6))

lab.prop("machine", 14.6, 0, 17.4, yaw=180)
lab.prop("tank", 14.8, 0, 2.2)
lab.prop("rack", 15.2, 0, 10, yaw=180)
lab.prop("terminal", 13.5, 0, 0.8, yaw=90)
lab.prop("crate", 5.2, 0, 18.8, yaw=8)
lab.prop("crate", 6.4, 0, 18.9, yaw=-4)
lab.prop("crate", 5.8, 1, 18.8, yaw=20)
lab.prop("barrel", 1, 3, 2.6)
lab.prop("toolbox", 3.2, 3, 10.8, yaw=30)
lab.prop("trolley", 12.6, 0, 14, yaw=60)
lab.wall_prop("breaker", 16, 1.5, 15, facing="-x")
lab.wall_prop("jbox", 0, 1.4, 14, facing="+x")
lab.wall_prop("fan", 0, 6, 16, facing="+x")
lab.wall_prop("panel", 4.5, 1.6, 0, facing="+z")

lab.cube("cube", 2, 3, 4)
lab.button("button", 11, 0, 6, opens="door")
lab.door("door", 8, 0, -0.6, facing="+z", width=2, height=3)
lab.goal(7, 0, -7.5, 9, 3, -5.5)

v = game.level("Valley")
v.outdoor(sky="dusk", sun=(-0.75, 0.18, -0.5), fog=0.0045)
v.terrain(-48, -48, 48, 48, hills=9.0, seed=7)
v.flatten(-18, -14, 18, 16, height=0.0, falloff=12)
v.building(-3, -11, 8, -3, door=("+z", 2.5), windows=[("+z", 6.0), ("+x", -7), ("-x", -7)])
v.prop("table", 2.5, 0, -7)
v.prop("chair", 1.5, 0, -7, yaw=90)
v.prop("bookshelf", -1.9, 0, -9.5, yaw=90)
v.prop("bed", 6, 0, -9.2, yaw=180)
v.prop("sconce", 7.3, 1.8, -5.5, yaw=-90)
v.trigger("home", -2.5, 0, -10.5, 7.5, 3, -3.5)
v.spawn(14, 0, 22, yaw=-35)

v.prop("walllamp", 0.6, 1.9, -2.55, light=True, name="beacon1", on=False)
v.prop("walllamp", 4.4, 1.9, -2.55, light=True, name="beacon2", on=False)
v.prop("streetlamp", 5.0, 0, 0.5, name="beacon3", on=False)

v.path((2.5, -2.5), (2.5, 3), (-3, 8), (-12, 12), (-24, 14), width=2.4)
v.path((2.5, 3), (10, 7), (14, 14), (16, 24), width=2.0)
v.path((10, 7), (20, 2), (28, -6), width=1.8)

rng = random.Random(9)


def clear(x, z):
    return not (-4.5 < x < 9.5 and -12.5 < z < -1.5) and abs(x - 2.75) + abs(z - 1) > 2.5


for i in range(16):
    a = rng.uniform(0, 6.28)
    r = rng.uniform(20, 38)
    v.prop(rng.choice(["oak", "pine", "pine", "birch"]), math.cos(a) * r, 0, math.sin(a) * r,
           yaw=rng.uniform(0, 360), scale=rng.uniform(0.85, 1.25))
for (x, z, k) in ((13, -8, "oak"), (-12, -3, "birch"), (-7, 4, "birch"), (19, 10, "oak"), (-16, 18, "pine")):
    v.prop(k, x, 0, z, yaw=x * 13)
for i in range(18):
    x, z = rng.uniform(-20, 22), rng.uniform(-16, 20)
    if clear(x, z):
        v.prop("bush", x, 0, z, yaw=rng.uniform(0, 360), scale=rng.uniform(0.7, 1.2))
for i in range(34):
    x, z = rng.uniform(-20, 22), rng.uniform(-14, 20)
    if clear(x, z):
        v.prop(rng.choice(["grass", "grass", "fern"]), x, 0, z, yaw=rng.uniform(0, 360))
for (x, z, s) in ((8, 11, 1.1), (-15, 1, 0.8), (22, -1, 1.4), (-6, 15, 0.7), (26, -9, 1.0)):
    v.prop("boulder", x, 0, z, yaw=x * 31, scale=s)
v.prop("rock", 6, 0, 9, yaw=40)
v.prop("stump", -10, 0, 9)
v.prop("firepit", 11, 0, 0)
v.prop("bench", 11, 0, 2.2, yaw=180)
v.prop("woodbarrel", 10.5, 0, -2.5)
v.prop("woodcrate", 11.6, 0, -2.8, yaw=20)
v.prop("streetlamp", -8, 0, 10.5)

v.pickup("lantern1", "lantern", -23, 0.9, 14, scale=1.5, glow=2.0)
v.pickup("lantern2", "lantern", 27, 0.9, -6.5, scale=1.5, glow=2.0)
v.pickup("lantern3", "lantern", -15, 0.9, 3, scale=1.5, glow=2.0)
