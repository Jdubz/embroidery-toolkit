"""SVG path parsing and flattening, enough to measure geometry in millimetres.

Written because measuring a satin column's width by counting on-curve points
does not work. A rail emitted by `stroke_to_satin` is often a single cubic —
`M x,y C ...` — so it has exactly two on-curve points and gets mistaken for a
rung, which is a straight two-point crossbar. That mistake made `satin_params`
fall back to a positional join against declared stroke widths, and when
`stroke_to_satin` split 9 strokes into 11 columns the join broke and every
column got the same blanket underlay.

Supports M L H V C S Q T A Z, absolute and relative, with implicit repeated
coordinates and the implicit lineto after a moveto. Curves are flattened to
polylines, which is all any measurement here needs.

**Arcs are parsed properly rather than approximated**, using the endpoint-to-
centre conversion from the SVG spec's implementation notes, because a silently
wrong number is the failure mode this module exists to remove. An unknown
command raises rather than being skipped, for the same reason.
"""

from __future__ import annotations

import math
import re

# Match ANY letter as a command, not just the valid ones. Listing only the legal
# letters here looks tighter but is worse: an unknown command would fail to
# tokenise, its coordinates would be swallowed as arguments to whatever came
# before, and the path would parse "successfully" into the wrong geometry.
# Exponents survive because the number alternative consumes `1e-5` whole.
_TOK = re.compile(r"([A-Za-z])|(-?\d*\.?\d+(?:[eE][-+]?\d+)?)")
_ARGC = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2, "A": 7, "Z": 0}


def _bezier3(p0, p1, p2, p3, n):
    out = []
    for i in range(1, n + 1):
        t = i / n
        u = 1 - t
        out.append((u * u * u * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t * t * t * p3[0],
                    u * u * u * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t * t * t * p3[1]))
    return out


def _bezier2(p0, p1, p2, n):
    out = []
    for i in range(1, n + 1):
        t = i / n
        u = 1 - t
        out.append((u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0],
                    u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1]))
    return out


def _arc(p0, rx, ry, rot, large, sweep, p1, n):
    """Endpoint -> centre parameterisation, per SVG 1.1 appendix F.6."""
    if rx == 0 or ry == 0 or (abs(p0[0] - p1[0]) < 1e-12 and abs(p0[1] - p1[1]) < 1e-12):
        return [p1]
    rx, ry = abs(rx), abs(ry)
    phi = math.radians(rot)
    cs, sn = math.cos(phi), math.sin(phi)
    dx, dy = (p0[0] - p1[0]) / 2.0, (p0[1] - p1[1]) / 2.0
    x1, y1 = cs * dx + sn * dy, -sn * dx + cs * dy
    lam = x1 * x1 / (rx * rx) + y1 * y1 / (ry * ry)
    if lam > 1:
        s = math.sqrt(lam)
        rx, ry = rx * s, ry * s
    num = rx * rx * ry * ry - rx * rx * y1 * y1 - ry * ry * x1 * x1
    den = rx * rx * y1 * y1 + ry * ry * x1 * x1
    co = math.sqrt(max(0.0, num / den)) * (-1 if large == sweep else 1)
    cx1, cy1 = co * rx * y1 / ry, -co * ry * x1 / rx
    cx = cs * cx1 - sn * cy1 + (p0[0] + p1[0]) / 2.0
    cy = sn * cx1 + cs * cy1 + (p0[1] + p1[1]) / 2.0

    def ang(ux, uy, vx, vy):
        d = (math.hypot(ux, uy) * math.hypot(vx, vy))
        if d == 0:
            return 0.0
        c = max(-1.0, min(1.0, (ux * vx + uy * vy) / d))
        a = math.acos(c)
        return -a if ux * vy - uy * vx < 0 else a

    t0 = ang(1, 0, (x1 - cx1) / rx, (y1 - cy1) / ry)
    dt = ang((x1 - cx1) / rx, (y1 - cy1) / ry, (-x1 - cx1) / rx, (-y1 - cy1) / ry)
    if not sweep and dt > 0:
        dt -= 2 * math.pi
    elif sweep and dt < 0:
        dt += 2 * math.pi
    out = []
    for i in range(1, n + 1):
        t = t0 + dt * i / n
        px, py = rx * math.cos(t), ry * math.sin(t)
        out.append((cs * px - sn * py + cx, sn * px + cs * py + cy))
    return out


def parse_path(d: str, samples: int = 12) -> list[dict]:
    """Flatten `d` into subpaths.

    Each subpath is {"points": [(x, y), ...], "curved": bool, "closed": bool}.
    `curved` records whether any curve command contributed — the reliable way to
    tell a straight rung from a rail that happens to be one cubic segment.
    """
    toks = _TOK.findall(d)
    subs: list[dict] = []
    cur: dict | None = None
    x = y = sx = sy = 0.0
    prev_ctrl: tuple[float, float] | None = None
    cmd = None
    i = 0
    while i < len(toks):
        c, num = toks[i]
        if c:
            if c.upper() not in _ARGC:
                raise ValueError(f"unsupported path command {c!r}")
            cmd = c
            i += 1
            if cmd in "Zz":
                if cur:
                    cur["closed"] = True
                    if cur["points"][0] != (x, y):
                        cur["points"].append(cur["points"][0])
                    subs.append(cur)
                    cur = None
                x, y = sx, sy
                prev_ctrl = None
            continue
        if cmd is None:
            raise ValueError("path data starts with a number, not a command")
        u = cmd.upper()
        if u not in _ARGC:
            raise ValueError(f"unsupported path command {cmd!r}")
        need = _ARGC[u]
        vals = []
        while len(vals) < need and i < len(toks) and not toks[i][0]:
            vals.append(float(toks[i][1]))
            i += 1
        if len(vals) < need:
            break
        rel = cmd.islower()

        if u == "M":
            if cur:
                subs.append(cur)
            x, y = (x + vals[0], y + vals[1]) if rel else (vals[0], vals[1])
            sx, sy = x, y
            cur = {"points": [(x, y)], "curved": False, "closed": False}
            cmd = "l" if rel else "L"       # implicit lineto for repeated pairs
            prev_ctrl = None
            continue
        if cur is None:                      # data before any moveto
            cur = {"points": [(x, y)], "curved": False, "closed": False}

        if u == "L":
            x, y = (x + vals[0], y + vals[1]) if rel else (vals[0], vals[1])
            cur["points"].append((x, y))
            prev_ctrl = None
        elif u == "H":
            x = x + vals[0] if rel else vals[0]
            cur["points"].append((x, y))
            prev_ctrl = None
        elif u == "V":
            y = y + vals[0] if rel else vals[0]
            cur["points"].append((x, y))
            prev_ctrl = None
        elif u in ("C", "S"):
            if u == "C":
                c1 = (x + vals[0], y + vals[1]) if rel else (vals[0], vals[1])
                c2 = (x + vals[2], y + vals[3]) if rel else (vals[2], vals[3])
                end = (x + vals[4], y + vals[5]) if rel else (vals[4], vals[5])
            else:
                c1 = (2 * x - prev_ctrl[0], 2 * y - prev_ctrl[1]) if prev_ctrl else (x, y)
                c2 = (x + vals[0], y + vals[1]) if rel else (vals[0], vals[1])
                end = (x + vals[2], y + vals[3]) if rel else (vals[2], vals[3])
            cur["points"] += _bezier3((x, y), c1, c2, end, samples)
            cur["curved"] = True
            prev_ctrl, (x, y) = c2, end
        elif u in ("Q", "T"):
            if u == "Q":
                c1 = (x + vals[0], y + vals[1]) if rel else (vals[0], vals[1])
                end = (x + vals[2], y + vals[3]) if rel else (vals[2], vals[3])
            else:
                c1 = (2 * x - prev_ctrl[0], 2 * y - prev_ctrl[1]) if prev_ctrl else (x, y)
                end = (x + vals[0], y + vals[1]) if rel else (vals[0], vals[1])
            cur["points"] += _bezier2((x, y), c1, end, samples)
            cur["curved"] = True
            prev_ctrl, (x, y) = c1, end
        elif u == "A":
            end = (x + vals[5], y + vals[6]) if rel else (vals[5], vals[6])
            cur["points"] += _arc((x, y), vals[0], vals[1], vals[2],
                                  bool(vals[3]), bool(vals[4]), end, samples)
            cur["curved"] = True
            prev_ctrl, (x, y) = None, end
    if cur:
        subs.append(cur)
    return [s for s in subs if len(s["points"]) >= 2]


_NUM = r"-?\d*\.?\d+(?:[eE][-+]?\d+)?"


def _ellipse(cx: float, cy: float, rx: float, ry: float, n: int) -> list[tuple[float, float]]:
    return [(cx + rx * math.cos(2 * math.pi * i / n),
             cy + ry * math.sin(2 * math.pi * i / n)) for i in range(n)]


def parse_shape(tag: str, attrib: dict, samples: int = 12) -> list[dict] | None:
    """Flatten ANY filled SVG shape into the subpath list `parse_path` returns.

    Added because reading only `<path>` is a silent-partial-application bug
    waiting to happen: LemonCat's prepared SVG draws its ear tufts as `<polygon>`
    and its pupils as `<ellipse>`, both filled #000000, so a tool that walked
    paths alone would report a black layer smaller than it is and would offset
    part of it. `svg_prep` already stitches all of these, so anything measuring
    or rewriting the same document has to see all of them too.

    Returns None for a tag with no fillable interior, so a caller can tell
    "not a shape" from "a shape enclosing no area" (which is `[]`).
    """
    def num(name: str, default: float = 0.0) -> float:
        v = attrib.get(name)
        try:
            return float(v) if v not in (None, "") else default
        except ValueError:                      # "12px", "50%" — units this
            return default                      # module has no viewport for

    if tag == "path":
        return parse_path(attrib.get("d") or "", samples)
    if tag in ("polygon", "polyline"):
        vals = [float(t) for t in re.findall(_NUM, attrib.get("points") or "")]
        pts = list(zip(vals[0::2], vals[1::2]))
        return [{"points": pts, "curved": False, "closed": tag == "polygon"}] \
            if len(pts) >= 3 else []
    if tag == "rect":
        if num("rx") or num("ry"):
            raise ValueError("rounded <rect> is not supported; convert it to a path "
                             "first (Inkscape: --actions=select-all;object-to-path)")
        x, y, w, h = num("x"), num("y"), num("width"), num("height")
        return [{"points": [(x, y), (x + w, y), (x + w, y + h), (x, y + h)],
                 "curved": False, "closed": True}] if w > 0 and h > 0 else []
    if tag in ("circle", "ellipse"):
        rx = num("r") or num("rx")
        ry = num("r") or num("ry")
        return [{"points": _ellipse(num("cx"), num("cy"), rx, ry, max(16, samples * 4)),
                 "curved": True, "closed": True}] if rx > 0 and ry > 0 else []
    return None


def parse_transform(s: str | None) -> tuple[float, float, float, float, float, float]:
    """Compose an SVG transform list into (a, b, c, d, e, f)."""
    m = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    if not s:
        return m

    def mul(p, q):
        return (p[0] * q[0] + p[2] * q[1], p[1] * q[0] + p[3] * q[1],
                p[0] * q[2] + p[2] * q[3], p[1] * q[2] + p[3] * q[3],
                p[0] * q[4] + p[2] * q[5] + p[4], p[1] * q[4] + p[3] * q[5] + p[5])

    for name, args in re.findall(r"(\w+)\s*\(([^)]*)\)", s):
        v = [float(t) for t in re.findall(_NUM, args)]
        # A transform with too few arguments is malformed. Skipping it beats
        # raising IndexError from inside a measurement, and beats silently
        # treating scale() as identity when it might have meant something.
        need = {"matrix": 6, "translate": 1, "scale": 1, "rotate": 1,
                "skewX": 1, "skewY": 1}.get(name)
        if need is None or len(v) < need:
            continue
        if name == "matrix":
            t = tuple(v[:6])
        elif name == "translate":
            t = (1, 0, 0, 1, v[0], v[1] if len(v) > 1 else 0)
        elif name == "scale":
            t = (v[0], 0, 0, v[1] if len(v) > 1 else v[0], 0, 0)
        elif name == "rotate":
            a = math.radians(v[0])
            r = (math.cos(a), math.sin(a), -math.sin(a), math.cos(a), 0, 0)
            if len(v) == 3:
                t = mul(mul((1, 0, 0, 1, v[1], v[2]), r), (1, 0, 0, 1, -v[1], -v[2]))
            else:
                t = r
        elif name in ("skewX", "skewY"):
            tn = math.tan(math.radians(v[0]))
            t = (1, tn, 0, 1, 0, 0) if name == "skewY" else (1, 0, tn, 1, 0, 0)
        else:
            continue
        m = mul(m, t)
    return m


def apply(m, pts):
    a, b, c, d, e, f = m
    return [(a * x + c * y + e, b * x + d * y + f) for x, y in pts]
