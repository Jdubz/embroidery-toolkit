"""Inspect a design file and check it against the machine profile.

The point of `validate` is to catch, on the desk, the three failure modes that
otherwise only show up at the machine: a design the machine silently refuses to
list (too big), one it truncates or chokes on (too many stitches), and a file
name it cannot render.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import pyembroidery as pe

from . import palette
from . import profile as prof

SAFE_NAME = re.compile(r"^[A-Za-z0-9_-]+$")

# Severity ordering used for exit codes and display.
ERROR = "error"
WARNING = "warning"
INFO = "info"

# How many stitches at each end of a run count as tie-in / tie-off. Locks are
# deliberately short and must stay short, so short-stitch reporting excludes
# them; without this every correctly-locked design trips the warning.
LOCK_WINDOW = 3


@dataclass
class Finding:
    severity: str
    code: str
    message: str


@dataclass
class DesignInfo:
    path: Path
    stitch_count: int = 0
    real_stitches: int = 0
    jumps: int = 0
    trims: int = 0
    color_changes: int = 0
    thread_count: int = 0
    width_mm: float = 0.0
    height_mm: float = 0.0
    bounds_units: tuple = (0, 0, 0, 0)
    threads: list = field(default_factory=list)
    extras: dict = field(default_factory=dict)
    # Consecutive-stitch pairs, and how many fall below the profile's minimum
    # length. Measured in describe() because that is where the stitch list is
    # already in hand; min_stitch_mm_used records the threshold actually
    # applied, so the finding can report an honest number.
    stitch_pairs: int = 0
    short_stitches: int = 0
    # Short stitches away from a run's ends. Tie-in and tie-off are deliberately
    # short and must stay short to anchor the thread, so counting them as
    # defects would flag every correctly-locked design. Only mid-run ones are
    # actionable.
    short_stitches_midrun: int = 0
    min_stitch_mm_used: float = 0.0
    # Needle penetrations per 1 mm cell. The median stays normal even when the
    # peaks are lethal, so the useful figures are the maximum and how many cells
    # sit above the risk lines -- never the average.
    density_cells: int = 0
    density_max: int = 0
    density_cells_risky: int = 0
    density_cells_danger: int = 0
    # Satin coverage. A satin column's neighbouring stitches are single threads
    # laid side by side; spaced wider than a thread is thick, they leave bare
    # fabric — and the bobbin thread crossing underneath — visible between them.
    satin_pairs: int = 0
    satin_gaps: int = 0
    satin_advance_p50_mm: float = 0.0

    @property
    def width_in(self) -> float:
        return prof.mm_to_in(self.width_mm)

    @property
    def height_in(self) -> float:
        return prof.mm_to_in(self.height_mm)

    def runtime_minutes(self, machine: dict | None = None) -> float:
        """Wall-clock estimate for a stitch-out on this machine.

        Matters far more on an SE700 than on a commercial head: 400 spm is slow,
        every colour change is a manual rethread you stand there for, and every
        automatic trim costs about a second of stop-cut-move-restart.

        Within-colour jumps are only charged on a machine that actually trims
        them. The SE700 does not — it jumps and carries on, leaving a float for
        you to cut. An earlier version charged ~1 s per trim regardless and
        reported 57 min for a design whose real machine time is ~42; the
        difference was hand labour miscounted as machine time. See
        `cleanup_minutes`. Assumes rated top speed, so treat it as a floor.
        """
        machine = machine or prof.load()
        spm = machine["embroidery"]["max_speed_spm"]
        stitching = self.real_stitches / spm
        # ~90 s per rethread: stop, snip, re-thread top, re-seat, restart.
        rethreads = max(0, self.color_changes) * 1.5
        trimming = 0.0
        if machine.get("trimming", {}).get("auto_trims_jumps_within_color", False):
            trimming = self.trims / 60.0   # ~1 s per automatic trim
        return stitching + rethreads + trimming

    def cleanup_minutes(self, machine: dict | None = None) -> float:
        """Hand-snipping time after the machine finishes.

        Zero where the machine trims its own jumps. On the SE700 every
        within-colour jump leaves a float that you cut by hand — so jump count
        is a labour cost, not a machine cost.
        """
        machine = machine or prof.load()
        t = machine.get("trimming", {})
        if t.get("auto_trims_jumps_within_color", False):
            return 0.0
        secs = t.get("seconds_per_manual_snip_estimate", 4)
        return self.jumps * secs / 60.0


def _readable_extras(extras: dict) -> dict:
    """Drop the embedded PEC thumbnail bitmaps — they are binary blobs, not metadata."""
    out = {}
    for k, v in extras.items():
        if k.startswith("pec_graphic"):
            continue
        text = str(v)
        out[k] = text if len(text) <= 120 else text[:117] + "..."
    return out


def read_pattern(path: str | Path) -> pe.EmbPattern:
    path = Path(path)
    pattern = pe.read(str(path))
    if pattern is None:
        raise ValueError(
            f"pyembroidery could not read {path.name}. Check the extension matches "
            f"the actual format."
        )
    return pattern


def describe(path: str | Path, pattern: pe.EmbPattern | None = None) -> DesignInfo:
    """Collect the measurements a validator or a human would want."""
    path = Path(path)
    pattern = pattern if pattern is not None else read_pattern(path)

    min_x, min_y, max_x, max_y = pattern.bounds()
    info = DesignInfo(
        path=path,
        stitch_count=len(pattern.stitches),
        real_stitches=pattern.count_stitch_commands(pe.STITCH),
        jumps=pattern.count_stitch_commands(pe.JUMP),
        trims=pattern.count_stitch_commands(pe.TRIM),
        color_changes=pattern.count_color_changes(),
        thread_count=len(pattern.threadlist),
        width_mm=prof.units_to_mm(max_x - min_x),
        height_mm=prof.units_to_mm(max_y - min_y),
        bounds_units=(min_x, min_y, max_x, max_y),
        extras=_readable_extras(pattern.extras),
    )

    floor_mm = prof.min_stitch_mm()
    if floor_mm:
        info.min_stitch_mm_used = floor_mm
        limit_sq = prof.mm_to_units(floor_mm) ** 2
        # Stitches either side of a jump or trim belong to different runs, so
        # the distance across the break is not a stitch length.
        runs: list[list[tuple]] = []
        cur: list[tuple] = []
        for x, y, cmd in pattern.stitches:
            if (cmd & pe.COMMAND_MASK) != pe.STITCH:
                if cur:
                    runs.append(cur)
                cur = []
                continue
            cur.append((x, y))
        if cur:
            runs.append(cur)

        for run in runs:
            for i in range(1, len(run)):
                info.stitch_pairs += 1
                (ax, ay), (bx, by) = run[i - 1], run[i]
                if (bx - ax) ** 2 + (by - ay) ** 2 >= limit_sq:
                    continue
                info.short_stitches += 1
                if LOCK_WINDOW < i < len(run) - LOCK_WINDOW:
                    info.short_stitches_midrun += 1

        # Satin coverage.
        #
        # A finished stitch file carries no note saying "this run is satin", so
        # detect it geometrically. In a satin column consecutive stitches cross
        # from rail to rail and then reverse, so the step from stitch i to i+2
        # (same rail, one place along) is far shorter than the crossing from i
        # to i+1. A fill does the opposite: it advances along a row, so i to i+2
        # is roughly twice i to i+1. Treating a triple as satin when the advance
        # is under half the crossing separates them cleanly.
        #
        # Then the actual test: is that advance wider than a thread is thick? If
        # so the threads do not overlap and fabric shows between them. This is
        # not hypothetical — a build went out with a 0.41 mm advance against a
        # 0.40 mm thread and the white bobbin swamped the black.
        # Two further conditions, both needed to avoid false positives. A lone
        # reversal is not satin: a serpentine fill reverses at the end of every
        # row, and tie-offs reverse in place. Require the column to be at least
        # as wide as the minimum satin width, and require the reversals to be
        # SUSTAINED — a real column is dozens in a row, a fill turn is one.
        # Without both, scream2 — which contains no satin whatsoever — reported
        # 1,176 satin pairs and tripped the warning.
        # Judged against the validated fill density, not a separate "thread
        # width" figure. An earlier version compared against 0.4 mm — the very
        # number this profile calls the correct fill row spacing — so it
        # reported Ink/Stitch's default satin as defective and, worse, sent a
        # diagnosis down the wrong path. A satin is a fill rotated 90 degrees;
        # if 0.4 mm rows cover, 0.4 mm satin covers.
        tw = prof.mm_to_units(prof.design_limit("fill_density_mm", 0.4)
                              * prof.design_limit("satin_sparse_factor", 1.5))
        min_w = prof.mm_to_units(prof.design_limit("min_satin_width_mm", 1.0))
        RUN_MIN = 8

        advances: list[float] = []
        for run in runs:
            streak: list[float] = []

            def flush(streak=streak):
                if len(streak) >= RUN_MIN:
                    advances.extend(streak)
                    info.satin_pairs += len(streak)
                    info.satin_gaps += sum(1 for v in streak if v > tw)
                streak.clear()

            for i in range(len(run) - 2):
                (ax, ay), (bx, by), (cx, cy) = run[i], run[i + 1], run[i + 2]
                span = ((bx - ax) ** 2 + (by - ay) ** 2) ** 0.5
                adv = ((cx - ax) ** 2 + (cy - ay) ** 2) ** 0.5
                if span >= min_w and adv < 0.5 * span:
                    streak.append(adv)
                else:
                    flush()
            flush()
        if advances:
            advances.sort()
            info.satin_advance_p50_mm = prof.units_to_mm(advances[len(advances) // 2])

        # Penetration density on a 1 mm grid. Cheap to fold in here since the
        # runs are already built, and it is the measurement that distinguishes
        # a design that stitches from one that snaps needles.
        cell = prof.mm_to_units(1.0)
        grid: dict[tuple[int, int], int] = {}
        for run in runs:
            for x, y in run:
                k = (int(x // cell), int(y // cell))
                grid[k] = grid.get(k, 0) + 1
        if grid:
            risky = prof.design_limit("max_density_per_mm2", 16)
            danger = prof.design_limit("density_danger_per_mm2", 30)
            info.density_cells = len(grid)
            info.density_max = max(grid.values())
            info.density_cells_risky = sum(1 for v in grid.values() if v >= risky)
            info.density_cells_danger = sum(1 for v in grid.values() if v >= danger)

    for i, t in enumerate(pattern.threadlist):
        info.threads.append(
            {
                "index": i + 1,
                "hex": t.hex_color(),
                "description": t.description,
                "catalog_number": t.catalog_number,
                "brand": t.brand,
            }
        )
    return info


def validate(info: DesignInfo, machine: dict | None = None,
             cloth: str | None = None, hoop: str | None = None) -> list[Finding]:
    """Return every reason this design might not stitch out on the machine.

    `cloth` is the fabric colour this design is stitched on, from its spec. Pass
    it and the thread colours are checked against it; omit it and that one check
    is skipped, because there is nothing in a .pes that records the fabric.

    `hoop` is the frame it is stitched in, likewise from its spec, and likewise
    unknowable from the file. Omit it and the design is only checked against the
    machine's full 100 x 100 mm field.
    """
    machine = machine or prof.load()
    findings: list[Finding] = []

    # Thread the colour of the cloth is thread you cannot see. It costs stitches,
    # time and a rethread and contributes nothing, and on an inverted dark-cloth
    # design it is a real risk: the whole technique is to DROP the ink layer and
    # let the fabric supply it, so a layer that failed to drop looks fine
    # everywhere except on the fabric.
    #
    # Judged by CIELAB distance rather than by equality, because "the same
    # colour" is a perceptual claim and PES quantises every thread to the fixed
    # 64-entry Brother palette on the way out — a layer authored as #000000 is
    # not the byte the file ends up carrying.
    if cloth:
        limit = prof.design_limit("min_thread_cloth_delta_e", 25.0)
        for t in info.threads:
            d = palette.delta_e(t["hex"], cloth)
            if d < limit:
                findings.append(Finding(
                    ERROR, "thread-matches-cloth",
                    f"Thread {t['index']} ({t['hex']}) is the colour of the cloth "
                    f"(#{cloth}) — CIELAB distance {d:.1f}, under the {limit:g} "
                    f"this machine's profile calls distinguishable. It will not "
                    f"be visible. Drop the layer and let the fabric supply it, or "
                    f"change the thread.",
                ))

    max_w, max_h = prof.max_field_mm(machine)
    if info.width_mm > max_w or info.height_mm > max_h:
        findings.append(
            Finding(
                ERROR,
                "field-overflow",
                f"Design is {info.width_mm:.1f} x {info.height_mm:.1f} mm; the "
                f"{prof.model_name(machine)} field is {max_w:.0f} x {max_h:.0f} mm. "
                f"The machine will not list a design that does not fit.",
            )
        )
    elif not hoop:
        margin_w = max_w - info.width_mm
        margin_h = max_h - info.height_mm
        if min(margin_w, margin_h) < 2.0:
            findings.append(
                Finding(
                    WARNING,
                    "tight-margin",
                    f"Only {min(margin_w, margin_h):.1f} mm of clearance to the edge "
                    f"of the field. Hooping is rarely that accurate — leave 2 mm+.",
                )
            )

    # The hoop, when one is declared, is the binding constraint — always tighter
    # than the machine field, so it supersedes the margin check above.
    #
    # It has to be declared because neither the file nor the machine knows it.
    # Nothing in a .pes records which frame it is for, and the SE700 does not
    # sense the frame either: you pick it on the settings screen. So a design
    # built for the SA431's 20 mm-tall field but drawn 40 mm tall passes every
    # other check here, gets listed on the machine, and then drives the presser
    # foot into the frame — which the manual calls out as a damage and injury
    # risk (p.64). This is the one envelope error the existing checks cannot see.
    if hoop:
        h = prof.hoop(hoop, machine)
        if h is None:
            known = ", ".join(str(x.get("id")) for x in prof.hoops(machine))
            findings.append(
                Finding(
                    WARNING,
                    "hoop-unknown",
                    f"'{hoop}' is not a hoop in the machine profile ({known}). "
                    f"Checked against the full field instead. Add it to "
                    f"reference/machine-profile.json rather than dropping the "
                    f"declaration.",
                )
            )
        else:
            fields = prof.hoop_fields_mm(hoop, machine)
            fits = [(w, ht) for w, ht in fields
                    if info.width_mm <= w and info.height_mm <= ht]
            areas = " or ".join(f"{w:g} x {ht:g}" for w, ht in fields)
            if not fits:
                # A design that fits only turned is a real and common case — the
                # machine rotates a pattern in two touches — so say so rather
                # than reporting a flat refusal the user then has to second-guess.
                turned = any(info.height_mm <= w and info.width_mm <= ht
                             for w, ht in fields)
                fix = (" It fits turned 90° — rotate it on the machine, or build "
                       "it that way round." if turned else "")
                findings.append(
                    Finding(
                        ERROR,
                        "hoop-overflow",
                        f"Design is {info.width_mm:.1f} x {info.height_mm:.1f} mm; "
                        f"hoop {h.get('id')} ({h.get('name')}) stitches "
                        f"{areas} mm.{fix}",
                    )
                )
            else:
                # Roomiest fit, judged on the tighter of the two axes — that is
                # the one that runs out first.
                w, ht = max(fits, key=lambda f: min(f[0] - info.width_mm,
                                                    f[1] - info.height_mm))
                margin = min(w - info.width_mm, ht - info.height_mm)
                if margin < 2.0:
                    findings.append(
                        Finding(
                            WARNING,
                            "hoop-tight-margin",
                            f"Only {margin:.1f} mm of clearance inside hoop "
                            f"{h.get('id')} ({w:g} x {ht:g} mm). Floating narrow "
                            f"material on stabilizer is rarely that accurate — "
                            f"leave 2 mm+.",
                        )
                    )

    limit = prof.max_stitches(machine)
    if info.real_stitches > limit:
        findings.append(
            Finding(
                ERROR,
                "stitch-overflow",
                f"{info.real_stitches:,} stitches exceeds the {limit:,} per-pattern "
                f"limit. Split the design.",
            )
        )
    elif info.real_stitches > limit * 0.8:
        findings.append(
            Finding(
                WARNING,
                "stitch-high",
                f"{info.real_stitches:,} stitches is over 80% of the {limit:,} limit.",
            )
        )

    ext = info.path.suffix.lower()
    readable = [e.lower() for e in prof.readable_extensions(machine)]
    if ext not in readable:
        findings.append(
            Finding(
                ERROR,
                "format-unreadable",
                f"'{ext}' is not one of the formats the machine reads "
                f"({', '.join(readable)}).",
            )
        )

    # Container checks need the file on disk. Skip them rather than crash when
    # validating a DesignInfo built in memory.
    if ext == ".pes" and info.path.is_file():
        from . import convert as _convert
        hoop = _convert.read_pes_hoop(info.path)
        max_w, max_h = prof.max_field_mm(machine)
        want = (_convert.PES_HOOP_100x100 if (max_w <= 100 and max_h <= 100)
                else _convert.PES_HOOP_130x180)
        if hoop is not None and hoop != want:
            findings.append(
                Finding(
                    WARNING,
                    "pes-hoop-mismatch",
                    f"PES header declares a "
                    f"{'100x100' if hoop == 0 else '130x180'} mm hoop, but this "
                    f"machine is {max_w:.0f}x{max_h:.0f} mm. Fix: stitch fix-pes.",
                )
            )
        # PEC coordinates must start at (0,0). A design centred on the origin
        # renders in Brother software with its left and top halves off-canvas.
        min_x, min_y = info.bounds_units[0], info.bounds_units[1]
        if min_x < -1 or min_y < -1:
            findings.append(
                Finding(
                    WARNING,
                    "pes-origin-centred",
                    f"Stitches start at ({min_x}, {min_y}) instead of (0, 0). "
                    f"Design Database Transfer reads PEC coordinates as running "
                    f"0..width, so a centred design shows only its bottom-right "
                    f"quadrant. Fix: stitch fix-pes <file>.",
                )
            )

        # A PES section written by pyembroidery is positioned for a 130x180
        # hoop, so Brother software previews the design off in a corner.
        try:
            with info.path.open("rb") as fh:
                head = fh.read(20)
            if head.startswith(b"#PES0001"):
                import struct as _s
                pec_off = _s.unpack("<I", head[8:12])[0]
                blocks = _s.unpack("<H", head[16:18])[0]
                if pec_off > 22 and blocks:
                    findings.append(
                        Finding(
                            WARNING,
                            "pes-section-misplaced",
                            "This PES carries a pyembroidery-written PES section "
                            "laid out for a 130x180 mm hoop. Brother's Design "
                            "Database Transfer renders that section, so the "
                            "design previews off in a corner even though the "
                            "stitches are correct. Fix: stitch fix-pes <file>.",
                        )
                    )
        except OSError:
            pass

    if ext == ".dst":
        findings.append(
            Finding(
                INFO,
                "dst-no-colour",
                "DST carries no thread colours: the machine shows this design by "
                "filename with no thumbnail and applies its default colour sequence.",
            )
        )

    stem = info.path.stem
    if not SAFE_NAME.match(stem):
        findings.append(
            Finding(
                WARNING,
                "filename-charset",
                f"'{stem}' uses characters outside A-Z a-z 0-9 - _. Brother "
                f"recommends sticking to that set; other characters can render "
                f"wrongly or hide the file.",
            )
        )
    # This used to be a hard-coded 8 justified as "the design list truncates".
    # No manual says so: a full-text search of all four finds no filename length
    # rule, and the embroidery retrieve screen picks patterns from a thumbnail
    # grid, not a name list — the settings screen has thumbnail size and
    # thumbnail background options. Filenames only drive selection for .dst,
    # which has no thumbnail. So the limit is a legibility guideline for the DDT
    # list, it lives in the profile, and it is set where a descriptive name like
    # LemonCat_outline_on_yellow does not trip it.
    long_name = int((prof.load().get("usb") or {}).get("filename_long_chars", 32))
    if len(stem) > long_name:
        findings.append(
            Finding(
                INFO,
                "filename-length",
                f"'{stem}' is {len(stem)} characters, past the {long_name} this "
                f"profile calls comfortable. Not a machine limit — patterns are "
                f"chosen by thumbnail — but long names are awkward to scan in the "
                f"Design Database Transfer list.",
            )
        )

    if info.thread_count == 0:
        findings.append(
            Finding(WARNING, "no-threads", "No thread colours defined in the file.")
        )

    if info.color_changes >= 5:
        findings.append(
            Finding(
                WARNING if info.color_changes >= 7 else INFO,
                "many-colours",
                f"{info.color_changes} colour changes. This is a single-needle "
                f"machine, so that is {info.color_changes} manual rethreads with "
                f"you standing at it. Four or fewer colours is the practical "
                f"sweet spot.",
            )
        )

    runtime = info.runtime_minutes(machine)
    if runtime > 45:
        auto = machine.get("trimming", {}).get(
            "auto_trims_jumps_within_color", False)
        extra = ("" if auto else
                 " Note that routing around holes deliberately trades machine "
                 "time for fewer jump floats to snip, so some of this length is "
                 "bought, not wasted — lower --travel to shorten it.")
        findings.append(
            Finding(
                INFO if not auto else WARNING,
                "long-runtime",
                f"~{runtime:.0f} minutes at {machine['embroidery']['max_speed_spm']} "
                f"spm, which is a fixed rate on this machine. For scale, the "
                f"longest of Brother's own 128 built-in designs is 47 minutes "
                f"and 99% finish inside 45. Long unattended runs invite thread "
                f"breaks and hoop shift, so stay near the machine.{extra}",
            )
        )

    auto_trim = machine.get("trimming", {}).get(
        "auto_trims_jumps_within_color", False)
    if info.jumps and not auto_trim:
        cleanup = info.cleanup_minutes(machine)
        if cleanup > 20:
            findings.append(
                Finding(
                    WARNING,
                    "hand-trimming",
                    f"{info.jumps:,} jumps, and this machine does not trim jumps "
                    f"within a colour — that is ~{cleanup:.0f} min of snipping "
                    f"floats by hand afterwards. Raise --travel to route around "
                    f"holes instead of jumping.",
                )
            )
    elif info.real_stitches and info.jumps / info.real_stitches > 0.15:
        findings.append(
            Finding(
                WARNING,
                "jump-heavy",
                f"{info.jumps:,} jumps against {info.real_stitches:,} stitches "
                f"({info.jumps / info.real_stitches:.0%}). Consider re-pathing.",
            )
        )

    # Stitches shorter than the profile minimum put two penetrations in almost
    # the same hole. The upper thread gets no length over which to take up
    # tension, so the bobbin thread is drawn to the surface and shows as flecks
    # of bobbin colour; keep going and the needle saws the thread against its
    # own eye until it breaks.
    #
    # raster.py enforces this floor at generation time via _filter_short, but
    # files from anywhere else -- Ink/Stitch, a purchased design, a conversion
    # -- never pass through it, so check the finished stitch list. Measured on
    # the first Ink/Stitch designs built here: 11-18% of stitches were under
    # 0.5 mm purely because the exporter was never told the limit.
    # Satin coverage. Renders cannot show this — a preview draws each stitch as
    # a line and a sparse comb looks identical to a solid column, which is
    # exactly how a design with zero thread overlap passed visual review and
    # went onto fabric.
    if info.satin_pairs >= 50:
        density = prof.design_limit("fill_density_mm", 0.4)
        limit = density * prof.design_limit("satin_sparse_factor", 1.5)
        share = info.satin_gaps / info.satin_pairs
        med = info.satin_advance_p50_mm
        if med > limit or share >= 0.40:
            findings.append(
                Finding(
                    WARNING,
                    "satin-coverage",
                    f"satin stitches average {med:.2f} mm apart and {share:.0%} "
                    f"exceed {limit:.2f} mm — well beyond the {density} mm "
                    f"spacing validated for this machine. At that spacing the "
                    f"threads stop overlapping and fabric shows between them. "
                    f"Tighten the satin density.",
                )
            )
        elif med > density:
            findings.append(
                Finding(
                    INFO,
                    "satin-coverage",
                    f"satin stitches average {med:.2f} mm apart, a little wider "
                    f"than the {density} mm validated density. Fine on straight "
                    f"runs; the outer rail of a tight curve will be the first "
                    f"place any sparseness shows.",
                )
            )

    # Peak penetration density. The manual's own failure mode: "the thread may
    # break or the needle may break or bend when embroidering with a stitch
    # density that is too fine or when embroidering three or more overlapping
    # stitches." Two broken needles here were traced to cells at 45-52/mm^2,
    # and unchecked travel routing once reached 111.
    #
    # Judged on the peak and on how many cells are hot, never on the average --
    # the median sits at ~3 whether the design is safe or lethal.
    if info.density_cells:
        risky = prof.design_limit("max_density_per_mm2", 16)
        danger = prof.design_limit("density_danger_per_mm2", 30)
        hot_share = info.density_cells_risky / info.density_cells
        if info.density_cells_danger:
            findings.append(
                Finding(
                    WARNING,
                    "density-peak",
                    f"{info.density_cells_danger:,} cell(s) at or above "
                    f"{danger} penetrations/mm² (peak {info.density_max}). This "
                    f"is the manual's stated cause of broken thread and needles. "
                    f"Find them by classifying hot cells as colour-boundary / "
                    f"region-rim / interior, then cut passes: drop the outline, "
                    f"then the underlay, then lower --max-density or --travel.",
                )
            )
        elif hot_share >= 0.01:
            findings.append(
                Finding(
                    INFO,
                    "density-peak",
                    f"{info.density_cells_risky:,} of {info.density_cells:,} "
                    f"cells ({hot_share:.0%}) are at or above {risky} "
                    f"penetrations/mm² (peak {info.density_max}). Not dangerous "
                    f"yet — {danger}+ is where breakage starts — but worth "
                    f"knowing where they are before adding another pass.",
                )
            )

    if info.short_stitches_midrun and info.stitch_pairs:
        share = info.short_stitches_midrun / info.stitch_pairs
        locks = info.short_stitches - info.short_stitches_midrun
        aside = (f" A further {locks:,} sit at run ends, which is tie-in and "
                 f"tie-off doing its job — leave those alone." if locks else "")
        findings.append(
            Finding(
                # A few are unavoidable where a path turns tightly; a
                # systematic problem shows up as a percentage, not a count.
                WARNING if share >= 0.02 else INFO,
                "short-stitches",
                f"{info.short_stitches_midrun:,} of {info.stitch_pairs:,} "
                f"stitches ({share:.0%}) are under {info.min_stitch_mm_used} mm "
                f"mid-run. Short stitches draw bobbin thread up to the surface "
                f"and saw the upper thread against the needle eye. For "
                f"Ink/Stitch output set inkstitch:min_stitch_len_mm in the "
                f"document metadata; for stitch trace raise --min-stitch."
                f"{aside}",
            )
        )

    return findings


def worst_severity(findings: list[Finding]) -> str | None:
    for level in (ERROR, WARNING, INFO):
        if any(f.severity == level for f in findings):
            return level
    return None
