# Troubleshooting

Ordered by how often each thing is actually the cause. Work top-down.

---

## The machine won't show my design

In order:

1. **Is the embroidery unit attached?** Without it there is no embroidery mode
   and no design browser. This is the most common cause by a wide margin.
2. **Is the design larger than 100 × 100 mm?** The machine does not warn — it
   just omits the file from the list. Run `.\stitch.ps1 validate <file>`.
3. **Is [Embroidery Frame Identification View] ON with a small frame selected?**
   Settings screen → Embroidery, item 3: *"When set to [ON], you can only select
   the embroidery pattern corresponding to the embroidery frame size that you
   selected."* With the 2 × 6 cm SA431 selected, a perfectly valid 90 mm design
   will not be listed, and pushing on gives "Pattern extends to the outside of
   embroidery frame. Select a larger frame." Check this **before** concluding
   the file is at fault — it is the one cause `validate` cannot see, because
   nothing is wrong with the file.
4. **Is the format one of `.pes` `.phc` `.dst` `.pen`?** JEF, EXP, VP3, ART will
   not appear. Convert: `.\stitch.ps1 convert in.jef out.pes`.
5. **Is the drive FAT32?** exFAT and NTFS are not read. `.\stitch.ps1 drives`
   reports the filesystem.
6. **Does the filename use anything outside `A-Z a-z 0-9 - _`?** Rename.
7. **Was the drive ejected properly?** A truncated file reads as corrupt.
8. **Over 100,000 stitches?** Split the design.
9. **Did it arrive wirelessly, and has the machine been switched off since?**
   Wirelessly transferred patterns land in the volatile "wireless function
   pocket" and are **deleted when the machine is powered off**. See
   `03-transferring-designs.md`.

## The design stitched, but it's the OLD version

Almost always the wireless pocket, and it does not look like a transfer problem
at all — it looks like your edits did nothing.

A Design Database Transfer lands in the **wireless pocket** (source 3 on the
retrieve screen). It does **not** overwrite anything in the machine's memory. If
you saved that design to memory on an earlier run, the old copy is still there,
still has the same name, and is still selectable from source 1.

1. Confirm the file on the PC actually changed — check its timestamp and size.
2. Re-transfer from DDT.
3. On the machine retrieve from **source 3, the wireless pocket**.
4. If you want it in memory, **delete the old copy of that name first**, then
   save the new one. Two designs with the same name is how this repeats.

Check this before re-examining the design file. Chasing a phantom defect in a
file that never ran is expensive.

## Bird-nesting — loops and tangles under the fabric

Despite appearances this is nearly always a **top thread** problem, not a bobbin
one. The nest forms underneath because the top thread has no tension holding it.

1. **Rethread the top completely, with the presser foot UP.** The tension discs
   only open when the foot is raised; threading with it down leaves the thread
   sitting beside the discs with no tension at all. This fixes it most of the time.
2. Check the bobbin is inserted with the thread unwinding the correct direction
   (use the `b` mark on the supplied bobbins as reference).
3. Check the bobbin is Class 15, not 15J, and seated flat.
4. Clean lint out of the bobbin case and race. Lint packs in and blocks the
   thread path.
5. Replace the needle — a bent one misses the bobbin hook.

## Bobbin thread showing on the top

**Triage by severity first — the two cases have different causes.**

| What you see | Cause | Fix |
|---|---|---|
| **Bobbin thread everywhere, swamping the top colour** | **Incorrect bobbin threading** | Re-install the bobbin. Set the dial back to 4 first. |
| **Satin swamped, fills fine — in the same colour block** | **Incorrect bobbin threading** | As above. See the warning below. |
| Occasional flecks of bobbin colour | Upper tension too tight | Lower the tension dial |

> **"Swamped" does not have to mean everywhere, and this is the trap.** On
> LemonY the bobbin lay white over the entire 2.56 mm satin outline while the
> fills — one pass earlier, same thread, same bobbin, same run — came out solid
> black. That reads overwhelmingly like a defect in the *design*, and a whole
> session went into measuring the file. It was the bobbin.
>
> The split is expected, not evidence: the bobbin thread surfaces wherever the
> cloth grips the lockstitch knot least, and a satin rail puts 2.5 needle holes
> per millimetre on a single line — a perforation a sparse, stagger-offset fill
> never creates. **One fault, two substrates.** A stitch-type-selective symptom
> does not exonerate the bobbin; work this section to the end first.

### Swamped — you can barely see the top thread

This is not a tension adjustment. The manual is explicit (p.85, *Upper thread
tightened up*), and lists among the symptoms:

> "The upper thread tension is tight, **and the results do not change even after
> the thread tension is adjusted**."

> **Cause: Incorrect bobbin threading.** "If the bobbin thread is incorrectly
> threaded, instead of the appropriate tension being applied to the bobbin
> thread, it is pulled through the fabric when the upper thread is pulled up.
> For this reason, the thread is visible from the right side of the fabric."

The bobbin thread is bypassing its tension spring entirely, so it has almost no
tension and the upper thread simply drags it to the surface. Chasing this with
the dial cannot work and will waste material.

**Remedy** (p.86 states the order):

1. **Return the thread tension dial to 4.** Undo any adjusting done while
   chasing the symptom — you are re-baselining, not tuning.
2. **Remove and re-install the bobbin** (p.22). The thread must be drawn into
   the slot and **under the tension spring**; dropping the bobbin in and pulling
   the thread straight out leaves it untensioned. That is this failure.
3. **Check the winding direction.** Place the bobbin into the case in the same
   orientation it sat on the winder shaft — the `b` mark on the supplied bobbins
   is the reference.
4. **Confirm from the back.** Correct is upper thread just visible on the wrong
   side. If the back shows a flat line of bobbin thread with no upper thread at
   all, the bobbin still has no tension.
5. Test on scrap before re-running the design.

If it survives all five, then look at the design — but in that order, not the
reverse.

### Occasional flecks

Now it is a tension adjustment. The manual (p.72, *Adjusting thread tension*):

> **Upper thread is too tight** — "The bobbin thread will be visible on the
> right side (top) of the fabric. In this instance, decrease the upper thread
> tension."

**Turn the thread tension dial DOWN.** It is the physical dial, not an on-screen
setting. Lower number = looser. For machine embroidery the manual specifies the
dial should sit **between 2 and 6** — if yours is above 6, that alone explains
it. Move one number at a time and re-test on scrap; the useful range is narrow.

**How to know when it is right** (same page):

> "The thread tension is correct when upper thread is just visible on the wrong
> side (bottom) of the fabric."

So judge it from the **back**, not the front. The classic embroidery check is
the same rule stated as a ratio: looking at the reverse, you want a band of
bobbin thread down the middle with upper thread showing at both edges — roughly
one third upper, one third bobbin, one third upper.

If the dial is already at 2–4 and bobbin is still coming through, work down this
list:

1. **Rethread the top with the presser foot UP.** The tension discs only open
   when the foot is raised. Threading with it down leaves the thread sitting
   beside the discs, and the resulting tension is erratic rather than simply
   loose — it can read as too tight in places.
2. **Check the spool cap.** A cap that is too small lets thread catch under the
   spool and snatch, which spikes tension intermittently. That produces bobbin
   show-through *in places* rather than everywhere.
3. **Re-seat the bobbin.** Class 15, not 15J, sitting flat, unwinding the
   correct way — use the `b` mark on the supplied bobbins as reference.
4. **New needle.** A blunt or burred needle drags the upper thread, which
   behaves exactly like too much tension. Do this anyway after any needle break.
5. **Clean the bobbin case and race.** Lint under the bobbin case tension spring
   changes bobbin tension.
6. **Match the bobbin thread to the job.** 60 wt white bobbin under a dark
   40 wt top thread is the standard setup, but it is also the highest-contrast
   one — any show-through is maximally visible. For a dark design a black bobbin
   makes small imperfections invisible. This is cosmetic cover, not a fix;
   correct the tension first.

### Then check the design for short stitches

Short stitches cause this too, and they cause it **in places** rather than
uniformly — which is the tell. Two penetrations closer together than about
0.5 mm sit in nearly the same hole, so the upper thread has almost no length
over which to take up tension and the bobbin thread gets drawn to the surface.

```powershell
.\stitch.ps1 validate designs\out\yours.pes
```

A `short-stitches` finding reports what share of the design is below the
profile's `min_stitch_mm`. Anything at or above 2% is worth fixing at the
source:

- **Ink/Stitch output** — set `inkstitch:min_stitch_len_mm` in the document
  metadata. `tools/color_separate.py` and `tools/svg_merge.py` now write it from
  the machine profile; a document without it gets no filtering at all.
- **`stitch trace` output** — raise `--min-stitch`.

## Needles breaking

Stop and check these before running again — a broken needle can throw fragments.

**1. Is the fabric hanging off the table?** The manual is explicit, and this is
the one people miss:

> "When embroidering on large garments (especially jackets or other heavy
> fabrics), **do not let the fabric hang over the table**. Otherwise, the
> embroidery unit cannot move freely and the **embroidery frame may strike the
> needle, causing the needle to break**."

If you can hear the frame snapping or thumping as it moves, something is
resisting the carriage — hanging fabric, the hoop catching, or an object in its
path. Support the whole garment level with the bed.

**2. Fabric thicker than 2 mm?** Embroidery's limit is 2 mm, not the 6 mm
sewing limit. Fleece, heavy denim and multiple layers exceed it.

**3. Is the hoop tight?** Loose fabric flags up and down with the needle, which
deflects it. Taut like a drum, not stretched.

**4. Replace the needle now.** After any needle break, the next needle is
working next to a damaged plate or hook. Fit a fresh 75/11 and check the needle
plate and bobbin case for burrs.

**Checking a needle is straight** (manual p.28): lay the **flat side of the
shank on a flat surface** and look along it. The gap between needle and surface
must be even along the whole length. A needle bent a few hundredths of a
millimetre looks perfect held up to the light and fails this test immediately.
Do it on every needle before fitting, not just after a break — a new needle can
arrive bent.

**Knowing when a needle is due.** The rule is a fresh needle every 6–8 stitching
hours, and the machine will tell you where you are: Settings → General shows the
**total number of stitches sewn**. At the fixed 400 spm that is roughly
**144,000–192,000 stitches** per needle. Note the reading when you fit one.

**5. Design too dense.** See below — over-dense areas force the needle through
packed thread and it deflects until it snaps.

## Thread keeps breaking

Work the machine side first — it is free and fixes most cases.

1. **New needle.** A burr or blunt tip shreds thread. Do this first, always,
   even if the needle looks fine. Change every 6–8 stitching hours regardless.
2. **Rethread the top with the presser foot UP.** The tension discs only open
   when the foot is raised; threading with it down leaves the thread beside the
   discs. This is the second most common cause.
3. **Lower the upper tension** a little.
4. **Check the thread path for snags** — including the spool cap. A wrong-size
   cap lets thread catch under the spool, and the thread then yanks.
5. **Clean the bobbin case and race.** Lint drags on the thread.
6. ~~Slow the machine down.~~ **You cannot.** This is standard advice for
   embroidery machines and it does not apply here. The manual states the sewing
   speed controller "cannot be adjusted while sewing decorative stitches or
   **embroidering**", and the Embroidery settings screen (p.15) has no speed
   option — only frame, grid, thread display, brand, units and colours. The
   400 spm maximum is therefore a **fixed** rate, not a ceiling you can back
   off. Skip this step and spend the effort on the needle, the threading and
   the design's density instead.
7. **Old or dry thread breaks.** Thread has a shelf life; cheap thread more so.
   Try a different spool before blaming the machine.

### Then check the design's density

If the machine side is clean and breaks cluster in the *same place each run*,
the design is too dense there. The manual is explicit: thread or needle may
break "when embroidering with a stitch density that is too fine or when
embroidering three or more overlapping stitches".

Measure rather than guess — median density stays normal even when the peaks are
lethal:

```powershell
.\stitch.ps1 info designs\out\yours.pes
```

Rules of thumb for a 0.4 mm fill on this machine:

| Penetrations / mm² | Meaning |
|---|---|
| ~3 | normal fill |
| 8–12 | underlay + fill + outline + colour overlap; fine |
| 16+ | getting risky |
| 30+ | expect breaks, needle damage and a perforated, board-stiff patch |

The usual culprit in files from this repo is **travel routing** — walking around
holes instead of jumping lays extra thread through already-stitched ground.
`--max-density` caps it (default 16). Lower it, or lower `--travel`, and
re-trace. Both cost you extra jump floats to snip, which is the right trade.

## Recovering mid-design — you do not have to start over

Two facilities that are easy to miss, and both save a ruined piece.

**After a thread break or an empty bobbin** (manual p.71): stop, rethread or
replace the bobbin, then use the machine's reverse-stitch keys to **move the
needle back to before the break** and resume. Back up past the break, not to
it — the last few stitches before a break are usually already bad. If you
cannot reach the spot, jump to the start of that colour and step forward.

Note this is also why a thread break is not a disaster on a 30-minute design:
you lose seconds, not the run.

**After a power cut, or if you switch off mid-run** (manual p.71): the machine
saves the current colour and stitch number. On the next power-on it offers to
resume — "OK to recall and resume previous memory?" — and restores the pattern
position and stitch count. Align the needle as for a thread break and carry on.

## Skipped stitches

Needle, needle, needle. Then:
- Wrong needle type for the fabric — knits need ball point.
- Needle inserted not fully up, or backwards.
- Fabric flagging (bouncing) because the hooping is loose.

## Puckering around the design

- Stabilizer too light for the design's density, or the wrong type — knits need
  cut-away.
- Fabric was stretched when hooped rather than merely taut.
- Design density too high for the fabric.

## Design distorts or shifts partway through

- Hoop is loose; fabric slipped. Re-hoop tighter.
- Something is snagging the hoop as the carriage travels — check clearance
  around and behind the machine.
- Excess fabric caught under the hoop or trapped against the machine body.

## Design looks fuzzy / stitches sink in

Missing water-soluble topping on a fabric with pile — towelling, fleece,
corduroy, sweatshirt knit. Add it on top before hooping.

## Colours are wrong from the file

Two possibilities:

- **It's a DST.** DST has no colour data; the machine applies its own default
  sequence. Convert to PES.
- **PES palette quantisation.** Colour is stored as an index into Brother's
  64-colour palette; your hex was snapped to the nearest. Check with
  `.\stitch.ps1 palette --match "#YOURHEX"` and pick a palette colour instead.

## Machine won't join WiFi

- **5 GHz network.** The machine is 2.4 GHz only.
- **WPA/WPA2 Enterprise.** Not supported at all. Use a phone hotspot.
- **Band steering** — one SSID for both bands. Split 2.4 GHz onto its own SSID.
- **Client/AP isolation** on a guest network blocks PC↔machine traffic even once
  both are connected.

Operation Manual p.95 covers finding your SSID and network key.

## Error messages on screen

The Operation Manual lists them all on **p.93**
(`reference/manuals/SE700-Operation-Manual-EN.pdf`). Common ones:

| Message | Meaning |
|---|---|
| "A malfunction occurred. Turn the machine off, then on again." | Generic fault. Power cycle. If persistent, service. |
| "Cannot change the configuration of the characters." | Too many characters in a lettering pattern to fit. |

## Fabric jammed and won't come out

Manual p.87 has the full procedure. Summary: do not pull. Raise the needle, cut
the threads, remove the needle plate, free the fabric, clear the race, then
**replace the needle** — it will have been damaged — and test-sew on scrap
before returning to the project.

---

## Maintenance schedule

| When | Do |
|---|---|
| Every bobbin change | Brush lint from the bobbin case |
| Every 6–8 stitching hours | New needle |
| Every few projects | Remove needle plate, clean the race thoroughly |
| Never | **Oil the machine** — the manual prohibits it |
| Storage | Cover it; dust in the tension discs causes tension faults |

Clean the race with the supplied brush, not compressed air — air drives lint
deeper into the mechanism. Never use solvents, thinner, or alcohol on the body.
