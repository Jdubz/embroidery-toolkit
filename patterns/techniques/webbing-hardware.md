# Webbing, keepers and box-X tacks

A reusable technique note. Patterns reference this rather than re-explaining it;
nothing here depends on any particular bag's dimensions.

Everything a bag hangs from is one of three things: a **box-X tack**, a **belt
keeper**, or a piece of **hardware threaded onto webbing**. Get those three
right and no strap on a bag will ever fail.

---

## The box-X

A rectangle of straight stitching with an X corner to corner inside it. It is
the only tack used here, on every webbing joint.

**It tests stronger than a bar-tack**, which fails at its first bar and then
unzips along the row. The X spreads load into four directions instead of one,
so no single line of stitching sees the whole force.

```svg
<svg viewBox="0 0 560 250" role="img" aria-label="A box-X stitching path, numbered in the order it is sewn, showing the one edge that gets retraced.">
  <g fill="none" stroke="var(--web)" stroke-width="34" stroke-linecap="butt" opacity=".35">
    <path d="M60,125 H500"/>
  </g>
  <rect x="120" y="60" width="200" height="130" fill="none" stroke="var(--rule)" stroke-width="1.5"/>

  <g stroke="var(--stitch)" stroke-width="3.5" fill="none" stroke-linejoin="round">
    <path d="M120,190 L120,60 L320,60 L320,190 L120,190"/>
    <path d="M120,190 L320,60"/>
    <path d="M320,60 L320,190" stroke="var(--cut)" stroke-dasharray="7 5"/>
    <path d="M320,190 L120,60"/>
  </g>
  <circle cx="120" cy="190" r="7" fill="var(--stitch)"/>

  <g fill="var(--ink)" font-family="var(--f-data)" font-size="14">
    <text x="103" y="215" text-anchor="middle">start</text>
    <text x="100" y="128">1</text>
    <text x="216" y="50" text-anchor="middle">2</text>
    <text x="333" y="128">3</text>
    <text x="216" y="211" text-anchor="middle">4</text>
    <text x="200" y="112">5</text>
    <text x="228" y="152">7</text>
  </g>
  <text x="352" y="128" fill="var(--cut)" font-family="var(--f-data)" font-size="14">6 — retraced</text>

  <g font-family="var(--f-label)" font-size="12" letter-spacing="1.4" fill="var(--muted)">
    <text x="60" y="105" >WEBBING</text>
    <text x="380" y="222">box ≈ 3 × the webbing width on a load-critical joint</text>
  </g>
</svg>
```

**It cannot be sewn as one continuous path, and a pattern that says otherwise is
wrong.** Every corner meets two box edges and one diagonal — degree three — and
a shape with four odd vertices has no path that crosses each edge exactly once.
So one edge always gets retraced. Sew the box `1-2-3-4`, take the first diagonal
`5`, retrace the right edge `6`, then the second diagonal `7`.

**Go round twice anyway**, which makes the retrace moot and doubles the thread
in the joint for one extra pass.

| | |
|---|---|
| Stitch | Straight, **2.5–3.0 mm** (8–10 per inch) — shorter than a seam, because this is a tack |
| Size | **3 × the webbing width** on anything load-critical. A shorter tab cannot reach that and does not need to; a tab carrying a few pounds is not a harness joint |
| Foot | Walking |
| Speed | Hand-wheel it. This is the thickest stack on most bags |
| Support | A folded scrap under the back of the foot, level with the tack, or the foot tips and the first stitches bunch |

**Never start or stop inside the box.** Begin and end at the same corner so the
lock-off sits on the outside of the pattern where load does not concentrate.

---

## A belt keeper

A strip that makes a tunnel for a belt to slide through. Two of them hold a hip
pack; one holds a pouch on a trouser belt.

**The belt slides, and that is the point.** A keeper is not an attachment
point — it is a sleeve. The pack moves round the body to the front, the hip or
the small of the back, and the buckle moves off the hip bone. A sewn-on belt can
do none of that.

```svg
<svg viewBox="0 0 620 280" role="img" aria-label="Section through a belt keeper, cut across the belt. The panel and anchor strip on the right, the belt in the tunnel, and the keeper arching over it, tacked above and below.">
  <g font-family="var(--f-label)" font-size="11" letter-spacing="1.6" fill="var(--muted)">
    <text x="150" y="26" text-anchor="middle">OUTSIDE — AGAINST THE BODY</text>
    <text x="520" y="26" text-anchor="middle">INSIDE THE BAG</text>
  </g>

  <!-- back panel, and the anchor strip behind it -->
  <rect x="400" y="40" width="12" height="220" fill="var(--shell)"/>
  <rect x="412" y="70" width="12" height="160" fill="var(--shell)" opacity=".6"/>
  <path d="M424,70 H470 M424,230 H470" stroke="var(--rule)" stroke-width="1" stroke-dasharray="4 4"/>
  <text x="476" y="74" font-family="var(--f-data)" font-size="12" fill="var(--muted)">anchor strip —</text>
  <text x="476" y="90" font-family="var(--f-data)" font-size="12" fill="var(--muted)">ends caught in</text>
  <text x="476" y="106" font-family="var(--f-data)" font-size="12" fill="var(--muted)">the side binding</text>
  <text x="476" y="234" font-family="var(--f-data)" font-size="12" fill="var(--muted)">back panel</text>

  <!-- the belt, seen end-on: its width runs up the page -->
  <rect x="386" y="105" width="14" height="90" fill="var(--web)"/>
  <text x="330" y="155" font-family="var(--f-data)" font-size="13" fill="var(--ink)">belt, end on</text>
  <path d="M382,150 H340" stroke="var(--ink)" stroke-width="1"/>

  <!-- the keeper: flat on the panel at both ends, arching over the belt -->
  <path d="M400,52 L400,88 C400,96 392,100 384,102 L378,104 L378,196 L384,198
           C392,200 400,204 400,212 L400,248"
        fill="none" stroke="var(--ink)" stroke-width="4"/>
  <path d="M400,52 L400,64 M400,236 L400,248" stroke="var(--cut)" stroke-width="4"/>

  <!-- box-X tacks through keeper + panel + anchor -->
  <g stroke="var(--stitch)" stroke-width="2" fill="none">
    <rect x="396" y="60" width="22" height="26"/><path d="M396,60 L418,86 M418,60 L396,86"/>
    <rect x="396" y="214" width="22" height="26"/><path d="M396,214 L418,240 M418,214 L396,240"/>
  </g>
  <text x="150" y="76" font-family="var(--f-data)" font-size="13" fill="var(--stitch)">box-X through keeper + panel + anchor</text>
  <path d="M300,72 H392" stroke="var(--stitch)" stroke-width="1"/>
  <text x="150" y="244" font-family="var(--f-data)" font-size="13" fill="var(--cut)">¾″ folded under — no raw end</text>
  <path d="M300,240 H392" stroke="var(--cut)" stroke-width="1"/>

  <!-- the tunnel dimension -->
  <g stroke="var(--muted)" stroke-width="1">
    <path d="M362,104 H372 M362,196 H372"/>
    <path d="M367,104 V196"/>
  </g>
  <text x="356" y="154" text-anchor="end" font-family="var(--f-data)" font-size="12" fill="var(--muted)">tunnel</text>
</svg>
```

### Assembling one

1. **Hot-knife the strip to length**, both long edges and both ends. Cordura and
   nylon seal; nothing frays, so no long edge needs turning.
2. **Fold ⅜″ under at each end.** This is the only fold. It hides the cut ends,
   and it is the layer the box-X bites into — a tack through a single thickness
   at the very end of a strip pulls straight off it.
3. **Lay the anchor strip on the panel's interior**, behind where the keepers
   will go, with its ends flush to the panel's side edges so the binding catches
   them. Without it, a loaded bag hangs off two stitch fields in one layer of
   shell fabric.
4. **Fold the keeper round the actual belt** — not round a ruler, and not to a
   number. Wrap it over a scrap of the belt itself, pinch it to the panel, and
   mark where the tacks fall. That is the only way to get a tunnel the belt
   slides through but does not rattle in.
5. **Box-X each end**, through keeper + panel + anchor at once. Hand-wheel it.
6. **Trim the surplus** after the first tack, before the second.

> ### Cut long and fit it to the belt
>
> The cut length is a rule of thumb — **2 × belt width + 1½″** — and it is
> deliberately generous. What it has to cover is the fold at each end, the tack
> footprint at each end, the belt itself, and the two thicknesses the strip
> climbs over the belt. The surplus is trim allowance, and it is there because a
> keeper an eighth of an inch too tight cannot be threaded and one an eighth too
> loose lets the bag bounce on the belt.

### Where they go

| | |
|---|---|
| **High on the panel** | The belt should sit in the top fifth of the bag, so the bag hangs below it. Worn higher on the hips it bounces less |
| **Wide apart** | The span between keepers is what resists the bag rocking outward when it is loaded. Wider is better until it runs out of panel |
| **Clear of anything else** | A tack landing on a zip tape, a binding flange or another seam is a stack nobody planned |

---

## Threading a tri-glide

A tri-glide is three bars in a frame. It holds by friction and by the webbing
pinching itself, which means **there is a wrong way that looks right and slips
under load.**

```svg
<svg viewBox="0 0 620 250" role="img" aria-label="Tri-glide threading. On the left, webbing passed straight through, which slips. On the right, webbing over the top bar, under the middle bar and back over the top bar, which locks.">
  <g font-family="var(--f-label)" font-size="12" letter-spacing="1.6">
    <text x="150" y="26" text-anchor="middle" fill="var(--cut)">SLIPS</text>
    <text x="470" y="26" text-anchor="middle" fill="var(--stitch)">HOLDS</text>
  </g>

  <!-- LEFT: straight through -->
  <path d="M40,120 H260" stroke="var(--web)" stroke-width="30" fill="none"/>
  <g stroke="var(--metal, #8E9691)" stroke-width="7" fill="none">
    <rect x="110" y="72" width="90" height="96" rx="6"/>
    <path d="M155,72 V168"/>
  </g>
  <path d="M62,175 H238" stroke="var(--cut)" stroke-width="2"/>
  <path d="M238,175 l-10,-5 v10 z" fill="var(--cut)"/>
  <text x="150" y="200" text-anchor="middle" font-family="var(--f-data)"
        font-size="13" fill="var(--cut)">nothing pinches — it pays out</text>

  <!-- RIGHT: over, under, back over -->
  <g stroke="var(--metal, #8E9691)" stroke-width="7" fill="none">
    <rect x="430" y="72" width="90" height="96" rx="6"/>
    <path d="M475,72 V168"/>
  </g>
  <path d="M360,100 H452 C468,100 468,140 452,140 H430
           C414,140 414,100 430,100 H560"
        stroke="var(--web)" stroke-width="26" fill="none" stroke-linejoin="round"/>
  <g stroke="var(--metal, #8E9691)" stroke-width="7" fill="none" opacity=".9">
    <path d="M475,72 V168"/>
  </g>
  <path d="M560,180 H480" stroke="var(--stitch)" stroke-width="2"/>
  <path d="M480,180 l10,-5 v10 z" fill="var(--stitch)"/>
  <text x="470" y="212" text-anchor="middle" font-family="var(--f-data)"
        font-size="13" fill="var(--stitch)">the tail is trapped under the load strand</text>
</svg>
```

**Over the top bar, under the centre bar, back over the top bar.** Pull on the
load side and the webbing clamps itself against the centre bar. Threaded
straight through, there is nothing to clamp and it pays out the first time
somebody leans on it.

The free tail wants **4–6″** beyond the tri-glide: enough to grip and pull, and
enough that it cannot back out. Hot-knife the end, and a small elastic keeper
stops it flapping.

## Hot-knifing

| | |
|---|---|
| **Heat** | Well down. Nylon melts around 220 °C and these tools reach 500 °C — too hot and the seal beads up and will not thread through hardware |
| **Pass** | One steady pass. A stop-and-restart leaves a notch and a blob |
| **Duty cycle** | Non-air-cooled units are rated for ~15-second intervals. A long strip is 30–45 seconds of unbroken cutting |
| **Surface** | Glass or scrap plywood, never a self-healing mat, and a **metal** straightedge — a plastic ruler melts |
| **Air** | Ventilate. And never hot-knife PVC: it releases hydrogen chloride, which is corrosive and genuinely harmful rather than merely unpleasant |

---

## When it goes wrong

| Symptom | Cause | Fix |
|---|---|---|
| Belt will not thread through the keeper | Keeper folded to a number rather than round the belt | Unpick one tack, refit round the belt, re-tack. Trim afterwards, never before |
| Bag bounces vertically on the belt | Tunnel too loose | Same fix, the other way. Aim to just slide, not to rattle |
| A tack pulls out of the shell | No anchor behind it, or the tack sat on a single fold | Anchor strip with its ends in the binding; fold ⅜″ under so the tack bites two layers |
| Box-X puckers, or the first stitches bunch | Foot tipped onto the stack | Height-compensation scrap under the back of the foot, and hand-wheel |
| Tri-glide creeps under load | Threaded straight through | Re-thread over, under, back over |
| Loops of thread under a webbing pass | Top tension too low for the thickness | Raise the upper tension for webbing; drop it again for binding |
| Webbing end will not go through a buckle | Hot knife too hot — the end beaded | Trim it back and re-cut cooler; pinch the hot end flat with pliers while it sets |
| Bag rocks outward when loaded | Keepers too close together | Widen the span. It is the base, not the tack, that resists rotation |

## Further reading

- [Sewing a box-X / box stitch](https://www.stitchbackgear.com/blogs/news/how-to-sew-a-box-x-stitch)
- [Threading a tri-glide slider](https://www.strapworks.com/pages/how-to-thread-a-tri-glide)
- [Working with webbing — hot knives and finishing](https://ripstopbytheroll.com/blogs/news/how-to-cut-and-finish-webbing)

---

*Used by:* `patterns/constructions/box-bound.json` — the keeper, D-ring tab,
chassis and handle steps all point here.
