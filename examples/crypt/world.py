from loophole import Game

game = Game("Crypt Crawl", camera="top down", camera_distance=5.5, camera_pitch=56, walk_speed=5.5, player_model="knight")
game.script("game.py")

c = game.level("Crypt")
c.style("dungeon")
c.cutaway(2.6)
c.grade(0.9, 0.96, 1.14, saturation=0.92, exposure=1.0, auto_exposure=0.2)

c.room(0, 0, 0, 22, 4, 10)
c.room(0, 0, -22, 22, 5, -2)
c.room(2, 0, -34, 20, 4, -24)
c.room(9, 0, -2, 13, 2.5, 0)
c.room(9.5, 0, -2, 12.5, 3.0, 0)
c.room(10, 0, -2, 12, 3.5, 0)
c.room(10, 0, -24, 12, 3.0, -22)
c.spawn(11, 0, 7, yaw=0)


def column(x, z, h):
    c.solid(x - 0.75, 0, z - 0.75, x + 0.75, 0.5, z + 0.75, material="stone")
    c.solid(x - 0.5, 0.5, z - 0.5, x + 0.5, h - 0.5, z + 0.5, material="rock")
    c.solid(x - 0.75, h - 0.5, z - 0.75, x + 0.75, h, z + 0.75, material="stone")


for x in (4.5, 17.5):
    for z in (-6.5, -12, -17.5):
        column(x, z, 5)
for x in (3.5, 18.5):
    column(x, 5, 4)
c.solid(9.5, 0, -12.5, 12.5, 0.5, -11.5, material="stone")

c.prop("firepit", 11, 0.5, -12, flicker=0.35)
c.prop("candlestick", 4.5, 0.5, -6.5, flicker=0.5)
c.prop("candlestick", 17.5, 0.5, -17.5, flicker=0.5)
c.prop("candlestick", 4.5, 0.5, -17.5, flicker=0.5)
c.prop("candlestick", 17.5, 0.5, -6.5, flicker=0.5)
c.prop("oillamp", 0.8, 0, -21.2, yaw=45, flicker=0.3)
c.prop("oillamp", 21.2, 0, -2.8, yaw=-120, flicker=0.3)
c.prop("oillamp", 1.0, 0, 9.0, yaw=30, flicker=0.3)
c.prop("candlestick", 9.2, 0, 0.6, flicker=0.5)
c.prop("candlestick", 12.8, 0, 0.6, flicker=0.5)
c.prop("candlestick", 6, 0, -25, flicker=0.5)
c.prop("candlestick", 16, 0, -25, flicker=0.5)
c.prop("oillamp", 3, 0, -33, yaw=20, flicker=0.3)
c.prop("oillamp", 19, 0, -33, yaw=-20, flicker=0.3)
c.spot(11, 4.6, -29, target=(11, 0, -31), color="amber", power=30, cone=(14, 26), haze=1.2, fixture=False)
for (lx, ly, lz) in ((5, 3.7, 5), (17, 3.7, 5), (5, 4.7, -6), (17, 4.7, -6), (5, 4.7, -18), (17, 4.7, -18),
                     (11, 4.7, -12), (7, 3.7, -29), (15, 3.7, -29)):
    c.light(lx, ly, lz, color="blue", power=4.5, fixture=None)

c.prop("woodbarrel", 1.0, 0, 1.0)
c.prop("woodbarrel", 1.9, 0, 0.8, yaw=40)
c.prop("woodcrate", 21.0, 0, 1.2, yaw=15)
c.prop("bucket", 19.8, 0, 0.7)
c.prop("statue", 1.2, 0, -12, yaw=90, scale=1.1)
c.prop("catstatue", 20.9, 0, -12, yaw=-90, scale=2.0)
c.prop("winebarrel", 21, 0, -20.6, yaw=90)
c.prop("rock", 1.5, 0, -3.5, yaw=20, scale=0.7)
c.prop("rock", 20, 0, -8.5, yaw=80, scale=0.5)
c.prop("woodcrate", 3, 0, -30, yaw=40)
c.prop("woodcrate", 3.2, 0.9, -30.3, yaw=10)
c.prop("goblet", 13.0, 0, -32.8, yaw=10, scale=1.4)
c.prop("candlestick", 13.8, 0, -32.6, flicker=0.6)

c.pickup("goblet1", "goblet", 1.6, 0.5, -8.5, scale=2.4, spin=90)
c.pickup("goblet2", "goblet", 20.4, 0.5, -19.5, scale=2.4, spin=90)
c.pickup("goblet3", "goblet", 11, 0.5, -20.6, scale=2.4, spin=90)

rat = dict(scale=11, solid=False, highlight=(0.35, 0.03, 0.01), mode="patrol", sight=7, fov=150)
c.object("rat1", "rat", 2, 0, -4.5, path=[(2, 0, -4.5), (20, 0, -4.5)], speed=2.6, **rat)
c.object("rat2", "rat", 20, 0, -9.5, path=[(20, 0, -9.5), (14.5, 0, -9.5), (14.5, 0, -15), (7.5, 0, -15),
                                         (7.5, 0, -9.5), (2, 0, -9.5)], speed=2.2, **rat)
c.object("rat3", "rat", 2, 0, -15, path=[(2, 0, -15), (2, 0, -20), (20, 0, -20), (20, 0, -15)], speed=2.8, **rat)

c.object("gate", "statue", 11, 0, -23, scale=1.35, kind=1, slide=-3.6, open_speed=0.5, solid=True, yaw=180)
c.object("chest", "treasure", 11, 0, -31, scale=1.6, solid=True, highlight=(0.5, 0.36, 0.1))
c.goal(9.5, 0, -30, 12.5, 3, -28.5, paint=False)

intro = c.cutscene("intro", play_at_start=True)
intro.camera(0, (11, 2.4, -25.5), turn=0, tilt=-12)
intro.camera(3.5, (6, 3.6, -14), turn=120, tilt=-22)
intro.camera(7, (11, 3.3, 9.2), turn=0, tilt=-32)
intro.subtitle(0.4, "Deep under the old chapel lies a treasure vault", duration=3)
intro.subtitle(3.8, "Find the 3 golden goblets. Watch out for the rats!", duration=3)
