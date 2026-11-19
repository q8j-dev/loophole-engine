import numpy as np

TABLE = {
    "white": dict(id=0, alb=0.82, tint=(1.0, 1.0, 0.98), panel=(1.0, 1.0), portal=True),
    "metal": dict(id=1, alb=0.26, tint=(0.9, 0.97, 1.08), panel=(2.0, 1.0)),
    "floor": dict(id=2, alb=0.3, tint=(1.0, 1.0, 1.02), panel=(2.0, 2.0), portal=True),
    "ceil": dict(id=3, alb=0.4, tint=(1.0, 1.0, 1.03), panel=(2.0, 2.0)),
    "dark": dict(id=4, alb=0.14, tint=(0.9, 0.95, 1.1), panel=(1.0, 0.5)),
    "hazard": dict(id=6, alb=0.5, tint=(1.0, 0.85, 0.5)),
    "goo": dict(id=8, alb=0.3, tint=(0.6, 1.3, 0.3), emit=(0.19, 0.55, 0.1), kill=True),
    "exit": dict(id=9, alb=0.5, tint=(1.2, 1.0, 0.6), emit=(1.4, 1.0, 0.42)),
    "light": dict(id=10, alb=0.6, tint=(1.0, 1.0, 1.0), emit=(3.2, 3.1, 2.95)),
    "glass": dict(id=11, alb=0.06, tint=(1.0, 1.0, 1.0)),
    "boost": dict(id=17, alb=0.3, tint=(1.0, 0.95, 0.9), emit=(0.35, 0.18, 0.04), portal=True),
    "vent": dict(id=18, alb=0.08, tint=(1.0, 1.0, 1.0), emit=(0.12, 0.2, 0.25)),
    "rust": dict(id=34, alb=0.22, tint=(1.0, 0.85, 0.7)),
    "grate": dict(id=35, alb=0.18, tint=(1.0, 0.95, 0.9)),
    "shutter": dict(id=36, alb=0.32, tint=(1.0, 1.0, 1.0)),
    "concrete": dict(id=37, alb=0.36, tint=(1.0, 0.99, 0.97), portal=True),
    "plate": dict(id=38, alb=0.3, tint=(1.0, 1.0, 1.0)),
    "water": dict(id=39, alb=0.05, tint=(0.7, 0.9, 1.0), emit=(0.0, 0.02, 0.03)),
    "lava": dict(id=42, alb=0.3, tint=(1.3, 0.5, 0.2), emit=(1.6, 0.45, 0.06), kill=True),
}

ALIASES = {"panel": "white", "panels": "white", "ceiling": "ceil", "tile": "ceil", "tiles": "ceil",
           "steel": "metal", "dark metal": "dark", "slime": "goo", "toxic": "goo", "diamond": "plate",
           "stripes": "hazard", "glow": "light", "booster": "boost"}

MATID = {k: v["id"] for k, v in TABLE.items()}
ALB = {k: v["alb"] for k, v in TABLE.items()}
TINT = {k: v["tint"] for k, v in TABLE.items()}
EMIT = {k: np.array(v["emit"], float) for k, v in TABLE.items() if "emit" in v}
PANEL = {k: v["panel"] for k, v in TABLE.items() if "panel" in v}
KILL = {k for k, v in TABLE.items() if v.get("kill")}
PORTAL = {k for k, v in TABLE.items() if v.get("portal")}


def resolve(name):
    n = name.strip().lower()
    n = ALIASES.get(n, n)
    if n not in TABLE:
        raise ValueError(f"unknown material '{name}'. Known: {', '.join(sorted(set(TABLE) | set(ALIASES)))}")
    return n
