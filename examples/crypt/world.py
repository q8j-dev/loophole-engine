from loophole import Game

game = Game("Crypt Crawl", camera="top down", camera_distance=10.0, camera_pitch=62, walk_speed=5.5)
game.script("game.py")

c = game.level("Crypt")
c.outdoor(sky="night", sun=(0.35, 0.7, -0.4), fog=0.004, clouds=0.25)
c.grade(1.05, 0.97, 0.9, saturation=1.05)

c.solid(-2, -1, -36, 24, 0, 12, material="cobble")


def wall(x0, z0, x1, z1, h=3.5):
    c.solid(x0, 0, z0, x1, h, z1, material="stone")


wall(-2, 10, 24, 12)
wall(-2, -36, 24, -34)
wall(-2, -36, 0, 12)
wall(22, -36, 24, 12)
wall(0, -2, 9, 0)
wall(13, -2, 22, 0)
wall(0, -24, 10, -22)
wall(12, -24, 22, -22)
for x in (5, 11, 17):
    for z in (-7, -17):
        c.solid(x - 0.5, 0, z - 0.5, x + 0.5, 4.0, z + 0.5, material="stone")
c.paint("planks", 9, 0, -2, 13, 0.01, 0, facing="+y")

c.spawn(11, 0, 7, yaw=0)

c.prop("oillamp", 2, 0, 9, yaw=30)
c.prop("oillamp", 20, 0, 9, yaw=-40)
c.prop("candlestick", 7.6, 0, 1.0)
c.prop("candlestick", 14.4, 0, 1.0)
c.prop("woodbarrel", 1.2, 0, 2.2)
c.prop("woodcrate", 20.6, 0, 2.0, yaw=15)
c.prop("bucket", 19.4, 0, 1.4)
c.prop("statue", 1.2, 0, -12, yaw=90, scale=0.9)
c.prop("catstatue", 20.8, 0, -12, yaw=-90, scale=1.6)
c.prop("firepit", 11, 0, -12)
c.prop("candlestick", 5, 4.0, -7)
c.prop("candlestick", 17, 4.0, -7)
c.prop("candlestick", 5, 4.0, -17)
c.prop("candlestick", 17, 4.0, -17)
c.prop("oillamp", 1, 0, -21, yaw=45)
c.prop("oillamp", 21, 0, -3, yaw=-120)
c.prop("winebarrel", 21, 0, -20.5, yaw=90)
c.prop("rock", 2, 0, -4, yaw=20, scale=0.6)
c.prop("candlestick", 6, 0, -27)
c.prop("candlestick", 16, 0, -27)
c.prop("oillamp", 4, 0, -33, yaw=20)
c.prop("oillamp", 18, 0, -33, yaw=-20)
c.prop("woodcrate", 2, 0, -30, yaw=40)
c.prop("goblet", 13.5, 0, -32.5, yaw=10)

c.pickup("goblet1", "goblet", 2, 0.4, -9, scale=2.4, spin=90)
c.pickup("goblet2", "goblet", 20, 0.4, -19, scale=2.4, spin=90)
c.pickup("goblet3", "goblet", 11, 0.4, -20.5, scale=2.4, spin=90)

c.object("rat1", "rat", 2, 0, -5, scale=9, solid=False, path=[(2, 0, -5), (20, 0, -5)], speed=2.6)
c.object("rat2", "rat", 20, 0, -12, scale=9, solid=False, path=[(20, 0, -12), (14, 0, -12), (14, 0, -19), (8, 0, -19), (8, 0, -12), (2, 0, -12)], speed=2.2)
c.object("rat3", "rat", 2, 0, -15, scale=9, solid=False, path=[(2, 0, -15), (2, 0, -20), (20, 0, -20), (20, 0, -15)], speed=3.0)

c.object("gate", "statue", 11, 0, -23, scale=1.35, kind=1, slide=-3.6, open_speed=0.5, solid=True, yaw=180)
c.object("chest", "treasure", 11, 0, -31, scale=1.0, solid=True)
c.goal(9, 0, -30.5, 13, 3, -28.5, paint=False)
