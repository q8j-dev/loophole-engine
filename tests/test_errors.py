import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loophole.build import build

ROOT = Path(__file__).resolve().parent.parent
WORLD = (ROOT / "loophole" / "templates" / "starter" / "world.py").read_text(encoding="utf-8")
GAME = 'def show(n):\n    message = n\n\n\n@when_broadcast("level start")\ndef begin():\n    show("hi")\n    status = "ok"\n'

WORLD_CASES = [
    ("lab.room(5, 0, -6", "lab.romo(5, 0, -6", "world.py line 7: levels don't have romo(). Did you mean room?"),
    ('game = Game("My Game")', 'game = Gme("My Game")', "world.py line 3: Gme isn't defined. Did you mean Game?"),
    ("lab.spawn(6, 0, 12, yaw=0)", "lab.spawn(6, 0, 12, yaw=0", "world.py line 8: Python can't read this line"),
    ('color="warm", power=55', 'colour="warm", power=55', "spot() has no setting called colour. Did you mean color?"),
    ("lab.room(0, 0, 0, 12, 6, 14)", "lab.room(0, 0, 0, 12, 6)", "room() needs more values. Missing: z1."),
    ('lab.prop("barrel"', 'lab.prop("barel"', "there's no prop called 'barel'. Did you mean barrel"),
    ('Game("My Game")', 'Game("My Game", camra="top down")', "Game() has no setting called camra. Did you mean camera?"),
]
GAME_CASES = [
    ('show("hi")', 'shwo("hi")', "game.py line 7: there's no block called shwo(). Did you mean show()?"),
    ('status = "ok"', "status = show(3)", "game.py line 8: show() can't give back a value."),
    ('show("hi")', 'show("hi"', "game.py line 7: Python can't read this line"),
    ('show("hi")', 'show("hi", 2)', "game.py line 7: show() needs 1 value but got 2."),
]


def message(world, game=None, cache=None):
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "world.py").write_text(world, encoding="utf-8")
        if game is not None:
            (Path(d) / "game.py").write_text(game, encoding="utf-8")
        try:
            build(Path(d) / "world.py", out=Path(d) / "out.sb3", log=lambda m: None, cache=cache)
        except SystemExit as e:
            return str(e)
    return ""


def main():
    failed = 0
    cache = tempfile.mkdtemp()
    for old, new, want in WORLD_CASES:
        got = message(WORLD.replace(old, new, 1), cache=cache)
        ok = want in got
        failed += not ok
        print(("PASS " if ok else "FAIL ") + want + ("" if ok else "\n     got: " + got))
    with_script = WORLD.replace('game = Game("My Game")', 'game = Game("My Game")\ngame.script("game.py")', 1)
    for old, new, want in GAME_CASES:
        got = message(with_script, GAME.replace(old, new, 1), cache=cache)
        ok = want in got
        failed += not ok
        print(("PASS " if ok else "FAIL ") + want + ("" if ok else "\n     got: " + got))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
