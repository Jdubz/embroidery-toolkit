# Zippers in bags

A reusable technique note. Patterns reference this rather than re-explaining
it; **nothing here depends on any particular bag's dimensions** — and that is
the point, because the lengths are the part that goes stale.

> **For the actual numbers, read the *Zipper schedule* table on the pattern
> itself.** It is generated from the spec, so it lists every zipper on that bag
> with its opening, the chain to cut, the stock length to buy, how many sliders,
> and where each stop goes. A hand-written length in a technique note would be
> wrong the first time the bag was resized.

A bag zipper is not a garment zipper. It is almost always **continuous coil
chain cut to length**, with the stops made by you rather than bought, and it is
almost always set by **lapping fabric onto the tape** rather than by cutting an
opening into a panel.

---

## What #5 coil means

**#5** is the chain width in millimetres, roughly, across the closed coil.
**Coil** is a monofilament spiral sewn to the tape, as against moulded plastic
teeth or metal.

| | |
|---|---|
| **Why coil** | It is self-healing: force the slider through a misalignment and the spiral springs back, where a moulded tooth shears off. It also curves round a corner, which moulded chain will not do |
| **Why not metal** | Metal teeth snag, and they are the one chain that cannot be cut and re-stopped with a needle |
| **Sizes** | #3 for pockets and light work, **#5 for bag openings**, #8 and #10 for luggage. Bigger is not stronger in any way that matters here — it is heavier, stiffer and turns a worse corner |
| **Tape** | About ½″ each side of the coil, and it is what you sew through. Never sew through the coil itself |
| **Buy it** | By the yard as chain, with sliders separate. That is cheaper, and it is the only way to make a two-way opening or a length nobody sells |

---

## Reverse coil — which is what every zipper in this family is

**Standard coil** puts the spiral on the face you look at. **Reverse coil** is
the same chain, the same size, made up the other way: the coil is on the
*back*, and the outside shows flat tape with the slider riding on it.

It is not a premium part and it costs nothing extra. It is a different make-up
of the identical chain, and on a coated shell it is the right one.

| | Standard coil | **Reverse coil** |
|---|---|---|
| Outside face shows | the spiral | **flat tape** |
| Water | sits in the coil and wicks along it | **runs off the tape**; the interlock is under cover |
| Grit | packs into an upward-facing spiral | falls out of a downward-facing one |
| Look | reads as hardware | **reads as a seam** — which is the point on a hidden pocket |
| Slider | rides on the coil | rides on the tape, so it sits flatter |

**This is not a waterproof zipper.** A reverse coil is *water-shedding* — the
interlock faces inward and the tape sheds — but it has no polyurethane film and
it will not hold out driven rain. If it needs to be waterproof, that is a
different, stiffer, far more expensive chain, and a storm flap over an ordinary
reverse coil beats it for most bags.

### The two ways it changes what you do

**1. The pull ends up on the wrong side if you build it the obvious way.** The
face that shows flat tape is the OUTSIDE, so the slider body and the pull have
to be on that same side. Lay the chain coil-DOWN on the bench and lap the shell
onto the tape from above; if you have laid it coil-up out of habit, the finished
bag has its pull on the inside and there is no fixing it without unpicking both
laps.

> **Check before the first row:** close the zip, put it on the bench the way the
> bag will hang, and look at it. If you can see the spiral, turn it over.

**2. A reverse slider is not the same part as a standard one.** They are not
interchangeable — a standard slider on reverse chain rides the wrong face, sits
proud, and drags. Order sliders as reverse to match the chain, and check them
against the chain before you build anything.

### Where it earns its keep here

On the hidden back pocket especially. Half of hiding a zip is the placket over
it; the other half is that a reverse coil shows a flat tape line rather than a
row of spiral, so the closed opening reads as **a seam rather than a zip**. The
two together do more than either.

---

## The lapped panel — no opening is cut

The technique this construction uses everywhere. Two pieces of shell lap onto
the tape from each side and are topstitched down. The zipper *becomes* a strip
of the panel rather than being let into one.

```svg
<svg id="lapped-panel" viewBox="0 0 640 260" role="img" aria-label="Section through a lapped zipper panel: two shell strips lapping onto the zipper tape from each side, the coil standing between them, and two rows of topstitching holding each lap.">
  <g font-family="var(--f-label)" font-size="11" letter-spacing="1.6" fill="var(--muted)">
    <text x="20" y="24">SECTION — CUT ACROSS THE PANEL</text>
  </g>

  <!-- the tape, running under everything -->
  <rect x="215" y="150" width="210" height="12" fill="var(--muted)" opacity=".45"/>
  <text x="320" y="188" text-anchor="middle" font-family="var(--f-data)"
        font-size="12" fill="var(--muted)">zipper tape</text>

  <!-- the coil, standing proud in the middle -->
  <rect x="305" y="126" width="30" height="36" fill="var(--coil)"/>
  <g stroke="var(--shell)" stroke-width="1.6" opacity=".55">
    <path d="M305,134 h30 M305,143 h30 M305,152 h30"/>
  </g>
  <text x="320" y="112" text-anchor="middle" font-family="var(--f-data)"
        font-size="12" fill="var(--ink)">coil</text>

  <!-- the two shell strips, lapping onto the tape -->
  <path d="M30,150 H305 V126 H30 Z" fill="var(--shell)"/>
  <path d="M610,150 H335 V126 H610 Z" fill="var(--shell)"/>

  <!-- the lap: where strip lies over tape -->
  <g stroke="var(--cut)" stroke-width="1.5">
    <path d="M215,116 V96 M305,116 V96 M215,106 H305"/>
    <path d="M335,116 V96 M425,116 V96 M335,106 H425"/>
  </g>
  <text x="260" y="90" text-anchor="middle" font-family="var(--f-data)"
        font-size="12" fill="var(--cut)">lap</text>
  <text x="380" y="90" text-anchor="middle" font-family="var(--f-data)"
        font-size="12" fill="var(--cut)">lap</text>

  <!-- two rows of topstitching through strip + tape, seen end on -->
  <g fill="var(--stitch)">
    <circle cx="238" cy="138" r="4.5"/><circle cx="272" cy="138" r="4.5"/>
    <circle cx="368" cy="138" r="4.5"/><circle cx="402" cy="138" r="4.5"/>
  </g>
  <text x="150" y="214" font-family="var(--f-data)" font-size="12" fill="var(--stitch)">two rows through strip + tape, each side</text>
  <path d="M300,208 L272,146" stroke="var(--stitch)" stroke-width="1"/>

  <!-- what the finished width adds up to -->
  <g stroke="var(--muted)" stroke-width="1">
    <path d="M30,236 H305 M335,236 H610"/>
    <path d="M30,230 v12 M305,230 v12 M335,230 v12 M610,230 v12"/>
    <path d="M305,236 H335" stroke="var(--coil)" stroke-width="3"/>
  </g>
  <text x="320" y="256" text-anchor="middle" font-family="var(--f-data)"
        font-size="12" fill="var(--ink)">(strip − lap) + coil + (strip − lap) = the panel it replaces</text>
</svg>
```

**Nothing is cut open.** That matters more than it sounds: a welt opening in a
loaded panel is the hardest operation in bag making, it puts a slit across the
grain where the load runs, and it is the one step that cannot be practised on
scrap first — because the practice piece *is* the panel.

### Doing it

1. **Basting tape, not clips.** A lap that shifts a sixteenth shows for the life
   of the bag, and the tape holds it exactly while you sew.
2. **Zipper foot, Microtex 90/14.** Not optional: a standard foot cannot get
   close enough to the coil, and a jeans needle is too blunt for tape.
3. **Two rows on each lap**, 3.0 mm. The first row is structural, the second is
   what stops the lap curling away from the tape in wear.
4. **Sew both strips in the same direction.** Sewing the second one back the
   other way twists the panel — the tape feeds slightly differently under the
   foot each way, and the difference shows up as a bow across a long panel.
5. **Check the sum before you go near the bag.** The finished panel has to equal
   the piece it replaces; the arithmetic is above, and getting it wrong is only
   discoverable when the ring no longer fits.

### Sew the practice one first

This note already says the hard part out loud — *the practice piece is the
panel* — and then never tells you to make one. Make one.

**Two strips of scrap and a foot of chain, built exactly as the real panel is
built.** It costs ten minutes and it settles the four things that are only
learnable by doing:

1. **Where the zipper foot actually rides** relative to the coil on YOUR
   machine, which no instruction can tell you.
2. **Whether the tension is right through tape.** Tape is denser than the shell
   and the top thread often needs easing off; you want to find that out on
   scrap.
3. **Which way up the reverse coil goes** — build the practice piece, then hold
   it the way the bag hangs and look for the pull.
4. **The lap arithmetic**, measured on a finished sample rather than trusted.
   Measure the practice panel across: it must equal the two strips less two
   laps, plus the coil.

Keep it. It is also the piece you test a new stop's bar-tack on before you
trust one on the bag.

---

## Shortening, and making a new stop

You will almost always buy longer than you need. **A coil zipper cut without a
new stop lets the slider run straight off the end, and there is no putting it
back on in a hurry.**

```svg
<svg id="shorten" viewBox="0 0 640 210" role="img" aria-label="Shortening a zipper: a dense zigzag bar-tack worked across the coil at the new length, the trim line one inch beyond it, and a fabric cap folded over the cut end.">
  <rect x="20" y="70" width="600" height="54" fill="var(--muted)" opacity=".35"/>
  <rect x="20" y="86" width="600" height="22" fill="var(--coil)"/>
  <g stroke="var(--shell)" stroke-width="1.6" opacity=".5">
    <path d="M40,86 v22 M60,86 v22 M80,86 v22 M100,86 v22 M120,86 v22 M140,86 v22
             M160,86 v22 M180,86 v22 M200,86 v22 M220,86 v22 M240,86 v22 M260,86 v22
             M280,86 v22 M300,86 v22 M320,86 v22 M340,86 v22 M360,86 v22 M380,86 v22
             M400,86 v22 M420,86 v22 M440,86 v22 M460,86 v22 M480,86 v22 M500,86 v22"/>
  </g>

  <!-- the new stop: dense zigzag across the coil -->
  <path d="M368,70 L382,124 L368,124 L382,70 L368,70 L382,124"
        stroke="var(--stitch)" stroke-width="3" fill="none"/>
  <rect x="364" y="68" width="22" height="58" fill="var(--stitch)" opacity=".35"/>
  <text x="375" y="52" text-anchor="middle" font-family="var(--f-data)"
        font-size="13" fill="var(--stitch)">new stop</text>
  <text x="375" y="36" text-anchor="middle" font-family="var(--f-data)"
        font-size="11" fill="var(--muted)">dense zigzag, 5–6 passes</text>

  <!-- trim line -->
  <path d="M470,58 V136" stroke="var(--cut)" stroke-width="2" stroke-dasharray="8 5"/>
  <text x="478" y="52" font-family="var(--f-data)" font-size="13" fill="var(--cut)">trim — 1″ beyond, never flush</text>

  <!-- the cap -->
  <path d="M500,64 H560 V130 H500" fill="var(--shell)" opacity=".8"/>
  <text x="530" y="152" text-anchor="middle" font-family="var(--f-data)"
        font-size="12" fill="var(--muted)">cap the cut end</text>

  <!-- slider, parked -->
  <path d="M120,76 h40 v42 h-40 z" fill="none" stroke="var(--metal, #8E9691)" stroke-width="4"/>
  <path d="M140,118 v22" stroke="var(--metal, #8E9691)" stroke-width="4"/>
  <text x="140" y="176" text-anchor="middle" font-family="var(--f-data)"
        font-size="12" fill="var(--muted)">slider</text>

  <text x="20" y="196" font-family="var(--f-data)" font-size="12" fill="var(--ink)">Open it halfway first. Bar-tack with the slider well clear, or you will sew it in.</text>
</svg>
```

| | |
|---|---|
| **Stitch** | Dense zigzag, **~3 mm wide, 0.4 mm long, 5–6 passes** back and forth across the coil. This machine has no programmed bar-tack, so it is worked by hand |
| **Where** | At the new length, with the slider **open and well clear** — bar-tack over the slider and you have sewn it in permanently |
| **Trim** | **1″ beyond the tack**, not flush. Flush leaves the tack at the raw edge with nothing behind it |
| **Cap** | A scrap folded over the cut end and topstitched. It stops the coil unravelling and stops the cut tape sawing at whatever it sits against |

---

## When the ends get bound over

The awkward case, and the one worth drawing. If a zipper runs the **full cut
width of a panel**, both of its ends finish inside the seam allowance and get
wrapped in binding. **No metal stop can live there** — it is a lump under the
binding at exactly the point the binding is already thickest.

```svg
<svg id="bound-end" viewBox="0 0 640 240" role="img" aria-label="A zipper whose end runs into a bound seam. The panel cut edge on the right, the stitch line inboard of it, a bar-tacked stop just inside the stitch line, and the binding wrapping the whole edge.">
  <g font-family="var(--f-label)" font-size="11" letter-spacing="1.6" fill="var(--muted)">
    <text x="20" y="24">PLAN — LOOKING AT THE PANEL</text>
  </g>

  <!-- panel -->
  <rect x="20" y="44" width="500" height="150" fill="var(--shell)" opacity=".9"/>
  <!-- binding wrapping the right edge -->
  <rect x="470" y="44" width="50" height="150" fill="var(--binding)"/>
  <text x="495" y="214" text-anchor="middle" font-family="var(--f-data)"
        font-size="12" fill="var(--muted)">binding</text>

  <!-- the stitch line, inboard of the cut edge -->
  <path d="M452,36 V202" stroke="var(--stitch)" stroke-width="2" stroke-dasharray="7 4"/>
  <text x="446" y="32" text-anchor="end" font-family="var(--f-data)"
        font-size="12" fill="var(--stitch)">stitch line</text>
  <text x="524" y="32" font-family="var(--f-data)" font-size="12" fill="var(--cut)">cut edge</text>
  <path d="M520,36 V202" stroke="var(--cut)" stroke-width="2"/>

  <!-- zipper running to the cut edge -->
  <rect x="20" y="104" width="500" height="34" fill="var(--muted)" opacity=".4"/>
  <rect x="20" y="114" width="500" height="14" fill="var(--coil)"/>

  <!-- new stop, just inside the stitch line -->
  <rect x="426" y="100" width="18" height="42" fill="var(--stitch)" opacity=".5"/>
  <path d="M428,100 L442,142 M442,100 L428,142" stroke="var(--stitch)" stroke-width="2.5"/>
  <path d="M435,96 V64" stroke="var(--stitch)" stroke-width="1"/>
  <text x="435" y="58" text-anchor="middle" font-family="var(--f-data)"
        font-size="12" fill="var(--stitch)">bar-tack INSIDE the stitch line</text>

  <!-- slider parked -->
  <path d="M60,102 h44 v38 H60 z" fill="none" stroke="var(--metal, #8E9691)" stroke-width="4"/>
  <path d="M82,140 v24" stroke="var(--metal, #8E9691)" stroke-width="4"/>
  <text x="82" y="186" font-family="var(--f-data)" font-size="12" fill="var(--muted)">park it at the reachable end</text>

  <path d="M456,160 H516" stroke="var(--cut)" stroke-width="1"/>
  <path d="M456,160 l10,-4 v8 z" fill="var(--cut)"/>
  <path d="M516,160 l-10,-4 v8 z" fill="var(--cut)"/>
  <text x="486" y="180" text-anchor="middle" font-family="var(--f-data)"
        font-size="11" fill="var(--cut)">seam allowance —</text>
  <text x="486" y="194" text-anchor="middle" font-family="var(--f-data)"
        font-size="11" fill="var(--cut)">tape only, no stop</text>
</svg>
```

1. **Bar-tack a new stop just inside the stitch line**, both ends, before
   trimming anything. Inside, so the binding never has to wrap it.
2. **Trim the tape to the panel's cut edge**, flush this time — the tape is
   thin, and it is about to be bound.
3. **Park the slider at the end you can reach**, and do it before the binding
   goes on. Once both ends are bound there is no way to add a slider, and no way
   to retrieve one that has run off.
4. The stop is **the only thing between the slider and open air.** Work it
   properly, and test it by hauling the slider into it hard before you commit.

---

## Two sliders, and which way they face

Two sliders on one run means the bag opens from **either** end. On anything
worn on the body that is worth more than it costs, because a single slider is
handed — a belt bag's zip should open away from the centre of the body toward
the dominant hand, and one slider gets that wrong for half of people.

```svg
<svg id="two-sliders" viewBox="0 0 640 240" role="img" aria-label="Two sliders on one zipper. Correct: noses point outward and the tails meet, so the run is closed with the sliders together and opens from either side. Wrong: noses point inward, which leaves both ends permanently open.">
  <g font-family="var(--f-label)" font-size="11" letter-spacing="1.6">
    <text x="20" y="22" fill="var(--stitch)">TAILS TOGETHER, NOSES OUTWARD — CLOSED</text>
  </g>
  <rect x="20" y="46" width="600" height="34" fill="var(--muted)" opacity=".35"/>
  <rect x="20" y="56" width="600" height="14" fill="var(--coil)"/>
  <g fill="none" stroke="var(--metal, #8E9691)" stroke-width="4">
    <path d="M282,44 h36 v38 h-36 z"/><path d="M322,44 h36 v38 h-36 z"/>
  </g>
  <path d="M296,82 v20 M344,82 v20" stroke="var(--metal, #8E9691)" stroke-width="4"/>
  <path d="M276,63 l-16,0 M260,63 l8,-6 v12 z" fill="var(--stitch)" stroke="var(--stitch)" stroke-width="2"/>
  <path d="M364,63 l16,0 M380,63 l-8,-6 v12 z" fill="var(--stitch)" stroke="var(--stitch)" stroke-width="2"/>
  <text x="320" y="122" text-anchor="middle" font-family="var(--f-data)"
        font-size="12" fill="var(--stitch)">each slider zips behind itself, so everything outboard of the pair is closed</text>

  <g font-family="var(--f-label)" font-size="11" letter-spacing="1.6">
    <text x="20" y="162" fill="var(--cut)">NOSES INWARD — NEVER CLOSES</text>
  </g>
  <rect x="20" y="182" width="600" height="34" fill="var(--muted)" opacity=".35"/>
  <rect x="20" y="192" width="140" height="14" fill="var(--coil)"/>
  <rect x="480" y="192" width="140" height="14" fill="var(--coil)"/>
  <g fill="none" stroke="var(--cut)" stroke-width="4">
    <path d="M282,180 h36 v38 h-36 z"/><path d="M322,180 h36 v38 h-36 z"/>
  </g>
  <path d="M170,186 h300 M170,212 h300" stroke="var(--cut)" stroke-width="3"/>
  <text x="320" y="236" text-anchor="middle" font-family="var(--f-data)"
        font-size="12" fill="var(--cut)">both ends stay open however far you push them</text>
</svg>
```

A slider zips **behind** itself — it joins the chain as it travels nose-first.
So two sliders close a run only when their **noses point outward and their tails
meet**: each one has zipped everything it has travelled over. Push them together
anywhere along the run and the whole thing is shut; slide either one away and
that side opens.

**Thread one slider on from each end**, before either end is stopped. On a
lapped panel that means putting both sliders on the chain *first*, then building
the panel round it — there is no adding one later.

### Getting a slider onto coil chain

It goes on nose-first, from the cut end, with both tapes fed into the wide
mouth at once. Two things decide whether it works:

- **The right way up.** A coil slider is asymmetric. The pull sits on the face
  that will be outward; put it on inverted and the zip works but the pull lies
  against the fabric and cannot be gripped.
- **Feed both tapes together.** Pinch the two tape ends flat and level, push
  them in as one, and ease the slider on with pliers on its body — never on the
  pull, which will simply snap off.

If the coil has splayed at the cut end, trim ¼″ back to sound chain and start
again. Coaxing a slider onto a damaged end is how you break the slider.

---

## The order, and the two steps that cannot be undone

Almost everything in bag making can be unpicked. Two things here cannot, and
both are decisions made *early* that only become visible *late*.

| | Do it | Because by then |
|---|---|---|
| **1** | Put **both sliders on the chain** | Once either end is stopped, and certainly once the panel is built round it, there is no adding one. A two-slider opening cannot be retro-fitted |
| **2** | Check the **coil faces the right way** | Both laps are sewn; unpicking them means re-cutting the strips, because the needle holes stay |
| **3** | Lap and topstitch both strips | — |
| **4** | Bar-tack the new stops, **slider well clear** | Tack over the slider and it is sewn in permanently |
| **5** | Trim 1″ beyond, cap the ends | — |
| **6** | **Open the zip** before the last seam | A bound seam cannot be unpicked, and with the zip closed the bag will not open afterwards |

Step 6 is the one that gets people, because it is the only step whose omission
produces a finished, correct-looking, permanently-shut bag.

---

## Machine setup

| | |
|---|---|
| **Foot** | Zipper foot, both rows. A standard foot cannot get near enough to the coil |
| **Needle** | **Microtex / sharp 90/14** for tape. Jeans needles are too blunt and push the tape rather than piercing it |
| **Stitch** | **3.0 mm** for the lap rows. Short stitches perforate the tape into a tear line |
| **Bar-tack** | Zigzag, ~3 mm wide, **0.4 mm** long |
| **Holding** | Double-sided basting tape. Pins leave holes in coated tape and clips cannot hold a lap flat |
| **Direction** | Both laps sewn the same way, or the panel bows |

---

## When it goes wrong

| Symptom | Cause | Fix |
|---|---|---|
| Slider ran off the end | No stop, or the stop was trimmed flush and pulled through | Re-thread from the other end if it is still open; otherwise the chain is scrap. Bar-tack **before** trimming, always |
| Slider will not go back on | Splayed coil at the cut end, or on upside down | Trim ¼″ to sound chain; check the pull faces outward; pliers on the body, never the pull |
| Zip opens behind the slider | A missing or damaged coil, or the slider has spread | Replace the slider first — it is almost always the slider, not the chain |
| Panel bows along its length | The two laps were sewn in opposite directions | Unpick one and re-sew it the same way as the other |
| Lap curls away from the tape | Only one row of topstitching | Second row, ⅛″ from the first |
| Lump under the binding at a corner | A metal stop left inside the seam allowance | Bar-tack a new stop inboard of the stitch line and remove the metal one |
| Sewn the slider in while bar-tacking | Slider was not moved clear | Unpick the tack, move the slider, re-tack. There is no other way out |
| Pull is on the inside of the finished bag | Reverse chain laid coil-up | Nothing but unpicking both laps, and the holes stay. Check it on the practice piece |
| Slider sits proud and drags | Standard slider on reverse chain | They are different parts. Replace the slider |
| Needle strike on the coil | Sewing too close, or the foot rode over the chain | The stitch line belongs on the **tape**. Slow down and use the zipper foot's edge as the guide |

## Further reading

- [Zippers: an overview — coil, moulded, sizes and tape](https://ripstopbytheroll.zendesk.com/hc/en-us/articles/360031232032-Zippers-An-Overview)
- [Making a two-way bag zipper from continuous chain](https://zippershipper.com/blogs/blog/how-to-make-a-two-way-bag-zipper-with-continuous-zipper-chain-step-by)
- [Zipper direction in bag making](https://sallietomato.com/blogs/blog/zipper-direction-in-bag-making-how-to-position-zippers-for-comfortable-use)
- [Choosing a zipper for a custom bag](https://www.gentlepk.com/how-to-choose-the-right-zipper-for-your-custom-bag/)

---

*Used by:* `patterns/constructions/box-bound.json` — the zipper panel, the
shortening step, any back-panel pocket, and the final closing seam.
*Numbers by:* `BoxBag.zipper_schedule()` in `tools/bag_pattern.py`.
