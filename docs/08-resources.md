# Resources

Links verified 2026-08-07.

## Official Brother

| Resource | Link |
|---|---|
| SE700 product page | <https://www.brother-usa.com/p/sewing-embroidery/SE700> |
| SE700 support hub | <https://support.brother.com/g/b/producttop.aspx?c=us&lang=en&prod=hf_se700eus> |
| Downloads & firmware | <https://support.brother.com/g/b/downloadtop.aspx?c=us&lang=en&prod=hf_se700eus> |
| Manuals | <https://support.brother.com/g/b/manualtop.aspx?c=us&lang=en&prod=hf_se700eus> |
| Design Database Transfer | <https://support.brother.com/g/s/hf/pcapp_info/ddt/en/index.html?prod=WLAN&media=i_txt> |
| USB media compatibility list | <https://s.brother/cpjap/> |
| iBroidery (design store) | <https://www.ibroidery.com> |

### Bundled locally

Already downloaded into [`../reference/manuals/`](../reference/manuals/):

- `SE700-Operation-Manual-EN.pdf` — 104 pages, the authoritative reference
- `SE700-Operation-Manual-EN.txt` — extracted text, greppable
- `SE700-Quick-Reference-Guide.pdf`
- `SE700-Embroidery-Design-Guide.pdf` — the 135 built-in patterns
- `SE700-Software-Update-via-Wireless-v1.60.pdf`
- `SE700-Reset-Before-Lending-or-Disposing.pdf`

And in [`../reference/charts/`](../reference/charts/):

- `Brother-Embroidery-Thread-Color-List-Artspira.pdf` — Brother's thread codes
- `brother-pec-thread-palette.csv` — the 64-colour PEC palette with RGB

Useful manual page numbers: specifications p.96 · software update p.97 ·
error messages p.93 · troubleshooting symptoms p.89 · jammed fabric p.87 ·
finding your SSID p.95 · fabric/thread/needle table p.27.

```powershell
# grep the manual text
Select-String -Path reference\manuals\SE700-Operation-Manual-EN.txt -Pattern "tension"
```

## Software

| Tool | Link | Cost |
|---|---|---|
| Ink/Stitch | <https://inkstitch.org> · [GitHub](https://github.com/inkstitch/inkstitch) | Free |
| Inkscape | <https://inkscape.org> | Free |
| pyembroidery | <https://github.com/EmbroidePy/pyembroidery> | Free |
| Wilcom TrueSizer | <https://www.wilcom.com/truesizer> | Free |
| Embrilliance | <https://www.embrilliance.com> | Express free · Essentials ~$139 |
| PE-DESIGN 11 | <https://www.brother-usa.com/products/pedesign11> | ~$1,000–2,000 |

## Format documentation

- **PES/PEC format reverse engineering** — <https://github.com/frno7/libpes/wiki/PES-format>
  The best public description of the container: `#PES0001`…`#PES0060` headers,
  the embedded PEC block, 1/10 mm signed-16 coordinates, palette indexing.
- **pyembroidery format notes** — <https://github.com/EmbroidePy/pyembroidery#readme>

## Learning

- [Ink/Stitch tutorials](https://inkstitch.org/tutorials/) — start here for digitizing
- [Ink/Stitch video playlist](https://www.youtube.com/playlist?list=PLtQ8IvTMaEGI3NeU2MppOkukHviNKmrJl)
- [Asmbly wiki: Designing for the Brother Embroidery Machine](https://wiki.asmbly.org/index.php/Designing_for_the_Brother_Embroidery_Machine)
  — concise, practical, written for exactly this class of machine

## Designs

**Free, reputable:**
- Brother's own free monthly designs (via the support site and iBroidery)
- [Ann the Gran](https://www.annthegran.com) — weekly free designs, filterable by hoop size
- [Designs by JuJu](https://www.designsbyjuju.com) — at least one free design monthly
- [Design Bundles free section](https://designbundles.net/free-design-resources/free-embroidery-designs)

**Filter every download by:** PES format, ≤ 100 × 100 mm, ≤ 100,000 stitches. Then
run it through `.\stitch.ps1 validate` before staging it. Free-design sites are
inconsistent about stated sizes.

**On licensing:** most commercial designs are licensed for *personal use only*.
Selling finished items — never mind redistributing the file — usually requires a
separate commercial licence. Character and franchise designs circulating free are
overwhelmingly unlicensed; Brother's iBroidery is the only legitimate source for
licensed Disney designs, and even there most are paid. Check the licence before
selling anything.

## Community

- [r/Embroidery](https://reddit.com/r/Embroidery) and [r/MachineEmbroidery](https://reddit.com/r/MachineEmbroidery)
- [PatternReview forums](https://sewing.patternreview.com) — long-running, good archive
- [Ink/Stitch GitHub Discussions](https://github.com/inkstitch/inkstitch/discussions) — responsive maintainers

## Parts

Hoops, bobbins and needles for the SE700 are the common Brother 4×4 SE/PE parts,
also fitting SE400/SE425/SE600/SE625/SE630/PE535/PE550D/LB5000 and Baby Lock
Sofia 2 / Verve. Any of those listings will fit.

- Hoops: SA431 (1"×2.5") · **SA432 (4"×4", included)** · SA434 (4"×6.75" frame)
- Bobbins: SA156, Class 15
- Needles: 75/11 embroidery, ball point for knits
- Magnetic hoops (MaggieFrame, MagneticHoop and others) fit the same bracket
