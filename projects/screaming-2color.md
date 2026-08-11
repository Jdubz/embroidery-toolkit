# I ♥ Screaming — 2 colour

> **SUPERSEDED by `i-heart-screaming.md`.** This build was traced from a raster
> derived from an AI render; the current one starts from clean vector, is
> 3 colours, and lives at `designs/out/Scream.pes`. **`scream2.pes` has been
> deleted** — `designs/out` now holds one file per design. Everything below is
> kept for the measurements and the two PES container bugs it uncovered; the
> commands will rebuild it if you ever want it back.

**Date:** 2026-08-07
**Design:** `designs/out/scream2.pes` *(deleted — see above)*
**Source art:** `images/scream_2col.png` (derived from `images/screaming simple.png`)

## Target

| | |
|---|---|
| Item | white cloth, test piece |
| Design size | 82.2 × 80.6 mm |
| Stitch count | 9,863 (152 jumps) |
| Colours | 2 — black, green |
| Run time | ~36 min (25 sewing + 10 snipping + 2 rethreading) |

Rebuilt through Ink/Stitch (see `docs/11-inkstitch-pipeline.md`). Against the
built-in tracer's version of the same art:

| | stitches | jumps | machine | hand-snipping |
|---|---|---|---|---|
| `stitch trace` | 12,742 | 400 | 33 min | 27 min |
| Ink/Stitch | **9,863** | **152** | **26 min** | **10 min** |

Peak density 18 penetrations/mm², nothing at or above 30. Mid-run stitches under
0.5 mm: 1%, the rest being tie-ins and tie-offs, which are meant to be short.

The stitch count dropped from 11,487 once the document declared
`inkstitch:min_stitch_len_mm` — 18% of the stitches had been sub-0.5 mm, doing
no work and pulling bobbin thread to the surface.

Earlier iterations of the tracer version ran 73 min, then 54 once
travel-under-fill routing replaced trims with walked connections.

## Setup

| | |
|---|---|
| Hoop | SA432 4×4 |
| Stabilizer | medium cut-away if knit; tear-away if stable woven |
| Needle | 75/11 |
| Top thread | 40 wt — black, then green |
| Bobbin | 60 wt white |

Stitch order is **black first (7,026 st), then green (2,837 st)**. All white areas
are left unstitched — the cloth is the third colour.

## How it was built

Reproducible from the original art:

```powershell
# 1. Strip the AI-render's simulated stitch texture back to flat colour.
#    --colors INCLUDES the background, so 5 = 4 design colours + bg.
.\stitch.ps1 flatten ".\images\screaming simple.png" -o ".\images\scream_flat.png" --colors 5

# 2. Merge red into green; leave whites unstitched so the fabric shows.
.\stitch.ps1 recolor ".\images\scream_flat.png" -o ".\images\scream_2col.png" `
    --map "#D11316=#7DA41C" --drop "#FBFBFA" --drop "#D2CDC7"

# 3. Digitize. Black first, then green -- -Layer order IS stitch order.
#    'auto' splits each colour by stroke width: solid masses filled, thin
#    linework centrelined. 85% of the black and 93% of the green fill.
.\tools\inkstitch_pipeline.ps1 -Image "images\scream_2col.png" `
    -Out designs\out\scream2.pes -Mode layered -WidthMm 89 `
    -Layer '0E0E0C:auto','7DA41C:auto'

# 4. Check and send.
.\stitch.ps1 validate designs\out\scream2.pes
.\stitch.ps1 stage    designs\out\scream2.pes --to E:\
```

`flatten` is deterministic (fixed k-means seed), so step 1 reproduces exactly.

## Two PES bugs found and fixed while building this

Both produced a file whose stitches were perfect but which previewed in Design
Database Transfer as only the bottom corner of the artwork.

1. **Origin convention.** pyembroidery centres designs on the origin
   (`-443..+443`); DDT expects `0..886`. Confirmed by A/B: the shifted file
   renders correctly, the centred one does not. DST was always fine because it
   has no such convention — that mismatch is the fastest way to spot it.
2. **PES section placement.** pyembroidery builds the PES section transform from
   hard-coded `hoop_width = 1300, hoop_height = 1800`, putting a 4x4 design
   outside the field. Stripping the section (keeping header + PEC block) fixes
   the preview and cuts file size ~75%.

Both are now automatic on every PES write, flagged by `validate`, and repairable
with `stitch fix-pes`.

## Notes carried forward

- **Green matches poorly** (ΔE 17.9 vs Brother Leaf Green). Irrelevant to
  stitching — colour in a PES is a label, and you load whatever spool you like.
  Only the on-screen name will differ.
- **23% jump ratio** is inherent: the fill legitimately breaks at every letter
  counter rather than sewing across it. Trims cost more time than sewing here.
- Measured text at this size: letter bodies 3.49 mm, keyline 1.23 mm, cap height
  ~15 mm — all clear of the SE700 minimums. Flattening is what got the keyline
  above 1.2 mm; the un-flattened original measured 0.77 mm.

## Result

- [ ] Test stitch-out on matching scrap first
- [ ] Traced boundary before stitching

**What worked:**

**What didn't:**

**Change next time:**
