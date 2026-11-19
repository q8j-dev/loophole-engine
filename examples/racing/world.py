from loophole import Game

game = Game("Kart Cup", camera="third person", camera_distance=5.0, player_model="rogue")
game.script("game.py")

t = game.level("Hillside Ring")
t.outdoor(sky="day", sun=(0.5, 0.72, 0.4), fog=0.002, clouds=0.5)
t.grade(1.02, 1.0, 0.98, saturation=1.1)
t.terrain(-65, -65, 65, 65, hills=4.0, seed=31, grass_style="meadow")

track = t.road((0, 34), (30, 32), (48, 14), (43, -15), (21, -27), (3, -14), (-14, -32), (-40, -26), (-50, 0),
               (-34, 24), width=8)
track.checkpoints(3)
track.cones()

t.spawn(-9, 0, 39, yaw=100)
t.vehicle("kart", "kart", -9.7, 0, 34.3, yaw=100)
t.vehicle("kart2", "kart_pink", -13.2, 0, 29.9, yaw=100)
t.vehicle("kart3", "kart_yellow", -18.4, 0, 32.4, yaw=103)
t.vehicle("kart4", "kart_green", -21.8, 0, 27.6, yaw=103)

t.prop("bench", -4, 0, 44, yaw=180)
t.prop("bench", 2, 0, 44, yaw=180)
t.prop("streetlamp", -9, 0, 43)
t.prop("streetlamp", 8, 0, 43)
t.prop("toolcart", 13, 0, 43, yaw=200)
t.prop("woodbarrel", 15, 0, 42.5)
t.prop("woodcrate", 16.2, 0, 43.3, yaw=20)

t.forest(-65, 46, 65, 65, kind="broadleaf", density=0.5, undergrowth=False, seed=2)
t.forest(-65, -65, 65, -40, kind="mixed", density=0.5, undergrowth=False, seed=3)
t.forest(58, -40, 65, 46, kind="broadleaf", density=0.5, undergrowth=False, seed=4)
t.forest(-65, -40, -58, 46, kind="mixed", density=0.5, undergrowth=False, seed=5)
t.forest(-28, -12, 30, 18, kind="broadleaf", density=0.12, undergrowth=False, seed=6)
t.scatter(["boulder", "rock", "mossrock"], -60, -60, 60, 60, spacing=16)
