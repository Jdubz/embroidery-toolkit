# Techniques

Reusable how-to notes referenced by patterns in `patterns/`. Nothing here is
specific to a single design — a pattern links to a technique rather than
re-explaining it, so the explanation improves in one place.

| Note | Covers |
|---|---|
| [binding.md](binding.md) | Wrapping a raw edge in a strip: width formula, single vs double fold, straight vs bias, the one-pass method, mitred corners, inside corners, 3D seams, closing the loop |
| [webbing-hardware.md](webbing-hardware.md) | The box-X tack and why it cannot be sewn in one pass, assembling a belt keeper and its anchor strip, threading a tri-glide, hot-knifing |
| [zippers.md](zippers.md) | Coil chain and what #5 means, the lapped panel that cuts no opening, shortening and bar-tacking a new stop, ends that get bound over, two sliders and which way they face, getting a slider back on |
| [panel-pocket.md](panel-pocket.md) | Building a zipped pocket INTO a panel: the two layers and the cavity between them, the sum the outer pieces have to reassemble to, why the compartment stays sealed and no load crosses the zip, and where a tack may go |

## Diagrams

A note may carry inline SVG in an ```` ```svg ```` fence. The player renders it
verbatim; everywhere else it is a fenced block that no reader has to care
about. **Draw with the player's own tokens** — `var(--ink)`, `var(--cut)`,
`var(--stitch)`, `var(--web)`, `var(--shell)`, `var(--muted)` — so a diagram
follows the reader's theme instead of pinning one. Give every diagram a
`role="img"` and an `aria-label` that says what it shows, because a diagram
that only exists as a picture excludes the people most likely to need it.

The page can fetch nothing, so a diagram has to *be* the document. No image
files, no external references.

## Linking a note to the step that needs it

An assembly step in `patterns/constructions/*.json` may carry
`"see": ["patterns/techniques/<note>.md"]`, and the player renders a button
that opens it. Prefer that to explaining a method inside a step: a step should
say what to do to *this bag*, and a technique note should say how the operation
works at all.

Both directions are checked. `bag_pattern.py` fails if a link points at a
document the package does not carry — a dead link renders as nothing, and the
step then reads as though no method existed — **and** if a technique note is
never linked from any step, because a note nobody reaches is a note nobody
reads.

A step may also legitimately link nothing. Five of the box-bound family's
twenty-two do: they state the whole operation in the step and there is no
method behind them worth a page. That is a decision, and the wiring records it
rather than leaving the gap looking like an oversight.

Notes may also point across domains. The embroidery step links
`docs/12-design-generation-playbook.md`, `docs/14-designing-for-dark-cloth.md`
and `docs/16-narrow-material.md`, which are the other half of this repository —
carried as `"kind": "embroidery"` so the quick-help rail groups them apart.

## Adding one

Write it when a pattern starts explaining something a second time, or when a
pattern assumes a skill it does not teach — those are the two signals.

Each note should stand alone: nothing that depends on a particular bag's
dimensions, materials or machine. Where a pattern needs specifics, the pattern
states them and links here for the method.

Keep a **When it goes wrong** table. The failure modes are the part worth
writing down — the happy path is on YouTube, the symptom-to-cause mapping is not.

End with a *Used by* line so it is obvious what breaks if the note changes.
