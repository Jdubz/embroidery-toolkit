"""Render a design to SVG, drawn inside the machine's real hoop boundary.

pyembroidery can already dump an SVG of the stitches. This module adds the thing
that actually prevents wasted stabilizer: the 100 x 100 mm field drawn to scale
around the design, so you can see the clearance before you hoop anything.
"""

from __future__ import annotations

from pathlib import Path

import pyembroidery as pe

from . import profile as prof

PX_PER_MM = 4  # SVG user units per mm — big enough to read, small enough to open.


def _polyline(points: list[tuple[float, float]], color: str, width: float) -> str:
    pts = " ".join(f"{x:.2f},{y:.2f}" for x, y in points)
    return (
        f'<polyline points="{pts}" fill="none" stroke="{color}" '
        f'stroke-width="{width:.2f}" stroke-linecap="round" stroke-linejoin="round"/>'
    )


def render_svg(
    src: str | Path,
    dst: str | Path,
    *,
    show_jumps: bool = False,
    background: str = "#ffffff",
) -> Path:
    src, dst = Path(src), Path(dst)
    pattern = pe.read(str(src))
    if pattern is None:
        raise ValueError(f"Could not read {src}")

    field_w, field_h = prof.max_field_mm()
    pad_mm = 8.0
    canvas_w = (field_w + 2 * pad_mm) * PX_PER_MM
    canvas_h = (field_h + 2 * pad_mm) * PX_PER_MM

    min_x, min_y, max_x, max_y = pattern.bounds()
    design_w_mm = prof.units_to_mm(max_x - min_x)
    design_h_mm = prof.units_to_mm(max_y - min_y)

    # Centre the design inside the drawn field, matching how the machine
    # positions a pattern in the hoop by default.
    off_x_mm = pad_mm + (field_w - design_w_mm) / 2 - prof.units_to_mm(min_x)
    off_y_mm = pad_mm + (field_h - design_h_mm) / 2 - prof.units_to_mm(min_y)

    def project(x: float, y: float) -> tuple[float, float]:
        return (
            (prof.units_to_mm(x) + off_x_mm) * PX_PER_MM,
            (prof.units_to_mm(y) + off_y_mm) * PX_PER_MM,
        )

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_w:.0f}" '
        f'height="{canvas_h:.0f}" viewBox="0 0 {canvas_w:.0f} {canvas_h:.0f}">',
        f'<rect width="100%" height="100%" fill="{background}"/>',
        # Hoop / stitchable field.
        f'<rect x="{pad_mm * PX_PER_MM:.1f}" y="{pad_mm * PX_PER_MM:.1f}" '
        f'width="{field_w * PX_PER_MM:.1f}" height="{field_h * PX_PER_MM:.1f}" '
        f'fill="none" stroke="#c8c8c8" stroke-width="1.5" stroke-dasharray="6 4"/>',
        # Centre cross-hairs.
        f'<line x1="{(pad_mm + field_w / 2) * PX_PER_MM:.1f}" y1="{pad_mm * PX_PER_MM:.1f}" '
        f'x2="{(pad_mm + field_w / 2) * PX_PER_MM:.1f}" '
        f'y2="{(pad_mm + field_h) * PX_PER_MM:.1f}" stroke="#e8e8e8" stroke-width="1"/>',
        f'<line x1="{pad_mm * PX_PER_MM:.1f}" y1="{(pad_mm + field_h / 2) * PX_PER_MM:.1f}" '
        f'x2="{(pad_mm + field_w) * PX_PER_MM:.1f}" '
        f'y2="{(pad_mm + field_h / 2) * PX_PER_MM:.1f}" stroke="#e8e8e8" stroke-width="1"/>',
    ]

    for block, thread in pattern.get_as_stitchblock():
        if len(block) < 2:
            continue
        color = thread.hex_color() if thread is not None else "#333333"
        run: list[tuple[float, float]] = []
        for x, y, cmd in block:
            command = cmd & pe.COMMAND_MASK
            if command == pe.STITCH:
                run.append(project(x, y))
            else:
                if len(run) >= 2:
                    parts.append(_polyline(run, color, 1.6))
                run = [project(x, y)] if command in (pe.JUMP, pe.TRIM) else []
        if len(run) >= 2:
            parts.append(_polyline(run, color, 1.6))

    if show_jumps:
        jump_pts: list[tuple[float, float]] = []
        for x, y, cmd in pattern.stitches:
            if (cmd & pe.COMMAND_MASK) == pe.JUMP:
                jump_pts.append(project(x, y))
        for px, py in jump_pts:
            parts.append(
                f'<circle cx="{px:.1f}" cy="{py:.1f}" r="2" fill="none" '
                f'stroke="#ff00aa" stroke-width="0.8"/>'
            )

    label = (
        f"{src.name} — {design_w_mm:.1f} x {design_h_mm:.1f} mm "
        f"({prof.mm_to_in(design_w_mm):.2f} x {prof.mm_to_in(design_h_mm):.2f} in) "
        f"in a {field_w:.0f} x {field_h:.0f} mm field"
    )
    parts.append(
        f'<text x="{pad_mm * PX_PER_MM:.1f}" y="{canvas_h - 6:.1f}" '
        f'font-family="monospace" font-size="11" fill="#666">{_escape(label)}</text>'
    )
    parts.append("</svg>")

    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text("\n".join(parts), encoding="utf-8")
    return dst


def render_png(src: str | Path, dst: str | Path) -> Path:
    """Delegate to pyembroidery's PNG writer (needs Pillow installed).

    Note this draws jump stitches, so a design with many trims looks like a
    scribble. Prefer `render_realistic` to see what will actually be sewn.
    """
    src, dst = Path(src), Path(dst)
    pattern = pe.read(str(src))
    if pattern is None:
        raise ValueError(f"Could not read {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    pe.write(pattern, str(dst))
    return dst


def render_realistic(
    src: str | Path,
    dst: str | Path,
    *,
    fabric: str = "#F2F0EB",
    px_per_mm: float = 8.0,
    thread_mm: float = 0.45,
    show_jumps: bool = False,
    show_hoop: bool = True,
) -> dict:
    """Render what the finished embroidery will actually look like.

    Draws only real stitches — the travel between them is trimmed away on the
    machine and must not appear, which is exactly why the machine's own preview
    and pyembroidery's PNG writer both look like scribbles on a trim-heavy
    design. Threads get a darker body and a lighter core so direction and
    overlap read the way stitched thread does.

    `show_jumps` overlays the travel in magenta — useful for judging pathing,
    not for judging the result.
    """
    from PIL import Image, ImageDraw

    src, dst = Path(src), Path(dst)
    pattern = pe.read(str(src))
    if pattern is None:
        raise ValueError(f"Could not read {src}")

    field_w, field_h = prof.max_field_mm()
    pad = 6.0
    min_x, min_y, max_x, max_y = pattern.bounds()
    design_w = prof.units_to_mm(max_x - min_x)
    design_h = prof.units_to_mm(max_y - min_y)

    canvas_w = int((field_w + 2 * pad) * px_per_mm)
    canvas_h = int((field_h + 2 * pad) * px_per_mm)

    # Centre the design in the field, as the machine does.
    off_x = pad + (field_w - design_w) / 2 - prof.units_to_mm(min_x)
    off_y = pad + (field_h - design_h) / 2 - prof.units_to_mm(min_y)

    def proj(x, y):
        return ((prof.units_to_mm(x) + off_x) * px_per_mm,
                (prof.units_to_mm(y) + off_y) * px_per_mm)

    img = Image.new("RGB", (canvas_w, canvas_h), fabric)
    d = ImageDraw.Draw(img)

    if show_hoop:
        d.rectangle(
            [pad * px_per_mm, pad * px_per_mm,
             (pad + field_w) * px_per_mm, (pad + field_h) * px_per_mm],
            outline="#C9C4BA", width=2,
        )

    def lighten(hex_color: str, amount: float = 0.28) -> tuple:
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return (int(r + (255 - r) * amount),
                int(g + (255 - g) * amount),
                int(b + (255 - b) * amount))

    body_w = max(2, int(thread_mm * px_per_mm))
    core_w = max(1, int(body_w * 0.45))

    runs_by_thread: list[tuple[str, list]] = []
    for block, thread in pattern.get_as_stitchblock():
        color = thread.hex_color() if thread is not None else "#333333"
        run = []
        for x, y, cmd in block:
            if (cmd & pe.COMMAND_MASK) == pe.STITCH:
                run.append(proj(x, y))
            else:
                if len(run) >= 2:
                    runs_by_thread.append((color, run))
                run = []
        if len(run) >= 2:
            runs_by_thread.append((color, run))

    # Two passes so every thread body is laid down before any core highlight,
    # which stops later stitches looking like they float above earlier ones.
    for color, run in runs_by_thread:
        d.line(run, fill=color, width=body_w, joint="curve")
    for color, run in runs_by_thread:
        d.line(run, fill=lighten(color), width=core_w, joint="curve")

    jumps = 0
    if show_jumps:
        prev = None
        for x, y, cmd in pattern.stitches:
            c = cmd & pe.COMMAND_MASK
            p = proj(x, y)
            if c == pe.JUMP and prev is not None:
                d.line([prev, p], fill="#FF00AA", width=1)
                jumps += 1
            prev = p

    dst.parent.mkdir(parents=True, exist_ok=True)
    img.save(dst)
    return {
        "path": dst,
        "width_mm": round(design_w, 1),
        "height_mm": round(design_h, 1),
        "stitch_runs": len(runs_by_thread),
        "jumps_drawn": jumps,
        "px_per_mm": px_per_mm,
    }


def _escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
