# Embroidery — Brother SE700

Design generation, machine reference, and file management for a Brother SE700
sewing/embroidery machine.

> **Model note.** Brother has never made an "SE7000". The 4"×4" wireless combo
> machine is the **SE700**. This repo is built for that. Machine specs are
> isolated in [`reference/machine-profile.json`](reference/machine-profile.json) —
> if your unit is an SE600, SE625, SE630, SE1900 or SE2100i, edit that one file
> and all tooling re-targets itself.

## The five numbers that matter

| | |
|---|---|
| Embroidery field | **100 × 100 mm** (4" × 4") — hard limit |
| Max stitches per design | **100,000** |
| Formats read | **`.pes`** `.phc` `.dst` `.pen` |
| Machine memory | 20 designs / 1024 KB |
| Wireless | 2.4 GHz only, **no WPA-Enterprise** |

A design that exceeds the field does not produce an error — it simply never
appears in the machine's list. That silent failure is what most of the tooling
here exists to prevent.

## Quick start

```powershell
.\stitch.ps1 machine                              # show the active machine profile
.venv\Scripts\python.exe tools\examples\generate_monogram_frame.py
.\stitch.ps1 validate designs\out\frame.pes       # check it against the machine
.\stitch.ps1 preview  designs\out\frame.pes       # SVG drawn inside the real hoop
.\stitch.ps1 drives                               # find your USB stick
.\stitch.ps1 stage    designs\out\frame.pes --to E:\
```

`stitch.ps1` bootstraps its own virtualenv on first run. Requires Python 3.10+
(`py --version`).

## What this repository does not contain

The toolkit and the documentation are here. Three things deliberately are not,
and the tooling works without all of them:

- **Brother's manuals.** `docs/` cites them by page throughout and the tooling
  greps text extractions of them, but they are Brother Industries' copyrighted
  material and not ours to republish. [`reference/manuals/README.md`](reference/manuals/README.md)
  lists which four to download and how to make the extractions.
- **Artwork** (`art/`) and **built designs** (`designs/out/`). Artwork carries
  its own rights and stitch files are build artifacts. `designs/specs/*.json`
  is gitignored with them, since a spec points at artwork — so a fresh clone
  reports zero designs, which is correct rather than broken. See
  [`designs/specs/README.md`](designs/specs/README.md) to start your own.
- **Stitch-out photographs** (`photos/`).

Everything needed to build, validate and transfer *your* designs is present.
`docs/13-repository-layout.md` describes the full directory scheme, including
the parts you populate locally.

## Commands

| Command | Does |
|---|---|
| `machine` | Print the active machine profile |
| `info <files>` | Size, stitch counts, colours, run time, PES version |
| `validate <files>` | Check against field size, stitch limit, format, filename |
| `convert <in> <out>` | Between ~19 formats; PES version aware |
| `preview <files>` | Render SVG (and PNG) with the hoop boundary drawn to scale |
| `palette [--match HEX]` | Brother's 64-colour palette; find the nearest real thread |
| `drives` | List removable drives and flag non-FAT32 |
| `stage <files> --to E:\` | Validate, then copy to USB. Refuses broken designs. |
| `discover [--deep]` | Find the machine on the LAN by MAC vendor / SNMP |
| `probe <ip>` | Fingerprint one address: ports, SNMP, vendor, hostname |
| `flatten <image>` | Strip simulated stitch texture / posterise before tracing |
| `recolor <image>` | Merge colours, or drop one so the fabric shows through |
| `trace <image>` | Auto-digitize an image → PES (fill, underlay, outlines) |
| `render <files>` | **Realistic PNG of the finished embroidery** |
| `fix-pes <files>` | Repair origin/hoop so Brother software previews correctly |

Globs work: `.\stitch.ps1 validate designs\out\*.pes`

## Tests

```powershell
.venv\Scripts\python.exe tools\tests\test_toolkit.py
```

54 invariant checks, no test framework needed. Every one corresponds to a bug
that actually shipped here at some point — short stitches, missing tie-offs,
zero-length stitches, the PES origin convention. **Run it after touching
`raster.py` or `convert.py`**: the two worst defects so far were invisible in the
rendered preview and only showed up in the stitch-length histogram.

## Layout

```
docs/          Written reference — start at 01
reference/
  machine-profile.json    Single source of truth for all machine limits
  manuals/                Official Brother PDFs (+ extracted, greppable text)
  charts/                 Thread palettes with RGB
tools/
  embroidery_tools/       The Python package behind stitch.ps1
  examples/               Worked design generators
designs/
  source/                 Vector masters (SVG) — the real source of truth
  out/                    Generated, machine-ready files
  library/                Purchased and downloaded designs
projects/      Per-project stitch-out logs
```

## Documentation

1. [Machine Reference](docs/01-machine-reference.md) — specs, hoops, firmware, connectivity
2. [File Formats](docs/02-file-formats.md) — PES versions, why DST loses colour, the 64-colour ceiling
3. [Transferring Designs](docs/03-transferring-designs.md) — USB, Design Database Transfer, Artspira
4. [Software Landscape](docs/04-software-landscape.md) — Ink/Stitch, PE-Design, Embrilliance, and what to skip
5. [Materials & Consumables](docs/05-materials-and-consumables.md) — needles, thread, stabilizer, hooping
6. [Stitch-Out Playbook](docs/06-stitch-out-playbook.md) — the repeatable sequence
7. [Troubleshooting](docs/07-troubleshooting.md) — ordered by actual frequency
8. [Resources](docs/08-resources.md) — links, manuals, design sources, licensing
9. [Image → Embroidery](docs/09-image-to-embroidery.md) — auto-digitizing, AI prompting, limits
10. [Designing for the SE700](docs/10-designing-for-the-se700.md) — **why generic digitizing advice misleads here**: minimum feature sizes, colour budget, run time
11. [The Ink/Stitch Pipeline](docs/11-inkstitch-pipeline.md) — **the preferred digitizer**: line art as continuous running stitch, flat colour as layered fills, and the traps in driving it headless
12. [Design Generation Playbook](docs/12-design-generation-playbook.md) — **start here to make a design**: which mode to use, and the five gates that catch every failure this repo has shipped

## Two things worth knowing up front

**PES stores colour as an index into a fixed 64-colour Brother palette.** Your
hex gets snapped to the nearest entry on write. Sometimes that's invisible
(`#1F3A93` → Ultramarine, ΔE 4.7); sometimes it's not (`#C0392B` → Clay Brown,
ΔE 24). Check before you commit:

```powershell
.\stitch.ps1 palette --match "#C0392B" -n 5
```

**Resizing a stitch file is not the same as resizing a design.** Scaling doesn't
re-space stitches — up thins coverage, down bunches it. Beyond about ±10%,
re-digitize instead.

## What the network tooling can and can't do

```powershell
.\stitch.ps1 discover          # ARP sweep + IEEE vendor lookup across your subnet
.\stitch.ps1 discover --deep   # + port scan, SNMP sysDescr, reverse DNS per host
.\stitch.ps1 probe 192.168.1.42
```

`discover` finds the machine and confirms it's reachable. That's the useful
half, and it turns "why can't Design Database Transfer see my machine" into a
two-minute answer.

**Use `--deep`.** The machine's MAC is *not* registered to Brother — its radio
is an OEM Foxconn module — so vendor lookup alone will not find it. `--deep`
fingerprints services instead, keying on Brother's `debut/1.20` embedded httpd
and a TLS certificate whose CN encodes the machine's software version:

```
1 Brother device(s) identified:
  192.168.86.74  (44-f7-9f-58-04-37)
      - runs Brother's 'Debut' embedded httpd
      - TLS cert identity string, software v1.72
```

**It cannot push designs.** Brother's wireless transfer protocol is closed —
no published API, no SDK, no public reverse-engineering for the SE-series. The
only network paths to the machine are Brother's own **Design Database Transfer**
(free, Windows, GUI) and the **Artspira** phone app. Wireless is a convenience
layer; USB via `stitch stage` is the programmable path.

## Image → embroidery

```powershell
.\stitch.ps1 trace designs\source\logo.png -o designs\out\logo.pes --colors 4 --preview
.\stitch.ps1 stage designs\out\logo.pes --to E:\
```

`trace` fits the image to the hoop, strips the background, reduces to real
Brother threads, then generates underlay, an angled serpentine fill, and running-
stitch outlines — one thread block per colour.

It also **scores whether the image is suitable at all**, which matters more than
any parameter:

```
colour fit    3.1/255  (good)    <- flat logo, stitches well
colour fit   45.4/255  (POOR)    <- photograph, will look muddy
```

Auto-digitizing only works on flat, bold, few-colour artwork — logos,
silhouettes, line art, sticker-style illustration. Photographs do not embroider.
The full guide, including **how to prompt an AI generator so its output is
actually stitchable**, is in
[Image → Embroidery](docs/09-image-to-embroidery.md).

## Building designs in code

`pyembroidery` works in units of 1/10 mm. The example generator in
`tools/examples/` shows the shape of it: build geometry in millimetres, read
bounds from the machine profile rather than hard-coding them, validate before
writing.

```powershell
.venv\Scripts\python.exe tools\examples\generate_monogram_frame.py
```

For drawn rather than generated work, use **Ink/Stitch** (free, Inkscape
extension) and keep the SVG in `designs/source/`.
