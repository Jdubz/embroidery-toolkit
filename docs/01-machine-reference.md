# Machine Reference — Brother SE700

Every number here is from the **SE700 Operation Manual, "Specifications" (p.96)**,
a copy of which is in [`reference/manuals/`](../reference/manuals/). Where a fact
comes from elsewhere it is marked.

> **A note on the model number.** Brother does not make an "SE7000". The 4"×4"
> wireless combo sewing/embroidery machine is the **SE700** (released late 2022).
> Machine-readable specs live in [`reference/machine-profile.json`](../reference/machine-profile.json);
> if your unit is actually an SE600, SE625, SE630, SE1900 or SE2100i, edit that
> one file and every tool in `tools/` re-targets itself.

## Embroidery

| | |
|---|---|
| Maximum pattern size | **100 mm × 100 mm** (4 in × 4 in) |
| Maximum stitches per pattern | **100,000** |
| Maximum embroidery speed | 400 spm |
| Maximum fabric thickness | **2 mm** (not the 6 mm sewing limit) |
| Built-in designs | 135 |
| Built-in embroidery fonts | 10 |

The field is the hard constraint. The machine will not *display* a design that
does not fit — it does not warn you, the design simply is not in the list. That
failure mode is the single most common "my file isn't showing up" complaint, and
it is what `stitch validate` exists to catch.

The usable area is slightly under the nominal 100 mm because the hoop's inner
edge intrudes; treat **96 mm × 96 mm** as your practical design ceiling and you
will never fight it.

## Sewing

| | |
|---|---|
| Sewing speed | 70–710 spm |
| Built-in stitches | 103+ |
| Buttonhole styles | 10 (one-step, auto-size) |
| Maximum fabric thickness | 6 mm (**embroidery is 2 mm** — see above) |
| Included presser feet | 8 |

## Memory

| Storage | Capacity |
|---|---|
| Embroidery patterns | 1024 KB **or** 20 patterns |
| Stitch (sewing) patterns | 128 KB **or** 15 patterns |
| Decorative stitch combinations | up to 70 |

Whichever limit you hit first wins. Twenty patterns is not many — treat machine
memory as a scratch space, not a library. The library lives in `designs/`.

## Physical

| | Machine alone | With embroidery unit |
|---|---|---|
| Dimensions (W × D × H) | 419 × 197 × 307 mm | 522 × 219 × 307 mm |
| Weight | 6.8 kg (15 lb) | 8.3 kg (18 lb) |

Allow ~52 cm of bench width plus clearance to the left, because the embroidery
carriage travels well past the machine body during a stitch-out.

## Connectivity

- **Wireless LAN**, IEEE 802.11 b/g/n, **2.4 GHz only**.
- **WPA/WPA2 Enterprise is not supported.** On a network that uses enterprise
  auth (most corporate and many university networks) the machine cannot join at
  all — use a phone hotspot or a 2.4 GHz guest SSID.
- If your router publishes one SSID for both bands ("band steering"), the
  machine may fail to associate. Split the 2.4 GHz band onto its own SSID.
- **USB-A host port** for a flash drive.

PC-side transfer requires **Design Database Transfer** (free) or **PE-DESIGN 11
or later**. Older PE-Design versions cannot push over the network.

## Software version

| | |
|---|---|
| Latest known version | **1.72** (checked 2026-08-07) |
| Minimum for wireless self-update | 1.60 |

**Check your version:** Settings key → page forward → the version is on one of
the settings screens.

**Update over wireless** (needs ≥ 1.60): an update badge appears on the wireless
LAN key when Brother publishes a new build; tap through to install.

**Update over USB** (works from any version):
1. Put **only** the update file on a FAT32 flash drive — nothing else.
2. Power the machine on **while holding the Needle Position button**.
3. Insert the drive, touch the load key, and do not power off during the update.
4. Remove the drive, power cycle.

Update files: <https://support.brother.com/g/b/downloadtop.aspx?c=us&lang=en&prod=hf_se700eus>

## Needles, bobbins, thread

| | |
|---|---|
| Embroidery needle | **75/11** home sewing machine needle |
| Needle threader works with | 75/11 through 100/16 (**not** twin needles) |
| Bobbin | **SA156**, Class 15, 11.5 mm high |
| Embroidery bobbin thread | 60 weight |
| Embroidery top thread | 40 weight (Brother polyester recommended) |

**Do not oil this machine.** The manual explicitly prohibits user lubrication —
the hole beside the spool pin is for the extra spool pin, not for oil. Cleaning
the race is the only user-serviceable lubrication-adjacent task.

## Hoops

| Part | Size | Notes |
|---|---|---|
| **SA432** | 100 × 100 mm (4" × 4") | Medium — **included** |
| SA431 | 20 × 60 mm (1" × 2.5") | Small — optional, good for names and monograms |
| SA434 | 100 × 170 mm (4" × 6.75") | Large — the frame attaches, but **the stitchable field is still 100 × 100 mm** |

SA434 does not give you a bigger design. It is useful for holding a longer piece
of fabric steady so you can reposition and stitch multiple 4×4 blocks without
re-hooping. Do not buy it expecting 4×6.75 designs to work.

The bracket is the common Brother 4×4 SE/PE mount, shared with the SE400, SE425,
SE600, SE625, SE630, PE535, PE550D, LB5000, and the Baby Lock Sofia 2 and Verve.
Third-party and magnetic hoops sold for any of those fit the SE700.

## Sources

- SE700 Operation Manual (bundled at `reference/manuals/SE700-Operation-Manual-EN.pdf`)
- [Brother SE700 product page](https://www.brother-usa.com/p/sewing-embroidery/SE700)
- [Brother SE700 support](https://support.brother.com/g/b/producttop.aspx?c=us&lang=en&prod=hf_se700eus)
