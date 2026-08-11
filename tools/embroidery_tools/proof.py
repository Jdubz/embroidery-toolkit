"""Photorealistic proof of a finished PES, rendered by Ink/Stitch itself.

The point of this over `preview.render_realistic` is independence. This repo's
own renderer draws what this repo *thinks* it wrote; if the writer and the
renderer share a wrong assumption, both agree and the error is invisible. Here
the file is read back from disk by a completely separate implementation —
Ink/Stitch's PES importer — and rendered by its own engine. A defect that
survives that has to be in the file.

Two Ink/Stitch extensions, chained:

    input          .pes -> SVG   (its own PES reader, not pyembroidery's)
    png_realistic  SVG  -> PNG   (thread texture, sheen, real thread width)

`png_realistic` shells out to `inkscape.exe` to rasterize, and Ink/Stitch does
not know where Inkscape lives, so it must be on PATH for the child process or
the render dies with CommandNotFound.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

INKSTITCH = Path(os.environ.get("APPDATA", "")) / (
    r"inkscape\extensions\inkstitch\inkstitch\bin\inkstitch.exe")

INKSCAPE_CANDIDATES = (
    Path(r"C:\Program Files\Inkscape\bin\inkscape.exe"),
    Path(r"C:\Program Files (x86)\Inkscape\bin\inkscape.exe"),
)


def _find_inkscape() -> Path | None:
    for c in INKSCAPE_CANDIDATES:
        if c.exists():
            return c
    return None


def _run(args: list[str], out: Path, env: dict, timeout: int) -> None:
    """Run inkstitch, capturing stdout to a file.

    inkstitch.exe is a GUI-subsystem binary and writes its result to stdout;
    shell redirection yields an empty file, so the pipe is drained here.
    """
    with open(out, "wb") as fh:
        proc = subprocess.Popen([str(INKSTITCH), *args], stdout=fh,
                                stderr=subprocess.PIPE, env=env)
        try:
            _, err = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            raise RuntimeError(
                f"Ink/Stitch did not finish in {timeout}s. It may be showing a "
                f"modal dialog, which headless nobody can answer.")
    if proc.returncode != 0 or out.stat().st_size == 0:
        msg = (err or b"").decode("utf-8", "replace").strip()
        raise RuntimeError(f"Ink/Stitch failed (exit {proc.returncode}):\n{msg}")


def render(design: str | Path, out_png: str | Path, *, dpi: int = 300,
           timeout: int = 600) -> dict:
    design, out_png = Path(design), Path(out_png)
    if not design.exists():
        raise FileNotFoundError(design)
    if not INKSTITCH.exists():
        raise RuntimeError(f"Ink/Stitch not found at {INKSTITCH}")

    inkscape = _find_inkscape()
    if inkscape is None:
        raise RuntimeError(
            "Inkscape not found. png_realistic shells out to inkscape.exe to "
            "rasterize; without it the render fails with CommandNotFound.")

    env = dict(os.environ)
    env["PATH"] = f"{inkscape.parent}{os.pathsep}{env.get('PATH', '')}"

    with tempfile.TemporaryDirectory() as td:
        svg = Path(td) / "from_pes.svg"
        # Ink/Stitch's own PES reader, deliberately not pyembroidery's.
        _run(["--extension=input", str(design)], svg, env, timeout)
        out_png.parent.mkdir(parents=True, exist_ok=True)
        _run([f"--extension=png_realistic", f"--dpi={dpi}", str(svg)],
             out_png, env, timeout)

    from PIL import Image
    with Image.open(out_png) as im:
        size = im.size
    return {"path": out_png, "px": size, "dpi": dpi,
            "bytes": out_png.stat().st_size}
