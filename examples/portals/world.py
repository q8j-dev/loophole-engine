from loophole import Game

game = Game("Portal Lab", viewmodel="device", portals=True)
game.script("game.py")

lab = game.level("Ledge")
lab.style("lab")
lab.room(0, 0, 0, 16, 9, 18)
lab.platform(0, 0, 16, 5, 4.5)
lab.paint("metal", 0, 0, 5, 16, 4.5, 5, facing="+z")
lab.spawn(8, 0, 16, yaw=0)
lab.strip(4, 8.95, 1, 4, 8.95, 17, power=30)
lab.strip(12, 8.95, 1, 12, 8.95, 17, power=30)
lab.spot(8, 8.6, 9, target=(8, 4.5, 2), color="warm", power=50, cone=(16, 30))
lab.sign("PORTALS", 8, 6.8, 0, facing="+z", height=1.0)
lab.prop("crate", 1.5, 0, 16.5, yaw=10)
lab.prop("barrel", 14.5, 0, 16.6)
lab.goal(6.5, 4.5, 0.5, 9.5, 7.5, 2.5)
