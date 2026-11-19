import argparse
import json
import shutil
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EXAMPLES = [
    ("starter", "Starter lab", ROOT / "loophole" / "templates" / "starter", "Starter.sb3"),
    ("showcase", "Afterglow", ROOT / "examples" / "showcase", "Afterglow.sb3"),
    ("orchard", "Orchard Dash", ROOT / "examples" / "orchard", "Orchard-Dash.sb3"),
    ("crypt", "Crypt Crawl", ROOT / "examples" / "crypt", "Crypt-Crawl.sb3"),
    ("portals", "Portal Lab", ROOT / "examples" / "portals", "Portal-Lab.sb3"),
    ("woods", "Autumn Woods", ROOT / "examples" / "woods", "Autumn-Woods.sb3"),
    ("journey", "The Long Walk", ROOT / "examples" / "journey", "The-Long-Walk.sb3"),
]
EXT = {"penPlus.js": "https://extensions.turbowarp.org/obviousAlexC/penPlus.js",
       "pointerlock.js": "https://extensions.turbowarp.org/pointerlock.js",
       "gamepad.js": "https://extensions.turbowarp.org/gamepad.js"}


def copy_package(out):
    pkg = ROOT / "loophole"
    source, data = {}, []
    for f in sorted(pkg.rglob("*")):
        if not f.is_file() or "__pycache__" in f.parts or ".loophole" in f.parts or f.suffix == ".sb3":
            continue
        rel = f.relative_to(pkg.parent).as_posix()
        if f.suffix == ".py" or f.suffix == ".json" and f.stat().st_size < 20000:
            source[rel] = f.read_text(encoding="utf-8")
        else:
            dst = out / "py" / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dst)
            data.append([rel, f.stat().st_size])
    (out / "py").mkdir(parents=True, exist_ok=True)
    (out / "py" / "manifest.json").write_text(json.dumps({"source": source, "data": data}), encoding="utf-8")
    return sum(s for _, s in data)


def copy_templates(out, games):
    items = []
    for key, name, folder, asset in EXAMPLES:
        files = {}
        for fn in ("world.py", "game.py"):
            if (folder / fn).exists():
                files[fn] = (folder / fn).read_text(encoding="utf-8")
        game = None
        if games and (Path(games) / asset).exists():
            (out / "games").mkdir(parents=True, exist_ok=True)
            shutil.copy2(Path(games) / asset, out / "games" / asset)
            game = "games/" + asset
        items.append(dict(id=key, name=name, files=files, game=game))
    (out / "templates.json").write_text(json.dumps(items), encoding="utf-8")


def copy_docs(out):
    d = out / "docs"
    (d / "img").mkdir(parents=True, exist_ok=True)
    for f in (ROOT / "docs").glob("*.md"):
        shutil.copy2(f, d / f.name)
    for f in (ROOT / "docs" / "img").iterdir():
        shutil.copy2(f, d / "img" / f.name)


def copy_ext(out):
    d = out / "ext"
    d.mkdir(parents=True, exist_ok=True)
    local = ROOT / "tools" / "harness" / "ext"
    for name, url in EXT.items():
        if (local / name).exists():
            shutil.copy2(local / name, d / name)
        else:
            req = urllib.request.Request(url, headers={"User-Agent": "loophole-site-build"})
            (d / name).write_bytes(urllib.request.urlopen(req).read())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "build" / "site"))
    ap.add_argument("--games", default=None, help="folder with prebuilt .sb3 files to host")
    a = ap.parse_args()
    out = Path(a.out)
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(ROOT / "studio", out)
    size = copy_package(out)
    copy_templates(out, a.games)
    copy_docs(out)
    copy_ext(out)
    (out / ".nojekyll").write_text("", encoding="utf-8")
    print(f"site written to {out} ({size // 1024 // 1024} MB of engine data, loaded on demand)")


if __name__ == "__main__":
    main()
