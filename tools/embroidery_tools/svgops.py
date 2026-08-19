"""Atomic operations on a `svgdoc.Doc`. One verb each, composable in any order.

Every SVG tool in this repo is a fixed sequence of these. `svg_ground_invert`'s
whole LemonCat behaviour — 400 lines — is four of them:

    subtract --colour FFD400 --by 000000     cut the linework out of the body
    subtract --colour FFFFFF --by 000000     and out of the eyes
    subtract --colour FFD400 --by FFFFFF     knock the eyes out of the body
    drop     --colour 000000                 let the cloth supply the linework

That is the point of the refactor: a new asset is a new *sequence*, not new
Python. When one of these is wrong it is wrong for every asset at once, which is
the only way a fix stays fixed.

**Selectors are measured, never positional where a measurement will do.** Colour,
area, enclosure, adjacency and centroid band are stable when artwork moves; a
hand-placed coordinate is not, and one silently dropped the question mark from
`HOT PISS?` by clipping it out of a circle. `--band` and `--at` exist because
some choices genuinely are positional, and both report what they matched so a
silent miss becomes a loud one.
"""

from __future__ import annotations

import numpy as np
import shapely
import shapely.affinity
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from . import profile as prof
from . import svggeom as G
from .measure import frac_below_mm, widths_mm

JOINS = {"round": 1, "mitre": 2, "bevel": 3}
OPS: dict[str, dict] = {}

#: The narrowest thread feature this machine holds. `widen-negative` sizes
#: knockouts against it because a hole and a line are the same measurement seen
#: from opposite sides — see the note there.
SAFE_W = prof.design_limit("safe_satin_width_mm", 1.2)

#: Narrowest thread this machine will hold at all. `pockets` uses it to tell a
#: white AREA from a hairline keyline gap that only ever meant "paper shows
#: here" — see the note there.
MIN_W = prof.design_limit("min_satin_width_mm", 1.0)

PAD_PX = 2


def _rasterise(geom, upm: float, ppm: float) -> np.ndarray:
    """Bool mask of `geom`, one sample at each pixel centre.

    Pixel centres via `shapely.contains_xy`, matching `svg_offset`, and NOT
    `PIL.ImageDraw.polygon`, whose fill is boundary-inclusive and measures a
    flat 2 px wide at every resolution — 0.08 mm at the 24 px/mm used here, but
    0.2 mm at the 10 px/mm the older rasterising tools use. Two tools reporting
    widths that differ by a fixed offset is worse than either being wrong.

    Sized to the geometry's own bounds: local width is local, so a knockout in
    one corner of a design costs a corner-sized grid. Even-odd nesting needs no
    special handling — `contains` already answers exactly that question.
    """
    if geom is None or geom.is_empty:
        return np.zeros((1, 1), bool)
    gx0, gy0, gx1, gy1 = geom.bounds
    W = int((gx1 - gx0) / upm * ppm) + 2 * PAD_PX + 1
    H = int((gy1 - gy0) / upm * ppm) + 2 * PAD_PX + 1
    xs = gx0 + (np.arange(W) + 0.5 - PAD_PX) * upm / ppm
    ys = gy0 + (np.arange(H) + 0.5 - PAD_PX) * upm / ppm
    shapely.prepare(geom)
    return shapely.contains_xy(geom, *np.meshgrid(xs, ys))


def op(name: str, help: str):
    def wrap(fn):
        OPS[name] = {"fn": fn, "help": help}
        return fn
    return wrap


def _split_by_band(doc, region, band, axis: int = 1):
    """Split a region's geometry into (inside the band, outside it), by COMPONENT.

    Filters have to address connected components, not elements. Artwork routinely
    puts a whole layer in one path — PissMuffy's 29 letters, eyes, brows and
    mouth are a single `<path>` — so an element-level band filter matches the
    centroid of the entire design and selects nothing at all. That is not a
    missing feature, it is the difference between a selector language and a
    colour switch.

    `axis` is 1 for a band measured DOWN from the top and 0 for one measured
    ACROSS from the left. Both are positional and both report what they caught,
    for the reason in this module's header: a hand-placed circle once clipped
    the question mark out of `HOT PISS?` and said nothing.

    A partial match splits the element: the matching components move to a new
    one, the rest stay. Returns (matched, rest), either possibly empty.
    """
    lo, hi = band
    inside, outside = [], []
    for p in G.polys(region.geom):
        (inside if lo <= doc.centroid_mm(p)[axis] <= hi else outside).append(p)
    return (unary_union(inside) if inside else None,
            unary_union(outside) if outside else None)


# --------------------------------------------------------------------------- #

@op("drop", "drop --colour X [--band A:B] [--band-x A:B]   stop stitching colour X; the cloth supplies it")
def drop(doc, colour: str, band=None, band_x=None, **_):
    """Drop a colour, or only the components of it inside a centroid band.

    `--band` is the same selector `recolour`, `move`, `scale` and `space-out`
    already take, and it is component-level for the same reason: PissMuffy's 29
    letters, both eyes, the brows and the mouth are ONE `<path>`, so an
    element-level filter would take all of them or none. Without it, removing
    the lettering from an asset that carries its lettering in the same element
    as its face could only be done by hand-editing the original -- which is the
    thing `art/originals/` exists never to need.

    **Dropping SHRINKS the drawing, and bands are measured against the live
    extent.** `recolour --band` can be given in any order because it moves
    nothing; two `drop --band`s cannot. Take the LOWER band first: removing it
    leaves the top edge where it was, so the upper band's numbers still hold.
    Do it the other way round and the second band addresses geometry that has
    already slid up underneath it -- which raises here rather than silently
    matching the wrong components, because the miss is reported.
    """
    a = G.norm(colour)
    regions = doc.select(colour=a)
    if not regions:
        raise SystemExit(f"drop: nothing is painted #{a}")
    if band is not None and band_x is not None:
        raise SystemExit("drop: give --band or --band-x, not both. Two "
                         "positional filters in one op hide which one missed.")
    axis, band = (0, band_x) if band_x is not None else (1, band)
    if band is None:
        area = doc.mm2(unary_union([r.geom for r in regions]))
        for r in regions:
            doc.clear_paint(r)
        doc.rescan()
        return f"dropped {len(regions)} region(s) of #{a}, {area:,.0f} mm2 now bare cloth"

    lo, hi = band
    gone, kept, n = [], [], 0
    for r in regions:
        # _split_by_band returns unions, not lists -- count the COMPONENTS
        # back out of them, because "dropped 9 component(s)" is the line that
        # tells you the band caught the glyphs you meant and not the face.
        inside, outside = _split_by_band(doc, r, band, axis)
        if inside is None:
            continue
        n += len(G.polys(inside))
        gone.append(inside)
        if outside is not None:
            doc.set_fill_geom(r, outside)
            kept.extend(G.polys(outside))
        else:
            doc.clear_paint(r)
    if not n:
        raise SystemExit(
            f"drop: no #{a} component has its centroid in "
            f"{lo:g}:{hi:g} mm {'across from the left' if axis == 0 else 'down from the top'} "
            "of the drawing -- run `report` and check the geometry first.")
    area = doc.mm2(unary_union(gone))
    doc.rescan()
    return (f"dropped {n} component(s) of #{a} in "
            f"{'x-band' if axis == 0 else 'band'} {lo:g}:{hi:g} mm, "
            f"{area:,.0f} mm2 now bare cloth"
            + (f"; {len(kept)} component(s) of #{a} left" if kept else ""))


@op("subtract", "subtract --colour X --by Y   cut Y's area out of X's fills")
def subtract(doc, colour: str, by: str, **_):
    a, b = G.norm(colour), G.norm(by)
    cutter = doc.geom_of(b)
    if cutter is None:
        raise SystemExit(f"subtract: nothing is painted #{b} to cut with")
    targets = doc.select(colour=a, kind="fill")
    if not targets:
        raise SystemExit(f"subtract: nothing is FILLED #{a}. A stroke cannot be "
                         "reshaped in place — drop or recolour it instead.")
    cut = 0.0
    emptied = 0
    for r in list(targets):
        after = r.geom.difference(cutter)
        if after.area >= r.geom.area - 1e-9:
            continue
        cut += doc.mm2(r.geom) - doc.mm2(after)
        if after.is_empty:
            doc.clear_paint(r)
            emptied += 1
        else:
            doc.set_fill_geom(r, after)
    doc.rescan()
    if not cut:
        return f"subtract: #{b} does not overlap #{a}; nothing changed"
    tail = f", {emptied} region(s) emptied entirely" if emptied else ""
    return f"cut {cut:,.0f} mm2 of #{b} out of #{a}{tail}"


@op("recolour", "recolour --colour X --to Y   repaint X as Y (optionally --band Y0:Y1)")
def recolour(doc, colour: str, to: str, band=None, **_):
    a, b = G.norm(colour), G.norm(to)
    regions = doc.select(colour=a)
    if not regions:
        raise SystemExit(f"recolour: nothing is painted #{a}")

    if band is None:
        area = doc.mm2(unary_union([r.geom for r in regions]))
        for r in regions:
            doc.set_colour(r, b)
        n = len(regions)
    else:
        moved, n = [], 0
        for r in list(regions):
            if r.kind == "stroke":
                continue                # a stroke cannot be split; recolour whole
            inside, outside = _split_by_band(doc, r, band)
            if inside is None:
                continue
            n += len(G.polys(inside))
            moved.append(inside)
            if outside is None:
                doc.set_colour(r, b)    # the whole element matched
            else:
                doc.set_fill_geom(r, outside)
                doc.add_fill(inside, b, ident=f"recoloured_{len(moved)}")
        if not moved:
            raise SystemExit(
                f"recolour: no #{a} component's centroid falls in "
                f"{band[0]:g}:{band[1]:g} mm. Bands are measured down from the top "
                "of the drawing; run `report` to see what is there.")
        area = doc.mm2(unary_union(moved))
    doc.rescan()
    merged = "" if len(doc.select(colour=b)) <= n else \
        " (joins an existing layer of that colour — one pass, one stop)"
    return f"recoloured {n} component(s), {area:,.0f} mm2, #{a} -> #{b}{merged}"


@op("offset", "offset --colour X --mm N     grow (or shrink) X's fills by N mm")
def offset(doc, colour: str, mm: float, join: str = "round", **_):
    a = G.norm(colour)
    targets = doc.select(colour=a, kind="fill")
    if not targets:
        raise SystemExit(f"offset: nothing is FILLED #{a}")
    before = doc.mm2(unary_union([r.geom for r in targets]))
    shells_before = sum(len(G.polys(r.geom)) for r in targets)
    for r in list(targets):
        doc.set_fill_geom(r, r.geom.buffer(mm * doc.upm, quad_segs=8,
                                           join_style=JOINS[join], mitre_limit=5.0))
    doc.rescan()
    after_rs = doc.select(colour=a, kind="fill")
    after = doc.mm2(unary_union([r.geom for r in after_rs]))
    shells_after = sum(len(G.polys(r.geom)) for r in after_rs)
    warn = ""
    if shells_after != shells_before:
        # Merging is invisible in a render at design size and invisible to
        # validate, because the stitches are good stitches of the wrong shape.
        warn = (f"  WARNING shapes merged or split: {shells_before} -> "
                f"{shells_after}; check the preview")
    return f"offset #{a} by {mm:+.2f} mm, {before:,.0f} -> {after:,.0f} mm2{warn}"


@op("gap", "gap --colour X --by Y --mm N [--min-keep N]   cut an N mm cloth channel out of X along Y")
def gap(doc, colour: str, by: str, mm: float, min_keep: float = MIN_W, **_):
    """Open a channel of bare cloth between two colours that touch.

    Two colours drawn edge to edge do not stitch edge to edge. `svg_prep`'s pull
    compensation grows EVERY colour outward independently, so a shared boundary
    is claimed twice and the two thread masses meet and merge. Measured on
    MuffyHat_on_black: 339 mm of the white hat's 735 mm perimeter sat at exactly
    zero distance from the gold body, and after 0.2 mm of pull compensation on
    each side the two overlapped by 136 mm2. On black cloth that reads as one
    pale mass, which is the complaint this op exists to answer.

    The channel comes out of ONE colour, not split between them, and WHICH one
    is the whole decision — the arithmetic is identical either way, so pick on
    what the cut destroys. Cutting MuffyHat's white hat lost 180 mm2 and
    consumed two white shells outright, because the whites are small detail
    that has no 0.8 mm to spare; cutting the gold body cost 262 mm2 out of
    3,455 and changed no topology at all. Take it from the shape that can
    afford it and read the shell counts below, which is what caught that.

    Budget it against pull compensation, not against what you want to see. Both
    colours advance `expand` into the channel, so a cut of N leaves N - 2*expand
    of visible cloth: at the 0.2 mm default, a 0.8 mm cut shows as a 0.4 mm line.

    A hairline is the intent, not a restored keyline. Where a dark-cloth
    inversion has dropped ink that used to separate the two colours, the honest
    width would be that ink's own — but on this artwork only 35% of the 339 mm
    contact line ever carried black, and the keyline measures 1.33 mm median,
    which at 2*expand of shrinkage would need a 1.7 mm cut. The 0.8 mm in the
    profile is deliberately less than that: enough that the two masses stop
    reading as one, not enough to redraw the design.
    """
    a, b = G.norm(colour), G.norm(by)
    other = doc.geom_of(b)
    if other is None:
        raise SystemExit(f"gap: nothing is painted #{b} to open a gap from")
    targets = doc.select(colour=a, kind="fill")
    if not targets:
        raise SystemExit(f"gap: nothing is FILLED #{a}. A stroke cannot be "
                         "reshaped in place — set-stroke or drop it instead.")
    contact = doc.geom_of(a).boundary.intersection(other.buffer(1e-6)).length / doc.upm
    if contact < 1.0:
        return (f"gap: #{a} and #{b} share only {contact:.1f} mm of boundary; "
                "nothing to separate")

    def cutter_at(d: float):
        return other.buffer(d * doc.upm, quad_segs=8, join_style=JOINS["round"])

    def holds_thread(g) -> bool:
        """Is there anywhere in `g` at least `min_keep` wide? Exact, via erosion."""
        return not g.is_empty and not g.buffer(-min_keep / 2 * doc.upm).is_empty

    cutter = cutter_at(mm)
    cut = 0.0
    spared: list[str] = []
    for r in list(targets):
        # PER SHELL, not per element. A channel takes the same width off every
        # side of every feature, so a narrow one is consumed outright — and the
        # element it belongs to is not empty, so nothing downstream notices.
        # MuffyHat's hat bracket is a 1.25 mm-wide gold shell: a 0.9 mm channel
        # removes 1.8 mm and deletes it. The gold shell count went 9 -> 9,
        # because another shell split in the same pass and the net was zero, so
        # a count-based guard reported nothing at all. Counting is not enough;
        # each shell has to be asked whether IT survived.
        pieces = []
        for shell in G.polys(r.geom):
            after = shell.difference(cutter)
            if after.area >= shell.area - 1e-9:
                pieces.append(shell)            # the channel never reaches it
                continue
            if holds_thread(after):
                pieces.append(after)            # survives the cut
                continue
            # Leave it whole. Backing the channel off to the widest this shell
            # can afford was tried and is worse: the channel eats a narrow
            # feature from BOTH sides, so MuffyHat's 1.25 mm hat bracket kept
            # only 3.35 mm2 of its 13.27 even at a 0.42 mm cut — a mutilated
            # shape instead of a deleted one. A feature this narrow simply
            # cannot afford separation, and touching its neighbour is a far
            # smaller defect than not being there.
            pieces.append(shell)
            spared.append(f"{doc.mm2(shell):.1f} mm2 at {doc.at(shell)}")
        keep = unary_union([p for p in pieces if not p.is_empty])
        if keep.is_empty:
            continue
        cut += doc.mm2(r.geom) - doc.mm2(keep)
        if keep.area < r.geom.area - 1e-9:
            doc.set_fill_geom(r, keep)
    doc.rescan()
    note = ""
    if spared:
        note = (f"; left {len(spared)} feature(s) UNCUT that the channel would "
                f"have erased — they now touch #{b}: " + ", ".join(spared[:4])
                + (", ..." if len(spared) > 4 else ""))
    return (f"cut a {mm:g} mm channel out of #{a} along {contact:.0f} mm of #{b}, "
            f"{cut:,.1f} mm2{note}")


@op("widen-negative",
    "widen-negative --colour X --to-min N   open X's knocked-out holes to N mm")
def widen_negative(doc, colour: str, to_min: float, tolerate: float = 5.0,
                   ppm: float = 24.0, **_):
    """Widen the holes in a colour's fills until the bare cloth in them reads.

    Knocked-out detail is measured on the WRONG side of every limit in this
    repo. `design_limits` sizes thread — the narrowest line that will hold — and
    everything is drawn to clear it. A hole is the complement: what has to
    survive is the cloth, and it is attacked from both sides at once. Pull
    compensation takes `expand` off each rail, and the thread laid on those
    rails blooms over the edge on top of that.

    Measured on MuffyHat_on_black's SOUR PUSS lettering: drawn at a 1.42 mm
    median gap, which is comfortably over the 1.2 mm safe feature width and
    looks fine in every render. 0.2 mm of pull compensation on each side takes
    it to 1.00 mm and closes 29% of the negative area outright, and bloom
    finishes it. It came off the machine barely legible — the defect the user
    reported and the one nothing in the pipeline could see.

    So size a knockout as `safe_satin_width + 2*expand`, plus an allowance for
    bloom; ~1.8-2.0 mm at 0.2 mm pull compensation against a 1.2 mm safe width.

    The search is `svg_offset --to-min`'s, on the holes rather than on the ink:
    bracket outward from the bar estimate, bisect, and MEASURE every step with
    `frac_below_mm` rather than trusting the estimate, which corners and letter
    tips put out by a factor of two. Nested islands inside a widened hole shrink
    from the outside, which is the same widening seen from the other side.

    **The topology guard has to count HOLES, not shells.** Widening a knockout
    fails by the holes running into each other — the O fills in, two letters
    join — and that is invisible from the shell side. The first version of this
    op guarded on shells, watched them go 9 -> 12 on MuffyHat_on_black, read
    that as the crown being severed between the letters (which it was, and which
    is harmless), and shipped a SOUR PUSS whose every counter had closed. It had
    made the lettering less legible than the defect it was fixing, and the render
    is what caught it, not the guard. So the search is clamped: never open wider
    than the largest gap that leaves every hole a separate hole. When the clamp
    binds before the target is met, the artwork is what is wrong — the detail is
    too fine to be a knockout at this size, and it needs redrawing, enlarging, or
    stitching as thread.
    """
    a = G.norm(colour)
    targets = doc.select(colour=a, kind="fill")
    if not targets:
        raise SystemExit(f"widen-negative: nothing is FILLED #{a}")
    holes = [Polygon(ring) for r in targets for p in G.polys(r.geom)
             for ring in p.interiors]
    if not holes:
        return f"widen-negative: #{a} has no holes; nothing is knocked out of it"
    neg = unary_union(holes)

    def under(delta: float) -> float:
        """Percent of the negative area still narrower than the target.

        Measured hole by hole and area-weighted, NOT on the union of them. On
        the union, two holes that grow into each other read as one wide hole and
        the number IMPROVES — the metric rewards exactly the failure the clamp
        below exists to prevent. Caught by a test plate whose two slots sit
        0.04 mm apart: at 24 px/mm a 0.02 mm opening closes that in the raster,
        and the union measure reported the negative going from 100% under target
        to 10% while nothing had been widened at all.
        """
        tot = num = 0.0
        for h in holes:
            g = h.buffer(delta * doc.upm, quad_segs=8) if delta else h
            m = _rasterise(g, doc.upm, ppm)
            if not m.any():
                continue
            w = m.sum()
            num += frac_below_mm(m, ppm, to_min) * w
            tot += w
        return (num / tot * 100) if tot else 0.0

    def holes_after(delta: float) -> int:
        """Interior rings left in the fills once the widened holes are cut.

        Counted on the resulting fill and not on the buffered holes, so it sees
        both ways a knockout can be lost: two holes running into each other, and
        one breaking out through the edge of the shape into the background.
        """
        cut = neg.buffer(delta * doc.upm, quad_segs=8) if delta else neg
        n = 0
        for r in targets:
            for p in G.polys(r.geom.difference(cut)):
                n += len(p.interiors)
        return n

    at0 = under(0.0)
    if at0 <= tolerate:
        return (f"widen-negative: #{a}'s {len(holes)} hole(s) already clear "
                f"{to_min:g} mm ({at0:.0f}% under, tolerating {tolerate:g}%)")

    w0 = np.concatenate([widths_mm(_rasterise(h, doc.upm, ppm), ppm,
                                   max_mm=to_min + 1.0)
                         for h in holes
                         if _rasterise(h, doc.upm, ppm).any()] or [np.zeros(1)])
    want = max(0.05, (to_min - float(np.percentile(w0, tolerate))) / 2.0)
    lo, hi = 0.0, want
    for _ in range(6):
        if under(hi) <= tolerate:
            break
        lo, hi = hi, hi * 2
    else:
        raise SystemExit(
            f"widen-negative {a}={to_min:g}: opening to {hi:g} mm still leaves "
            f"{under(hi):.0f}% of the negative under target against a "
            f"{tolerate:g}% tolerance. The knockout is not narrow at its edges, "
            "it is narrow throughout — redraw the detail larger, or stitch it "
            "as thread instead of as cloth.")
    for _ in range(6):
        mid = (lo + hi) / 2
        if under(mid) <= tolerate:
            hi = mid
        else:
            lo = mid
    want = hi

    # Clamp to what the topology allows. Monotone in delta — every extra
    # micron of opening can only join holes, never separate them — so the same
    # bisection finds the largest opening that keeps all of them distinct.
    n0 = holes_after(0.0)
    clamp = ""
    if holes_after(want) < n0:
        klo, khi = 0.0, want
        for _ in range(8):
            mid = (klo + khi) / 2
            if holes_after(mid) < n0:
                khi = mid
            else:
                klo = mid
        clamp = (f"  CLAMPED: {want:.2f} mm per side would have merged the "
                 f"negative ({n0} holes -> {holes_after(want)}); the most that "
                 f"keeps them distinct is {klo:.2f} mm.")
        hi = klo
        # A clamp this tight buys nothing and still costs material: lettering
        # has an enormous perimeter, so even 0.02 mm per side took 71 mm2 out of
        # MuffyHat's crown while moving the width figure not at all. Refuse
        # rather than half-do it, and say what the artwork actually needs.
        if at0 - under(hi) < 1.0:
            return (f"widen-negative: #{a}'s {len(holes)} hole(s) CANNOT be "
                    f"opened — {at0:.0f}% of the negative is under {to_min:g} mm "
                    f"and {clamp.strip()} Nothing done. The knockout is not "
                    "narrow at its edges, it is narrow everywhere and the thread "
                    "between the holes is just as narrow; there is no material "
                    "to move. Enlarge the detail in the artwork, redraw it, or "
                    "stitch it as thread instead of as cloth.")

    cutter = neg.buffer(hi * doc.upm, quad_segs=8) if hi else neg
    before = doc.mm2(unary_union([r.geom for r in targets]))
    shells_before = sum(len(G.polys(r.geom)) for r in targets)
    for r in list(targets):
        after = r.geom.difference(cutter)
        if after.is_empty:
            doc.clear_paint(r)
        elif after.area < r.geom.area - 1e-9:
            doc.set_fill_geom(r, after)
    doc.rescan()
    after_rs = doc.select(colour=a, kind="fill")
    now = doc.mm2(unary_union([r.geom for r in after_rs])) if after_rs else 0.0
    shells_after = sum(len(G.polys(r.geom)) for r in after_rs)
    # The thread BETWEEN two widened holes is what pays for the widening, and it
    # is the thing that can drop under the minimum feature width. Report it: a
    # letter that reads because the bridge beside it vanished is not a fix.
    m = _rasterise(unary_union([r.geom for r in after_rs]), doc.upm, ppm) \
        if after_rs else np.zeros((1, 1), bool)
    thin = frac_below_mm(m, ppm, SAFE_W) * 100 if m.any() else 0.0
    warn = ""
    if shells_after != shells_before:
        # Informational, not a defect: widening lettering severs the shape it is
        # knocked out of, which costs a few trims and nothing else. The count
        # that can indicate a defect is the hole count, and it is clamped above.
        warn = (f"; #{a} {shells_before} -> {shells_after} shell(s), so a few "
                "more runs to reach")
    return (f"opened {len(holes)} hole(s) in #{a} by {hi:.2f} mm per side "
            f"({2 * hi:.2f} mm of gap), {at0:.0f}% -> {under(hi):.0f}% of the "
            f"negative under {to_min:g} mm; #{a} {before:,.0f} -> {now:,.0f} mm2, "
            f"{thin:.0f}% of what is left is under the {SAFE_W:g} mm safe "
            f"width{warn}{clamp}")


def _matched(doc, colour: str, band, axis: int = 1):
    """[(region, [matching components], [the rest])] for a colour, by band.

    `axis` is 1 for a band measured DOWN from the top and 0 for one measured
    ACROSS from the left -- the same convention as `_split_by_band`. Two words
    on ONE line can only be told apart across, which is what a horizontal band
    is for.

    Component-level, like `_split_by_band` and for the same reason: a whole
    layer routinely lives in one <path>. Sour Puss Muffy draws its eight
    letters, both eyes and the mouth as eleven components of a single black
    element, so anything that addresses "the lettering" has to reach inside.
    """
    out = []
    for r in doc.select(colour=G.norm(colour), kind="fill"):
        keep, rest = [], []
        for p in G.polys(r.geom):
            if band is None or band[0] <= doc.centroid_mm(p)[axis] <= band[1]:
                keep.append(p)
            else:
                rest.append(p)
        if keep:
            out.append((r, keep, rest))
    return out


def _rows_of(doc, comps, share: float = 0.5):
    """Group components into rows of text by vertical overlap of their extents.

    Two components share a row when they overlap vertically by more than `share`
    of the shorter one's height. **Not** a nearness test: the first version here
    admitted anything within 1 mm of overlapping, and SOUR PUSS's two lines sit
    0.4 mm apart, so all eight letters became one row and were re-spaced into an
    interleaved single line. Real overlap is the thing that distinguishes a row
    from the line below it, and adjacent lines of type do not have it.
    """
    rows: list[list] = []
    for p in sorted(comps, key=lambda q: q.bounds[1]):
        y0, y1 = p.bounds[1], p.bounds[3]
        for row in rows:
            ry0 = min(q.bounds[1] for q in row)
            ry1 = max(q.bounds[3] for q in row)
            if min(y1, ry1) - max(y0, ry0) > share * min(y1 - y0, ry1 - ry0):
                row.append(p)
                break
        else:
            rows.append([p])
    return [sorted(r, key=lambda q: q.bounds[0]) for r in rows]


def _shift_to_gap(fixed, moving, want_units: float, axis: int):
    """Translate `moving` along `axis` until its distance to `fixed` is `want`.

    Bisected on the true geometric distance rather than computed from bounding
    boxes. Letters are slanted and irregular, so a bbox gap is not the gap: on
    this artwork the two differ by up to 0.4 mm, which is a third of the target.
    """
    def at(d):
        off = (d, 0.0) if axis == 0 else (0.0, d)
        return fixed.distance(shapely.affinity.translate(moving, *off))

    if at(0.0) >= want_units:
        return moving                      # already far enough; never pull closer
    # Bracket by DOUBLING, not by an estimate. Once earlier components have been
    # pushed along, a later one can start deep inside its predecessor and need a
    # shift many times the target gap: on SOUR PUSS the fourth letter had to
    # travel 14.5 mm to clear a 2.2 mm gap. A bracket sized from the target
    # capped that at 5.4 mm and quietly returned a 1.79 mm gap — no error, just
    # the wrong answer, in the one place a wrong answer is invisible.
    lo, hi = 0.0, max(want_units, 1.0)
    for _ in range(30):
        if at(hi) >= want_units:
            break
        lo, hi = hi, hi * 2
    else:
        raise SystemExit("space-out: could not separate two components; "
                         "are they nested rather than side by side?")
    for _ in range(40):
        mid = (lo + hi) / 2
        if at(mid) < want_units:
            lo = mid
        else:
            hi = mid
    off = (hi, 0.0) if axis == 0 else (0.0, hi)
    return shapely.affinity.translate(moving, *off)


@op("scale", "scale --colour X --factor N [--band A:B]   resize components in place")
def scale(doc, colour: str, factor: float, band=None, about: str = "own", **_):
    """Grow or shrink selected components, each about its own centre.

    `--about own` is the default and is the one that matters for knockout
    detail: it thickens every stroke without moving anything, so a letter gets
    bolder where it stands. Scaling about the GROUP centre instead (`--about
    group`) magnifies the spacing along with the letters, which is a different
    job — see `space-out`, and see below for why one scale cannot do both.

    A knockout has two widths and they move in opposite directions. On the SOUR
    PUSS lettering the bare-cloth letter strokes measure 1.33-1.42 mm against
    the 1.8 mm `negative_space_mm`, and the WHITE THREAD BRIDGES between
    adjacent letters measure 0.45-0.67 mm against a 1.2 mm safe feature width.
    Both are under limit at once, which is exactly why `widen-negative` refuses
    here: widening the letters can only come out of bridges that are already
    too thin. Scaling about each letter's own centre fixes the strokes and makes
    the bridges worse; scaling about the group centre fixes neither fast enough,
    since taking 0.5 mm bridges to 1.2 mm needs a factor of 2.4 that would put
    the block at 45 x 33 mm on a 52 x 30 mm crown. The two ops together do it.
    """
    groups = _matched(doc, colour, band)
    if not groups:
        raise SystemExit(f"scale: nothing FILLED #{G.norm(colour)} matches"
                         + (f" band {band[0]:g}:{band[1]:g} mm" if band else ""))
    n = sum(len(k) for _, k, _ in groups)
    before = doc.mm2(unary_union([p for _, k, _ in groups for p in k]))
    staged = []
    for r, keep, rest in groups:
        if about == "group":
            c = unary_union(keep).centroid
            done = [shapely.affinity.scale(p, factor, factor, origin=c) for p in keep]
        else:
            done = [shapely.affinity.scale(p, factor, factor, origin="centroid")
                    for p in keep]
        # Growing components in place makes neighbours collide, and the union
        # that has to follow — evenodd would XOR an overlap into a hole rather
        # than merge it — fuses them into ONE polygon for good. Every later op
        # then addresses eight letters as one blob and silently does nothing:
        # `space-out` reported "re-spaced 1 component(s)" and moved nothing.
        # Check before committing, and name the op that fixes it.
        if len(G.polys(unary_union(done))) < len(done):
            raise SystemExit(
                f"scale: {factor:g}x would fuse {len(done)} component(s) of "
                f"#{G.norm(colour)} into {len(G.polys(unary_union(done)))} — they "
                "collide, and the union is not reversible. Open the spacing "
                "FIRST with `space-out`, then scale into the room that makes. "
                "Allow for scaling closing the gaps again: at this factor each "
                f"component grows about {factor - 1:.0%} of its own width.")
        staged.append((r, done, rest))
    for r, done, rest in staged:
        doc.set_fill_geom(r, unary_union(done + rest))
    doc.rescan()
    after = doc.mm2(unary_union([p for _, k, _ in _matched(doc, colour, band)
                                 for p in k]))
    return (f"scaled {n} component(s) of #{G.norm(colour)} by {factor:g}x about "
            f"{'the group' if about == 'group' else 'each own'} centre, "
            f"{before:,.1f} -> {after:,.1f} mm2")


@op("move", "move --colour X --dx N --dy N [--band A:B] [--band-x A:B]   translate components")
def move(doc, colour: str, dx: float = 0.0, dy: float = 0.0, band=None,
         band_x=None, **_):
    """Translate selected components, and report what they now clear.

    Placement on a hand-drawn asset is a genuine design choice — where the
    lettering sits on the hat is not derivable from anything — so this is one of
    the few positional ops. It follows the same rule as `--band` and `--at`: a
    positional operation must **report what it did**, so a silent miss becomes a
    loud one. The clearance line below is the check, not the offsets.

    Enlarging a block of detail almost always needs this. `space-out` re-centres
    each row where it was, and the SOUR PUSS block was never centred on its
    crown to begin with — 11.1 mm of clearance on the left against 22.1 mm on
    the right — so growing it symmetrically ran it off the near edge while a
    third of the crown stayed empty.
    """
    if band and band_x:
        raise SystemExit("move: give --band OR --band-x, not both -- a component "
                         "is selected by one axis or the other")
    axis, sel = (0, band_x) if band_x else (1, band)
    groups = _matched(doc, colour, sel, axis)
    if not groups:
        raise SystemExit(f"move: nothing FILLED #{G.norm(colour)} matches"
                         + (f" band{'-x' if band_x else ''} "
                            f"{sel[0]:g}:{sel[1]:g} mm" if sel else ""))
    n = sum(len(k) for _, k, _ in groups)
    # Keep the MOVED geometry as we go rather than re-selecting afterwards. A
    # move whose whole point is to leave the band -- stacking a second word
    # under the first -- selects nothing on the way back, and the report then
    # took the centroid of an empty geometry and crashed.
    moved = []
    for r, keep, rest in groups:
        shifted = [shapely.affinity.translate(p, dx * doc.upm, dy * doc.upm)
                   for p in keep]
        moved += shifted
        doc.set_fill_geom(r, unary_union(shifted + rest))
    doc.rescan()
    blk = unary_union(moved)
    near = []
    for c in sorted(doc.colours()):
        if c == G.norm(colour):
            continue
        g = doc.geom_of(c)
        if g is not None and not g.is_empty:
            near.append(f"#{c} {blk.distance(g) / doc.upm:.2f} mm")
    x0, y0, x1, y1 = blk.bounds
    return (f"moved {n} component(s) of #{G.norm(colour)} by "
            f"{dx:+.2f},{dy:+.2f} mm -> now at {doc.at(blk)} mm, "
            f"{(x1 - x0) / doc.upm:.1f} x {(y1 - y0) / doc.upm:.1f} mm"
            + ("; clears " + ", ".join(near) if near else ""))


@op("space-out", "space-out --colour X --gap N [--band A:B]   re-space rows of components")
def space_out(doc, colour: str, gap: float, band=None, line_gap: float | None = None,
              **_):
    """Open the spacing between components to a declared minimum, row by row.

    The gap between two letters is THREAD when the lettering is knocked out of
    a filled shape, so it is bound by the same minimum feature width as any
    other thread. Sour Puss Muffy's letters sit 0.45-0.67 mm apart, and that
    sliver of white crown between two letters cannot hold: it is what "the
    stitching bleeds into it" describes.

    Rows are found by vertical overlap and each is re-spaced along its own
    baseline, then re-centred where it was, so the block does not walk across
    the design. Rows are then separated by `--line-gap` (default: the same
    figure) and the block re-centred vertically. Distances are solved on the
    true geometry, not on bounding boxes.

    This does not check that the result still fits inside whatever encloses it.
    Nothing here can — the enclosing shape may not exist yet, as on this artwork
    where the crown is a cloth pocket that `pockets` has not computed. Measure
    the containment afterwards.
    """
    groups = _matched(doc, colour, band)
    if not groups:
        raise SystemExit(f"space-out: nothing FILLED #{G.norm(colour)} matches"
                         + (f" band {band[0]:g}:{band[1]:g} mm" if band else ""))
    lg = gap if line_gap is None else line_gap
    want, want_l = gap * doc.upm, lg * doc.upm
    lines = []
    for r, keep, rest in groups:
        rows = _rows_of(doc, keep)
        moved_rows = []
        for row in rows:
            was = [row[i + 1].distance(row[i]) / doc.upm for i in range(len(row) - 1)]
            x_before = unary_union(row).centroid.x
            out = [row[0]]
            for p in row[1:]:
                out.append(_shift_to_gap(out[-1], p, want, axis=0))
            merged = unary_union(out)
            out = [shapely.affinity.translate(p, x_before - merged.centroid.x, 0.0)
                   for p in out]
            moved_rows.append(out)
            if was:
                lines.append(f"    row of {len(row)}: gaps "
                             + ", ".join(f"{g:.2f}" for g in was)
                             + f" -> {gap:g} mm, width "
                             + f"{(merged.bounds[2] - merged.bounds[0]) / doc.upm:.1f} mm")
        # Then the rows against each other, block re-centred vertically.
        if len(moved_rows) > 1:
            y_before = unary_union([p for rw in moved_rows for p in rw]).centroid.y
            stacked = [moved_rows[0]]
            for rw in moved_rows[1:]:
                prev = unary_union(stacked[-1])
                d = _shift_to_gap(prev, unary_union(rw), want_l, axis=1)
                dy = d.centroid.y - unary_union(rw).centroid.y
                stacked.append([shapely.affinity.translate(p, 0.0, dy) for p in rw])
            allp = unary_union([p for rw in stacked for p in rw])
            dy = y_before - allp.centroid.y
            moved_rows = [[shapely.affinity.translate(p, 0.0, dy) for p in rw]
                          for rw in stacked]
            lines.append(f"    {len(moved_rows)} rows separated to {lg:g} mm")
        doc.set_fill_geom(r, unary_union([p for rw in moved_rows for p in rw] + rest))
    doc.rescan()
    n = sum(len(k) for _, k, _ in groups)
    return (f"re-spaced {n} component(s) of #{G.norm(colour)} to a {gap:g} mm gap\n"
            + "\n".join(lines))


@op("pockets", "pockets --adjacent X --emit C [--min-width N]   stitch enclosed bare cloth beside X in C")
def pockets(doc, adjacent: str, emit: str, lid_above: float | None = None,
            min_width: float = MIN_W, **_):
    ink_c, thread_c = G.norm(adjacent), G.norm(emit)
    ink = doc.geom_of(ink_c)
    if ink is None:
        raise SystemExit(f"pockets: nothing is painted #{ink_c}")
    drawn = unary_union([r.geom for r in doc.regions])
    x0, y0, x1, y1 = doc.bounds

    note = ""
    sealed = drawn
    if lid_above is not None:
        # An outline with no top silhouette holds no pocket at all. The lid is
        # the convex hull of what IS drawn up there, which pins the closure to
        # real extreme points of the artwork rather than to an invented curve.
        # It authors geometry that is not in the source — look at the preview.
        crown_box = box(x0, y0, x1, y0 + lid_above * doc.upm)
        crown = drawn.intersection(crown_box)
        if crown.is_empty:
            raise SystemExit(f"pockets --lid-above {lid_above:g}: nothing is drawn there")
        sealed = unary_union([drawn, crown_box.difference(crown.convex_hull)])
        note = (f"; sealed the top {lid_above:g} mm with the convex hull of "
                f"{doc.mm2(crown):.0f} mm2 (AUTHORED, not in the source)")

    pad = 5 * doc.upm
    canvas = box(x0 - pad, y0 - pad, x1 + pad, y1 + pad)
    corner = shapely.Point(x0 - pad / 2, y0 - pad / 2)
    parts = G.polys(canvas.difference(sealed))
    enclosed = [p for p in parts if not p.contains(corner)]
    eps = 0.05 * doc.upm
    chosen = [p for p in enclosed if p.buffer(eps).intersects(ink)]
    if not chosen:
        raise SystemExit(
            f"pockets: {len(enclosed)} enclosed pocket(s) found but none touches "
            f"#{ink_c}. If the region you want is open to the background, it holds "
            "no pocket — see --lid-above.")

    # Not every gap in the artwork is a white AREA. Illustration for light paper
    # routinely sets ink into a hairline gap in the colour beneath it, so the
    # paper shows as a keyline around it. That gap is bare cloth by intent, and
    # emitting it as THREAD puts a white halo around every eye and mouth which
    # then runs into the colour beside it — observed on both Muffy designs, on
    # fabric, after everything else here was right.
    #
    # Discriminate by whether the pocket can hold a disc of `min_width`: an area
    # can, a keyline cannot. Erosion is exact, so no rasterising and no
    # threshold to tune. Measured on MuffyHat the two populations are three
    # orders apart — real pockets 1.25-5.42 mm across, keylines 0.08 mm — so
    # this is not a close call anywhere it has been run.
    thin = [p for p in chosen if p.buffer(-min_width / 2 * doc.upm).is_empty]
    keep = [p for p in chosen if not p.buffer(-min_width / 2 * doc.upm).is_empty]
    if not keep:
        raise SystemExit(
            f"pockets: all {len(chosen)} pocket(s) touching #{ink_c} are narrower "
            f"than --min-width {min_width:g} mm, so every one of them is a keyline "
            "rather than an area. Lower it if this artwork really is that fine.")
    dropped = ""
    if thin:
        w = ", ".join(f"{doc.mm2(p):.1f} mm2 at {doc.at(p)}" for p in thin[:4])
        dropped = (f"; dropped {len(thin)} keyline pocket(s) under {min_width:g} mm "
                   f"wide, left as bare cloth ({w}"
                   + (", ..." if len(thin) > 4 else "") + ")")

    geom = unary_union(keep)
    doc.add_fill(geom, thread_c, ident="pockets")
    doc.rescan()
    return (f"{len(keep)} of {len(enclosed)} enclosed pocket(s) emitted as "
            f"#{thread_c}: {doc.mm2(geom):,.0f} mm2{note}{dropped}")


@op("set-stroke", "set-stroke --colour X --mm N   set X's stroke width (and --to colour)")
def set_stroke(doc, colour: str, mm: float, to: str | None = None, **_):
    a = G.norm(colour)
    targets = [r for r in doc.regions if r.colour == a]
    if not targets:
        raise SystemExit(f"set-stroke: nothing is painted #{a}")
    stroke_c = G.norm(to) if to else a
    for r in targets:
        el = r.el
        doc._drop_style(el, ("stroke", "stroke-width"))
        el.set("stroke", f"#{stroke_c}")
        el.set("stroke-width", f"{mm * doc.upm:.4f}".rstrip("0").rstrip("."))
    doc.rescan()
    return f"stroked {len(targets)} element(s) of #{a} at {mm:g} mm in #{stroke_c}"


@op("report", "report                      list colours, areas and region counts")
def report(doc, **_):
    lines = ["  %-9s %10s %8s %8s" % ("colour", "area mm2", "fills", "strokes")]
    for c, area in sorted(doc.colours().items(), key=lambda kv: -kv[1]):
        lines.append("  #%-8s %10.1f %8d %8d"
                     % (c, area, len(doc.select(c, "fill")), len(doc.select(c, "stroke"))))
    return "\n".join(lines)
