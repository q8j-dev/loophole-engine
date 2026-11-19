import numpy as np


RES = 2
AXES = [(0, 1), (0, -1), (1, 1), (1, -1), (2, 1), (2, -1)]


class Level:
    def __init__(self, name, size, origin=(0, 0, 0)):
        self.name = name
        self.size = tuple(int(s * RES) for s in size)
        self.origin = np.array(origin, float)
        self.air = np.zeros(self.size, bool)
        self.paint_ops = []
        self.start = (0, 0, 0, 0)
        self.items = []

    def g(self, p):
        return tuple(int(round((p[i] - self.origin[i]) * RES)) for i in range(3))

    def box_idx(self, x0, y0, z0, x1, y1, z1):
        a, b = self.g((x0, y0, z0)), self.g((x1, y1, z1))
        for i in range(3):
            if a[i] < 1 or b[i] > self.size[i] - 1:
                raise ValueError(f"{self.name}: box {(x0, y0, z0, x1, y1, z1)} outside grid")
        return a, b

    def carve(self, x0, y0, z0, x1, y1, z1):
        if not hasattr(self, "main_box"):
            self.main_box = (x0, y0, z0, x1, y1, z1)
        a, b = self.box_idx(x0, y0, z0, x1, y1, z1)
        self.air[a[0]:b[0], a[1]:b[1], a[2]:b[2]] = True

    def fill(self, x0, y0, z0, x1, y1, z1):
        a, b = self.box_idx(x0, y0, z0, x1, y1, z1)
        self.air[a[0]:b[0], a[1]:b[1], a[2]:b[2]] = False

    def paint(self, mat, x0, y0, z0, x1, y1, z1, facing=None):
        self.paint_ops.append((mat, np.array([x0, y0, z0], float), np.array([x1, y1, z1], float), facing))

    def material(self, center, normal):
        dm = getattr(self, "default_mats", {"floor": "floor", "ceil": "ceil", "wall": "white"})
        m = dm["wall"]
        if normal[1] > 0.5:
            m = dm["floor"]
        elif normal[1] < -0.5:
            m = dm["ceil"]
        for mat, lo, hi, facing in self.paint_ops:
            if all(lo[i] - 1e-6 <= center[i] <= hi[i] + 1e-6 for i in range(3)):
                if facing is None or (facing == "walls" and abs(normal[1]) < 0.5) or facing == tuple(int(v) for v in normal):
                    m = mat
        return m

    def faces(self):
        nx, ny, nz = self.size
        air = self.air
        rects = []
        for axis, sgn in AXES:
            u, v = [a for a in range(3) if a != axis]
            for k in range(self.size[axis]):
                grid = {}
                for i in range(self.size[u]):
                    for j in range(self.size[v]):
                        idx = [0, 0, 0]
                        idx[axis], idx[u], idx[v] = k, i, j
                        if not air[tuple(idx)]:
                            continue
                        nb = list(idx)
                        nb[axis] = k - sgn
                        if 0 <= nb[axis] < self.size[axis] and air[tuple(nb)]:
                            continue
                        if not (0 <= nb[axis] < self.size[axis]) and (axis, sgn) in getattr(self, "open_faces", ()):
                            continue
                        plane = k if sgn > 0 else k + 1
                        c = np.zeros(3)
                        c[axis] = plane / RES
                        c[u] = (i + 0.5) / RES
                        c[v] = (j + 0.5) / RES
                        n = np.zeros(3)
                        n[axis] = sgn
                        grid[(i, j)] = self.material(c + self.origin, n)
                done = set()
                for (i, j), m in sorted(grid.items()):
                    if (i, j) in done:
                        continue
                    w = 1
                    while (i + w, j) in grid and grid[(i + w, j)] == m and (i + w, j) not in done:
                        w += 1
                    h = 1
                    while all((i + a, j + h) in grid and grid[(i + a, j + h)] == m and (i + a, j + h) not in done
                              for a in range(w)):
                        h += 1
                    for a in range(w):
                        for b in range(h):
                            done.add((i + a, j + b))
                    plane = k if sgn > 0 else k + 1
                    rects.append((axis, sgn, plane / RES, i / RES, j / RES, (i + w) / RES, (j + h) / RES, m))
        return rects
