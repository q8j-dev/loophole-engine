import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2]))
import loophole.build as B

TEST = '''

@when_key("t")
def helper_test():
    move_object("cube", 2, 0, 2)
    turn_object("cube", 45)
    hide_object("button")
    open_object("door")
    switch_light("lamp1", 0)
    start_weather("rain")
    teleport_player(4, 0, 10)
    rumble_controller(0.5, 0.2)
    fade_out(0.2)
    seen_fade = fade
    fade_in(0.2)
    set_status(join("tested ", seen_fade))


@when_key("1")
def save_test():
    save_data.clear()
    save_data.append("score 7")
    save_data.append(42)
    save_slot(1)


@when_key("2")
def load_test():
    load_slot(1)


@when_key("3")
def code_test():
    make_save_code()


@when_key("4")
def code_load_test():
    load_save_code(save_code)
'''

orig = B.helpers_sprite
B.helpers_sprite = lambda A, proj, **kw: orig(A, proj, extra=TEST, **kw)
out = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "test.sb3"
if out.exists():
    out.unlink()
B.build(HERE / "world.py", out=out, cache=HERE.parents[2] / "build" / "helpertest-cache")
