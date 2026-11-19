import random

from loophole import Game

game = Game("Orchard Dash", camera="third person", camera_distance=5.0, walk_speed=7.0)
game.script("game.py")

o = game.level("Orchard")
o.outdoor(sky="day", sun=(0.45, 0.8, 0.35), fog=0.0022, clouds=0.55)
o.grade(1.02, 1.0, 0.97, saturation=1.12)
o.terrain(-50, -50, 50, 50, hills=6.0, seed=23)
o.flatten(-24, -24, 24, 24, height=0.0, falloff=14)
o.spawn(0, 0, 20, yaw=0)

o.building(14, -30, 24, -22, height=3.5, walls="planks", inside="planks", floor="planks", roof="roof",
           door=("+z", 19), windows=[("-x", -26)], pitch=38, trim="wood", plinth="stone")
o.prop("woodcrate", 12.8, 0, -20.6, yaw=12)
o.prop("woodcrate", 13.9, 0, -20.9, yaw=-8)
o.prop("woodcrate", 13.3, 0.9, -20.7, yaw=30)
o.prop("woodbarrel", 25, 0, -21)
o.prop("winebarrel", 25.3, 0, -24, yaw=90)
o.prop("toolcart", 9.5, 0, -24, yaw=70)
o.prop("bucket", 11.5, 0, -21.6)
o.prop("bench", -6, 0, 22, yaw=180)

for z in (-14, -2, 10):
    o.path((-30, z + 3), (30, z + 3), width=2.2, material="dirt")
o.path((0, 24), (0, -20), (8, -24), (19, -21), width=2.6, material="gravel")

rng = random.Random(5)
for ix, x in enumerate((-18, -11, -4, 4, 11, 18)):
    for z in (-14, -2, 10):
        o.prop("oak", x + rng.uniform(-0.6, 0.6), 0, z + rng.uniform(-0.6, 0.6), yaw=rng.uniform(0, 360),
               scale=rng.uniform(0.62, 0.72))
for i in range(12):
    a = i / 12 * 6.283
    r = rng.uniform(32, 42)
    import math
    o.prop(rng.choice(["pine", "birch", "pine"]), math.cos(a) * r, 0, math.sin(a) * r, yaw=rng.uniform(0, 360),
           scale=rng.uniform(0.9, 1.2))
for i in range(40):
    x, z = rng.uniform(-24, 24), rng.uniform(-20, 22)
    if abs(x) > 1.8 and not (8 < x < 27 and -32 < z < -19):
        o.prop(rng.choice(["grass", "grass", "fern", "bush"]), x, 0, z, yaw=rng.uniform(0, 360),
               scale=rng.uniform(0.7, 1.1))
for (x, z, s) in ((-26, 8, 1.2), (27, 4, 0.9), (-22, -22, 1.4)):
    o.prop("boulder", x, 0, z, yaw=x * 17, scale=s)

spots = [(-14.5, -11), (-7.5, -11), (0.5, -11), (7.5, -11), (14.5, -11),
         (-14.5, 1), (-7.5, 1), (7.5, 1), (14.5, 1),
         (-7.5, 13), (7.5, 13), (21, -18)]
for i, (x, z) in enumerate(spots):
    o.pickup(f"apple{i + 1}", "apple", x, 0.35, z, scale=3.2, spin=120)

o.object("rat1", "rat", -20, 0, -11, scale=6, solid=False, path=[(-20, 0, -11), (20, 0, -11)], speed=2.4)
o.object("rat2", "rat", 20, 0, 1, scale=6, solid=False, path=[(20, 0, 1), (-20, 0, 1)], speed=3.0)
o.object("rat3", "rat", -20, 0, 13, scale=6, solid=False, path=[(-20, 0, 13), (20, 0, 13)], speed=3.4)
