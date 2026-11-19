from loophole import Game

game = Game("Autumn Woods")

w = game.level("Woods")
w.outdoor(sky="day", sun=(0.5, 0.62, 0.35), fog=0.004)
w.wind((1.0, 0.3), strength=0.8)
w.terrain(-60, -60, 60, 60, hills=4.0, seed=8, grass_style="forest")
w.spawn(0, 0, 22, yaw=0)
w.path((0, 26), (0, 5), (-6, -10), (-4, -40), width=2.2, material="dirt")
w.forest(-45, -45, 45, 16, kind="autumn")
w.forest(-45, 16, -8, 45, kind="pine", density=0.8, seed=5)
