# The pattern schema

A sewing pattern here is **three files, two of them written by hand and one
generated**. The generated one — the *package* — is the only thing any consumer
reads. `tools/pattern_player.py` builds the player app from packages and from
nothing else.

```
patterns/constructions/box-bound.json     construction   how this KIND of bag is built
patterns/specs/<Name>.json                spec           what THIS bag is
        |
        |  tools/bag_pattern.py --package
        v
build/patterns/<Name>.json                package        everything, flattened + derived
```

**Never hand-edit a package.** It is regenerated from the two above and carries
a `provenance` block saying exactly which files and tool versions produced it.
Editing one is the same class of mistake as hand-editing a cut list, which
`patterns/README.md` already forbids and for the same reason: a figure checked
by nothing drifts.

---

## Why the construction is its own layer

`BoxBound_family.md` states it outright — the **stitch schedule, lock-off
policy, tool list and machine setup are properties of the materials and the
machine, not of the size**, and apply unchanged to all four bags. Copying them
into four specs would create four things to keep in step.

So the construction file holds the *procedure* and the spec holds the *object*.
A new size is a spec and nothing else; a change to how a box-bound bag is
assembled is one edit that reaches every bag.

---

## Layer 1 — construction

`patterns/constructions/<construction>.json`. A spec names it via
`"construction": "box-bound"`.

| Key | Type | Holds |
|---|---|---|
| `construction` | string | must equal the filename stem |
| `title`, `summary` | string | shown at the top of the player |
| `assembly[]` | step objects | the build order |
| `stitch_schedule[]` | `{operation, stitch, length_mm, foot, needle}` | one row per operation |
| `tools[]` | `{tool, why}` | what the bench needs |
| `checklist[]` | `{item, why}` | the before-cutting gates |
| `thickness[]` | `{location, stack, formula}` | the thickness budget, computed per bag |
| `docs[]` | `{title, path, kind}` | supporting Markdown every bag in the family shares |

### A step

```json
{
  "n": 11,
  "title": "Fit the ring and trim the gusset",
  "when": ["has_chassis"],
  "stitch": "straight, 3.0 mm, walking foot",
  "body": "Clip the ring round the back panel and trim the gusset to length — target {gusset_cut}, so that with a {lap} lap at each end onto the zipper panel the ring closes at {ring}."
}
```

`n` is the author's ordering key, not the displayed number — the package
renumbers after conditions are applied, so a bag that skips three steps still
reads 1, 2, 3.

### Tokens

`{name}` in `body`, `stitch` or `title` resolves against the package's flat
`geometry` map and is replaced with that figure's **`text`** form — the
fraction a cutting mat is marked in, not a float.

An unrecognised token is a **hard error**, never a passthrough. Same rule as
`svgpath.parse_path` raising on an unknown command: a token that silently
survives into the output reads as literal text in a build instruction, and the
person at the machine has no way to know a number went missing.

Available tokens are every key of `geometry`, plus the handful in `words` whose
value is a **name rather than a figure** — `{divider_face}` is the only one so
far. Those are kept out of `geometry` because every value there is a dimension
the package renders twice, as a float for the drawing and a fraction for the
human, and a face name is neither. They exist because a step that says "the
panel's interior" on a bag with two doubled panels is not an instruction. Run
`py tools/bag_pattern.py <spec> --tokens` to list both for a given bag.

### Conditions

`when` requires **all** listed flags true; `unless` requires all listed flags
false. Both may appear. Flags are a closed set, derived by `BoxBag`:

| Flag | True when |
|---|---|
| `has_chassis` | the spec declares a chassis (absent means yes; only explicit `null` turns it off) |
| `shell_frays` | the shell material's `MATERIALS` row says so |
| `double_fold` | the *binding* frays, so its outer edge must be turned under |
| `has_windows` | `"windows": true` |
| `has_handle` | `features.handle_in` is set |
| `has_drings` | `features.d_rings` > 0 |
| `has_belt_loop` | `features.belt_loops` is declared |
| `has_belt_anchor` | ...and it declares `"anchor": true` |
| `has_ring_anchor` | `features.d_ring_anchor` is true |
| `has_sling` | there are rings **and** a declared `wearer.crossbody_in` |
| `has_back_pocket` / `has_front_pocket` | that face appears in `panel_pockets` |
| `has_panel_pocket` | any face does |
| `has_divider` | `divider` is declared |
| `shell_melts` | the shell material's `MATERIALS` row says `melt_seal` — **independent of `frays`**, and conflating the two is how a step came to say "Cordura seals, so no edge needs a hem". Fraying decides whether an edge is turned under and whether the binding is double-fold; melt-sealing decides only how a piece is *cut*. A coated cotton neither ravels nor melts. |
| `self_bound` | the binding material is the shell — so the bag buys no tape, and the bias square comes out of the same cloth |
| `has_webbing` | anything on the bag is webbing: a chassis, D-ring tabs, a handle, or a belt this pattern cuts |
| `supplies_carry` | a `wearer` is declared and it supplies **both** belt and strap — see below |
| `has_bound_divider` | ...and its `attach` is `"binding"` rather than `"topstitch"`. They are different operations with different figures, and one step cannot describe both — it used to try, and described only the second while the schema still offered the first |
| `has_stiffener` | `"stiffener": true` |
| `has_pockets` | `pieces[]` holds something of `"kind": "pocket"` |

`has_panel_pocket` is separate from `has_pockets` on purpose. A panel pocket is
built *out of* the panel — cut in two and lapped onto a zipper tape — while
`has_pockets` means pocket pieces applied *to* something. A step written for
one does not describe the other, and a rename that collapsed the two steps into
one is exactly the mistake `test_patterns.py` now guards against.

There is no expression language and there should not be one. If a step needs a
condition these flags cannot express, the flag set is what is missing.

---

## Layer 2 — spec

`patterns/specs/<Name>.json`. `name` must equal the filename stem.

### Required — the geometry inputs

These already existed and are unchanged; `bag_pattern.py` derives every cut size
from them.

| Key | Example | Note |
|---|---|---|
| `name` | `"HipPack_10x7x4"` | must match the filename |
| `construction` | `"box-bound"` | names the construction file |
| `finished_in` | `{"w":10,"h":6,"d":3}` | the finished envelope |
| `shell` | `"canvas-600d-pu"` | a key of `MATERIALS` in `bag_pattern.py` |
| `binding` | `{"material":"nylon-binding-tape"}` | optional; defaults to the shell |
| `windows` | `false` | clear panels |
| `chassis` | `{"webbing_in":0.75,"overlap_in":3.0}` | **explicit `null`** means carried by a belt |
| `closure` | `{"coil_in":0.25,"lap_in":0.5}` | optional, but declare it — see below |
| `features` | `{"d_rings":2,"handle_in":8}` | counts and lengths |
| `panel_pockets` | `{"back":{"zip_from_top_in":2.125}}` | optional, per face; see below |
| `divider` | `{"face":"front","height_in":3.5}` | optional; see below |
| `wearer.supplies` | `["belt","strap"]` | optional; what the wearer brings rather than what this pattern cuts — see below |
| `stiffener` | `true` | optional; a loose base panel. It used to be an unconditional step, so every bag was told to cut one — including bags that have none, and including a rounded-bottom bag, where a rectangle cut to the interior cannot lie flat because the flat floor is `2 × corner_r` shorter than the face. It is now declared, and sized from `floor_w × floor_d`. |
| `fits_within_in` | `{"w":12,"d":6,"h":12}` | optional envelope limit to check against |

### Belt keepers

```json
"features": { "belt_loops": { "for_in": 0.75, "count": 2,
                              "width_in": 1.5, "anchor": true } }
```

`for_in` is the belt's width and sets the cut **length** — `2 × for_in + 1½"`,
enough to wrap the belt and tack down both ends. `width_in` is how much of the
belt's *length* the keeper grips and is a choice, not a consequence; the check
only insists it is at least the belt's width.

`anchor` adds a strip across the panel's full width, on the interior behind the
keepers, **with its ends caught in the side binding**. Without it, a loaded bag
hangs off two box-X tacks in one layer of shell. With it, the load spreads into
a seam that was carrying the bag anyway — the StadiumTote's hidden-anchor
argument, applied to a panel instead of a gusset.

### Who wears it

```json
"wearer": { "waist_in": [28, 44], "crossbody_in": 52,
            "handed": "right", "taper_in_per_in": 0.75, "tail_in": 6 }
```

Declaring the fit range is what turns the belt from a hand-typed row in the
takeoff into a derived one. With D-rings **and** a `crossbody_in`, a separate
sling strap is derived and the belt only has to reach a waist; without rings,
the belt has to do both jobs and the longer figure sizes it.

`supplies` names what the wearer **brings**, not what the pattern makes:
`"supplies": ["belt", "strap"]` stops both being derived and cut, drops them
from the takeoff as webbing, and lists them instead as *yours* with the width
and length they have to be. The BeltPouch says the same thing by having no
`wearer` block at all — but that also throws away the fit range, the
contact-pressure figures and the handedness, every one of which still describes
a belt somebody else made. Declaring what is supplied keeps the reasoning and
drops only the cutting. With both supplied, `supplies_carry` fires and the
strap-making step is replaced by one that just threads the belt and clips the
strap on.

`belt_takeup_in` (default 4″) is what the buckle's folded fixed half and the
tri-glide eat before the wearer sees any of it, exactly as `sling_takeup_in` is
for two hook folds and a slider. The sling had always carried that term and the
belt had not, so a belt derived as `waist + tail` advertised six inches of tail
and delivered about two at the largest declared fit. Both now pay it.

`taper_in_per_in` is how much girth the body gains per inch of drop from waist
to hip — it is what makes a **flat strap the wrong shape**, and it bounds belt
width from above. `handed` decides which end a single slider parks at.

**Note what is deliberately not checked.** The belt is derived from the fit
range, so "does the belt reach the largest fit" could only ever pass. The
declared parts are the *tail* and the *take-up*, and the tail is what gets a
check.

### A divider lying flat against a panel

```json
"divider": { "face": "front", "height_in": 3.5, "channels_in": [2.5, 7.5] }
```

A slip pocket for small items, flat against the inside of a panel. Its sides
and bottom are caught in **that panel's own binding** — already structural,
already there — so the only new seam is its own bound top edge, which is added
to the binding run. A pocket's contents sit on its bottom seam, and putting
that seam in the middle of a panel makes a loaded stitch line where there was
none.

`attach` is `"binding"` (sides and bottom caught in the panel's binding, top
edge bound) or `"topstitch"` (inset `inset_in` and topstitched down three
sides, top edge left raw — a shell that does not fray needs no hem there, and
if it frays, that top edge is what the fold-under step means). Out of the
binding it costs three straight runs and gives back a bound edge, a layer in
the worst seam on the bag, and any argument with a rounded corner.

`channels_in` are topstitch positions in face coordinates; *n* lines make
*n + 1* channels, and they are measured **across the divider**, not across the
panel. A topstitched divider stops `inset_in` short of the binding on each
side, so reading its outer channels off the panel's visible face — which the
check and the report each did separately — overstated both of them by the
inset. Checked: the divider leaves room to reach past it, every
channel is at least 1″ wide, every line sits inside the binding — **and no line
crosses an embroidery field declared on the same face**, because a channel line
goes through the panel and shows on the outside, where the logo is. That one
cannot be fixed after it is sewn.

A divider also doubles that panel's bound seam, and the binding is sized from
the worst seam on the bag.

### D-rings, and what goes behind them

```json
"features": { "d_rings": 2, "d_ring_anchor": true }
```

A D-ring tab is box-X'd through **tab + gusset + whatever backs it**, and the
tack is the connection rather than the tab. Something has to be back there: a
tab sewn to one layer of shell puts the whole bag into two stitch fields.

Two things qualify, and `validate` refuses a bag with rings and neither:

- **the chassis**, if it has one — the webbing loop is already behind the whole
  gusset;
- **`d_ring_anchor`**, which derives one strip per ring, cut to the gusset's
  full width so both ends finish flush with the panel edges and the bindings
  catch them. Same argument as the chassis over a shorter span.

Declaring rings *and* `wearer.crossbody_in` sets `has_sling`, and then the belt
stops having to reach a crossbody: it is sized from the waist range alone and a
separate sling strap is derived. Both stay rigged at once.

### Rounded corners

```json
"corners": { "bottom_in": 1.5 }
```

A square corner costs a **mitre** in the binding and a **clip** in the gusset's
seam allowance, and the mitre is the thickest point on the bag. A curve costs
neither. The gusset does not notice either way: a band standing on a curved
edge is a *developable* surface, so a flat straight strip follows it with no
easing, no clipping and no seam.

What it changes, all derived:

```
ring     shortens by R × (2 − π/2) per corner — a quarter turn replaces
         2R of path with πR/2
binding  shortens the same way, at the cut radius R + SA
mitres   4 per panel → 2
bias     any curve forces bias binding, and buys 30% more of it
```

**Bias is not optional and it is the price.** Round a quarter turn the
binding's outer fold travels a third further than its own stitch line, and
nothing but bias eases that. Checked: the radius must be at least the binding
show (or the binding cannot lie round it), at most half the shorter face (or
the curves meet and no flat edge is left), and a divider caught in the binding
is refused on a rounded panel because its own corners would have to be cut to
the radius.

### Zipped pockets built into panels

```json
"panel_pockets": {
  "back":  { "zip_from_top_in": 2.125, "must_hold_in": [6.42, 3.06] },
  "front": { "zip_from_top_in": 2.125 }
}
```

A panel that carries a pocket becomes **two layers**: an inner one, full size
and bound on all four edges, which is the compartment's wall; and an outer one
cut in two and lapped onto a zipper tape. The pocket is the cavity between
them, the zip is its only mouth, and **no slit is cut anywhere** — a welt
opening in a loaded panel is the hardest step in bag making and the only one
that cannot be practised on scrap, because the practice piece is the panel.

Two properties fall out, and both are checked:

- **the compartment stays sealed** — the zip opens into the cavity, never into
  the bag, so nothing migrates between them;
- **no load crosses the zip** — anything tacked to the panel goes through to
  the inner layer, which the gusset ring holds on every side. A keeper placed
  *below* the zip line would not, and `belt load bypasses the pocket zip` says so.

Everything else derives from the one number per face:

```
upper  = zip_from_top − coil/2 + lap
lower  = panel_h − (zip_from_top + coil/2) + lap
reach  = panel_h − zip_from_top − coil/2      depth below the opening; the
                                              usable inside is reach − SA,
                                              because the bottom is bound
band   = upper − lap − SA                     what is left to tack into above
```

**Every pocket on a bag shares its zip height, coil and lap**, and `panel
pockets agree` reports it if they diverge. That is a deliberate constraint, not
an oversight: it makes the outer pieces identical front and back — two pairs
instead of four singletons — and it lets one assembly step state the figures
for all of them. There are always exactly **two full-size panels** whatever the
pockets do, because a pocketed panel spends its on the inner layer and a plain
one is just itself.

## Layer 3 — package

`build/patterns/<Name>.json`, `schema_version` `"1.0"`. Generated by
`py tools/bag_pattern.py --all --package`. Regenerate rather than editing;
`build/` is disposable in this repo and this directory is no exception.

```
schema_version name title construction construction_title description summary
finished    { w{} d{} h{} w_mm d_mm h_mm }
interior    { w{} h{} d{} in3 litres }
flags       { has_chassis shell_frays double_fold has_windows has_handle
              has_drings has_belt_loop has_pockets }
geometry    { <key>: { "in": 9.125, "text": "9⅛\"" }, ... }
materials[] { role material thickness_mm frays note }
cut_list[]  { piece qty w{} l{} material note }
layouts[]   { material roll_width_in used{} buy{} pieces[ {piece x y w h} ] }
takeoff[]   { item qty note }
hardware[]  { item qty note }
assembly[]  { n title body stitch }        conditions applied, tokens resolved, renumbered
stitch_schedule[] { operation stitch length_mm foot needle }
tools[]     { tool why }
checklist[] { item why }
thickness[] { location stack mm }     peak_mm carries the worst of them
comfort[]   { measure value basis }   REPORTED, never gated -- see below
sources[]   { title url gives }       where the comfort figures come from
model3d     { faces{ <face>: {w{} h{}} } binding_show{} flange{} features[] }
checks[]    { ok name detail }
notes[]     { kind title body }
open_questions[] { title body }
docs[]      { title path kind body }       body is the Markdown, inlined
embroidery  { panel design field_mm }
provenance  { generated_at schema_version spec{path sha256}
              construction{path sha256} tools{ <path>: sha256 } }
```

`{}` marks a dimension object — `{"in": 9.125, "text": "9⅛\""}`.

**`layouts` is plural, one per material sold on a roll.** The StadiumTote nests
vinyl, denim and Cordura on three different roll widths; anything the material
table marks `by_length` — webbing, binding tape — is bought by the yard and
never nested.

**Every dimension appears twice** — a float in inches for the renderer and a
`text` fraction for the human. The player does no arithmetic on dimensions at
all; if it needs a number in a new form, the generator grows a key. That keeps
rounding in one place, and `frac()` is already the only thing in this repo that
knows how a cutting mat is marked.

`docs[].body` carries the Markdown text itself, not just a path, so the package
is self-contained and the player has nothing to fetch.

---

## Checks

`py tools/bag_pattern.py --all --check` exits non-zero on any failure. The nine
geometry checks are unchanged. Packaging adds:

| Check | Fails when |
|---|---|
| the cut pieces close the ring | `gusset_cut + zip_cut − 2 × lap ≠ ring`. **This replaced a check that could not fail.** The old one asserted `gusset_face + zip_face == ring`, which is a restatement of the line that *defines* `gusset_face` — so it passed happily while both pieces were cut long and every bag in the family assembled a ring `2 × lap` over. Exactly the shape the *comfort is reported, not enforced* section warns about, one layer down. |
| construction resolves | the named construction file is missing |
| tokens resolve | any step, title or stitch note contains a token `geometry` has no key for |
| placements are on their face | a feature's rectangle leaves the face it names |
| feature kinds are known | a `kind` outside the table above |
| docs exist | a `docs[].path` points at a missing file |
| layout nests | two pieces overlap, or a piece exceeds the roll width |
| hardware declared | a bag with a zipper closure declares no zipper in `hardware[]` |

The last one exists because the cut list sizes fabric and webbing and stops
there. Both `HipPack` and `SlingPack` shipped a complete-looking cut list with
no zipper in it.

## Comfort is reported, not enforced

`comfort[]` carries figures from the load-carriage literature and from
published testing — belt contact pressure against the 16 kPa blood-occlusion
threshold, the girth a flat strap gets wrong on a conical waist, capacity
against the band real packs occupy. **None of them is a gate**, and that is
deliberate: the threshold that matters depends on how hard a wearer cinches a
belt, and nothing here has been worn by anybody. What *can* be stated without
inventing a number is the tension at which a belt of a given width reaches
16 kPa, which is a property of the belt and the body alone.

Two rules follow, and they are the same rule twice:

- **A figure with a literature threshold gets reported with its basis.** Every
  row carries where it came from, and `sources[]` carries the link.
- **A check has to be able to fail.** "Does the belt reach the largest declared
  fit" reads like a safety check and is worthless, because the belt is derived
  from that fit — it can only ever pass. Prefer a check on something *declared*.

The gates that did come out of the research are pure geometry: `back pocket
holds what it must`, `keepers fit clear of the pocket zip`, `the bag fits the
smallest declared wearer`. Those can fail, and on this family they do.

---

## Adding a bag

1. Write `patterns/specs/<Name>.json` — geometry inputs first.
2. `py tools/bag_pattern.py patterns/specs/<Name>.json` and read the checks.
   **A failed check is the design telling you something.** Both failures so far
   were real: a hip pack whose zipper had no room beside 1&Prime; webbing, and a
   belt pouch too shallow for a chassis at all. Neither wanted a fudge.
3. Add the narrative and the `features[]` placements.
4. `py tools/bag_pattern.py --all --package && py tools/pattern_player.py`
5. `py tools/tests/test_patterns.py`

---

*Generator:* `tools/bag_pattern.py` · *Player:* `tools/pattern_player.py` ·
*Tests:* `tools/tests/test_patterns.py`
