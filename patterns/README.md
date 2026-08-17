# Patterns

Sewing patterns for bags and accessories. Separate from `designs/`, which is
embroidery — though the two meet whenever a panel gets a logo.

```
patterns/
  SCHEMA.md                 how a pattern is declared and what gets derived
  BoxBound_family.md        the four box-bound bags, and the geometry they share
  StadiumTote_12x12x4.md    the reference build, long-form
  specs/                    one JSON per bag — the object
  constructions/            one JSON per construction — the procedure
  techniques/               reusable how-to notes, referenced not repeated
```

## A pattern is declared, not remembered

Nothing about a bag is written down twice. Three files, two authored by hand
and one generated:

| | | |
|---|---|---|
| **Construction** | `constructions/box-bound.json` | assembly order, stitch schedule, tools, gates — shared by every bag of that kind |
| **Spec** | `specs/<Name>.json` | finished envelope, materials, hardware, notes, 3D placements |
| **Package** | `build/patterns/<Name>.json` | **generated** — the two above flattened, plus every derived figure |

```powershell
py tools\bag_pattern.py --all --check       # geometry, and the checks
py tools\bag_pattern.py --all --package     # write the packages
py tools\pattern_player.py --open           # build and open the player
py tools\tests\test_patterns.py             # the pattern invariants
```

**Never hand-edit a cut list or a package.** Edit the spec and regenerate, or
the pattern and its record diverge — which is the whole reason the generator
exists. Five revisions of the StadiumTote each moved a number that only
re-deriving the geometry caught, and a bad cut costs material rather than a
rebuild.

The construction is its own layer because `BoxBound_family.md` already said so:
the **stitch schedule, lock-off policy, tool list and machine setup are
properties of the materials and the machine, not of the size**, and apply
unchanged to all four bags. Steps carry `{token}` figures resolved from the
bag's own geometry, and `when`/`unless` conditions from a closed flag set — so
the BeltPouch is never told to close a chassis it does not have. Full
vocabulary in [`SCHEMA.md`](SCHEMA.md).

## The player

`py tools\pattern_player.py` builds **`build/patterns/player.html`**: one
self-contained file with a dropdown over every pattern, a 3D preview, the
materials and cut list, a nesting layout, the assembly order, the checks, and
every technique note one click away.

It reads packages and nothing else — no Markdown is parsed and no geometry is
computed in the page. The 3D preview is driven entirely by each package's
`model3d`, so **a new bag previews the moment it is packaged**; no pattern has
rendering code of its own.

## Two rules that have both already been paid for

**Run a new check against a known-good file first.** The generator was
validated by reproducing all of the StadiumTote's hand-computed figures before
it was trusted with anything new. Then it immediately failed two of the three
other sizes, which is the point.

**But assert on values, not on printed output.** A regression run against a
known-good *file* validates the geometry and not the presentation, because the
file was printed by the same code being tested. `frac()` rendered 1 5/16" as
`15/16"` for as long as this repo has existed, understating the BeltPouch's
zipper strips by ⅜" in every published cut list, and the file-level regression
passed the whole time. `test_patterns.py` asserts on `Fraction` values.

## The two kinds of prose file

| | |
|---|---|
| **Pattern** | One bag, or one family. The reasoning: why it is shaped this way, what went wrong, what was tried. Everything a *build* needs lives in the spec instead, and the player links here for the rest. |
| **Technique** | One skill, no dimensions, reused across patterns. `techniques/README.md` sets the conventions. |

When a pattern starts explaining something a second time, it wants to be a
technique note. When it states a *figure*, it wants to be in the spec.

## Adding a bag

1. Write `specs/<Name>.json` — the geometry inputs first.
2. `py tools\bag_pattern.py specs\<Name>.json` and read the checks.
   **A failed check is the design telling you something.** Both failures so far
   were real: a hip pack whose zipper had no room beside 1" webbing, and a belt
   pouch too shallow for a chassis at all. Neither wanted a fudge; both wanted
   a decision.
3. Add the narrative — description, notes, hardware, `open_questions` — and the
   `features.placements` that draw it in 3D.
4. `py tools\bag_pattern.py --all --package && py tools\pattern_player.py`
5. `py tools\tests\test_patterns.py`
