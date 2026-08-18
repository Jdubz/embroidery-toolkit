# Binding a bag edge

A reusable technique note. Patterns in `patterns/` reference this rather than
re-explaining it; nothing here is specific to any one design.

**Binding** is a strip of material wrapped around a raw edge and stitched
through, so the edge is enclosed and both faces are finished in one pass. In bag
making it does two jobs at once: it finishes the edge *and* it is the seam — two
panels held together with nothing but the binding round their common edge.

---

## First: this is not quilt binding

Almost every binding tutorial online is about quilts, and it teaches a different
geometry. **Following it will give you a strip too narrow to work.**

| | Bias *tape* (quilt / garment) | **Bound edge** (bags) |
|---|---|---|
| What it does | Lies flat on **one** face, raw edges turned under | **Wraps** the edge, shows on **both** faces |
| Width rule | finished × 2 (single fold) or × 4 (double fold) | **2 × show + the sandwich** — see below |
| ½" finished | cut 1" or 2" | cut ~**1⅛"** |

The quilt formula measures the strip that ends up on top. The bag formula has to
get all the way round the edge and back. They are not interchangeable.

## The width formula

```
cut width  =  2 × (what you want showing on each face)
           +  the thickness of the sandwich it wraps
           +  1/16"  for the turn
```

| Showing each face | Sandwich | Cut |
|---|---|---|
| ⅜" | thin, 2 light layers | **⅞"** |
| ½" | ~1.5 mm — two coated layers plus a shell | **1⅛"** |
| ½" | ~3 mm — heavy or four layers | **1¼"** |
| ⅝" | ~3 mm | **1½"** |

**Always cut a test strip and wrap it round the actual sandwich before cutting
yards of it.** The sandwich term is the one people guess wrong, and binding that
is ⅛" short does not reveal itself until you are halfway round a bag.

```svg
<svg id="bound-seam" viewBox="0 0 620 280" role="img" aria-label="Section through a bound seam. Two panels lie wrong sides together with their seam allowances pointing outward, forming a flange; the binding wraps that flange and one line of stitching catches binding, both panels and binding again.">
  <g font-family="var(--f-label)" font-size="11" letter-spacing="1.6" fill="var(--muted)">
    <text x="20" y="24">SECTION THROUGH A BOUND SEAM</text>
  </g>

  <!-- the two panels, wrong sides together, allowances pointing right -->
  <rect x="40" y="118" width="440" height="16" fill="var(--shell)"/>
  <rect x="40" y="142" width="440" height="16" fill="var(--shell)"/>
  <text x="90" y="110" font-family="var(--f-data)" font-size="12" fill="var(--ink)">panel</text>
  <text x="90" y="180" font-family="var(--f-data)" font-size="12" fill="var(--ink)">gusset</text>

  <!-- the binding, wrapping the flange -->
  <path d="M427,104 H480 Q500,104 500,138 Q500,172 480,172 H427"
        fill="none" stroke="var(--binding)" stroke-width="13" stroke-linecap="round"/>

  <!-- the stitch line: raw edge to it is the seam allowance -->
  <path d="M435,88 V196" stroke="var(--stitch)" stroke-width="2" stroke-dasharray="7 4"/>
  <g fill="var(--stitch)">
    <circle cx="435" cy="110" r="4"/><circle cx="435" cy="126" r="4"/>
    <circle cx="435" cy="150" r="4"/><circle cx="435" cy="166" r="4"/>
  </g>
  <text x="435" y="80" text-anchor="middle" font-family="var(--f-data)"
        font-size="12" fill="var(--stitch)">one line, through all of it</text>

  <!-- raw edges, inside -->
  <path d="M480,118 V158" stroke="var(--cut)" stroke-width="2.5"/>
  <text x="504" y="214" font-family="var(--f-data)" font-size="12" fill="var(--cut)">raw edges,</text>
  <text x="504" y="230" font-family="var(--f-data)" font-size="12" fill="var(--cut)">enclosed</text>

  <!-- dimensions -->
  <g stroke="var(--muted)" stroke-width="1">
    <path d="M435,244 H480 M435,238 v12 M480,238 v12"/>
    <path d="M427,262 H500 M427,256 v12 M500,256 v12"/>
  </g>
  <text x="457" y="240" text-anchor="middle" font-family="var(--f-data)"
        font-size="11" fill="var(--muted)">SA</text>
  <text x="463" y="278" text-anchor="middle" font-family="var(--f-data)"
        font-size="11" fill="var(--muted)">binding shows</text>

  <text x="40" y="244" font-family="var(--f-data)" font-size="12" fill="var(--ink)">the allowance does NOT turn inward —</text>
  <text x="40" y="262" font-family="var(--f-data)" font-size="12" fill="var(--ink)">both point outward and become a flange</text>
</svg>
```

That picture is the whole convention. **The allowance does not turn in.** Both
pieces' allowances lie together pointing outward, the binding wraps them, and
one line of stitching catches binding, panel, gusset and binding again. It is
why the cut size is very nearly the finished size, and why the ring follows the
stitch line rather than the raw edge.

## Single fold or double fold

| | When | Layers at the seam |
|---|---|---|
| **Single fold** — outer edge left raw | The binding material **does not fray**: coated or laminated cloth, hot-knifed nylon, leather, vinyl, faux leather | 2 |
| **Double fold** — outer edge turned under first | Anything that frays: canvas, denim, quilting cotton, waxed canvas | 4 |

Double fold costs another ¾" of strip width and doubles the layers at every seam,
which matters on a domestic machine. **If you can choose a non-fraying binding
material, do** — it is the single biggest simplification available.

## Straight grain or bias

| | Use for | Cost |
|---|---|---|
| **Straight grain** | Straight runs and **square corners you will mitre** | Long strips, no piecing, no waste |
| **Bias** (45°) | **Curves and rounded corners** — nothing else eases round a curve | ~30% more material, and strips need piecing |

This is another place bags differ from quilts. Quilts are bound on the bias as a
matter of course, because a bias fold wears better along an edge that gets
handled for decades. **A bag with square corners does not need it.** Cut straight
grain, mitre the corners, and keep the long uninterrupted strips.

Round a corner and you have no choice: cut bias.

**How much ease the bias has to absorb does not depend on the radius.** The
outer fold travels `(π/2) × show` further than the stitch line round any
quarter turn — 13/16″ at a ½″ show, the same at a 1″ radius as at a 3″ one.
What the radius changes is the *arc it is spread over*, so a tight corner asks
for the same inch in less room: 50% of the arc at 1″, 33% at 1½″, 25% at 2″.
When a binding will not ease round a curve, **open the radius**; widening the
strip does nothing.

**A coated or laminated cloth has less bias give than a bare weave.** Bias
stretch is the weave shearing, and a coating is a film across it that resists
exactly that. It still eases — MYOG bags are bound in coated fabric routinely
— but not as generously as cotton bias does, so treat the percentages above as
the thing to keep low rather than as headroom. Cut a test strip and ease it
round a scrap of the actual corner before committing to a radius.

---

## Preparing the strip

- **Cut it long.** Joins are the ugliest part of a binding run; the fewer the
  better. Cut the longest strips the material allows.
- **Piece with a 45° seam**, not a square one. A diagonal join spreads the bulk
  over an inch instead of stacking it in one place.
- **Never plan a join at a corner.** Corners are already the thickest point.
- **Pre-fold or fold as you go.** A bias tape maker helps on light materials; on
  a coated or laminated cloth, and on leather, it is easier to fold with clips
  as you sew, because they
  hold a crease anyway.

## The one-pass method

Bag makers almost never sew binding on in two passes. One line of stitching
catches the binding on the front, the sandwich in the middle, and the binding on
the back.

That only works because of one trick, and it is the thing most people get wrong:

> ### Set the underside deeper than the top
>
> Offset the strip so **about 1/16" more binding sits under the work than over
> it**. Then a stitch line placed by eye on the visible top face lands
> comfortably inside the binding underneath.
>
> You cannot see the back while you sew. Without the offset, a line that looks
> perfect on top will wander off the binding on the back in a dozen places, and
> the only fix is unpicking.

```svg
<svg id="offset-binding" viewBox="0 0 620 300" role="img" aria-label="Why the binding is set deeper on the underside. Even binding: a stitch line placed by eye on the top face falls off the edge of the binding underneath. Offset binding: the same line lands well inside it.">
  <g font-family="var(--f-label)" font-size="11" letter-spacing="1.6">
    <text x="20" y="22" fill="var(--cut)">EVEN — THE LINE MISSES UNDERNEATH</text>
  </g>
  <rect x="40" y="60" width="360" height="30" fill="var(--shell)"/>
  <path d="M300,44 H400 Q416,44 416,75 Q416,106 400,106 H300"
        fill="none" stroke="var(--binding)" stroke-width="11"/>
  <path d="M296,36 V118" stroke="var(--cut)" stroke-width="2" stroke-dasharray="6 4"/>
  <circle cx="296" cy="52" r="4.5" fill="var(--stitch)"/>
  <circle cx="296" cy="98" r="4.5" fill="var(--cut)"/>
  <text x="286" y="34" text-anchor="end" font-family="var(--f-data)" font-size="12" fill="var(--stitch)">looks right on top</text>
  <text x="286" y="128" text-anchor="end" font-family="var(--f-data)" font-size="12" fill="var(--cut)">off the binding underneath</text>

  <g font-family="var(--f-label)" font-size="11" letter-spacing="1.6">
    <text x="20" y="182" fill="var(--stitch)">OFFSET 1/16″ DEEPER UNDERNEATH — IT LANDS</text>
  </g>
  <rect x="40" y="220" width="360" height="30" fill="var(--shell)"/>
  <path d="M300,204 H400 Q416,204 416,235 Q416,266 400,266 H276"
        fill="none" stroke="var(--binding)" stroke-width="11"/>
  <path d="M296,196 V282" stroke="var(--stitch)" stroke-width="2" stroke-dasharray="6 4"/>
  <circle cx="296" cy="212" r="4.5" fill="var(--stitch)"/>
  <circle cx="296" cy="258" r="4.5" fill="var(--stitch)"/>
  <g stroke="var(--muted)" stroke-width="1">
    <path d="M276,286 H300 M276,280 v12 M300,280 v12"/>
  </g>
  <text x="288" y="300" text-anchor="middle" font-family="var(--f-data)" font-size="11" fill="var(--muted)">1/16″</text>
  <text x="440" y="240" font-family="var(--f-data)" font-size="12" fill="var(--stitch)">caught on both faces</text>
</svg>
```

### Sewing it

| | |
|---|---|
| Stitch | Straight, **3.0–3.5 mm** |
| Placement | **⅛" in from the binding's inner edge** — the edge nearest the middle of the panel |
| Foot | Walking foot. Binding is a multi-layer sandwich and the layers will creep apart otherwise |
| Guide | An edge guide, or a strip of tape on the throat plate. A wandering binding line is the thing that makes work look homemade |
| Clips | Every 2". Never stretch the strip while clipping — stretched binding ripples once the tension comes off |
| Pace | Slow. This is the seam that shows |

---

## Outside corners — the mitre

A mitre is a 45° tuck that lets the binding turn 90° and lie flat. It forms on
both faces at once if you fold it correctly.

1. **Sew up to the corner and stop** where your stitch line would meet the next
   edge — not at the fabric edge, at the *stitch line* intersection. Getting this
   point right is the whole trick; stop short or long and the mitre will not lie.
2. **Needle down, presser foot up.**
3. **Fold the binding straight back on itself**, away from the direction of
   travel. A 45° diagonal appears at the corner.
4. **Fold it forward down the next edge**, so the new fold lines up with the edge
   you just finished sewing.
5. **Foot down, resume.**

```svg
<svg id="mitre" viewBox="0 0 640 210" role="img" aria-label="The four folds of a mitred corner: sew to the stitch-line intersection and stop, fold the binding straight back on itself so a 45 degree diagonal appears, fold it forward down the next edge, then resume sewing.">
  <g font-family="var(--f-data)" font-size="12" fill="var(--muted)">
    <text x="72" y="196" text-anchor="middle">1 — stop at the</text>
    <text x="72" y="210" text-anchor="middle">stitch-line corner</text>
    <text x="232" y="196" text-anchor="middle">2 — fold straight</text>
    <text x="232" y="210" text-anchor="middle">back on itself</text>
    <text x="392" y="196" text-anchor="middle">3 — fold forward</text>
    <text x="392" y="210" text-anchor="middle">down the next edge</text>
    <text x="552" y="196" text-anchor="middle">4 — foot down,</text>
    <text x="552" y="210" text-anchor="middle">resume</text>
  </g>

  <g fill="var(--shell)" opacity=".85">
    <rect x="20" y="40" width="104" height="104"/><rect x="180" y="40" width="104" height="104"/>
    <rect x="340" y="40" width="104" height="104"/><rect x="500" y="40" width="104" height="104"/>
  </g>

  <!-- 1: binding along the top edge, stitching stops at the corner -->
  <path d="M20,52 H124" stroke="var(--binding)" stroke-width="13"/>
  <path d="M20,52 H112" stroke="var(--stitch)" stroke-width="2.5" stroke-dasharray="6 4"/>
  <circle cx="112" cy="52" r="5" fill="var(--cut)"/>

  <!-- 2: folded straight back, diagonal appears -->
  <path d="M180,52 H284" stroke="var(--binding)" stroke-width="13"/>
  <path d="M284,52 L232,52" stroke="var(--binding)" stroke-width="13" opacity=".55"/>
  <path d="M272,40 L272,64" stroke="var(--cut)" stroke-width="2"/>
  <path d="M284,40 L260,64" stroke="var(--cut)" stroke-width="2.5"/>
  <circle cx="272" cy="52" r="5" fill="var(--cut)"/>

  <!-- 3: folded forward down the right edge -->
  <path d="M340,52 H444" stroke="var(--binding)" stroke-width="13"/>
  <path d="M432,52 V144" stroke="var(--binding)" stroke-width="13"/>
  <path d="M444,40 L420,64" stroke="var(--cut)" stroke-width="2.5"/>

  <!-- 4: sewn through -->
  <path d="M500,52 H604" stroke="var(--binding)" stroke-width="13"/>
  <path d="M592,52 V144" stroke="var(--binding)" stroke-width="13"/>
  <path d="M500,52 H584 L584,144" stroke="var(--stitch)" stroke-width="2.5" stroke-dasharray="6 4" fill="none"/>
  <path d="M604,40 L580,64" stroke="var(--stitch)" stroke-width="2"/>
</svg>
```

The tuck you made becomes the mitre on the top face. A matching one forms
underneath as the binding wraps — coax it with a bodkin or the point of your
scissors before you sew over it.

## Inside corners

Rarer in bags, and they behave the opposite way: the binding has to *stretch*
round rather than fold.

**Clip the base material at the corner**, into the seam allowance, right up to
where the stitch line will run. That lets the corner open out until it is nearly
straight, and you bind straight through it. When it relaxes, the corner closes
and the binding lies flat.

Clip too little and it puckers. Clip past the stitch line and you have cut a hole
in the work.

## Binding a 3D seam

Where the binding *is* the seam — a panel joined to a gusset, say — the two
pieces are held wrong sides together with their raw edges pointing outward, and
the binding wraps that flange.

Two things follow, and both bite:

- **A rectangular gusset cannot turn a square corner unless you clip it.** Cut
  its seam allowance at each corner, **only as far as the stitch line**, so it can
  splay and lie flat.
- **The binding also has to mitre at that same corner**, on top of the clipped
  gusset. It is the thickest point on the whole bag — hand-wheel it, and use a
  height-compensation scrap under the back of the foot so it does not tip.

## Closing the loop

Binding a closed edge means the strip has to meet itself. Three ways, worst to
best:

| Method | How | Verdict |
|---|---|---|
| **Overlap** | Trim the finishing end to lap the start by ½", tuck the raw end in | Fast, bulky. Fine where nothing frays — a coated cloth or webbing |
| **Fold-under** | Turn the finishing end under ¼" and lap it over the start | Tidy, one extra layer |
| **45° join** | Leave both ends free at the start, cut both at 45°, seam them, then sew that section | Cleanest and flattest. Worth it on anything visible |

Whichever you use: **put the join mid-edge, never at a corner**, and never where
a strap, ring or handle is going to land on top of it.

---

## When it goes wrong

| Symptom | Cause | Fix |
|---|---|---|
| Stitch line misses the binding on the back, in patches | No offset — front and back were even | Set the underside 1/16" deeper next time. Unpick the misses; there is no other repair |
| Binding ripples along a straight run | The strip was stretched as it was clipped | Clip with zero tension. On bias, let it hang before applying |
| Corner mitre is lumpy or will not lie flat | Stopped at the wrong point going into the corner | Stop at the **stitch-line intersection**, not the fabric edge |
| Binding will not reach round the edge | Width taken from a quilt formula, or the sandwich term guessed | Recut using the wrap formula, after testing on the real sandwich |
| Corner is too thick to sew | Gusset not clipped, or a join landed at the corner | Clip the gusset to the stitch line; move joins mid-edge |
| Wavy stitch line | Sewn by eye | Edge guide or tape on the throat plate |

## Machine setup

- **Walking foot.** Not optional on a multi-layer sandwich, and mandatory if
  vinyl or coated fabric is anywhere in it.
- **Stitch 3.0–3.5 mm.** Long. Short stitches perforate coated materials into a
  tear line.
- **Lengthen for thickness, do not shorten.**
- **Height compensation** — a folded scrap under the back of the foot — for
  stepping onto corners and joins.
- **Test on the real sandwich** before the real work. Every number above is a
  starting point; the strip width in particular depends on materials you have and
  I do not.

## Further reading

- [Bias binding basics — cutting, making, attaching](https://sew4home.com/bias-binding-tutorial-figuring-yardage-cutting-making-attaching/)
  — the clearest general reference, though written for flat work.
- [Single vs double fold, with the width formulas](https://makeit-loveit.com/bias-tape-tutorial-single-double-fold)
  — read it knowing the caveat at the top of this page.
- [Mitred corners, step by step](https://snugglesquilts.com/quilt-binding-tips-and-a-tutorial/)
  — quilt context, but the corner fold is identical.
- [Bound seam finishes](http://sewaholic.net/seam-finishes-bound-edges/)
  — the garment version, useful for the inside-corner case.
- [Joining binding ends in the round](https://oliverands.com/community/blog/2014/03/bias-binding-tutorial.html)

---

*Used by:* `patterns/StadiumTote_12x12x4.md`
