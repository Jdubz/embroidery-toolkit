# Getting Designs Onto the Machine

Three routes. **Design Database Transfer over wireless is the preferred method
here** — see section 2. USB is the fallback and the one that always works.

Before any transfer, whichever route:

```powershell
.\stitch.ps1 stage designs\out\Thing.pes
```

With no `--to` this runs the validation gate and prints the wireless checklist
without copying anything. **DDT does not check that a design fits the hoop** —
its own manual says to check the size yourself. This is that check.

---

## ⚠ The wireless trap: a transfer does not replace a saved design

The single most likely cause of "I regenerated the file but the machine stitched
the old one". It has bitten this project already.

A wireless transfer lands in the **wireless function pocket**, which is a
separate, temporary area. It does **not** overwrite anything in the machine's
memory. So if you once saved `LemonY` to machine memory, that copy is still
there, still selectable, and still the old geometry — a fresh transfer changes
nothing about it.

When you go to stitch, the retrieve screen offers three sources:

| | source | behaviour |
|---|---|---|
| 1 | Machine memory | Persists. **Stale unless you deliberately re-saved it.** |
| 2 | USB flash drive | Whatever is on the stick. |
| 3 | **Wireless pocket** | What DDT just sent. **Deleted when the machine is switched off.** |

**After a DDT transfer, always retrieve from source 3.** If you want the design
to survive a power cycle, save it to machine memory afterwards — and delete the
previous copy of the same name first, or you will have two and pick the wrong
one later.

Symptom to watch for: a design that behaves exactly like an older revision, and
a design that was there yesterday and is missing today. Both are this.

---

## 1. USB flash drive

**Requirements**

- USB-A drive, **FAT32** (not exFAT, not NTFS)
- Designs at the drive **root** or in a top-level `BROTHER` folder — both are read
- Filenames restricted to `A-Z a-z 0-9 - _`

**With this repo's tooling** — validates before copying, so you never carry a
design to the machine that it will refuse to list:

```powershell
.\stitch.ps1 drives                                   # find the drive, check FAT32
.\stitch.ps1 stage designs\out\*.pes --to E:\          # validate + copy to E:\BROTHER
.\stitch.ps1 stage designs\out\rose.pes --to E:\ --root  # copy to E:\ instead
```

Designs with blocking errors are skipped and the reason printed. `--force`
overrides if you know better.

**Then eject the drive from Windows before unplugging it.** FAT32 write caching
will otherwise hand you a truncated file that the machine reads as corrupt.

**At the machine:** attach the embroidery unit *first*. A very common "the
machine can't see my USB designs" report is simply that the embroidery carriage
is not attached — without it the machine stays in sewing mode and the embroidery
file browser does not exist.

### Firmware updates are different

When updating machine software, the drive must contain **only** the update file.
Clear off your designs first.

---

## 2. Wireless from a PC — Design Database Transfer

**This is the preferred route here.** Brother's free Windows application.
Manages a design library with thumbnails and pushes files to the machine over
your LAN, no USB round trip.

- Download: <https://support.brother.com/g/s/hf/pcapp_info/ddt/en/index.html?prod=WLAN&media=i_txt>
- Windows only. There is no Mac build.
- Requires the machine and PC on the **same 2.4 GHz network**.
- Installed here: v1.2.0, `C:\Program Files (x86)\Brother\Design Database Transfer`

### The working loop

```powershell
.\tools\inkstitch_pipeline.ps1 ...          # build into designs\out\
.\stitch.ps1 stage designs\out\Thing.pes    # gate + wireless checklist
```

Then in DDT: point the folder pane at `designs\out`, select the design, add it
to the writing list, and transfer. On the machine, retrieve from the **wireless
pocket**.

Because DDT reads a folder directly, `designs\out` *is* the staging area — there
is no copy step and nothing to eject. That also means **DDT shows whatever is in
the folder right now**, so a rebuild is picked up on the next transfer with no
further action. The risk is entirely on the machine side, not the PC side: see
the trap above.

What DDT will and will not do for you:

| | |
|---|---|
| Transfers | `.pes` `.phc` `.phx` `.dst` `.pen` |
| Shows but cannot transfer | `.exp` `.pcs` `.hus` `.vip` `.shv` `.jef` `.sew` `.csd` `.xxx` |
| Cannot read | zipped files |
| Per transfer | **max 50 files** |
| Shows | remaining machine capacity |
| Does **not** check | that the design fits the 100 × 100 mm field — its manual tells you to check yourself |

### Finding the machine on the network

```powershell
.\stitch.ps1 discover           # sweep the subnet, resolve every MAC vendor
.\stitch.ps1 discover --deep    # + ports, SNMP banner, reverse DNS
.\stitch.ps1 probe 192.168.1.42 # fingerprint one address
```

`discover` ARP-sweeps your subnet and resolves each MAC against the IEEE
registry. ARP is the right signal — a device that ignores ICMP still has to
answer ARP on the same segment.

### MAC vendor alone will not find it

**The SE700's radio is an OEM module, and its MAC is not registered to
Brother.** The unit this repo was built against reports:

```
44:F7:9F:58:04:37   CLOUD NETWORK TECHNOLOGY SINGAPORE PTE. LTD.  (Foxconn)
```

Searching for Brother OUI prefixes (00:1B:A9, 00:80:77, 30:05:5C, 3C:2A:F4,
94:DD:F8, B0:7C:8E, B4:22:00) finds nothing. That is why `--deep` exists: it
fingerprints *services* instead of vendors.

### What actually identifies it

| Signal | Value |
|---|---|
| Open ports | **443 only** |
| HTTP `Server:` header | **`debut/1.20`** |
| TLS certificate CN | **`60;3;1;1.72.local`** |

`Debut embedded httpd` is Brother's own embedded web server — nmap fingerprints
it as "Brother/HP printer http admin", and Tenable ships plugin 104901,
"Brother Printer Debut Embedded HTTP Server Detection".

The certificate CN is the more precise tell: the last numeric field is the
**machine software version**. `1.72` in that string matches the SE700 firmware
version exactly, so the certificate tells you what build the machine is running
without touching the panel.

Every path on that HTTPS endpoint returns 404. There is no web admin UI — unlike
a Brother printer, the port exists purely for the design-transfer protocol.

`stitch discover --deep` checks all of this and reports its evidence:

```
1 Brother device(s) identified:
  192.168.86.74  (44-f7-9f-58-04-37)
      - runs Brother's 'Debut' embedded httpd
      - TLS cert identity string, software v1.72
```

### If it finds nothing

In order of likelihood: the machine is switched off (it only holds a DHCP lease
while powered), it joined a different SSID on a different subnet, client
isolation is hiding it, or it never associated (2.4 GHz only, no WPA-Enterprise).
Read the IP off the machine's screen (wireless LAN key) and `probe` it directly
to tell those apart.

### Do not port-scan the machine aggressively

Learned the hard way. A 1,039-port sweep at 250 concurrent connections made the
machine stop accepting TCP entirely — every port read as closed while it still
answered ping. It recovered on its own a few minutes later, but for a while it
looked like the machine had dropped its listener.

Debut httpd is **single-threaded**. A burst of parallel connections queues up
behind one another and the whole service stalls. That is the same weakness
behind CVE-2017-16249 below.

`stitch discover` and `stitch probe` are deliberately gentle — 13 ports, bounded
concurrency, short timeouts. Use them rather than pointing nmap at the machine,
and if it ever appears to have "gone offline" right after a scan, wait a few
minutes before concluding anything.

### Security note

Debut httpd ≤ 1.20 is affected by **CVE-2017-16249**, a remote denial of service
triggered by a malformed request. Brother has not fixed this server generation,
and the SE700 ships 1.20. The practical impact is low — worst case the machine's
network stack stops responding until you power-cycle it — but the mitigation is
network placement, not patching: keep it on your trusted LAN and never
port-forward it.

**What this cannot do:** push designs. See the note at the end of this section.

**Installed on this PC:** v1.2.0, `C:\Program Files (x86)\Brother\Design Database
Transfer\EmbDBT.exe`. Installer `ddt120_bro.exe`, SHA-256 `19596129…DD1A965`,
Authenticode signature valid (`CN="Brother Industries, Ltd."`). Manual bundled at
[`../reference/manuals/Design-Database-Transfer-Instruction-Manual.pdf`](../reference/manuals/Design-Database-Transfer-Instruction-Manual.pdf).

**Pairing (from the manual, p.2):**

1. PC and machine on the **same** network. Different subnets will not work.
2. Machine powered on, awake, embroidery unit attached.
3. In DDT: **Option → Network Machine Settings**
4. **Add** → select the machine from the list → **Add**
5. **OK** to register.

There is no field to type an IP — DDT discovers machines itself. If yours isn't
listed, click **Refresh**; if it still isn't, the machine is asleep or on another
subnet. Confirm it's reachable first with `stitch probe <ip>`.

**Transfer limits (manual p.3):**

- Transferable: `.pes` `.phc` `.phx` `.dst` `.pen`
- Shown in the browser but **not** transferable: `.exp` `.pcs` `.hus` `.vip`
  `.shv` `.jef` `.sew` `.csd` `.xxx` — convert these first with `stitch convert`
- **Zipped files cannot be read** — unpack before importing
- **Maximum 50 files per transfer**
- DDT does not check the design fits the hoop. `stitch validate` does.

**Wireless gotchas, in the order they usually bite:**

| Symptom | Cause |
|---|---|
| SSID not in the list | It's 5 GHz. The machine is 2.4 GHz only. |
| Connects then drops | Band steering — one SSID serving both bands. Split them. |
| Cannot authenticate at all | WPA/WPA2 **Enterprise**. Unsupported, full stop. Use a hotspot. |
| Machine visible, transfer fails | Client isolation / AP isolation enabled on the router or guest network. |

Finding your SSID and network key is covered in the Operation Manual p.95.

**A wirelessly transferred design does not survive a power cycle.** It lands in
what Brother calls the *wireless function pocket*, and the manual is explicit
(p.80–81):

> "Embroidery patterns which were uploaded via wireless network will be deleted
> from the machine when turning the machine off. Save patterns to the machine
> memory if necessary."

So after any wireless transfer, if you want to keep the design: retrieve it,
touch the memory key, and **save it to the machine's memory** (up to 1024 KB or
20 patterns). Otherwise it is gone at the next power-on, and the symptom — a
design that was there yesterday and is missing today — looks nothing like a
transfer problem. USB files have no such expiry.

### There is no programmable network path

Worth stating plainly so nobody sinks a weekend into it: Brother's wireless
design-transfer protocol is **closed**. There is no published API, no SDK, and
no public reverse-engineering effort for the SE-series. The machine is not a
network printer — it does not speak LPD, IPP, or JetDirect, and you cannot pipe
a PES file at a port.

The only network routes are Design Database Transfer (Windows GUI) and Artspira
(phone). Neither is scriptable.

That is a smaller limitation than it sounds, and it does **not** make USB the
better route. The automatable part of the job — generate, validate, gate — all
happens on the PC in `designs\out`, and DDT reads that folder directly. Only the
final click is manual, and it is one click on a folder the tooling already
maintains. `stitch stage` with no `--to` is the gate for that route; `--to`
copies to USB for the times you need it.

### PE-DESIGN 11+

If you own PE-DESIGN 11 or later it transfers wirelessly too. PE-DESIGN 10 and
earlier cannot — they predate the wireless protocol.

---

## 3. Artspira mobile app

Brother's iOS/Android app. Two useful things:

- A catalogue of downloadable designs, pushed straight to the machine over WiFi.
- A **drawing mode** — sketch line art on your phone (pen: single or zigzag,
  shapes, eraser) and it becomes an embroidery pattern.

Constraints:

- Designs up to **100 × 100 mm**, same as everything else.
- **20 slots** in the "My Creations" tab. It is a scratchpad, not storage.
- Requires a Brother account and the machine on the same network.

Artspira is not a digitizing tool — it cannot make fills, underlay, or proper
satin columns. Author in Ink/Stitch, PE-Design, or this repo's generators.

### Artspira will transfer *your own* files

Easy to miss, and it makes Artspira a real third route rather than a toy:
**Import External Files** takes designs you made elsewhere into *My Creations*,
then sends them to the machine over WiFi.

- Accepts **`.pes` `.phc` `.phx` `.dst`** (and `.fcm` / `.svg` for cutting machines)
- Works on the **free plan** — Artspira+ is not required
- Path: **My Creations → `+` → Import External Files** → pick the file →
  select the machine → **Transfer**

So a design generated here can reach the machine wirelessly without DDT:

```
stitch validate designs\out\rose.pes
   → get the .pes onto your phone (cloud drive, AirDrop, email)
   → Artspira → My Creations → + → Import External Files → Transfer
```

The phone step is manual and cannot be scripted — Artspira has no API, no PC
client, and no web version. But it does mean USB is not the only way to move
your own work.

Reference: [Brother — Artspira Import External Files](https://support.brother.com/g/s/hf/mobileapp_info/artspira/plan/func1/en.html)

### There is no Artspira API

Mobile only (Android 8+, iOS/iPadOS 15+), cloud-backed, Brother account
required. No PC or web client, no published API, no developer programme.
Emulator-based "Artspira on PC" guides are third-party Android emulators, not a
Brother product. Nothing here to integrate with programmatically.

---

## Which to use

| Situation | Route |
|---|---|
| Anything you generated in this repo | **Design Database Transfer** — the preferred method here |
| Iterating fast on one design | Design Database Transfer |
| Casual line art from your phone | Artspira |
| DDT or the network is misbehaving | USB via `stitch stage --to E:\` |
| Machine won't join your network | USB — and stop fighting the router |

DDT is the default because the PC-side folder *is* the staging area: rebuild the
design and the next transfer picks it up with no copy step and nothing to eject.

The cost of that convenience is entirely on the machine side, and it is real:
transfers land in a volatile pocket and **do not overwrite anything already
saved to machine memory**. Read the trap at the top of this document before
concluding that a regenerated design "did not change anything". USB has no such
ambiguity — the file on the stick is the file that stitches — which is why it
stays the tie-breaker when a result is confusing.
