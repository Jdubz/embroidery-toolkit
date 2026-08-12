# Designing for dark cloth

Unstitched fabric is a colour in the design. Every design in this repo uses it —
that is why `LemonCat_solid_on_white` is named for white cloth and `LemonCat_outline_on_yellow` for yellow, and why
`IHeartScreaming_on_white` needs no white thread despite having white eyeballs, white teeth and
white lettering. The paper shows through, and it is free: no thread, no stitches,
no machine time, and the piece stays soft where it is not sewn.

Move the same file to black cloth and that colour changes underneath you. This is
the procedure for building the dark-cloth counterpart.

`12-design-generation-playbook.md` still applies in full — this only covers what
is different.

---

## First: which kind of design is it?

The right tool depends on how the artwork is built, and the three cases need
completely different work. Getting this wrong is not a small error: two of the
three produce a file that validates clean and stitches the wrong picture.

| Artwork | Dark-cloth job | Tool |
|---|---|---|
| One colour, linework only | Relabel the thread | `tools/svg_recolor.py` |
| Shapes **painted over** each other | Knock the upper shape out of the lower | `tools/svg_knockout.py` |
| Ink layer with **holes** in it | Recover the holes as thread, drop the ink | `tools/svg_dark_invert.py` |
| **Anything else** | Compose the treatment | **`tools/svg_edit.py --op …`** |

Tell the middle two apart by looking at the artwork's own structure, not at the
picture. Open the SVG: if the white areas are *paths with a white fill*, it is
overpainted. If they are *subpaths of the ink path* with `fill-rule="evenodd"`,
they are holes. `tools/svg_subpath_filter.py --report` prints the nesting depth
of every subpath and settles it — odd depth is a hole, even is a fill.

**Most real artwork is the fourth row.** The first three cases were each derived
from one design and each assumes something the next artwork does not honour. The
Muffy and LemonCat drawings broke all three at once: their whites belong to no
layer's hole set at all (MuffyHat's hat interior is bounded by a yellow *outline*
and owned by nothing), and their ink is *stroke* rather than fill — 1,008 of
LemonCat's 1,341 mm² of black. Case 4 exists because the fixed sequences ran out.

---

## The question to ask before any of them

**Should the design carry the ink colour at all?**

`LemonCat_solid_on_black` was stitching 1,341 mm² of black thread onto black
cloth. Measured, 74% of it lay over the yellow where black-on-yellow reads
perfectly well — but 26% lay on bare cloth doing nothing, with the outer
silhouette stroke 50.8% over cloth and both whiskers 49.7%, so they stitched at
half width and read as broken.

Inverting it **cost a colour rather than adding one**: 3 → 2, and 8,768 stitches
→ 3,994. That is the usual shape of the answer on dark cloth. Check it with
`svg_edit … --op report` and a per-element overlap measurement before assuming
the ink has to be there.

---

## Case 1: one-colour linework — a thread swap, not a file

**The machine cannot detect what is on the spool.** It stops at each colour
change and shows a name; you load whatever you like. So `LemonCat_outline_on_yellow.pes` stitched
with white thread on black cloth already *is* the dark-cloth version, and no new
file is strictly needed.

What a recoloured copy buys is honesty in the previews:

```powershell
py tools\svg_recolor.py art\originals\LemonCat_embroidery_outline.svg `
    art\prepared\LemonCat_outline_on_black.svg --map '000000=FFFFFF'
```

The colour the machine names at each change, the Design Database Transfer
swatch, and `stitch render` / `stitch proof` all then agree with what is actually
being sewn. A black-labelled design previewed on black cloth is an invisible
smudge, which is exactly when you want the preview.

`LemonCat_outline_on_black.pes` is byte-comparable to `LemonCat_outline_on_yellow.pes` in geometry — 3,919 stitches
either way. If you would rather keep the DDT transfer list short, delete the spec
and just remember to load white.

> **Quote hex in PowerShell.** `--map 000000=FFFFFF` unquoted evaluates the left
> side as the number `0`. Both `svg_recolor` and `svg_dark_invert` reject
> malformed hex rather than guessing, because a wrong guess stitches the wrong
> colour.

---

## Case 2: overpainted artwork — the ordering trap

This one cost a build here and is worth reading even if you never touch dark
cloth, because **`validate` and `coverage` both pass the broken file.**

`LemonCat_embroidery_solid_yellow.svg` draws a full-silhouette yellow body and
then two white eyes on top of it. SVG is a painter's model, so the eyes win.

`svg_prep` orders layers **light to dark** — the invariant that makes a darker
colour own each shared boundary. White is lighter than yellow, so white is
stitched *first* and the yellow body is then sewn straight over it. The eyes come
out yellow.

Nothing caught it:

- `validate` — clean. Nothing about the file is malformed.
- `coverage` — **100%**. The yellow genuinely does cover the artwork; coverage
  asks whether pixels got stitched, not whether they got the right colour.
- `stitch info`, the density histogram, the short-stitch count — all normal.

Only `stitch render` showed it, and only because the fabric colour made the eyes
obvious. **Render every dark-cloth variant on its target fabric before believing
it**, and read the `stitch order` line `svg_prep` prints:

```
stitch order: #FFFFFF x2 -> #FFD400 x1 -> #000000 x16
```

If a colour is listed *before* something that sits under it in the artwork, and
they overlap, the lower one will cover it.

The fix is the knockout `svg_prep --skip` already performs, minus the dropping —
one path carrying both outlines with `fill-rule="evenodd"`, so the upper shape
becomes a hole in the lower and has bare fabric to sit on:

```powershell
py tools\svg_knockout.py art\originals\LemonCat_embroidery_solid_yellow.svg `
    art\prepared\LemonCat_solid_on_black.svg --knock 'FFFFFF=FFD400'
```

It also stops 452 mm² of yellow being stitched under thread that hides it.

`svg_knockout` refuses a punch shape that does not actually lie inside its host.
That is a registration check, not a validity one: concatenating the wrong
geometry still parses, still renders as a plausible drawing, and still stitches —
the error only appears on fabric.

---

## Case 3: knockout artwork — invert it

`IHeartScreaming_on_white` is the hard case. Its whites are not shapes at all; they are 27 holes in
a single black ink layer, and on black cloth every one of them goes dark. The
lettering, the teeth, the eyeballs and the spit droplets all vanish, and the ink
layer that used to define them is itself invisible against the fabric.

```powershell
py tools\svg_dark_invert.py art\prepared\IHeartScreaming_on_white.svg art\prepared\IHeartScreaming_on_black.svg `
    --artwork-mm 87 --ink '000000' --thread 'FFFFFF' --promote-at 11.0,15.4
```

Three things happen, and the reasoning behind each matters more than the command:

**The ink layer is dropped.** On dark cloth, bare fabric already *is* the ink
colour. Stitching it spends thread and time on something you cannot see. This is
not a compromise — outlines, pupils, tooth gaps and the mouth all still read,
because they are the fabric showing between stitched areas. It is also the
cheaper file: 2,742 mm² of ink removed against 1,630 mm² of white added.

**Holes that revealed bare paper become thread. Holes that revealed another
colour are left alone.** This is the part that must be measured. Three of
IHeartScreaming_on_white's 27 holes sit over the green head, the red heart and the red tongue.
Filling those with white would stitch white *under* a colour that is then
stitched over it — the manual's "three or more overlapping stitches", which
broke two needles here once already. The tool rasterises every other colour and
measures each hole's bare fraction rather than inferring it from position;
`--report` prints the table.

**`--promote-at` rescues a solid ink mass.** Ink shapes with nothing underneath
simply disappear when the layer is dropped. On IHeartScreaming_on_white that is the "I" of "I ♥
Screaming" — a discrete 225 mm² subpath, so it can be named by position and
stitched in the thread colour instead. The heart outline and the droplet outlines
are *not* promoted: on black cloth an absent outline reads as a black outline,
which is what the artwork wanted.

### What it cannot do

**It cannot split a shape.** IHeartScreaming_on_white's outlines, hair and tooth gaps are one
4,942 mm² subpath, so "keep the hair but drop the outlines" is unreachable from
this artwork — the hair goes unstitched with everything else, and the head reads
as a smooth green silhouette. Fixing that means editing the source artwork to
separate the hair, not adding a flag.

`--keep-ink` stitches the ink layer anyway. Black thread on black cloth is not
truly invisible — it reads by sheen and texture against matte fabric — so this is
a real option for a tonal look. It costs the full ink layer in stitches and adds
a fourth colour change.

---

## Case 4: compose it — `svg_edit`

When none of the three fixed sequences fits, build the treatment from atomic
operations. `svg_edit.py --list-ops` prints the vocabulary; the ones that matter
here are `subtract`, `drop`, `recolour` and `pockets`. Each prints what it
changed, `--preview DIR` writes a PNG after every step, and every run logs its
ops so `--replay` reproduces it byte-for-byte.

All three dark-cloth designs built this way are four operations or fewer.

**LemonCat_solid_on_black** — ink painted on top of a solid silhouette:

```
subtract --colour FFD400 --by 000000    cut the linework out of the body
subtract --colour FFFFFF --by 000000    and out of the eyes
subtract --colour FFD400 --by FFFFFF    knock the eyes out of the body
drop     --colour 000000                let the cloth supply the linework
```

**MuffyHat_on_black** — the whites are unowned pockets of cloth:

```
pockets --adjacent 000000 --emit FFFFFF --lid-above 26
drop    --colour 000000
```

**PissMuffy_on_black** — lettering stays as thread, the face inverts:

```
recolour --colour 000000 --to FFFFFF --band 0:30
recolour --colour 000000 --to FFFFFF --band 78:120
pockets  --adjacent 000000 --emit FFFFFF
drop     --colour 000000
```

### The three rules these encode

**Dropped ink must be SUBTRACTED from what lies under it.** Muffy's yellow and
black intersect over 0 units², so `drop` alone is enough there. LemonCat is drawn
the normal way round and they overlap by 993 mm², so dropping alone lets the
yellow fill straight back in — the cat loses its face and `validate` stays clean.
If the ink overlaps anything, subtract before you drop.

**Order is the design.** The eye knockout must come *after* the eyes have had the
ink cut out of them, or it knocks out the eyes as drawn rather than as stitched.

**A pocket needs a boundary.** `pockets` finds enclosed bare cloth as the
disconnected parts of canvas-minus-everything-drawn, so it does not care which
layer bounds a region — but an *open* region is not a pocket. MuffyHat's hat
crown has no top silhouette at all, only three free-standing ridge arcs with sky
between them, so its interior leaks into the background. Verified: a true
morphological closing at 2.0, 2.5 and 3.0 mm all reopened it, which is what tells
you it is a wide opening and not a hairline gap. `--lid-above MM` seals it with
the convex hull of the geometry above that line. **That authors geometry which is
not in the source** — the tool says so on every run, and you should look at the
preview before believing it.

### Selectors: measured, not positional

`--band Y0:Y1` selects by centroid, in mm down from the top of the drawing, and
it operates on connected **components** rather than elements — PissMuffy's 29
letters, eyes, brows and mouth are a single `<path>`, so an element-level filter
would match the centroid of the whole design and select nothing. A partial match
splits the element.

Prefer colour, area, enclosure and adjacency over coordinates wherever a
measurement will do. An earlier attempt selected the kept lettering with
hand-placed circles, and the lower circle clipped the question mark out of
`HOT PISS?` — it silently became bare cloth, with no error anywhere.

---

## Three things the render cannot show you

Added after the `MuffyHat_on_black` stitch-out
(`photos/PXL_20260812_064352867.jpg`). It passed every gate below, `validate`
was clean, `coverage` was fine, and the piece still came off the machine wrong
in three separate ways. All three are about **contrast on dark cloth**, which
nothing in the toolkit measured, because every check here asks whether the
stitches are *sound* and none asks whether they are *distinguishable*.

### 1. The validated fill density is validated on white

`design_limits.fill_density_mm` is 0.4 mm, and 0.4 mm covers. What it does not
do is *hide the cloth between the rows* — and on white cloth that does not
matter, because the gap between two rows of yellow thread over white fabric is
invisible. On black the same gap is a black dot at every needle penetration,
and a gold fill that reads solid on cream reads speckled on black twill.

Use `design_limits.fill_density_mm_dark` (0.33 mm) whenever the thread is much
lighter than the cloth. In a spec that is one option:

```json
"options": { "Cloth": "dark" }
```

It costs about 21% more rows. Check `density_max_per_mm2` in the manifest
afterwards against the 16 cap — on the five dark designs here it stayed at 13
or below, because the geometry changes below took area back out.

### 2. Two light colours drawn edge to edge stitch as one mass

The white hat and the gold body were **drawn** touching, which is correct in
vector art and wrong in thread. Pull compensation grows every colour outward
independently, so a shared boundary is claimed twice: 339 mm of the white's
735 mm perimeter sat at exactly zero distance from the gold, and after 0.2 mm
of expansion per side the two overlapped by 136 mm². On black cloth they read
as a single pale shape.

On light cloth this never came up, because a black keyline separated everything
— and inverting for dark cloth is precisely the operation that **drops that
keyline**. `CLAUDE.md` already says dropped ink must be subtracted from what
lies under it; this is the other half of that rule. Dropped ink that lay
*between* two colours has to be replaced by a cut, or they fuse:

```
gap --colour F6BE00 --by FFFFFF --mm 0.6
```

Two things to get right:

- **Take the channel out of the shape that can afford it, not out of the one
  stitched first.** The arithmetic is identical either way. Cutting MuffyHat's
  white hat cost 180 mm² and consumed two white shells outright; cutting the
  gold body cost 262 mm² out of 3,455 and changed no topology at all. Read the
  shell counts the op prints — that is what caught it.
- **Budget against pull compensation.** Both sides advance `expand` into the
  channel, so a cut of N shows as N − 2·expand.

This is a hairline, not a restored keyline. Only 35% of that contact line ever
carried black, and the keyline measures 1.33 mm median, so restoring it
properly would want a 1.7 mm cut. `design_limits.colour_gap_mm` is 0.8 —
deliberately less.

### 3. Knocked-out detail is measured on the wrong side of every limit

Everything in `design_limits` sizes **thread**: the narrowest line that will
hold. A knockout is the complement — what has to survive is the **cloth**, and
it is attacked from both rails at once. Pull compensation takes `expand` off
each side, and the thread on those rails blooms over the edge on top of that.

`SOUR PUSS` is knocked out of the white crown at a **1.42 mm median gap**. That
clears the 1.2 mm safe feature width, which is why nothing flagged it. 0.2 mm
of pull compensation per side takes it to **1.00 mm** and closes 29% of the
negative area outright; bloom finishes the job. It came off the machine barely
legible.

So size a knockout as `safe_satin_width + 2·expand + bloom` —
`design_limits.negative_space_mm`, 1.8 mm. There are two levers and you should
expect to need the second:

**Widen the holes** — `widen-negative --colour FFFFFF --to-min 1.8`. Often it
cannot help, and it will tell you so:

```
widen-negative: #FFFFFF's 12 hole(s) CANNOT be opened — 43% of the negative is
under 1.8 mm and CLAMPED: 0.44 mm per side would have merged the negative
(12 holes -> 2); the most that keeps them distinct is 0.02 mm.
```

That is the honest answer for lettering this size: the letters are as narrow as
the thread between them, so there is no material to move. **The guard has to
count holes, not shells.** An earlier version of this op counted shells,
watched them rise (widening lettering severs the shape it sits in — harmless),
and shipped a `SOUR PUSS` whose every counter had closed. It had made the text
*less* legible than the defect it was fixing, and the render caught it, not the
guard.

**Stop taking width off them** — drop `--expand`. Pull compensation exists to
stop a hairline of bare cloth appearing where two colours meet, and after a
`gap` op there is nowhere they meet. All that is left of its effect is the
0.2 mm per side it takes off every knockout:

```json
"options": { "Cloth": "dark", "Expand": 0.05 }
```

That returns the lettering from 1.00 mm to 1.25 mm, and the share of the negative that closes outright from 29% to 7% — the largest single
improvement available to it, and on this artwork the only one.

**When both levers are exhausted, the artwork is what is wrong.** At 5 mm cap
height the SOUR PUSS lettering is at `min_text_cap_height_mm` for *positive*
text, and a knockout is harder than positive text. That is the case here, so the
next section is how the artwork was changed.

---

## Redrawing detail that is too small

`scale`, `space-out` and `move` exist for this. They are ordinary `svg_edit`
ops, so a redraw is declared in the spec and rebuilt like anything else — the
original in `art/originals/` is still never edited.

**Measure both sides of a knockout before deciding what is wrong with it.** The
obvious read on SOUR PUSS is that the letters are too thin. Measured, that is
the *second* problem:

| | measured | limit | what it is |
|---|---|---|---|
| Letter stroke | 1.33–1.42 mm | 1.8 mm | bare cloth |
| **Bridge between letters** | **0.45–0.67 mm** | 1.2 mm | **white thread** |

A 0.5 mm sliver of fill between two letters does not form. It bleeds into them,
which is exactly what the photograph shows — and it is why `widen-negative`
refuses: widening the letters can only come out of bridges that are already too
thin. **When both sides of a knockout are under limit at once there is no
material to move, and only changing the geometry helps.**

```
space-out --colour 000000 --band 8:28 --gap 1.64 --line-gap 2.04
scale     --colour 000000 --band 8:28 --factor 1.10
move      --colour 000000 --band 8:28 --dx -0.75 --dy 3.25
```

**Order is forced, and `scale` enforces it.** Scaling first makes the letters
collide, and the union that has to follow — even-odd would XOR an overlap into a
*hole* rather than merge it — fuses eight letters into one polygon
irreversibly. Every later op then addresses one blob and silently does nothing;
`space-out` reported "re-spaced 1 component(s)" and moved nothing at all. So
space first, then scale into the room that makes. The 1.64 mm is not 1.2 mm
because scaling closes the gaps again by the growth.

**The scale ceiling is set by the enclosing shape, not by taste.** 1.10× leaves
the block 1.02 mm clear of the crown edge — and that margin is *itself* a thread
bridge under the same 1.2 mm limit. 1.15× drops it to 0.63 mm, 1.20× to 0.16 mm.
The usable interior is the hat pocket *less the three gold ridge arcs*, which is
far smaller than the pocket's bounding box suggests. Getting bigger lettering
than this needs a bigger hat.

**Growing a block of detail almost always needs `move` as well.** `space-out`
re-centres each row where it was, and this block was never centred on its crown
— 11.1 mm clear on the left against 22.1 mm on the right — so growing it
symmetrically ran it off the near edge while a third of the crown stayed empty.
`move` is positional, so it reports what it ended up clearing; that report is
the check, not the offsets.

Result, measured on the built file:

| | before | after |
|---|---|---|
| Letter stroke, after pull comp | 1.00 mm | **1.42 mm** |
| Thread around and between letters | 0.45–0.67 mm | **2.00 mm median, 4% under 1.2 mm** |
| White ↔ gold separation | 0 mm (overlapping) | **0.79 mm of bare cloth** |

**Apply the redraw to the light-cloth sibling too.** The two variants differ in
*treatment*, not in artwork, so `MuffyHat_on_white` gained a `prepare` step with
the same three ops and nothing else. The arithmetic there is different — the
letters are black thread and the gaps are cloth, so only the letters were ever
near a limit — but the drawing has to stay the same drawing.

---

## Gates

Run the full set from `12-design-generation-playbook.md`, plus:

**Render on the actual fabric colour.** Not the default off-white.

```powershell
.\stitch.ps1 render designs\out\IHeartScreaming_on_black.pes --fabric '#101010' -o build\reviews\ScreamB_on_black.png
```

**Check coverage against the *inverted* artwork, not the original.** Comparing
`IHeartScreaming_on_black` to the original IHeartScreaming_on_white PNG is meaningless — the black it "failed to
stitch" is deliberate. `coverage` keys on the alpha channel, so export the
prepared SVG to a transparent PNG and the recovered white counts as ink like
anything else:

```powershell
& "C:\Program Files\Inkscape\bin\inkscape.exe" --export-type=png `
    --export-background-opacity=0 --export-width=1200 `
    --export-filename=work\ScreamB_artwork.png art\prepared\IHeartScreaming_on_black.svg
.\stitch.ps1 coverage designs\out\IHeartScreaming_on_black.pes --source work\ScreamB_artwork.png
```

---

## The library, both ways

**Read `measured` in `build/manifest.json` for current figures — it is written on
every build and never drifts.** The table below is a dated snapshot kept because
it carries an argument the manifest does not: that the dark variant is usually
the *cheaper* one. Every design here has both a light and a dark form.

*Measured 2026-08-12.*

| Design | Cloth | Colours | Stitches | Run | Peak /mm² |
|---|---|---|---|---|---|
| `LemonCat_outline_on_yellow` | yellow / any light | 1 | 3,919 | 10 min | 9 |
| `LemonCat_outline_on_black` | black | 1 | 3,919 | 10 min | 9 |
| `LemonCat_solid_on_white` | white | 2 | 8,149 | 22 min | 14 |
| `LemonCat_solid_on_black` | black | **2** | **3,994** | **12 min** | **7** |
| `IHeartScreaming_on_white` | white / light | 3 | 10,751 | 30 min | 12 |
| `IHeartScreaming_on_black` | black | 3 | 7,054 | 21 min | 8 |
| `MuffyHat_on_white` | white / light | 2 | 6,933 | 19 min | 10 |
| `MuffyHat_on_black` | black | 2 | 8,180 | 22 min | 14 |
| `PissMuffy_on_white` | white / light | 2 | 8,427 | 23 min | 10 |
| `PissMuffy_on_black` | black | 2 | 8,557 | 23 min | 12 |

*An earlier version of this table listed the Muffy designs at 11,795 and 13,263
stitches. Those were the retired raster builds; both are now vector, and the
figures had been hand-copied here where nothing could check them.*

### What the earlier prediction got right and wrong

This section used to say the Muffy pair had no dark counterpart, that
`MuffyHat`'s hat "disappears entirely and would have to become a large white
fill, taking the design to three colours", and that `PissMuffy` was the easier of
the two because its lettering was a spec-level colour change.

The hat did become a large white fill — 781 mm² — and the prediction of *what*
was needed was right. **The colour count was wrong**: it stayed at two, because
the recovered white merges with the eye sclera into a single pass and a single
stop. And PissMuffy was not the easier one: its lettering could not be remapped
wholesale, because the same black also draws its eyes, brows and mouth, which had
to invert instead. Splitting one from the other is what forced selectors to
address components rather than elements.

`LemonCat_solid_on_black` used to peak at 16 penetrations/mm² — the profile's
`max_density_per_mm2` — where the white sclera, its underlay, the black satin eye
outline and the pupils all stacked. The inversion removed the satin outline
entirely and it now peaks at **7**, the lowest in the set. That was a side effect,
not the goal, and it is the clearest evidence that dropping ink on dark cloth
buys reliability as well as time.

`IHeartScreaming_on_black` being *cheaper* than `IHeartScreaming_on_white` is the general shape of this: on dark
cloth the ink layer usually turns into free negative space, and you pay only for
the whites you get back.
