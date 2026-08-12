# A composable architecture for AI-driven SVG design

Written after four bespoke tools in one session — `svg_offset`, `svg_stroke`,
`svg_ground_invert`, `svggeom` — and the observation that prompted it: *the code
that works for one asset is probably wrong for the next one*. That was true.
`svg_ground_invert` needed extending twice, once for strokes and once for
subtracting dropped ink, each time discovered by hitting a new asset.

The fix is not more tools. It is to stop writing task-specific code and start
composing a fixed vocabulary, with the per-asset part declared in the spec where
`stitch audit` can already see it.

## Does this platform already exist?

Researched properly rather than assumed. Nothing covers it, but four systems each
own a quarter, and every one of them contributes a design lesson.

| System | What it genuinely has | Why it is not the answer here |
|---|---|---|
| **[Graphite](https://github.com/GraphiteEditor/Graphite)** | The closest by far. Node graph **is** the document format — typed composable nodes, "inspectable, diffable, and scriptable". Non-destructive boolean ops. Rust + WASM, `graph-craft` and `interpreted-executor` as separate crates. | Alpha. No documented headless or CLI path, so a build script cannot drive it. Native `.graphite` format; SVG import does not preserve gradients and filters consistently. The Tauri desktop build was abandoned outright. |
| **[vpype](https://github.com/abey79/vpype)** | Exactly the pipeline shape wanted: `read … scale … linesort … write`, with a Click-based plug-in API and a shared document model between commands. | Plotter-oriented, so the data model is **lines**. It "does not aim to maintain full consistency with the SVG specification", and fills exist only as a speculative future hatching plug-in. Embroidery is fills and booleans first. |
| **[Penrose](https://penrose.cs.cmu.edu/blog/bloom)** | Declarative constraint specs compiled to diagrams by numerical optimisation, with domain / substance / style separated. `Bloom` extends it to interactive work. | Points the wrong way — it *synthesises* diagrams from abstract notation. We are *transforming* existing artwork whose geometry must survive intact. |
| **[build123d](https://github.com/gumyr/build123d)** | The architecture, proven: selectors as first-class values, algebraic composition, and a deliberate rejection of restrictive fluent chaining in favour of plain Python data so loops, filtering and sorting all work. | 3D BREP on OpenCascade. Wrong dimension — but the *pattern* transfers directly, and it is the single best precedent for the selector layer below. |
| **[Penpot MCP](https://github.com/penpot/penpot-mcp)** | Official, open source, merged into the main repo. AI clients read **and modify** real design files through the Plugin API. Agentic design editing that actually ships. | A UI/UX tool — components, styles, tokens. Not geometry-grade boolean and offset work, and it needs a server, a plugin and a WebSocket to reach the document. |

So: build it. But borrow rather than invent.

## The one result that settles the design

[MoVer](https://arxiv.org/html/2502.13372v2) pairs an LLM that generates SVG
motion graphics with a **verification DSL** that checks the result, and feeds
predicate-level failures back for another round. The numbers:

| | correct |
|---|---|
| generation alone, first pass | **58.8%** |
| with the verification feedback loop | **93.6%** |

Two details matter more than the headline. **Full predicate-level reports beat
minimal or absent feedback substantially** — the loop only works if the failure
says precisely which property broke. And the LLM writing the *verifier* scored
95.1%, against 84.7% for rule-based parsing: an LLM is markedly better at stating
what should be true than at producing the artefact that makes it true.

That lines up exactly with [SVGenius](https://arxiv.org/html/2506.03139v1), where
frontier models manage ~76% on *easy* SVG edits, and style and attribute edits
(79–91%) far outrun geometry edits. Both point one way:

> **Keep the model out of coordinate space.** It should choose operations and
> state assertions. Deterministic code should touch the numbers.

Every failure in this session obeys that rule. The welded letter counters, the
missing question mark, the yellow eyes, the phantom hairline strokes — all
coordinate-space consequences of a selection rule, none of them errors of intent.

## What was actually built

The seven-layer design below was **cut down before implementation**, and the cut
was right. Two layers were dropped:

* **the op DSL** — an ordered op list interpreted from the spec. Unnecessary:
  the driver takes `--op` strings directly and *records* what it ran, so an
  interactively-found sequence becomes reproducible without anyone designing a
  file format. Recording beats authoring.
* **the assertion language** — dropped because previewing after every op catches
  more, sooner, for far less work. Every failure this repo has had was caught by
  looking at a render, not by a predicate.

What exists:

| | |
|---|---|
| `embroidery_tools/svgdoc.py` | the document model — an SVG as a flat list of paint regions, strokes buffered to regions, writable back out |
| `embroidery_tools/svgops.py` | the operations: `subtract · drop · recolour · offset · pockets · set-stroke · report` |
| `tools/svg_edit.py` | applies a sequence, previews each step, logs the ops, `--replay` reproduces byte-for-byte |

The acceptance test held. All three black-cloth designs express as op sequences
and reproduce the bespoke tools they replaced **to the millimetre**:

| design | ops | result |
|---|---|---|
| `LemonCat_solid_on_black` | 4 | white 287, yellow 2,256 mm² |
| `MuffyHat_on_black` | 2 | 9 of 36 pockets, white 781 mm² |
| `PissMuffy_on_black` | 4 | 25 components kept / 875 mm², 6 pockets / 38 mm² |

`svg_ground_invert.py` — 400 lines — was deleted. LemonCat's entire treatment is
now four lines of declaration.

### Three bugs the shared model exposed immediately

All three were live in the per-asset tools, which hid them by parsing once and
never re-reading. Making the state explicit between operations surfaced them on
the first run:

1. **`d` is shared by an element's fill and its stroke.** Reshaping the fill
   drags the outline with it — cutting LemonCat's linework out of its body made
   the body's own keyline re-trace every whisker, tripling the black region, and
   the next operation then cut 333 mm² out of the eyes instead of 163. Nothing
   errored. The stroke is now split onto a clone at its original path.
2. **Stroke must resolve through ancestors.** LemonCat declares `stroke` once on
   a wrapping `<g>`, so `el.get("stroke")` is `None` and the split above
   silently never fired.
3. **Selectors must address components, not elements.** PissMuffy's 29 letters,
   eyes, brows and mouth are a *single* `<path>`, so a centroid band matched the
   middle of the whole design and selected nothing. A partial match now splits
   the element.

The recurring shape of all three, and of the phantom-hairline bug before them:
**`fill` and `stroke` have opposite initial values.** Absent `fill` means black;
absent `stroke` means none. Reading them the same way is worth its own check
every time either is touched.

## The architecture as originally proposed

Kept for the record. Layers 4 and 5 were not built — see above.

Seven layers. Layers 0–3 are domain-independent vector composition; only the
embroidery-specific assertions in layer 5 tie it to this repo, which is what
would let the core be extracted later.

### Layer 0 — geometry kernel  *(exists: `embroidery_tools/svggeom.py`)*

Shapely-backed regions. Even-odd folding, booleans, offset, path emission,
degenerate-geometry handling. Knows nothing about SVG semantics or embroidery.

### Layer 1 — document model  *(was buried inside the tool this replaced)*

Parse an SVG into a flat list of **paint regions**: `(element, kind, colour,
geometry)`, where `kind` is fill or stroke and a stroke is buffered by half its
declared width. One element contributes several regions — which is exactly how
LemonCat's yellow body carries a black outline. Round-trips back to SVG.

Promoting this out of one tool is the single highest-value refactor available.

### Layer 2 — selectors

Predicates over paint regions, composable with and / or / not, returning sets.
This is the build123d lesson and the part that makes the system general:

    colour, kind, area, local width, enclosure, adjacency, containment,
    centroid band, nearest-to-point, count/rank

Every ad-hoc rule written this session is one of these. `--keep-band 0:30` is a
centroid-band selector. `--drop-thin` is a width selector. The hand-placed
circles that clipped the question mark were a *bad* selector, and having a
vocabulary is what stops that being reinvented.

### Layer 3 — operations

Pure functions `(doc, selection, params) -> doc`. Registered by name, schema'd,
individually testable:

    subtract · union · intersect · offset · buffer_strokes · pockets
    emit · drop · recolour · knockout · close_gap

Each already exists somewhere in `tools/`; none is currently addressable by name.

### Layer 4 — pipeline

An ordered op list living in `designs/specs/<name>.json`, executed
deterministically, hashed into `build/manifest.json` like any other input. This
is the Graphite lesson — the graph *is* the document — expressed in the
declaration format this repo already has.

```json
"ops": [
  {"select": {"fill": "000000", "include_strokes": true}, "as": "ink"},
  {"select": {"fill": "F6BE00"}, "as": "body"},
  {"subtract": {"from": "body", "what": "ink"}},
  {"pockets": {"enclosed": true, "adjacent_to": "ink"}, "as": "negative"},
  {"emit": {"geom": "negative", "fill": "FFFFFF"}},
  {"drop": "ink"}
]
```

A new asset is new **ops**, not new Python. That is the whole point.

### Layer 5 — assertions

Checked after execution, failing the build the way `validate` does. Structured
per-predicate output, because MoVer shows that is what makes the loop converge:

```json
"assert": {
  "colours": ["FFD400", "FFFFFF"],
  "max_colours": 2,
  "min_feature_mm": 1.2,
  "probe": [{"at": [28, 39], "is": "FFFFFF"}]
}
```

Each entry maps to a real failure from this session. `colours` catches black
thread on black cloth. `min_feature_mm` catches the 1.25 mm whiskers. `probe` is
the check CLAUDE.md says would have caught the yellow LemonCat eyes and was never
built — it compares **colour** at a point, not merely coverage, which is the
distinction that made `coverage` report a clean 100% on a broken design.

### Layer 6 — the agent loop

Execute → render → assert. On failure the structured report says which predicate
broke and by how much, and that drives the next edit. Aesthetic judgement stays
with rendering and looking, which is how the welded counters and the missing `?`
were caught. No human hand-off; a human *review* remains worth having.

## Risks, honestly

**Over-abstraction before the vocabulary is proven.** The mitigation is a hard
acceptance test: port `MuffyHat_on_black`, `PissMuffy_on_black` and
`LemonCat_solid_on_black` onto the pipeline and delete the bespoke paths. If all
three express in ops with no special cases, the vocabulary is real. If any needs
an escape hatch, the design is wrong and should change before more is built.

**Selector instability.** Positional selectors break when artwork moves — a
circle centred on the lower lettering arc already dropped a question mark
silently. Prefer measured and structural predicates; make positional ones report
what they matched so a silent miss becomes a loud one.

**No GUI.** Deliberately. The op list in JSON is inspectable, diffable and
reviewable; a node editor is a presentation layer that can come later or never.

## What this is not

It does not remove taste, and it does not make the model good at coordinates. It
removes *bespoke code per asset* and it removes *silent wrongness*. Those were
the two actual problems.
