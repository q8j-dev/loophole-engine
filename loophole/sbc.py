import ast
import json


class CompileError(Exception):
    pass


MATHOPS = {
    "sqrt": "sqrt", "sin": "sin", "cos": "cos", "tan": "tan", "atan": "atan",
    "asin": "asin", "acos": "acos", "abs": "abs", "floor": "floor",
    "ceil": "ceiling", "ln": "ln", "log": "log", "exp": "e ^", "pow10": "10 ^",
}

BINOPS = {
    ast.Add: "operator_add", ast.Sub: "operator_subtract",
    ast.Mult: "operator_multiply", ast.Div: "operator_divide",
    ast.Mod: "operator_mod",
}

EFFECTS = {"ghost": "GHOST", "brightness": "BRIGHTNESS", "color": "COLOR"}

SH = ("shader", "menu", "penPlusShaders")
UN = ("uniformName", "text", None)
EXT_STMTS = {
    "set_num": ("penP_setNumberInShader", [UN, SH, ("number", "num", None)]),
    "set_vec2": ("penP_setVec2InShader", [UN, SH, ("numberX", "num", None), ("numberY", "num", None)]),
    "set_vec3": ("penP_setVec3InShader", [UN, SH, ("numberX", "num", None), ("numberY", "num", None),
                                          ("numberZ", "num", None)]),
    "set_vec4": ("penP_setVec4InShader", [UN, SH, ("numberX", "num", None), ("numberY", "num", None),
                                          ("numberZ", "num", None), ("numberW", "num", None)]),
    "set_tex": ("penP_setTextureInShader", [UN, SH, ("texture", "menu", "costumeMenu")]),
    "draw_list": ("penP_renderShaderTrisFromList", [("list", "menu", "listMenu"), SH]),
    "tex_filter": ("penP_setTriangleFilterMode", [("filter", "menu", "filterType")]),
    "clear_depth": ("penP_clearDepth", []),
}


class Project:
    def __init__(self, global_names=None, global_lists=None):
        self.counter = 0
        self.variables = {}
        self.lists = {}
        self.broadcasts = {}
        self.global_names = set(global_names or [])
        self.global_lists = set(global_lists or [])

    def uid(self, prefix="b"):
        self.counter += 1
        return f"z{prefix}{self.counter}"

    def var_id(self, name):
        if name not in self.variables:
            self.variables[name] = self.uid("v")
        return self.variables[name]

    def list_id(self, name):
        if name not in self.lists:
            self.lists[name] = self.uid("l")
        return self.lists[name]

    def bc_id(self, name):
        if name not in self.broadcasts:
            self.broadcasts[name] = self.uid("m")
        return self.broadcasts[name]


class SpriteCompiler:
    def __init__(self, project, source, list_names, consts=None, local_vars=None, local_lists=None,
                 ext_procs=None, aliases=None, existing_ok=None):
        self.p = project
        self.blocks = {}
        self.list_names = set(list_names)
        self.consts = dict(consts or {})
        self.procs = dict(ext_procs or {})
        self.local_vars = dict(local_vars or {})
        self.local_lists = dict(local_lists or {})
        self.existing_vars = set(self.local_vars)
        self.existing_lists = set(self.local_lists)
        self.existing_ok = set(existing_ok or [])
        self.aliases = dict(aliases or {})
        self.new_vars = {}
        self.new_lists = {}
        self.args = None
        self.script_y = 0
        self.comments = {}
        self.tree = ast.parse(source)
        self._collect()

    def vref(self, name):
        name = self.aliases.get(name, name)
        if name in self.local_vars:
            if name in self.existing_vars and name not in self.existing_ok:
                raise CompileError(f"variable {name} collides with an existing sprite variable")
            return [name, self.local_vars[name]]
        if name in self.p.global_names:
            return [name, self.p.var_id(name)]
        vid = self.p.uid("v")
        self.local_vars[name] = vid
        self.new_vars[name] = vid
        return [name, vid]

    def lref(self, name):
        name = self.aliases.get(name, name)
        if name in self.local_lists:
            if name in self.existing_lists and name not in self.existing_ok:
                raise CompileError(f"list {name} collides with an existing sprite list")
            return [name, self.local_lists[name]]
        if name in self.p.global_lists:
            return [name, self.p.list_id(name)]
        lid = self.p.uid("l")
        self.local_lists[name] = lid
        self.new_lists[name] = lid
        return [name, lid]

    def _collect(self):
        for node in self.tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                self.consts[node.targets[0].id] = self._const_eval(node.value)
            elif isinstance(node, ast.FunctionDef):
                decos = [self._deco_name(d) for d in node.decorator_list]
                if any(d in ("when_flag", "when_broadcast", "when_clone", "when_key") for d in decos):
                    continue
                params = [a.arg for a in node.args.args]
                proccode = node.name + "".join(" %s" for _ in params)
                if "block" in decos:
                    proccode = node.decorator_list[decos.index("block")].args[0].value
                    if proccode.count("%s") != len(params):
                        raise CompileError(f"{node.name}: block text needs one %s for each of its {len(params)} inputs")
                ids = [self.p.uid("a") for _ in params]
                self.procs[node.name] = {
                    "params": params, "proccode": proccode, "ids": ids,
                    "warp": "warp" in decos,
                }

    def _deco_name(self, d):
        if isinstance(d, ast.Call):
            return d.func.id
        return d.id

    def _const_eval(self, node):
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name) and node.id in self.consts:
            return self.consts[node.id]
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -self._const_eval(node.operand)
        if isinstance(node, ast.BinOp):
            a = self._const_eval(node.left)
            b = self._const_eval(node.right)
            ops = {ast.Add: lambda: a + b, ast.Sub: lambda: a - b, ast.Mult: lambda: a * b,
                   ast.Div: lambda: a / b, ast.Mod: lambda: a % b}
            return ops[type(node.op)]()
        raise CompileError(f"not constant: {ast.dump(node)}")

    def _try_const(self, node):
        try:
            return True, self._const_eval(node)
        except (CompileError, KeyError, ZeroDivisionError, TypeError):
            return False, None

    def compile(self):
        for node in self.tree.body:
            if isinstance(node, ast.FunctionDef):
                decos = node.decorator_list
                names = [self._deco_name(d) for d in decos]
                if "when_flag" in names:
                    top = self._hat("event_whenflagclicked", {}, {}, node.body)
                elif "when_clone" in names:
                    top = self._hat("control_start_as_clone", {}, {}, node.body)
                elif "when_key" in names:
                    key = decos[names.index("when_key")].args[0].value
                    top = self._hat("event_whenkeypressed", {"KEY_OPTION": [key, None]}, {}, node.body)
                elif "when_broadcast" in names:
                    d = decos[names.index("when_broadcast")]
                    msg = d.args[0].value
                    top = self._hat("event_whenbroadcastreceived",
                                    {"BROADCAST_OPTION": [msg, self.p.bc_id(msg)]}, {}, node.body)
                else:
                    top = self._proc_def(node)
                doc = ast.get_docstring(node)
                if doc and top:
                    cid = self.p.uid("c")
                    blk = self.blocks[top]
                    blk["comment"] = cid
                    lines = sum(max(1, -(-len(par) // 44)) for par in doc.split("\n"))
                    self.comments[cid] = {"blockId": top, "x": blk.get("x", 0) + 560, "y": blk.get("y", 0),
                                          "width": 340, "height": min(420, 30 + lines * 19), "minimized": False,
                                          "text": doc}
                stmts = [n for n in ast.walk(node) if isinstance(n, ast.stmt) and n is not node]
                nest = sum(1 for n in stmts if isinstance(n, (ast.If, ast.For, ast.While)))
                tall = 110 + 56 * len(stmts) + 40 * nest
                if doc:
                    tall = max(tall, 60 + min(420, 30 + sum(max(1, -(-len(p) // 44)) for p in doc.split("\n")) * 19))
                self.script_y += tall + 60
        return self.blocks

    def _new(self, opcode, parent=None, inputs=None, fields=None, shadow=False, top=False, mutation=None):
        bid = self.p.uid()
        blk = {"opcode": opcode, "next": None, "parent": parent, "inputs": inputs or {},
               "fields": fields or {}, "shadow": shadow, "topLevel": top}
        if top:
            blk["x"] = 0
            blk["y"] = self.script_y
        if mutation is not None:
            blk["mutation"] = mutation
        self.blocks[bid] = blk
        return bid

    def _hat(self, opcode, fields, inputs, body):
        hid = self._new(opcode, fields=fields, inputs=inputs, top=True)
        self.args = None
        first = self._stmts(body, hid)
        self.blocks[hid]["next"] = first
        return hid

    def _proc_def(self, node):
        info = self.procs[node.name]
        did = self._new("procedures_definition", top=True)
        pid = self._new("procedures_prototype", parent=did, shadow=True, mutation={
            "tagName": "mutation", "children": [], "proccode": info["proccode"],
            "argumentids": json.dumps(info["ids"]), "argumentnames": json.dumps(info["params"]),
            "argumentdefaults": json.dumps(["" for _ in info["params"]]),
            "warp": "true" if info["warp"] else "false"})
        for aid, name in zip(info["ids"], info["params"]):
            rid = self._new("argument_reporter_string_number", parent=pid, shadow=True,
                            fields={"VALUE": [name, None]})
            self.blocks[pid]["inputs"][aid] = [1, rid]
        self.blocks[did]["inputs"]["custom_block"] = [1, pid]
        self.args = set(info["params"])
        first = self._stmts(node.body, did)
        self.blocks[did]["next"] = first
        self.args = None
        return did

    def _stmts(self, body, parent):
        first = None
        prev = None
        for st in body:
            ids = self._stmt(st, prev if prev else parent)
            if not ids:
                continue
            head, tail = ids
            if first is None:
                first = head
                self.blocks[head]["parent"] = parent
            else:
                self.blocks[prev]["next"] = head
                self.blocks[head]["parent"] = prev
            prev = tail
        return first

    def _substack(self, bid, key, body):
        s = self._stmts(body, bid)
        if s:
            self.blocks[bid]["inputs"][key] = [2, s]

    def _single(self, bid):
        return bid, bid

    def _stmt(self, st, parent):
        if isinstance(st, ast.Expr) and isinstance(st.value, ast.Constant):
            return None
        if isinstance(st, ast.Pass):
            return None
        if isinstance(st, ast.Assign):
            tgt = st.targets[0]
            if isinstance(tgt, ast.Name):
                bid = self._new("data_setvariableto", parent, fields={"VARIABLE": self.vref(tgt.id)})
                self.blocks[bid]["inputs"]["VALUE"] = self._input(st.value, bid, "text")
                return self._single(bid)
            if isinstance(tgt, ast.Subscript):
                lname = tgt.value.id
                bid = self._new("data_replaceitemoflist", parent,
                                fields={"LIST": self.lref(lname)})
                self.blocks[bid]["inputs"]["INDEX"] = self._input(tgt.slice, bid, "int")
                self.blocks[bid]["inputs"]["ITEM"] = self._input(st.value, bid, "text")
                return self._single(bid)
            raise CompileError("bad assign")
        if isinstance(st, ast.AugAssign):
            name = st.target.id
            if isinstance(st.op, ast.Add):
                val = st.value
            elif isinstance(st.op, ast.Sub):
                val = ast.UnaryOp(op=ast.USub(), operand=st.value)
            else:
                val = ast.BinOp(left=ast.Name(id=name), op=st.op, right=st.value)
                bid = self._new("data_setvariableto", parent, fields={"VARIABLE": self.vref(name)})
                self.blocks[bid]["inputs"]["VALUE"] = self._input(val, bid, "text")
                return self._single(bid)
            bid = self._new("data_changevariableby", parent, fields={"VARIABLE": self.vref(name)})
            self.blocks[bid]["inputs"]["VALUE"] = self._input(val, bid, "num")
            return self._single(bid)
        if isinstance(st, ast.If):
            if st.orelse:
                bid = self._new("control_if_else", parent)
                self.blocks[bid]["inputs"]["CONDITION"] = self._bool_input(st.test, bid)
                self._substack(bid, "SUBSTACK", st.body)
                self._substack(bid, "SUBSTACK2", st.orelse)
            else:
                bid = self._new("control_if", parent)
                self.blocks[bid]["inputs"]["CONDITION"] = self._bool_input(st.test, bid)
                self._substack(bid, "SUBSTACK", st.body)
            return self._single(bid)
        if isinstance(st, ast.While):
            if isinstance(st.test, ast.Constant) and st.test.value is True:
                bid = self._new("control_forever", parent)
                self._substack(bid, "SUBSTACK", st.body)
                return self._single(bid)
            bid = self._new("control_repeat_until", parent)
            neg = ast.UnaryOp(op=ast.Not(), operand=st.test)
            self.blocks[bid]["inputs"]["CONDITION"] = self._bool_input(neg, bid)
            self._substack(bid, "SUBSTACK", st.body)
            return self._single(bid)
        if isinstance(st, ast.For):
            call = st.iter
            fname = call.func.id
            if fname == "rep":
                counter = st.target.id
                init = self._new("data_setvariableto", parent, fields={"VARIABLE": self.vref(counter)})
                self.blocks[init]["inputs"]["VALUE"] = [1, [10, "0"]]
                rid = self._new("control_repeat", init)
                self.blocks[init]["next"] = rid
                self.blocks[rid]["inputs"]["TIMES"] = self._input(call.args[0], rid, "int")
                inc = ast.AugAssign(target=ast.Name(id=counter), op=ast.Add(), value=ast.Constant(1))
                body = [inc] + st.body
                self._substack(rid, "SUBSTACK", body)
                return init, rid
            if fname == "range":
                counter = st.target.id
                lo = call.args[0] if len(call.args) > 1 else ast.Constant(0)
                hi = call.args[1] if len(call.args) > 1 else call.args[0]
                init = self._new("data_setvariableto", parent, fields={"VARIABLE": self.vref(counter)})
                self.blocks[init]["inputs"]["VALUE"] = self._input(ast.BinOp(left=lo, op=ast.Sub(), right=ast.Constant(1)),
                                                                  init, "num")
                rid = self._new("control_repeat", init)
                self.blocks[init]["next"] = rid
                self.blocks[rid]["inputs"]["TIMES"] = self._input(ast.BinOp(left=hi, op=ast.Sub(), right=lo), rid, "int")
                inc = ast.AugAssign(target=ast.Name(id=counter), op=ast.Add(), value=ast.Constant(1))
                self._substack(rid, "SUBSTACK", [inc] + st.body)
                return init, rid
            if fname == "times":
                rid = self._new("control_repeat", parent)
                self.blocks[rid]["inputs"]["TIMES"] = self._input(call.args[0], rid, "int")
                self._substack(rid, "SUBSTACK", st.body)
                return self._single(rid)
            raise CompileError("for loops need range(), e.g. for i in range(10):")
        if isinstance(st, ast.Return):
            bid = self._new("control_stop", parent, fields={"STOP_OPTION": ["this script", None]},
                            mutation={"tagName": "mutation", "children": [], "hasnext": "false"})
            return self._single(bid)
        if isinstance(st, ast.Expr) and isinstance(st.value, ast.Call):
            return self._call_stmt(st.value, parent)
        raise CompileError(f"unsupported statement line {st.lineno}: {ast.dump(st)[:120]}")

    def _menu(self, opcode, field, value, parent):
        return self._new(opcode, parent, fields={field: [value, None]}, shadow=True)

    def _call_stmt(self, call, parent):
        if isinstance(call.func, ast.Attribute):
            lname = call.func.value.id
            meth = call.func.attr
            lf = {"LIST": self.lref(lname)}
            if meth == "append":
                bid = self._new("data_addtolist", parent, fields=lf)
                self.blocks[bid]["inputs"]["ITEM"] = self._input(call.args[0], bid, "text")
            elif meth == "clear":
                bid = self._new("data_deletealloflist", parent, fields=lf)
            elif meth == "pop":
                bid = self._new("data_deleteoflist", parent, fields=lf)
                self.blocks[bid]["inputs"]["INDEX"] = self._input(call.args[0], bid, "int")
            elif meth == "insert":
                bid = self._new("data_insertatlist", parent, fields=lf)
                self.blocks[bid]["inputs"]["INDEX"] = self._input(call.args[0], bid, "int")
                self.blocks[bid]["inputs"]["ITEM"] = self._input(call.args[1], bid, "text")
            else:
                raise CompileError(meth)
            return self._single(bid)
        name = call.func.id
        a = call.args
        if name in self.procs:
            info = self.procs[name]
            if len(a) != len(info["params"]):
                raise CompileError(f"arg count {name} line {call.lineno}")
            bid = self._new("procedures_call", parent, mutation={
                "tagName": "mutation", "children": [], "proccode": info["proccode"],
                "argumentids": json.dumps(info["ids"]), "warp": "true" if info["warp"] else "false"})
            for aid, arg in zip(info["ids"], a):
                self.blocks[bid]["inputs"][aid] = self._input(arg, bid, "text")
            return self._single(bid)
        if name in EXT_STMTS:
            opcode, spec = EXT_STMTS[name]
            bid = self._new(opcode, parent)
            for (aname, kind, menu), arg in zip(spec, a):
                if kind == "menu":
                    ok, val = self._try_const(arg)
                    if ok and not (isinstance(arg, ast.Name) and arg.id not in self.consts):
                        mid = self._menu(f"penP_menu_{menu}", menu, str(val), bid)
                        self.blocks[bid]["inputs"][aname] = [1, mid]
                    else:
                        mid = self._menu(f"penP_menu_{menu}", menu, "", bid)
                        self.blocks[bid]["inputs"][aname] = [3, self._expr(arg, bid), mid]
                else:
                    self.blocks[bid]["inputs"][aname] = self._input(arg, bid, kind)
            return self._single(bid)
        simple = {
            "pen_down": "pen_penDown", "pen_up": "pen_penUp", "pen_clear": "pen_clear",
            "stamp": "pen_stamp", "show": "looks_show", "hide": "looks_hide",
            "reset_timer": "sensing_resettimer", "stop_all_sounds": "sound_stopallsounds",
            "clear_effects": "looks_cleargraphiceffects", "delete_clone": "control_delete_this_clone",
        }
        if name in simple:
            return self._single(self._new(simple[name], parent))
        if name == "goto":
            bid = self._new("motion_gotoxy", parent)
            self.blocks[bid]["inputs"]["X"] = self._input(a[0], bid, "num")
            self.blocks[bid]["inputs"]["Y"] = self._input(a[1], bid, "num")
            return self._single(bid)
        if name == "point":
            bid = self._new("motion_pointindirection", parent)
            self.blocks[bid]["inputs"]["DIRECTION"] = self._input(a[0], bid, "angle")
            return self._single(bid)
        if name == "pen_size":
            bid = self._new("pen_setPenSizeTo", parent)
            self.blocks[bid]["inputs"]["SIZE"] = self._input(a[0], bid, "num")
            return self._single(bid)
        if name == "pen_color":
            bid = self._new("pen_setPenColorToColor", parent)
            self.blocks[bid]["inputs"]["COLOR"] = self._input(a[0], bid, "color")
            return self._single(bid)
        if name == "pen_trans":
            bid = self._new("pen_setPenColorParamTo", parent)
            mid = self._menu("pen_menu_colorParam", "colorParam", "transparency", bid)
            self.blocks[bid]["inputs"]["COLOR_PARAM"] = [1, mid]
            self.blocks[bid]["inputs"]["VALUE"] = self._input(a[0], bid, "num")
            return self._single(bid)
        if name == "size":
            bid = self._new("looks_setsizeto", parent)
            self.blocks[bid]["inputs"]["SIZE"] = self._input(a[0], bid, "num")
            return self._single(bid)
        if name == "effect":
            bid = self._new("looks_seteffectto", parent, fields={"EFFECT": [EFFECTS[a[0].value], None]})
            self.blocks[bid]["inputs"]["VALUE"] = self._input(a[1], bid, "num")
            return self._single(bid)
        if name == "costume":
            bid = self._new("looks_switchcostumeto", parent)
            if isinstance(a[0], ast.Constant):
                mid = self._menu("looks_costume", "COSTUME", str(a[0].value), bid)
                self.blocks[bid]["inputs"]["COSTUME"] = [1, mid]
            else:
                mid = self._menu("looks_costume", "COSTUME", "", bid)
                rep = self._expr(a[0], bid)
                self.blocks[bid]["inputs"]["COSTUME"] = [3, rep, mid]
            return self._single(bid)
        if name == "backdrop":
            bid = self._new("looks_switchbackdropto", parent)
            mid = self._menu("looks_backdrops", "BACKDROP", "", bid)
            self.blocks[bid]["inputs"]["BACKDROP"] = [3, self._expr(a[0], bid), mid]
            return self._single(bid)
        if name == "clone":
            bid = self._new("control_create_clone_of", parent)
            mid = self._menu("control_create_clone_of_menu", "CLONE_OPTION", "_myself_", bid)
            self.blocks[bid]["inputs"]["CLONE_OPTION"] = [1, mid]
            return self._single(bid)
        if name == "back_layers":
            bid = self._new("looks_goforwardbackwardlayers", parent, fields={"FORWARD_BACKWARD": ["backward", None]})
            self.blocks[bid]["inputs"]["NUM"] = self._input(a[0], bid, "int")
            return self._single(bid)
        if name == "go_back":
            bid = self._new("looks_gotofrontback", parent, fields={"FRONT_BACK": ["back", None]})
            return self._single(bid)
        if name in ("front",):
            bid = self._new("looks_gotofrontback", parent, fields={"FRONT_BACK": ["front", None]})
            return self._single(bid)
        if name in ("play", "play_wait"):
            op = "sound_play" if name == "play" else "sound_playuntildone"
            bid = self._new(op, parent)
            mid = self._menu("sound_sounds_menu", "SOUND_MENU", a[0].value, bid)
            self.blocks[bid]["inputs"]["SOUND_MENU"] = [1, mid]
            return self._single(bid)
        if name == "set_volume":
            bid = self._new("sound_setvolumeto", parent)
            self.blocks[bid]["inputs"]["VOLUME"] = self._input(a[0], bid, "num")
            return self._single(bid)
        if name == "set_pitch":
            bid = self._new("sound_seteffectto", parent, fields={"EFFECT": ["PITCH", None]})
            self.blocks[bid]["inputs"]["VALUE"] = self._input(a[0], bid, "num")
            return self._single(bid)
        if name == "set_pan":
            bid = self._new("sound_seteffectto", parent, fields={"EFFECT": ["PAN", None]})
            self.blocks[bid]["inputs"]["VALUE"] = self._input(a[0], bid, "num")
            return self._single(bid)
        if name == "wait":
            bid = self._new("control_wait", parent)
            self.blocks[bid]["inputs"]["DURATION"] = self._input(a[0], bid, "num")
            return self._single(bid)
        if name in ("broadcast", "broadcast_wait"):
            op = "event_broadcast" if name == "broadcast" else "event_broadcastandwait"
            bid = self._new(op, parent)
            msg = a[0].value
            self.blocks[bid]["inputs"]["BROADCAST_INPUT"] = [1, [11, msg, self.p.bc_id(msg)]]
            return self._single(bid)
        if name == "stop_all":
            bid = self._new("control_stop", parent, fields={"STOP_OPTION": ["all", None]},
                            mutation={"tagName": "mutation", "children": [], "hasnext": "false"})
            return self._single(bid)
        raise CompileError(f"unknown statement call {name} line {call.lineno}")

    def _shadow_for(self, kind):
        return {"num": [4, "0"], "int": [7, "1"], "angle": [8, "90"], "text": [10, ""],
                "color": [9, "#000000"]}[kind]

    def _literal(self, value, kind):
        if isinstance(value, bool):
            value = 1 if value else 0
        if isinstance(value, float) and value.is_integer() and abs(value) < 1e15:
            value = int(value)
        if isinstance(value, float):
            s = repr(value)
        else:
            s = str(value)
        prim = self._shadow_for(kind)
        if kind == "color" and not (isinstance(value, str) and value.startswith("#")):
            s = "#%06x" % (int(float(value)) & 0xFFFFFF)
        return [prim[0], s]

    def _input(self, node, parent, kind):
        ok, val = self._try_const(node)
        if ok and not isinstance(node, ast.Name) or (ok and isinstance(node, ast.Name) and node.id in self.consts):
            return [1, self._literal(val, kind)]
        if isinstance(node, ast.Name) and not (self.args and node.id in self.args):
            return [3, [12] + self.vref(node.id), self._shadow_for(kind)]
        rid = self._expr(node, parent)
        return [3, rid, self._shadow_for(kind)]

    def _bool_input(self, node, parent):
        rid = self._expr(node, parent)
        return [2, rid]

    def _expr(self, node, parent):
        if isinstance(node, ast.Name):
            if self.args and node.id in self.args:
                return self._new("argument_reporter_string_number", parent, fields={"VALUE": [node.id, None]})
            if node.id in self.consts:
                bid = self._new("operator_add", parent)
                self.blocks[bid]["inputs"]["NUM1"] = [1, self._literal(self.consts[node.id], "num")]
                self.blocks[bid]["inputs"]["NUM2"] = [1, [4, "0"]]
                return bid
            return self._new("data_variable", parent,
                             fields={"VARIABLE": self.vref(node.id)})
        if isinstance(node, ast.Constant):
            bid = self._new("operator_join", parent)
            self.blocks[bid]["inputs"]["STRING1"] = [1, [10, str(node.value)]]
            self.blocks[bid]["inputs"]["STRING2"] = [1, [10, ""]]
            return bid
        if isinstance(node, ast.BinOp):
            op = BINOPS[type(node.op)]
            bid = self._new(op, parent)
            self.blocks[bid]["inputs"]["NUM1"] = self._input(node.left, bid, "num")
            self.blocks[bid]["inputs"]["NUM2"] = self._input(node.right, bid, "num")
            return bid
        if isinstance(node, ast.UnaryOp):
            if isinstance(node.op, ast.USub):
                bid = self._new("operator_subtract", parent)
                self.blocks[bid]["inputs"]["NUM1"] = [1, [4, "0"]]
                self.blocks[bid]["inputs"]["NUM2"] = self._input(node.operand, bid, "num")
                return bid
            if isinstance(node.op, ast.Not):
                bid = self._new("operator_not", parent)
                self.blocks[bid]["inputs"]["OPERAND"] = self._bool_input(node.operand, bid)
                return bid
        if isinstance(node, ast.BoolOp):
            op = "operator_and" if isinstance(node.op, ast.And) else "operator_or"
            vals = node.values
            cur = None
            left = vals[0]
            for right in vals[1:]:
                bid = self._new(op, parent)
                if cur is None:
                    self.blocks[bid]["inputs"]["OPERAND1"] = self._bool_input(left, bid)
                else:
                    self.blocks[bid]["inputs"]["OPERAND1"] = [2, cur]
                    self.blocks[cur]["parent"] = bid
                self.blocks[bid]["inputs"]["OPERAND2"] = self._bool_input(right, bid)
                cur = bid
            return cur
        if isinstance(node, ast.Compare):
            l, op, r = node.left, node.ops[0], node.comparators[0]
            if isinstance(op, (ast.LtE, ast.GtE, ast.NotEq)):
                inv = {ast.LtE: ast.Gt(), ast.GtE: ast.Lt(), ast.NotEq: ast.Eq()}[type(op)]
                return self._expr(ast.UnaryOp(op=ast.Not(), operand=ast.Compare(left=l, ops=[inv], comparators=[r])), parent)
            opc = {ast.Lt: "operator_lt", ast.Gt: "operator_gt", ast.Eq: "operator_equals"}[type(op)]
            bid = self._new(opc, parent)
            self.blocks[bid]["inputs"]["OPERAND1"] = self._input(l, bid, "text")
            self.blocks[bid]["inputs"]["OPERAND2"] = self._input(r, bid, "text")
            return bid
        if isinstance(node, ast.Subscript):
            lname = node.value.id
            bid = self._new("data_itemoflist", parent, fields={"LIST": self.lref(lname)})
            self.blocks[bid]["inputs"]["INDEX"] = self._input(node.slice, bid, "int")
            return bid
        if isinstance(node, ast.Call):
            name = node.func.id
            a = node.args
            if name in MATHOPS:
                bid = self._new("operator_mathop", parent, fields={"OPERATOR": [MATHOPS[name], None]})
                self.blocks[bid]["inputs"]["NUM"] = self._input(a[0], bid, "num")
                return bid
            if name == "round":
                bid = self._new("operator_round", parent)
                self.blocks[bid]["inputs"]["NUM"] = self._input(a[0], bid, "num")
                return bid
            if name == "max":
                x, y = a
                e = ast.BinOp(left=ast.BinOp(left=ast.BinOp(left=x, op=ast.Add(), right=y), op=ast.Add(),
                                             right=ast.Call(func=ast.Name(id="abs"), args=[ast.BinOp(left=x, op=ast.Sub(), right=y)])),
                              op=ast.Mult(), right=ast.Constant(0.5))
                return self._expr(e, parent)
            if name == "min":
                x, y = a
                e = ast.BinOp(left=ast.BinOp(left=ast.BinOp(left=x, op=ast.Add(), right=y), op=ast.Sub(),
                                             right=ast.Call(func=ast.Name(id="abs"), args=[ast.BinOp(left=x, op=ast.Sub(), right=y)])),
                              op=ast.Mult(), right=ast.Constant(0.5))
                return self._expr(e, parent)
            if name == "random":
                bid = self._new("operator_random", parent)
                self.blocks[bid]["inputs"]["FROM"] = self._input(a[0], bid, "num")
                self.blocks[bid]["inputs"]["TO"] = self._input(a[1], bid, "num")
                return bid
            if name == "join":
                bid = self._new("operator_join", parent)
                self.blocks[bid]["inputs"]["STRING1"] = self._input(a[0], bid, "text")
                self.blocks[bid]["inputs"]["STRING2"] = self._input(a[1], bid, "text")
                return bid
            if name == "letter":
                bid = self._new("operator_letter_of", parent)
                self.blocks[bid]["inputs"]["LETTER"] = self._input(a[0], bid, "int")
                self.blocks[bid]["inputs"]["STRING"] = self._input(a[1], bid, "text")
                return bid
            if name == "strlen":
                bid = self._new("operator_length", parent)
                self.blocks[bid]["inputs"]["STRING"] = self._input(a[0], bid, "text")
                return bid
            if name == "len":
                lname = a[0].id
                return self._new("data_lengthoflist", parent, fields={"LIST": self.lref(lname)})
            if name == "mouse_x":
                return self._new("sensing_mousex", parent)
            if name == "mouse_y":
                return self._new("sensing_mousey", parent)
            if name == "mouse_down":
                return self._new("sensing_mousedown", parent)
            if name == "timer":
                return self._new("sensing_timer", parent)
            if name == "key":
                bid = self._new("sensing_keypressed", parent)
                mid = self._menu("sensing_keyoptions", "KEY_OPTION", a[0].value, bid)
                self.blocks[bid]["inputs"]["KEY_OPTION"] = [1, mid]
                return bid
        raise CompileError(f"unsupported expression line {getattr(node, 'lineno', '?')}: {ast.dump(node)[:160]}")
