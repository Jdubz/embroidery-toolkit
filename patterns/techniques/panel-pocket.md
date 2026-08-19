# A zipped pocket built into a panel

A reusable technique note. Patterns reference this rather than re-explaining
it; nothing here depends on any particular bag's dimensions.

A panel pocket is **not a pocket applied to a panel**. The panel becomes two
layers and the pocket is the cavity between them. Nothing is sewn onto
anything, nothing is cut open, and the compartment behind carries on as if the
pocket were not there.

For the zipper itself — coil sizes, lapping onto tape, shortening, sliders —
see [`zippers.md`](zippers.md). This note is about the panel.

---

## The idea

```svg
<svg id="pocket-section" viewBox="0 0 640 320" role="img" aria-label="Section through a pocketed panel. An inner layer runs the full height and is bound top and bottom; an outer layer is cut in two with a zipper between the halves. The pocket is the cavity between the two layers and the compartment is sealed behind the inner layer.">
  <g font-family="var(--f-label)" font-size="11" letter-spacing="1.6" fill="var(--muted)">
    <text x="20" y="24">SECTION — CUT DOWN THROUGH THE PANEL</text>
    <text x="150" y="300" text-anchor="middle">OUTSIDE</text>
    <text x="470" y="300" text-anchor="middle">THE COMPARTMENT</text>
  </g>

  <!-- the cavity between the two layers -->
  <rect x="312" y="52" width="30" height="216" fill="var(--stitch)" opacity=".16"/>
  <text x="327" y="196" text-anchor="middle" font-family="var(--f-data)"
        font-size="13" fill="var(--stitch)" transform="rotate(-90 327 196)">the pocket</text>

  <!-- inner layer: one piece, full height -->
  <rect x="342" y="52" width="13" height="216" fill="var(--shell)"/>
  <text x="372" y="120" font-family="var(--f-data)" font-size="13" fill="var(--ink)">inner layer —</text>
  <text x="372" y="138" font-family="var(--f-data)" font-size="13" fill="var(--ink)">one piece, full size,</text>
  <text x="372" y="156" font-family="var(--f-data)" font-size="13" fill="var(--ink)">bound on all four edges</text>
  <text x="372" y="182" font-family="var(--f-data)" font-size="12" fill="var(--muted)">it is the compartment wall</text>

  <!-- outer layer: two pieces with the zip between -->
  <rect x="299" y="52" width="13" height="88" fill="var(--shell-2, var(--shell))"/>
  <rect x="299" y="180" width="13" height="88" fill="var(--shell-2, var(--shell))"/>
  <rect x="291" y="142" width="29" height="36" fill="var(--coil)"/>
  <g stroke="var(--shell)" stroke-width="1.6" opacity=".55">
    <path d="M291,150 h29 M291,160 h29 M291,170 h29"/>
  </g>
  <text x="270" y="100" text-anchor="end" font-family="var(--f-data)" font-size="13" fill="var(--ink)">outer, upper</text>
  <text x="270" y="164" text-anchor="end" font-family="var(--f-data)" font-size="13" fill="var(--coil)">the only mouth</text>
  <text x="270" y="228" text-anchor="end" font-family="var(--f-data)" font-size="13" fill="var(--ink)">outer, lower</text>
  <path d="M276,96 H295 M276,160 H286 M276,224 H295" stroke="var(--muted)" stroke-width="1"/>

  <!-- binding catching BOTH layers, top and bottom -->
  <path d="M291,52 H358 Q374,52 374,40 Q374,28 358,28 H291 Q275,28 275,40 Q275,52 291,52"
        fill="none" stroke="var(--binding)" stroke-width="11" transform="translate(0,10)"/>
  <path d="M291,268 H358 Q374,268 374,280 Q374,292 358,292 H291 Q275,292 275,280 Q275,268 291,268"
        fill="none" stroke="var(--binding)" stroke-width="11" transform="translate(0,-10)"/>
  <text x="392" y="46" font-family="var(--f-data)" font-size="12" fill="var(--muted)">the binding catches both layers</text>
  <text x="392" y="272" font-family="var(--f-data)" font-size="12" fill="var(--muted)">— and both again down the sides</text>
</svg>
```

Three consequences, and they are the whole reason to build it this way:

- **The pocket is sealed.** The zip opens into the cavity and never into the
  compartment, so nothing migrates between them. Hang a partial bag off one lip
  instead and the zip becomes a second mouth into the bag.
- **No load crosses the zip.** Anything tacked to the panel reaches the inner
  layer, which the seam holds on all four sides. Open the zip under load and
  the bag is still hanging off a complete panel.
- **Nothing is cut open.** A welt opening in a loaded panel is the hardest
  operation in bag making, it puts a slit across the grain where the load runs,
  and it is the one step that cannot be practised on scrap first — because the
  practice piece *is* the panel.

---

## The three pieces, and the sum that has to work

```svg
<svg id="pocket-pieces" viewBox="0 0 640 290" role="img" aria-label="The three pieces of a pocketed panel. The inner layer is the full panel height. The outer upper and outer lower each lap onto the zipper tape, and the upper less its lap, plus the coil, plus the lower less its lap, adds back up to the panel height.">
  <g font-family="var(--f-label)" font-size="11" letter-spacing="1.6" fill="var(--muted)">
    <text x="20" y="22">INNER — ONE PIECE</text>
    <text x="330" y="22">OUTER — TWO, ONTO THE TAPE</text>
  </g>

  <!-- inner -->
  <rect x="30" y="40" width="180" height="220" fill="var(--shell)" opacity=".9"/>
  <text x="120" y="156" text-anchor="middle" font-family="var(--f-data)" font-size="13" fill="#fff">panel, full size</text>
  <g stroke="var(--muted)" stroke-width="1">
    <path d="M232,40 V260 M226,40 h12 M226,260 h12"/>
  </g>
  <text x="248" y="154" font-family="var(--f-data)" font-size="12" fill="var(--muted)">panel height</text>

  <!-- outer, exploded -->
  <rect x="340" y="40" width="180" height="76" fill="var(--shell)" opacity=".9"/>
  <rect x="340" y="184" width="180" height="76" fill="var(--shell)" opacity=".9"/>
  <rect x="330" y="120" width="200" height="60" fill="var(--muted)" opacity=".35"/>
  <rect x="330" y="142" width="200" height="16" fill="var(--coil)"/>
  <text x="430" y="82" text-anchor="middle" font-family="var(--f-data)" font-size="13" fill="#fff">outer, upper</text>
  <text x="430" y="228" text-anchor="middle" font-family="var(--f-data)" font-size="13" fill="#fff">outer, lower</text>

  <!-- the laps -->
  <g stroke="var(--cut)" stroke-width="1.5" fill="none">
    <path d="M340,116 V138 M520,116 V138"/>
    <path d="M340,162 V184 M520,162 V184"/>
  </g>
  <text x="556" y="130" font-family="var(--f-data)" font-size="12" fill="var(--cut)">lap</text>
  <text x="556" y="178" font-family="var(--f-data)" font-size="12" fill="var(--cut)">lap</text>

  <!-- the sum -->
  <g stroke="var(--stitch)" stroke-width="1">
    <path d="M300,40 V116 M294,40 h12 M294,116 h12"/>
    <path d="M300,142 V158 M294,142 h12 M294,158 h12"/>
    <path d="M300,184 V260 M294,184 h12 M294,260 h12"/>
  </g>
  <text x="20" y="286" font-family="var(--f-data)" font-size="13" fill="var(--stitch)">(upper − lap)  +  coil  +  (lower − lap)  =  panel height</text>
</svg>
```

**Check the sum before you go near the bag.** The outer layer has to end up
exactly as tall as the inner one, and every pattern here derives both from that
identity. Get it wrong and the panel is the wrong size, which you discover when
the gusset ring no longer fits it — after the ring is made.

**Cut the outer pieces as pairs.** If a bag has a pocket on both panels, the two
outers are the same two pieces at the same zip height. That is deliberate: it is
what lets one step describe both, and it halves the number of distinct pieces on
the cutting mat.

**Whichever outer piece carries the panel's bottom edge inherits its shape.** If
the panel has rounded corners, the outer *lower* is not a rectangle either — the
inner layer and the lower outer both get cut round the same template.

---

## Building one

1. **Shorten the zipper and stop both ends** before anything else. If the ends
   will finish inside a bound seam, the new stops go **inside the stitch line**,
   so the binding never has to wrap a metal one — see
   [`zippers.md`](zippers.md).
2. **Lap the upper onto the tape and topstitch two rows.** Basting tape, zipper
   foot, sharp needle.
3. **Lap the lower onto the tape the same way, sewing in the same direction.**
   Both laps sewn the same way round or the panel bows — the tape feeds
   slightly differently under the foot each way, and over a long panel the
   difference shows.
4. **Measure the reassembled outer against the inner.** This is the last moment
   it is cheap to fix.
5. **Park the slider at the end you can reach.** Once both ends are bound there
   is no adding a slider and no retrieving one that has run off.
6. **Lay outer over inner, wrong sides together, and clip.** From here treat the
   pair as one panel: it goes into the ring, gets bound, and behaves like any
   other panel.

---

## Tacking anything to a pocketed panel

```svg
<svg id="pocket-tack" viewBox="0 0 640 260" role="img" aria-label="Where a tack may go on a pocketed panel. Above the zip the box-X passes through the outer piece and the inner layer, so load reaches a panel bound on four sides. Below the zip, on the lower outer piece, the only attachment upward is the zipper itself.">
  <g font-family="var(--f-label)" font-size="11" letter-spacing="1.6">
    <text x="20" y="22" fill="var(--stitch)">ABOVE THE ZIP — THROUGH BOTH LAYERS</text>
    <text x="350" y="22" fill="var(--cut)">BELOW IT — HANGING ON THE ZIP</text>
  </g>

  <!-- left: correct -->
  <rect x="40" y="44" width="240" height="66" fill="var(--shell)" opacity=".9"/>
  <rect x="40" y="126" width="240" height="90" fill="var(--shell)" opacity=".9"/>
  <rect x="30" y="110" width="260" height="16" fill="var(--coil)"/>
  <rect x="40" y="44" width="240" height="172" fill="none" stroke="var(--stitch)"
        stroke-width="2.5" stroke-dasharray="7 4"/>
  <g stroke="var(--stitch)" stroke-width="2.5" fill="none">
    <rect x="130" y="60" width="52" height="34"/><path d="M130,60 L182,94 M182,60 L130,94"/>
  </g>
  <path d="M156,100 V44" stroke="var(--stitch)" stroke-width="1"/>
  <text x="156" y="238" text-anchor="middle" font-family="var(--f-data)" font-size="12" fill="var(--stitch)">load reaches the inner panel,</text>
  <text x="156" y="254" text-anchor="middle" font-family="var(--f-data)" font-size="12" fill="var(--stitch)">which is bound on all four sides</text>

  <!-- right: wrong -->
  <rect x="360" y="44" width="240" height="66" fill="var(--shell)" opacity=".9"/>
  <rect x="360" y="126" width="240" height="90" fill="var(--shell)" opacity=".9"/>
  <rect x="350" y="110" width="260" height="16" fill="var(--coil)"/>
  <g stroke="var(--cut)" stroke-width="2.5" fill="none">
    <rect x="450" y="150" width="52" height="34"/><path d="M450,150 L502,184 M502,150 L450,184"/>
  </g>
  <path d="M476,146 V126" stroke="var(--cut)" stroke-width="2" stroke-dasharray="5 4"/>
  <text x="480" y="238" text-anchor="middle" font-family="var(--f-data)" font-size="12" fill="var(--cut)">open the zip and the only thing</text>
  <text x="480" y="254" text-anchor="middle" font-family="var(--f-data)" font-size="12" fill="var(--cut)">holding it up is the coil</text>
</svg>
```

A keeper, a tab or a ring on a pocketed panel must sit **on the piece that is
still attached to the rest of the bag with the zip open**, and its tack must go
through to the inner layer. In practice that means above the zip line, in the
band left between the panel's seam allowance and the upper piece's lap onto the
tape — and that band is the whole reason the zip's position is a compromise
between how deep the pocket is and how wide a belt the panel can carry.

---

## What the cut list will not tell you

- **The usable depth is less than the piece you cut.** The cavity runs to the
  panel's edge, but the outer seam allowance is caught in the binding and is not
  interior. On a panel with rounded corners the bottom pinches in as well, and
  how much depends on how wide the thing is you are putting in.
- **The cavity reaches above the opening too.** It is the whole space between
  the layers, so it runs from binding to binding with the zip as a slot part way
  down. Useful — it stops a flat thing sliding into a blind area — but only if
  something crosses it. Tacks through both layers partition it for free.
- **The binding gets a layer thicker here.** Two panels plus the gusset plus the
  binding itself, at every edge of that panel and at every mitred corner. Size
  the binding strip from the worst seam on the bag, not the average one.

---

## When it goes wrong

| Symptom | Cause | Fix |
|---|---|---|
| The ring no longer fits the panel | The reassembled outer is not the inner's height | Check the sum before assembly. After it, the only fix is recutting a strip |
| The panel bows along its length | The two laps were sewn in opposite directions | Unpick one and re-sew it the same way as the other |
| Things migrate from the pocket into the bag | The inner layer is not full size, or is not caught in the binding all round | There is no repair: the inner layer *is* the seal |
| The bag sags off the belt with the pocket open | A tack sits below the zip line | Move it above, through both layers. Below it, the coil is the load path |
| A lump under the binding at the panel's edge | A metal zip stop left inside the seam allowance | Bar-tack a new stop inboard of the stitch line and remove the metal one |
| A slider has run off and cannot be replaced | Both ends were bound before the slider was parked | Park it before the panel goes into the ring, every time |
| The lower outer piece will not lie on the panel | It was cut square on a panel with rounded corners | Cut the inner layer and the lower outer round the same template |

## Watch it done

Found and link-checked 2026-08-18. Nothing online builds this exact panel —
a pocket as the cavity between two layers, with nothing cut open — so these
cover the parts.

| | What it shows |
|---|---|
| **[How To Neatly Sew a Lapped Zip with a Concealing Flap](https://threadsmonthly.com/sew-lapped-zip/)** *(article + video)* | The closest thing to the **placket** step anywhere: a flap covering the coil, caught in the seam that is being sewn regardless |
| **[Bethany Lynne — How to Sew a Recessed Zipper, open-end method](https://www.bethanylynnemakes.com/how-to-sew-an-open-end-recessed-zipper/)** | Bag-maker's version of lapping cloth onto tape rather than cutting an opening into a panel |
| **[Sew Sweetness — Zippers 4 Ways](https://sewsweetness.com/2012/10/zippers-4-ways.html)** | Compares the approaches side by side, which is the useful thing when deciding |

**Translate one word.** In garment sewing a "lapped zipper" means one side of a
seam folded over to hide the coil. Here **lap** means a stated overlap onto the
tape, topstitched — a different operation with the same name. The arithmetic
in this note is what matters, not theirs.

---

## Further reading

- [`zippers.md`](zippers.md) — the coil, the lap, shortening, stops and sliders
- [`binding.md`](binding.md) — what the panel's edge becomes once both layers
  are in it

---

*Used by:* `patterns/constructions/box-bound.json` — the pocketed-panel step,
and every step that tacks something to a panel.
