# Stitch-Out Playbook

The repeatable sequence from idea to finished piece. Follow it in order; most
embroidery failures are sequence failures.

---

## 1. Design

Author at **final size**. Resizing a stitch file does not re-space the stitches —
scaling up thins the coverage, scaling down bunches it into a stiff mat. Under
about ±10% you can get away with it; beyond that, re-digitize.

Target **96 × 96 mm maximum** so you have real clearance in a 100 mm field.

Keep the vector source in `designs/source/`. The `.pes` is a build artifact.

## 2. Validate before you touch fabric

```powershell
.\stitch.ps1 validate designs\out\rose.pes
.\stitch.ps1 render   designs\out\rose.pes  # what it will actually look like
```

**Judge the design from `render`, never from the machine's own preview.** The
machine's LCD draws the travel between stitches as well as the stitches, so any
design with a lot of trims looks like a ball of scribble on it — even when the
file is perfect. `render` draws only what gets sewn, on a fabric background.

Add `--show-jumps` to see the travel in magenta. That view is for judging
pathing, not the result.

This catches, at the desk, everything that otherwise wastes a hooping:

- design larger than the field (the machine would silently not list it)
- stitch count over 100,000
- filename characters the machine mishandles
- jump-heavy pathing that will mean endless trimming
- colour-change count — i.e. how many times you'll rethread by hand

## 3. Choose thread colours against the real palette

PES quantises colour to Brother's 64-entry palette. Check what your colours will
actually become *before* you write the file:

```powershell
.\stitch.ps1 palette --match "#2E86AB" -n 3
```

ΔE under 5 is invisible. Over 15, pick a different colour.

## 4. Transfer

Preferred route — Design Database Transfer over wireless:

```powershell
.\stitch.ps1 stage designs\out\rose.pes
```

Runs the validation gate and prints the wireless checklist without copying;
`designs\out` is already the folder DDT reads. Transfer from DDT, then on the
machine **retrieve from the wireless pocket (source 3), not machine memory** — a
transfer does not overwrite a copy saved there on an earlier run, and picking
the stale one gives no warning. Details in `03-transferring-designs.md`.

USB fallback:

```powershell
.\stitch.ps1 drives
.\stitch.ps1 stage designs\out\rose.pes --to E:\
```

Eject properly from Windows. Then unplug.

## 5. Prepare the machine

1. **Attach the embroidery unit.** Without it, the machine has no embroidery
   mode and will not list any designs.
2. Fit a **fresh 75/11 needle**.
3. Wind or load a **60 wt bobbin**, correct direction.
4. Thread the top with 40 wt embroidery thread — presser foot **up** while
   threading, so the tension discs are open.
5. Confirm the machine is set for the hoop you're actually using.

## 6. Hoop

Fabric plus stabilizer as one sandwich. Taut, not stretched. Check nothing is
trapped underneath.

Match the stabilizer to the fabric (see
[Materials](05-materials-and-consumables.md)) — knits get cut-away, textured
fabric gets a water-soluble topping.

## 7. Trace before you stitch

Use the machine's trace/outline function to walk the carriage around the design
boundary. Watch the needle position relative to the hoop and the garment. This
five-second check is the last chance to catch a misplaced design, and it costs
nothing.

## 8. Stitch

- Stay with the machine. Thread breaks are silent until they aren't.
- **Start each colour, stop after 5–6 stitches, and cut the tail.** This is a
  numbered step in the manual's own procedure (p.70, steps d–e), not a nicety:

  > "If the thread is left at the beginning of the stitching, it may be
  > embroidered over as you continue embroidering the pattern, making it very
  > difficult to remove the excess thread after the pattern is finished."

  Hold the thread with a little slack as you start, run 5–6 stitches, press
  Start/Stop again, trim flush, then restart. Thirty seconds per colour buys
  you a tail you cannot otherwise get out. Raise the presser foot to trim if
  the tail is trapped under it.
- **The SE700 does not trim jumps within a colour.** It auto-cuts at colour
  changes only; the manual's own step (i) is "Cut the excess thread jumps within
  the color." So the piece comes off the machine with threads lying across it,
  and you snip them. That is normal, not a fault in the file.
- Trim those jump threads **as they happen**, not at the end — much easier while
  the design is still hooped and flat, and you avoid stitching over a float and
  trapping it.
- `stitch info` reports the snipping load, e.g. *"hand trimming ~44 min — 658
  jump(s) to snip"*. If that number is unpleasant, raise `--travel` when tracing
  so the fill routes around holes instead of jumping.
- At each colour stop, rethread with the presser foot up.

## 9. Finish

1. Unhoop carefully; don't drag the stitching across the hoop edge.
2. Trim stabilizer — cut-away trimmed to ~5 mm, tear-away torn along the
   stitch line in multiple directions rather than one hard pull.
3. Dissolve any water-soluble topping with a damp cloth or a rinse.
4. Press **from the back**, on a towel, never directly on the stitches.

## 10. Log it

Record what you did in `projects/`. Six months from now you will want to know
what stabilizer and tension worked on that fabric. Template:
[`projects/_TEMPLATE.md`](../projects/_TEMPLATE.md).

---

## Test stitch-out

Before committing to a garment, stitch the design once on scrap of the **same
fabric with the same stabilizer**. Not similar fabric — the same. This is the
difference between hobbyists who produce consistent work and those who don't.

There's a ready-made test design in this repo:

```powershell
.venv\Scripts\python.exe tools\examples\generate_monogram_frame.py
```

338 stitches, two colours, sized to the field — quick to run and it exercises
colour changes, curves, and corner registration.

---

## Tension quick reference

The upper tension dial is the adjustment you'll reach for. The classic test:
stitch a filled block and look at the **back**.

| What you see on the back | Meaning | Fix |
|---|---|---|
| ~⅓ bobbin, ⅔ top thread down the centre | Correct | Nothing |
| Bobbin thread pulled to the top face | Upper tension too tight | Lower the dial |
| Top thread showing heavily on the back | Upper tension too loose | Raise the dial |
| Loops and nests under the fabric | **Not tension** — rethread | See [Troubleshooting](07-troubleshooting.md) |

That last row matters: loops under the fabric almost never mean the bobbin
tension is wrong. It means the *top* thread isn't seated in the tension discs.
Rethread with the presser foot up before you touch any dial.
