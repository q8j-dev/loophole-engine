import json
import shutil
import tempfile
import zipfile
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loophole.build import API_VARS, build, hid

ROOT = Path(__file__).resolve().parent.parent
STARTER = ROOT / "loophole" / "templates" / "starter"


def read(p):
    with zipfile.ZipFile(p) as z:
        return json.loads(z.read("project.json")), {n: z.read(n) for n in z.namelist() if n != "project.json"}


def write(p, pj, files):
    with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("project.json", json.dumps(pj))
        for n, d in files.items():
            z.writestr(n, d)


def user_sprite(stage):
    px_id = next(k for k, v in stage["variables"].items() if v[0] == "player x")
    stage["variables"]["userScoreVar0001"] = ["score", 0]
    blocks = {
        "hat000000000000000001": {"opcode": "event_whenflagclicked", "next": "set000000000000000001", "parent": None,
                                  "inputs": {}, "fields": {}, "shadow": False, "topLevel": True, "x": 0, "y": 0},
        "set000000000000000001": {"opcode": "data_setvariableto", "next": "chg000000000000000001",
                                  "parent": "hat000000000000000001", "inputs": {"VALUE": [1, [10, "3"]]},
                                  "fields": {"VARIABLE": ["player x", px_id]}, "shadow": False, "topLevel": False},
        "chg000000000000000001": {"opcode": "data_changevariableby", "next": None, "parent": "set000000000000000001",
                                  "inputs": {"VALUE": [1, [4, "1"]]}, "fields": {"VARIABLE": ["score", "userScoreVar0001"]},
                                  "shadow": False, "topLevel": False},
    }
    svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><rect width="10" height="10" fill="red"/></svg>'
    return {"isStage": False, "name": "Hero", "variables": {}, "lists": {}, "broadcasts": {}, "blocks": blocks,
            "comments": {}, "currentCostume": 0,
            "costumes": [{"name": "c", "bitmapResolution": 1, "dataFormat": "svg", "assetId": "a" * 32,
                          "md5ext": "a" * 32 + ".svg", "rotationCenterX": 5, "rotationCenterY": 5}],
            "sounds": [], "volume": 100, "layerOrder": 5, "visible": True, "x": 10, "y": 20, "size": 100,
            "direction": 90, "draggable": False, "rotationStyle": "all around"}, svg


def test_rebuild_keeps_user_work():
    with tempfile.TemporaryDirectory() as td:
        proj = Path(td) / "game"
        shutil.copytree(STARTER, proj, ignore=shutil.ignore_patterns("*.sb3", ".loophole"))
        out = proj / "game.sb3"
        build(proj / "world.py", out=out, log=lambda *a: None)
        pj, files = read(out)
        stage = next(t for t in pj["targets"] if t["isStage"])
        sprite, svg = user_sprite(stage)
        pj["targets"].append(sprite)
        files["a" * 32 + ".svg"] = svg
        overlay = next(t for t in pj["targets"] if t["name"] == "Overlay")
        overlay["x"] = 123
        write(out, pj, files)
        build(proj / "world.py", out=out, log=lambda *a: None)
        pj2, files2 = read(out)
        names = [t["name"] for t in pj2["targets"]]
        assert names.count("Engine") == 1
        hero = next(t for t in pj2["targets"] if t["name"] == "Hero")
        assert hero["blocks"] == sprite["blocks"]
        assert "a" * 32 + ".svg" in files2
        assert next(t for t in pj2["targets"] if t["name"] == "Overlay")["x"] == 123
        stage2 = next(t for t in pj2["targets"] if t["isStage"])
        assert stage2["variables"]["userScoreVar0001"][0] == "score"
        px_id = hero["blocks"]["set000000000000000001"]["fields"]["VARIABLE"][1]
        assert stage2["variables"][px_id][0] == "player x"
        assert px_id == hid("lhv", "player x")
        for n in API_VARS.values():
            assert any(v[0] == n for v in stage2["variables"].values()), n


if __name__ == "__main__":
    test_rebuild_keeps_user_work()
    print("merge test passed")
