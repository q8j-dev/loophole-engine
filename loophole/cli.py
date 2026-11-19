import argparse
import shutil
import sys
from pathlib import Path

from . import __version__

HERE = Path(__file__).resolve().parent
TEMPLATES = HERE / "templates"


def find_world(p):
    p = Path(p)
    if p.is_dir():
        p = p / "world.py"
    if not p.exists():
        raise SystemExit(f"no world.py found at {p}. Run 'loophole new mygame' to start a project.")
    return p


def cmd_new(a):
    dst = Path(a.name)
    if dst.exists() and any(dst.iterdir()):
        raise SystemExit(f"{dst} already exists and is not empty")
    src = TEMPLATES / a.template
    if not src.exists():
        raise SystemExit(f"unknown template '{a.template}'. Templates: {', '.join(p.name for p in TEMPLATES.iterdir())}")
    shutil.copytree(src, dst, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", ".loophole", "*.sb3"))
    w = dst / "world.py"
    w.write_text(w.read_text().replace("My Game", dst.name.replace("-", " ").replace("_", " ").title()))
    print(f"created {dst}/")
    print(f"next: cd {dst} && loophole build")


def cmd_build(a):
    from .build import build
    build(find_world(a.path), out=a.out)


def cmd_info(a):
    from . import decor_place, props
    from .materials import ALIASES, TABLE
    print(f"loophole {__version__}")
    print("materials:", ", ".join(sorted(TABLE)))
    print("material aliases:", ", ".join(f"{k}->{v}" for k, v in sorted(ALIASES.items())))
    print("props:", ", ".join(decor_place.KINDS))
    print("object models:", ", ".join(sorted(set(props.BUILTIN) - {"arms", "device"}) + decor_place.KINDS))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="loophole", description="Build 3D games for Scratch and TurboWarp.")
    ap.add_argument("--version", action="version", version=f"loophole {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("new", help="create a project from a template")
    p.add_argument("name")
    p.add_argument("--template", default="starter")
    p.set_defaults(fn=cmd_new)
    p = sub.add_parser("build", help="bake lighting and write the .sb3")
    p.add_argument("path", nargs="?", default=".")
    p.add_argument("--out", default=None)
    p.set_defaults(fn=cmd_build)
    p = sub.add_parser("info", help="list materials, props and models")
    p.set_defaults(fn=cmd_info)
    a = ap.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main(sys.argv[1:])
