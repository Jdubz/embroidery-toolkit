"""`stitch` — command line entry point for the SE700 toolkit.

    py -m embroidery_tools.cli info designs/out/heart.pes
    py -m embroidery_tools.cli validate designs/out/*.pes
    py -m embroidery_tools.cli convert logo.dst designs/out/logo.pes
    py -m embroidery_tools.cli preview designs/out/logo.pes
    py -m embroidery_tools.cli palette --match "#2E86AB"
    py -m embroidery_tools.cli drives
    py -m embroidery_tools.cli stage designs/out/logo.pes --to E:\\
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

from . import analyze, convert, coverage, network, palette, preview, proof
from . import profile as prof
from . import usb

SEVERITY_TAG = {
    analyze.ERROR: "ERROR  ",
    analyze.WARNING: "WARNING",
    analyze.INFO: "note   ",
}


def _expand(patterns: list[str]) -> list[Path]:
    """Expand globs ourselves — PowerShell does not do it for us."""
    out: list[Path] = []
    for p in patterns:
        matches = glob.glob(p)
        out.extend(Path(m) for m in matches) if matches else out.append(Path(p))
    return out


_REPO = Path(__file__).resolve().parents[2]
_STAGING = _REPO / "designs" / "out"


def _resolve_output(paths: list[Path], output: str | None, suffix: str,
                    kind: str | None = None):
    """Guard against one -o swallowing several inputs, and keep staging clean.

    Without the first guard, `render a.pes b.pes -o out.png` writes both to
    out.png and silently keeps only the last — the first result is lost with no
    warning.

    The second: `designs/out` is the Design Database Transfer staging folder and
    holds nothing but `.pes`, so a render of a file living there goes to
    `build/<kind>/` instead of landing beside it. Writing alongside is still the
    behaviour everywhere else, and an explicit -o always wins.
    """
    if output and len(paths) > 1:
        raise ValueError(
            f"--output takes a single input, but {len(paths)} files matched. "
            f"Drop --output to write alongside each input."
        )
    if output:
        return [Path(output)]
    outs = []
    for p in paths:
        if kind and p.resolve().parent == _STAGING:
            d = _REPO / "build" / kind
            d.mkdir(parents=True, exist_ok=True)
            outs.append(d / (p.stem + suffix))
        else:
            outs.append(p.with_suffix(suffix))
    return outs


def _print_findings(findings: list[analyze.Finding], indent: str = "  ") -> None:
    for f in findings:
        print(f"{indent}{SEVERITY_TAG[f.severity]}  [{f.code}] {f.message}")


# --------------------------------------------------------------------------- #


def cmd_info(args) -> int:
    for path in _expand(args.files):
        try:
            info = analyze.describe(path)
        except Exception as exc:
            print(f"{path}: {exc}", file=sys.stderr)
            continue

        print(f"\n{info.path}")
        print(f"  size          {info.width_mm:.1f} x {info.height_mm:.1f} mm "
              f"({info.width_in:.2f} x {info.height_in:.2f} in)")
        print(f"  stitches      {info.real_stitches:,} real, "
              f"{info.jumps:,} jump, {info.trims:,} trim "
              f"({info.stitch_count:,} commands total)")
        print(f"  colours       {info.thread_count} thread(s), "
              f"{info.color_changes} change(s)")
        machine = prof.load()
        spm = machine['embroidery']['max_speed_spm']
        print(f"  machine time  ~{info.runtime_minutes():.0f} min at {spm} spm "
              f"({info.real_stitches / spm:.0f} sewing "
              f"+ {info.color_changes * 1.5:.0f} rethreading)")
        if not machine.get("trimming", {}).get("auto_trims_jumps_within_color", False):
            print(f"  hand trimming ~{info.cleanup_minutes():.0f} min — "
                  f"{info.jumps:,} jump(s) to snip. This machine does not trim "
                  f"jumps within a colour.")
        for t in info.threads:
            label = t["description"] or t["catalog_number"] or ""
            brand = f" {t['brand']}" if t["brand"] else ""
            print(f"                {t['index']:>2}. {t['hex']}  {label}{brand}".rstrip())
        if info.extras:
            for k, v in info.extras.items():
                print(f"  {k:<13} {v}")
        if args.verbose:
            print(f"  bounds        {info.bounds_units} (1/10 mm units)")
    return 0


def _spec_field(path, args, field: str) -> str | None:
    """A design fact that lives in its spec and nowhere in the file.

    The explicit flag wins; otherwise look the design up by name in
    `designs/specs/`. Two checks need this. A .pes records no fabric, so
    thread-vs-cloth has nothing to compare without one; and it records no hoop
    either — nor does the machine detect one — so the hoop-fit check likewise
    has no other source. Without a value the check is skipped rather than
    guessed.

    Looking it up means `stitch validate designs/out/*.pes` checks every design
    against its own cloth and its own frame with no extra typing — a check
    nobody has to remember is the only kind that runs.
    """
    v = getattr(args, field, None)
    if v:
        return v.lstrip("#") if field == "cloth" else v
    try:
        from . import build as B
        spec_path = B.SPECS / f"{Path(path).stem}.json"
        if spec_path.exists():
            return json.loads(spec_path.read_text(encoding="utf-8")).get(field)
    except Exception:                       # noqa: BLE001 - never block validate
        pass
    return None


def cmd_validate(args) -> int:
    machine = prof.load()
    print(f"Validating against {prof.model_name(machine)} "
          f"({machine['embroidery']['max_field_mm']['width']:.0f} x "
          f"{machine['embroidery']['max_field_mm']['height']:.0f} mm, "
          f"{machine['embroidery']['max_stitches_per_pattern']:,} stitches max)\n")

    worst = None
    checked = 0
    for path in _expand(args.files):
        try:
            info = analyze.describe(path)
        except Exception as exc:
            print(f"{path}\n  ERROR    [unreadable] {exc}")
            worst = analyze.ERROR
            continue

        findings = analyze.validate(info, machine,
                                    cloth=_spec_field(path, args, "cloth"),
                                    hoop=_spec_field(path, args, "hoop"))
        checked += 1
        level = analyze.worst_severity(findings)
        status = "OK" if level is None else level.upper()
        print(f"{path}  [{status}]  "
              f"{info.width_mm:.1f}x{info.height_mm:.1f} mm, "
              f"{info.real_stitches:,} stitches, {info.thread_count} colour(s)")
        _print_findings(findings)
        if level == analyze.ERROR or worst == analyze.ERROR:
            worst = analyze.ERROR
        elif level == analyze.WARNING and worst != analyze.ERROR:
            worst = analyze.WARNING

    if not checked and worst is None:
        print("No files matched.", file=sys.stderr)
        return 2
    return 1 if worst == analyze.ERROR else 0


def cmd_convert(args) -> int:
    if args.scale is not None:
        print(f"Scaling by {args.scale}x changes stitch spacing: the stitch count "
              f"stays the same while the design grows or shrinks. Scaling more than "
              f"~10% usually needs re-digitizing, not resizing.", file=sys.stderr)

    out = convert.convert(
        args.source,
        args.output,
        pes_version=args.pes_version,
        center=args.center,
        scale=args.scale,
        mirror_axis=args.mirror,
    )
    line = f"Wrote {out}"
    if out.suffix.lower() == ".pes":
        line += f"  ({convert.pes_signature(out)})"
    print(line)

    info = analyze.describe(out)
    findings = analyze.validate(info)
    if findings:
        _print_findings(findings)
    return 1 if analyze.worst_severity(findings) == analyze.ERROR else 0


def cmd_preview(args) -> int:
    paths = _expand(args.files)
    outs = _resolve_output(paths, args.output, ".preview.svg", kind="previews")
    for path, out in zip(paths, outs):
        preview.render_svg(path, out, show_jumps=args.show_jumps)
        print(f"Wrote {out}")
        if args.png:
            png = out.with_suffix(".png")
            try:
                preview.render_png(path, png)
                print(f"Wrote {png}")
            except Exception as exc:
                print(f"PNG render failed ({exc}). Install Pillow: "
                      f"pip install Pillow", file=sys.stderr)
    return 0


def cmd_proof(args) -> int:
    """Independent photorealistic render, by Ink/Stitch rather than by us.

    The value is that nothing in this repo touches it: the PES is re-read by
    Ink/Stitch's own importer and drawn by its own engine. Our writer and our
    renderer can share a wrong assumption and agree with each other; this
    cannot.
    """
    paths = _expand(args.files)
    outs = _resolve_output(paths, args.output, ".proof.png", kind="proofs")
    failed = 0
    for path, out in zip(paths, outs):
        try:
            r = proof.render(path, out, dpi=args.dpi, timeout=args.timeout)
        except Exception as e:                       # noqa: BLE001 - report, continue
            failed += 1
            print(f"FAILED   {path.name}: {e}", file=sys.stderr)
            continue
        print(f"\nWrote {r['path']}")
        print(f"  {r['px'][0]} x {r['px'][1]} px at {r['dpi']} dpi, "
              f"{r['bytes']:,} bytes")
    if not failed:
        print("\nRendered by Ink/Stitch from the file on disk — thread width, "
              "texture and sheen are to scale.\nIf the linework looks thin "
              "here, it will be thin on fabric.")
    return 1 if failed else 0


def cmd_coverage(args) -> int:
    """Report artwork that never got stitched.

    The one class of defect nothing else here can see: `validate` reads the PES
    alone and cannot know what the design was meant to be, and the render looks
    correct because whatever *is* stitched is stitched correctly.
    """
    rep = coverage.analyse(
        args.design, args.source,
        skip_hex=tuple(args.skip or ()),
        tolerance_mm=args.tolerance,
        min_patch_mm2=args.min_patch,
        overlay=args.overlay,
    )
    print(f"\n{rep.design.name}  vs  {rep.source.name}")
    print(f"  artwork        {rep.ink_mm2:,.0f} mm² of stitchable ink")
    print(f"  covered        {rep.covered_mm2:,.0f} mm²  ({rep.covered_pct:.0f}%) "
          f"within {rep.tolerance_mm} mm of a stitch")
    print(f"  NOT stitched   {rep.missing_mm2:,.0f} mm²  ({rep.missing_pct:.0f}%)")

    if rep.patches:
        print(f"\n  largest unstitched patches (>= {args.min_patch} mm²):")
        for p in rep.patches[:10]:
            print(f"    {p.area_mm2:7.1f} mm²  at ({p.cx_pct:3.0f}%, {p.cy_pct:3.0f}%) "
                  f"of the artwork")
    if args.overlay:
        print(f"\n  Wrote {args.overlay}  (orange = artwork, blue = stitched)")

    # Centrelining a stroke legitimately leaves its outer half uncovered, so a
    # low single-digit miss is normal. A third of the artwork missing is what
    # LemonY looked like when every solid mass had been reduced to a skeleton.
    if rep.missing_pct >= 25:
        print(f"\n  FAIL: {rep.missing_pct:.0f}% of the artwork is unstitched. Solid "
              f"areas are probably being centrelined — use "
              f"-Layer '<hex>:auto' so they are filled instead.")
        return 1
    if rep.missing_pct >= 12:
        print(f"\n  WARNING: {rep.missing_pct:.0f}% unstitched. Expected for pure "
              f"line art (the outer half of every stroke); suspicious otherwise. "
              f"Check the overlay.")
    return 0


def cmd_render(args) -> int:
    paths = _expand(args.files)
    outs = _resolve_output(paths, args.output, ".render.png", kind="renders")
    for path, out in zip(paths, outs):
        r = preview.render_realistic(
            path, out,
            fabric=args.fabric,
            px_per_mm=args.scale,
            show_jumps=args.show_jumps,
        )
        print(f"\nWrote {r['path']}")
        print(f"  {r['width_mm']} x {r['height_mm']} mm at {r['px_per_mm']:.0f} px/mm")
        print(f"  {r['stitch_runs']:,} stitch runs drawn"
              + (f", {r['jumps_drawn']:,} jumps overlaid" if args.show_jumps else ""))
        if not args.show_jumps:
            auto = prof.load().get("trimming", {}).get(
                "auto_trims_jumps_within_color", False)
            if auto:
                print("  (travel is trimmed by the machine, so it is not drawn)")
            else:
                print("  (this is the piece AFTER you snip the jump floats. This "
                      "machine does not trim jumps within a colour, so straight "
                      "off the machine it will have threads lying across it — "
                      "use --show-jumps to see them)")
    return 0


def cmd_palette(args) -> int:
    if args.regenerate:
        print(f"Wrote {palette.regenerate()}")
        return 0
    if args.match:
        for colour in args.match:
            print(f"\n{colour}")
            for m in palette.nearest(colour, args.count):
                print(f"  #{m['pec_index']:<3} {m['hex']}  dE {m['delta_e']:>6}  "
                      f"{m['name']}")
        return 0
    for e in palette.load():
        print(f"{e['pec_index']:>3}  {e['hex']}  {e['name']}")
    return 0


def cmd_drives(args) -> int:
    drives = usb.find_removable_drives()
    if not drives:
        print("No removable drives detected.")
        return 0
    for d in drives:
        gb = d["total_bytes"] / 1e9 if d["total_bytes"] else 0
        free = d["free_bytes"] / 1e9 if d["free_bytes"] else 0
        flag = "" if d["filesystem"].upper() == "FAT32" else "   <- not FAT32"
        print(f"{d['root']}  {d['label'] or '(no label)':<16} "
              f"{d['filesystem'] or '?':<8} {free:.1f}/{gb:.1f} GB free{flag}")
    return 0


def cmd_stage(args) -> int:
    # Design Database Transfer reads from an ordinary folder on this PC, so
    # there is nothing to copy — but the validation gate still has to run, and
    # the wireless route has a trap USB does not. With no --to, act as that
    # pre-flight.
    if not args.to:
        paths = _expand(args.files)
        failed = 0
        for path in paths:
            info = analyze.describe(path)
            findings = analyze.validate(info)
            blocking = [f for f in findings if f.severity == analyze.ERROR]
            tag = "BLOCKED" if blocking else "ready  "
            print(f"{tag}  {path.name}  "
                  f"{info.width_mm:.1f}x{info.height_mm:.1f} mm, "
                  f"{info.real_stitches:,} stitches, {info.thread_count} colour(s)")
            _print_findings([f for f in findings if f.severity != analyze.INFO],
                            indent="           ")
            failed += bool(blocking)

        print(f"\n{len(paths) - failed} ready for transfer, {failed} blocked.")
        if failed:
            return 1
        print("\nDesign Database Transfer checklist:")
        print("  1. Point DDT's folder pane at this folder, add the file to the")
        print("     writing list, and transfer. DDT does NOT check that a design")
        print("     fits the hoop — that is what the check above is for.")
        print("  2. On the machine, retrieve from the WIRELESS POCKET (the third")
        print("     destination icon), not from the machine's memory.")
        print("     A design of the same name saved to memory on an earlier run")
        print("     is still there and is NOT updated by a transfer. Selecting it")
        print("     silently stitches the old version.")
        print("  3. Wirelessly transferred designs are deleted when the machine is")
        print("     switched off. Save to machine memory only if you want to keep")
        print("     it — and delete the previous copy first.")
        return 0

    for w in usb.check_destination(args.to):
        print(f"WARNING  {w}", file=sys.stderr)

    results = usb.stage(
        _expand(args.files),
        args.to,
        subfolder=None if args.root else args.subfolder,
        force=args.force,
    )
    failed = 0
    for r in results:
        if r.copied:
            print(f"copied   {r.source.name} -> {r.target}")
            _print_findings([f for f in r.findings if f.severity != analyze.INFO],
                            indent="           ")
        else:
            failed += 1
            print(f"SKIPPED  {r.source.name}: {r.reason}")
            _print_findings(r.findings, indent="           ")
    print(f"\n{sum(1 for r in results if r.copied)} copied, {failed} skipped.")
    if any(r.copied for r in results):
        print("Eject the drive from Windows before unplugging it.")
    return 1 if failed else 0


def _fmt_host(h: network.Host, verbose: bool = False) -> str:
    tag = "  <<< BROTHER" if h.looks_like_machine else ""
    icmp = "up  " if h.icmp else "silent"
    line = f"  {h.ip:<16} {h.mac:<18} {icmp}  {h.vendor}{tag}"
    if verbose:
        if h.hostname:
            line += f"\n{'':<20}name: {h.hostname}"
        if h.open_ports:
            ports = ", ".join(f"{p} ({n})" for p, n in sorted(h.open_ports.items()))
            line += f"\n{'':<20}open: {ports}"
        if h.snmp_sysdescr:
            line += f"\n{'':<20}snmp: {h.snmp_sysdescr}"
    return line


def cmd_discover(args) -> int:
    if not network.load_oui():
        print("Downloading the IEEE OUI registry for vendor lookups (~4 MB)...")
        network.download_oui()

    if args.list_interfaces:
        for n in network.local_subnets():
            gw = n["gateway"] or "(no gateway)"
            print(f"  {n['interface']:<30} {n['ip']:<16} {n['network']:<20} gw={gw}")
        return 0

    net = args.network
    if net is None:
        nets = [n for n in network.local_subnets() if n["gateway"]]
        if not nets:
            print("error: no interface with a default gateway", file=sys.stderr)
            return 2
        net = nets[0]["network"]

    mode = "deep probe" if args.deep else "ARP + vendor lookup"
    print(f"Scanning {net} ({mode})...\n")
    hosts = network.discover(net, deep=args.deep)

    for h in hosts:
        print(_fmt_host(h, verbose=args.deep))

    matches = [h for h in hosts if h.looks_like_machine]
    print(f"\n{len(hosts)} host(s) found.")

    if matches:
        print(f"\n{len(matches)} Brother device(s) identified:")
        for h in matches:
            print(f"  {h.ip}  ({h.mac})")
            for e in h.evidence:
                print(f"      - {e}")
        print("\nUse that IP in Design Database Transfer to pair.")
        return 0

    if not args.deep:
        print("\nNo Brother-registered MAC found — but that test alone is weak,")
        print("because the machine may use an OEM radio module whose OUI belongs")
        print("to the module vendor, not Brother. Re-run with --deep to")
        print("fingerprint services rather than just MAC vendors.")
        return 1

    print("\nNo Brother device on this subnet. In rough order of likelihood:")
    print("  1. The machine is powered off, or its wireless is disabled.")
    print("     It only holds a DHCP lease while switched on.")
    print("  2. It joined a different SSID — a 2.4 GHz or guest network on a")
    print("     separate subnet from this PC. Check the machine's own screen for")
    print("     its IP (wireless LAN key), then: stitch probe <ip>")
    print("  3. Client/AP isolation on the network is hiding it from this host.")
    print("  4. It never joined: the machine is 2.4 GHz only and cannot do")
    print("     WPA/WPA2 Enterprise.")
    print(f"\n  Known Brother OUI prefixes checked: "
          f"{', '.join(sorted(k[:2] + ':' + k[2:4] + ':' + k[4:6] for k in network.brother_ouis()))}")
    return 1


def cmd_probe(args) -> int:
    if not network.load_oui():
        print("Downloading the IEEE OUI registry (~4 MB)...")
        network.download_oui()

    h = network.fingerprint(args.ip)
    print(f"\n{h.ip}")
    print(f"  icmp          {'responds' if h.icmp else 'no response'}")
    print(f"  mac           {h.mac or '(not in ARP cache — different subnet?)'}")
    if h.vendor:
        print(f"  vendor        {h.vendor}")
    if h.hostname:
        print(f"  hostname      {h.hostname}")
    if h.snmp_sysdescr:
        print(f"  snmp          {h.snmp_sysdescr}")
    if h.banner:
        print(f"  banner        {h.banner}")
    if h.open_ports:
        print("  open ports")
        for p, n in sorted(h.open_ports.items()):
            print(f"                {p:<6} {n}")
    else:
        print("  open ports    none of the probed ports answered")

    print()
    if h.looks_like_machine:
        print("  IDENTIFIED AS A BROTHER DEVICE. Evidence:")
        for e in h.evidence:
            print(f"    - {e}")
        print(f"\n  Pair with {h.ip} in Design Database Transfer.")
        return 0
    if not h.icmp and not h.open_ports:
        print("  Nothing at this address is responding.")
        return 1
    print("  Responding, but nothing identifies it as Brother.")
    print("  Confirm the IP on the machine's own screen (wireless LAN key).")
    return 0


def cmd_trace(args) -> int:
    from . import raster

    # Only pass values the user actually supplied, so TraceSettings stays the
    # single source of truth for defaults. Duplicating them here let the CLI
    # default silently shadow a retuned module default.
    opts = {
        "size_mm": args.size,
        "colors": args.colors,
        "underlay": not args.no_underlay,
        "outline": not args.no_outline,
        "remove_background": not args.keep_background,
        "lock_stitches": not args.no_locks,
    }
    for cli_name, field in (("density", "density_mm"), ("angle", "fill_angle_deg"),
                            ("min_region", "min_region_mm2"),
                            ("min_stitch", "min_stitch_mm"),
                            ("pull_comp", "pull_comp_mm"), ("travel", "travel_mm"),
                            ("bg_tolerance", "bg_tolerance"),
                            ("max_density", "max_density_per_mm2")):
        v = getattr(args, cli_name)
        if v is not None:
            opts[field] = v
    s = raster.TraceSettings(**opts)
    out = Path(args.output) if args.output else Path(args.image).with_suffix(".pes")
    report = raster.trace(args.image, out, s)

    print(f"\nWrote {out}")
    print(f"  size          {report.width_mm:.1f} x {report.height_mm:.1f} mm")
    print(f"  stitches      {report.total_stitches:,}")
    print(f"  colours       {len(report.layers)}")
    fit = ("good" if report.quant_error <= 22
           else "moderate" if report.quant_error <= 40 else "POOR")
    print(f"  colour fit    {report.quant_error}/255  ({fit})")
    print("  layers        (colour is a LABEL — load whatever thread you like;"
          " dE is preview fidelity only)")
    for i, layer in enumerate(report.layers, 1):
        t = layer["thread"]
        note = "  <- palette substitute, keeps layers separate" \
            if t.get("substituted") else ""
        print(f"    {i}. {t['hex']} {t['name']:<18} "
              f"{layer['area_mm2']:>7.0f} mm²  {layer['stitches']:>6,} st  "
              f"dE {t['delta_e']}{note}")
    if report.dropped_regions:
        # Report the setting actually used, not the raw CLI arg — that is None
        # unless the user passed one, since TraceSettings owns the defaults.
        print(f"  dropped       {report.dropped_regions} region(s) below "
              f"{s.min_region_mm2} mm²")
    for n in report.notes:
        print(f"  note          {n}")

    info = analyze.describe(out)
    findings = analyze.validate(info)
    if findings:
        print()
        _print_findings(findings)
    if args.preview:
        p = out.with_suffix(".preview.svg")
        preview.render_svg(out, p)
        print(f"\n  preview       {p}")
    return 1 if analyze.worst_severity(findings) == analyze.ERROR else 0


def cmd_flatten(args) -> int:
    from . import flatten as flat

    out = Path(args.output) if args.output else \
        Path(args.image).with_name(Path(args.image).stem + "_flat.png")

    before = flat.stroke_stats(args.image)
    r = flat.flatten(args.image, out, colors=args.colors,
                     texture_px=args.texture, min_region_px=args.min_region_px)
    after = flat.stroke_stats(out)

    print(f"\nWrote {out}")
    print(f"                        before      after")
    print(f"  unique colours  {r.unique_before:>10,} {r.unique_after:>10,}")
    print(f"  regions <1 mm²  {r.tiny_before:>10,} {r.tiny_after:>10,}")
    if before and after:
        print(f"  typical stroke  {before['median_mm']:>9.2f}mm {after['median_mm']:>9.2f}mm", end="")
        print("   (>=1.2mm is safe)" if after["median_mm"] >= 1.2 else "   still thin")
    print(f"\nNow trace it:\n  stitch trace {out} --colors {args.colors - 1}")
    return 0


def cmd_recolor(args) -> int:
    from . import recolor as rc

    out = Path(args.output) if args.output else \
        Path(args.image).with_name(Path(args.image).stem + "_recolored.png")

    mappings = []
    for m in args.map or []:
        if "=" not in m:
            print(f"error: --map needs SRC=DST, got '{m}'", file=sys.stderr)
            return 2
        a, b = m.split("=", 1)
        mappings.append((a, b))

    if args.list:
        import numpy as np
        from PIL import Image as _I
        arr = np.array(_I.open(args.image).convert("RGBA"))
        print(f"\n{args.image} flat palette:")
        for c, f in rc.image_palette(arr):
            print(f"  {c if isinstance(c,str) else rc._hex(c)}  {f*100:5.1f}%")
        return 0

    r = rc.recolor(args.image, out, mappings=mappings, drops=args.drop,
                   drop_lighter_than=args.drop_lighter_than)

    print(f"\nWrote {out}")
    print("  before:")
    for h, pct in r.palette_before:
        print(f"    {h}  {pct:5.1f}%")
    for h, n in r.dropped:
        print(f"  dropped  {h}  ({n:,} px -> left unstitched, fabric shows)")
    for a, b, n in r.mapped:
        print(f"  mapped   {a} -> {b}  ({n:,} px)")
    print("  after (opaque only):")
    for h, pct in r.palette_after:
        print(f"    {h}  {pct:5.1f}%")
    print(f"\nNow trace it:\n  stitch trace {out} --colors {len(r.palette_after)}")
    return 0


def cmd_fix_pes(args) -> int:
    fixed = 0
    for path in _expand(args.files):
        if convert.read_pes_hoop(path) is None:
            print(f"  {path}: not a recognised PES")
            continue
        before_size = path.stat().st_size
        info_before = analyze.describe(path)
        # Rewrite through write_pes so the origin convention is applied too,
        # not just the header/section repair.
        pattern = analyze.read_pattern(path)
        convert.write_pes(pattern, path)
        if args.keep_pes_section:
            convert.patch_pes_hoop(path)
        info_after = analyze.describe(path)

        ok = (round(info_before.width_mm, 1) == round(info_after.width_mm, 1)
              and info_before.real_stitches == info_after.real_stitches
              and info_before.thread_count == info_after.thread_count)
        print(f"  {path.name:<24} {before_size:>8,}B -> {path.stat().st_size:>8,}B  "
              f"hoop={convert.read_pes_hoop(path)}  "
              f"{info_after.width_mm:.1f}x{info_after.height_mm:.1f}mm  "
              f"{'geometry preserved' if ok else 'GEOMETRY CHANGED - CHECK'}")
        fixed += 1
    print(f"\n{fixed} file(s) processed.")
    return 0


def cmd_build(args) -> int:
    from . import build as B
    specs = B.load_specs(args.name or None)
    if not specs:
        # Nothing to build is the normal state of a fresh clone, not a failure:
        # designs/specs/*.json is gitignored because a spec points at artwork.
        print("No designs declared yet. Put artwork in art/originals/ and write "
              "a spec — see designs/specs/README.md.")
        return 0
    manifest = B.read_manifest()
    plan = [(s, B.is_stale(s, manifest["designs"].get(s["name"]))) for s in specs]

    if args.check:
        for spec, why in plan:
            print(f"  {spec['name']:<12} {why or 'up to date'}")
        return 1 if any(w for _, w in plan) else 0

    todo = [s for s, why in plan if why or args.all]
    if not todo:
        print("everything up to date; --all to rebuild anyway")
        return 0
    for spec, why in plan:
        if spec not in todo:
            continue
        print(f"--- {spec['name']} ({why or 'forced'})")
        manifest["designs"][spec["name"]] = B.build_one(spec)
        m = manifest["designs"][spec["name"]]["measured"]
        print(f"  {m['width_mm']}x{m['height_mm']} mm, {m['stitches']:,} stitches, "
              f"{m['colours']} colour(s), ~{m['runtime_min']:.0f} min"
              + (f"  [{m['worst']}]" if m["worst"] else ""))
    manifest["updated_at"] = B.datetime.now(B.timezone.utc).replace(microsecond=0).isoformat()
    B.write_manifest(manifest)
    print(f"\nprovenance recorded in {B.rel(B.MANIFEST)}")
    return 0


def cmd_audit(args) -> int:
    from . import build as B
    issues = B.audit()
    if not issues:
        specs = B.load_specs()
        print(f"layout clean: {len(specs)} design(s) declared, built, and accounted for")
        return 0
    for sev, msg in issues:
        print(f"  {sev:<5} {msg}")
    errors = sum(1 for s, _ in issues if s == "error")
    print(f"\n{errors} error(s), {len(issues) - errors} warning(s)")
    return 1 if errors else 0


def cmd_machine(args) -> int:
    m = prof.load()
    print(f"{prof.model_name(m)}  ({m['machine']['family']})")
    e = m["embroidery"]
    print(f"  field         {e['max_field_mm']['width']:.0f} x "
          f"{e['max_field_mm']['height']:.0f} mm "
          f"({e['max_field_in']['width']} x {e['max_field_in']['height']} in)")
    print(f"  max stitches  {e['max_stitches_per_pattern']:,} per pattern")
    # Flag the embroidery rate as fixed. Printed bare it reads as a ceiling,
    # and "slow the machine down" is the first thing people try on a thread
    # break — impossible here, and a waste of the attempt.
    fixed = " (fixed, not adjustable)" if e.get("speed_is_fixed") else ""
    print(f"  speed         {e['max_speed_spm']} spm embroidery{fixed}, "
          f"{m['sewing']['speed_spm']['min']}-{m['sewing']['speed_spm']['max']} spm sewing")
    print(f"  reads         {', '.join(m['file_formats']['embroidery_read'])}")
    print(f"  memory        {m['memory']['embroidery']['max_patterns']} designs / "
          f"{m['memory']['embroidery']['max_kb']} KB")
    print(f"  needle        {m['consumables']['embroidery_needle']}")
    print(f"  bobbin        {m['consumables']['bobbin']['part']} "
          f"({m['consumables']['bobbin']['class']})")
    print(f"  wireless      {m['wireless']['standards']} @ {m['wireless']['band_ghz']} GHz")
    print(f"  PES default   v{m['pes']['recommended_version']}")
    print(f"\n  profile       {prof.PROFILE_PATH}")
    return 0


# --------------------------------------------------------------------------- #


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="stitch",
        description="Generate, vet, and transfer embroidery designs for a "
                    "Brother SE700.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("machine", help="show the active machine profile")
    s.set_defaults(func=cmd_machine)

    s = sub.add_parser("info", help="describe design files")
    s.add_argument("files", nargs="+")
    s.add_argument("-v", "--verbose", action="store_true")
    s.set_defaults(func=cmd_info)

    s = sub.add_parser("validate", help="check designs against the machine profile")
    s.add_argument("files", nargs="+")
    s.add_argument("--cloth", metavar="RRGGBB",
                   help="fabric colour to judge the thread colours against. "
                        "Defaults to the design's spec if one exists; without "
                        "either, that check is skipped rather than guessed.")
    s.add_argument("--hoop", metavar="ID",
                   help="frame this design is stitched in, e.g. SA431. Neither "
                        "the file nor the machine records it. Defaults to the "
                        "design's spec; without either, only the full "
                        "100x100 mm field is checked.")
    s.set_defaults(func=cmd_validate)

    s = sub.add_parser("convert", help="convert a design to another format")
    s.add_argument("source")
    s.add_argument("output")
    s.add_argument("--pes-version", choices=convert.PES_VERSIONS,
                   help="PES version to write (default: profile's recommendation)")
    s.add_argument("--center", action="store_true",
                   help="recentre the design on the origin")
    s.add_argument("--scale", type=float,
                   help="scale factor; changes density, use sparingly")
    s.add_argument("--mirror", choices=("x", "y", "both"),
                   help="mirror the design. NOT needed for normal stitching — "
                        "only when the stitched face is viewed from the other "
                        "side (reverse applique, underside work, transfers)")
    s.set_defaults(func=cmd_convert)

    s = sub.add_parser("preview", help="render an SVG inside the hoop boundary")
    s.add_argument("files", nargs="+")
    s.add_argument("-o", "--output", help="output path (single input only)")
    s.add_argument("--show-jumps", action="store_true")
    s.add_argument("--png", action="store_true", help="also render a PNG (needs Pillow)")
    s.set_defaults(func=cmd_preview)

    s = sub.add_parser("flatten",
                       help="strip simulated stitch texture / posterise before tracing")
    s.add_argument("image")
    s.add_argument("-o", "--output")
    s.add_argument("--colors", type=int, default=5,
                   help="flat colours INCLUDING background (default 5)")
    s.add_argument("--texture", type=int, default=9,
                   help="median filter size; raise if texture survives (default 9)")
    s.add_argument("--min-region-px", type=int, default=60)
    s.set_defaults(func=cmd_flatten)

    s = sub.add_parser("recolor",
                       help="merge or drop colours (dropped = left unstitched)")
    s.add_argument("image")
    s.add_argument("-o", "--output")
    s.add_argument("--list", action="store_true",
                   help="just print the image's flat palette and exit")
    s.add_argument("--map", action="append", metavar="SRC=DST",
                   help="merge SRC colour into DST (repeatable)")
    s.add_argument("--drop", action="append", metavar="HEX",
                   help="leave this colour unstitched (repeatable)")
    s.add_argument("--drop-lighter-than", type=int, metavar="LUMA",
                   help="drop everything brighter than this 0-255 luma")
    s.set_defaults(func=cmd_recolor)

    s = sub.add_parser("trace", help="auto-digitize an image into a stitch file")
    s.add_argument("image")
    s.add_argument("-o", "--output", help="output path (default: alongside input)")
    s.add_argument("--size", type=float,
                   help="longest edge in mm (default: fit the hoop)")
    s.add_argument("--colors", type=int, default=5,
                   help="thread colours to reduce to (default 5)")
    s.add_argument("--density", type=float,
                   help="fill row spacing in mm (default 0.4)")
    s.add_argument("--angle", type=float,
                   help="fill angle in degrees (default 45)")
    s.add_argument("--min-region", type=float,
                   help="drop regions smaller than this many mm2 (default 4)")
    s.add_argument("--no-underlay", action="store_true")
    s.add_argument("--no-outline", action="store_true")
    s.add_argument("--min-stitch", type=float, metavar="MM",
                   help="drop stitches shorter than this; sub-0.5mm stitches "
                        "saw the thread through the needle eye (default 0.5)")
    s.add_argument("--no-locks", action="store_true",
                   help="omit tie-in/tie-off. Runs will unravel after a trim — "
                        "only for designs you will not wear or wash")
    s.add_argument("--pull-comp", type=float, metavar="MM",
                   help="grow each colour to offset fabric pull-in and overlap "
                        "adjacent colours (default 0.2; knits want 0.3-0.4)")
    s.add_argument("--travel", type=float, metavar="MM",
                   help="walk around holes rather than jump, up to this far "
                        "(default 60; 0 disables)")
    s.add_argument("--max-density", type=float, metavar="N",
                   help="ceiling on needle penetrations per mm2 that travel may "
                        "create (default 16). Raising it trades thread breaks "
                        "for fewer floats to snip; 0 removes the limit")
    s.add_argument("--keep-background", action="store_true",
                   help="do not strip a uniform background")
    s.add_argument("--bg-tolerance", type=int, metavar="N",
                   help="how close to the corner colour counts as background "
                        "(default 32). Lower it when a pale design element — a "
                        "white hat on cream — is being eaten by the strip")
    s.add_argument("--preview", action="store_true", help="also render an SVG preview")
    s.set_defaults(func=cmd_trace)

    s = sub.add_parser("proof",
                       help="photorealistic render of the PES, by Ink/Stitch (independent check)")
    s.add_argument("files", nargs="+")
    s.add_argument("-o", "--output")
    s.add_argument("--dpi", type=int, default=300, help="render DPI (default 300)")
    s.add_argument("--timeout", type=int, default=600, metavar="SEC")
    s.set_defaults(func=cmd_proof)

    s = sub.add_parser("coverage",
                       help="find artwork that never got stitched (needs the source image)")
    s.add_argument("design", help="finished .pes/.dst")
    s.add_argument("--source", required=True, help="the artwork it was made from")
    s.add_argument("--skip", action="append", metavar="RRGGBB",
                   help="colour deliberately left unstitched; repeatable")
    s.add_argument("--tolerance", type=float, default=0.4, metavar="MM",
                   help="how far from a stitch still counts as covered (default 0.4)")
    s.add_argument("--min-patch", type=float, default=2.0, metavar="MM2",
                   help="ignore unstitched patches smaller than this (default 2)")
    s.add_argument("--overlay", metavar="PNG",
                   help="write an orange/blue overlay image for eyeballing")
    s.set_defaults(func=cmd_coverage)

    s = sub.add_parser("render",
                       help="realistic PNG of the finished embroidery")
    s.add_argument("files", nargs="+")
    s.add_argument("-o", "--output")
    s.add_argument("--fabric", default="#F2F0EB",
                   help="fabric colour behind the stitches (default off-white)")
    s.add_argument("--scale", type=float, default=8.0,
                   help="pixels per mm (default 8)")
    s.add_argument("--show-jumps", action="store_true",
                   help="overlay travel in magenta to judge pathing")
    s.set_defaults(func=cmd_render)

    s = sub.add_parser("palette", help="Brother 64-colour thread palette")
    s.add_argument("--match", nargs="+", metavar="HEX",
                   help="find the nearest Brother threads to these colours")
    s.add_argument("-n", "--count", type=int, default=3)
    s.add_argument("--regenerate", action="store_true",
                   help="rewrite the palette CSV from pyembroidery")
    s.set_defaults(func=cmd_palette)

    s = sub.add_parser("fix-pes",
                       help="repair PES files so Brother software previews them correctly")
    s.add_argument("files", nargs="+")
    s.add_argument("--keep-pes-section", action="store_true",
                   help="only patch the hoop code; leave pyembroidery's PES "
                        "section in place (previews wrongly on 4x4 machines)")
    s.set_defaults(func=cmd_fix_pes)

    s = sub.add_parser("drives", help="list removable drives")
    s.set_defaults(func=cmd_drives)

    s = sub.add_parser("discover", help="find the machine on the local network")
    s.add_argument("--network", help="CIDR to scan (default: primary interface)")
    s.add_argument("--deep", action="store_true",
                   help="also port-scan, SNMP-query and reverse-resolve each host")
    s.add_argument("--list-interfaces", action="store_true",
                   help="just show local interfaces and subnets")
    s.set_defaults(func=cmd_discover)

    s = sub.add_parser("probe", help="fingerprint one IP address")
    s.add_argument("ip")
    s.set_defaults(func=cmd_probe)

    s = sub.add_parser("stage",
                       help="pre-flight designs for the machine; with --to, also copy to USB")
    s.add_argument("files", nargs="+")
    s.add_argument("--to", metavar="DRIVE",
                   help="USB drive to copy to. Omit for the Design Database "
                        "Transfer route, which reads from a PC folder — the "
                        "validation gate still runs.")
    s.add_argument("--subfolder", default="BROTHER")
    s.add_argument("--root", action="store_true",
                   help="copy to the drive root instead of a subfolder")
    s.add_argument("--force", action="store_true",
                   help="copy even if validation reports errors")
    s.set_defaults(func=cmd_stage)

    s = sub.add_parser("build",
                       help="build designs from designs/specs/*.json and record provenance")
    s.add_argument("name", nargs="*", help="design name(s); default is everything stale")
    s.add_argument("--all", action="store_true",
                   help="rebuild even designs whose recorded build still stands")
    s.add_argument("--check", action="store_true",
                   help="report what would rebuild and why, without building")
    s.set_defaults(func=cmd_build)

    s = sub.add_parser("audit",
                       help="check the repository layout and build provenance")
    s.set_defaults(func=cmd_audit)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
