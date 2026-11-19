import builtins
import difflib
import inspect
import re
import traceback
from pathlib import Path

KINDS = {"Level": "levels", "Game": "the game", "Road": "roads", "Cutscene": "cutscenes", "Obj": "objects"}


def _classes():
    from . import world
    return {n: getattr(world, n) for n in KINDS if hasattr(world, n)}


def _public(cls):
    return [n for n in dir(cls) if not n.startswith("_")]


def _suggest(word, options):
    m = difflib.get_close_matches(word, options, n=1, cutoff=0.6)
    return f" Did you mean {m[0]}?" if m else ""


def _frame(exc, path):
    hit = None
    for fr in traceback.extract_tb(exc.__traceback__):
        if Path(fr.filename).resolve() == path:
            hit = fr
    return hit


def explain(exc, path):
    path = Path(path).resolve()
    name = path.name
    if isinstance(exc, SyntaxError):
        code = (exc.text or "").strip()
        what = "an opening or closing bracket, quote or comma is probably missing"
        if exc.msg and "indent" in exc.msg.lower():
            what = "the spaces at the start of the line don't line up with the lines around it"
        elif exc.msg and "never closed" in exc.msg:
            what = "a bracket or quote is opened here but never closed"
        return f"{name} line {exc.lineno}: Python can't read this line, {what}." + (f"\n    {code}" if code else "")
    fr = _frame(exc, path)
    where = f"{name} line {fr.lineno}: " if fr else f"{name}: "
    code = f"\n    {fr.line.strip()}" if fr and fr.line else ""
    msg = str(exc)
    if isinstance(exc, AttributeError):
        m = re.match(r"'(\w+)' object has no attribute '(\w+)'", msg)
        if m and m.group(1) in KINDS:
            cls = _classes().get(m.group(1))
            hint = _suggest(m.group(2), _public(cls)) if cls else ""
            return f"{where}{KINDS[m.group(1)]} don't have {m.group(2)}().{hint}{code}"
    if isinstance(exc, NameError):
        nm = getattr(exc, "name", None) or (re.findall(r"'(\w+)'", msg) or [""])[0]
        from . import world
        opts = ["Game", "game", "level", "print", "range", "True", "False", "None"] + [n for n in dir(world) if not n.startswith("_")] + dir(builtins)
        return f"{where}{nm} isn't defined.{_suggest(nm, opts)}{code}"
    if isinstance(exc, TypeError):
        m = re.search(r"(\w+)\(\) got an unexpected keyword argument '(\w+)'", msg)
        if m:
            opts = []
            for cls in _classes().values():
                fn = getattr(cls, m.group(1), None)
                if fn:
                    opts += list(inspect.signature(fn).parameters)
            if m.group(1) == "__init__":
                opts += list(inspect.signature(_classes()["Game"]).parameters)
            label = "Game" if m.group(1) == "__init__" else m.group(1)
            return f"{where}{label}() has no setting called {m.group(2)}.{_suggest(m.group(2), opts)}{code}"
        m = re.search(r"(\w+)\(\) missing (\d+) required positional arguments?: (.+)", msg)
        if m:
            return f"{where}{m.group(1)}() needs more values. Missing: {m.group(3).replace(chr(39), '')}.{code}"
        m = re.search(r"(\w+)\(\) takes (\d+) positional arguments? but (\d+) (?:were|was) given", msg)
        if m:
            return f"{where}{m.group(1)}() got too many values. Check the commas between numbers.{code}"
    if isinstance(exc, (ValueError, KeyError)) and msg:
        return f"{where}{msg.strip(chr(39))}{code}"
    return f"{where}{type(exc).__name__}: {msg}{code}"
