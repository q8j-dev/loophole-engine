from loophole import Game

game = Game("My Game")

lab = game.level("Lab")
lab.room(0, 0, 0, 12, 6, 14)
lab.room(5, 0, -6, 7, 3, 0)
lab.spawn(6, 0, 12, yaw=0)

lab.strip(3, 5.95, 1, 3, 5.95, 13, power=26)
lab.strip(9, 5.95, 1, 9, 5.95, 13, power=26)
lab.spot(6, 5.6, 3.6, target=(6, 1.4, 0), color="warm", power=55, cone=(18, 30))
lab.window(12, 3.6, 4, 12, 5.4, 8, facing="-x")
lab.sign("01", 9.6, 3.3, 0, facing="+z")

lab.prop("crate", 1, 0, 12.5, yaw=10)
lab.prop("crate", 1, 1, 12.6, yaw=-5)
lab.prop("barrel", 2.2, 0, 13.1)
lab.wall_prop("jbox", 0, 1.6, 8, facing="+x")

lab.cube("cube", 9, 0, 9)
lab.button("button", 3, 0, 4, opens="door")
lab.door("door", 6, 0, -0.6, facing="+z", width=2, height=3)
lab.goal(5, 0, -5.5, 7, 3, -3.5)
