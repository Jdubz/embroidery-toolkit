"""Convert designs into a format the machine reads, at a version it accepts.

PES version matters more than it looks. Every PES file carries a PEC block that
all Brother machines read, but the surrounding PES structure differs by version.
v1 (`#PES0001`) is the conservative choice and what this repo defaults to.
"""

from __future__ import annotations

import struct
from pathlib import Path

import pyembroidery as pe

from . import profile as prof

# pyembroidery's PES writer accepts these version strings.
PES_VERSIONS = ("1", "6")

# PES header hoop codes.
PES_HOOP_100x100 = 0
PES_HOOP_130x180 = 1

# Byte offset of the hoop field, per version. v1 writes scale-to-fit first;
# v6 puts the hoop code immediately after the PEC pointer.
_HOOP_OFFSET = {b"#PES0001": 14, b"#PES0060": 12}


def patch_pes_hoop(path: str | Path, code: int | None = None) -> int | None:
    """Set the PES header's hoop field to match the machine.

    pyembroidery hard-codes this to 1 = 130x180 mm regardless of the design or
    the target machine. Brother's own Design Database Transfer reads it to lay
    out its preview, so a 4x4 design arrives sitting small and off-centre inside
    a 130x180 frame — it looks cropped to a corner even though the stitches are
    perfect. The machine stitches from the PEC block and is unaffected, but the
    preview is wrong and alarming.

    Returns the code written, or None if the file is not a PES we know.
    """
    path = Path(path)
    if code is None:
        w, h = prof.max_field_mm()
        code = PES_HOOP_100x100 if (w <= 100 and h <= 100) else PES_HOOP_130x180

    try:
        with path.open("r+b") as f:
            sig = f.read(8)
            offset = _HOOP_OFFSET.get(sig)
            if offset is None:
                return None
            f.seek(offset)
            f.write(struct.pack("<H", code))
    except OSError:
        return None
    return code


def rewrite_pes_pec_only(path: str | Path, hoop_code: int | None = None) -> bool:
    """Strip the PES section, keeping the header and the PEC block.

    pyembroidery's PES section is positioned for a 130x180 mm hoop and cannot be
    corrected by patching the hoop code alone. `write_pes_sewsegheader` builds
    the object transform from hard-coded `hoop_width = 1300, hoop_height = 1800`
    plus a fixed +350/+100 offset, so a 4x4 design lands outside a 100x100 field.
    Brother's Design Database Transfer renders that section, which is why a file
    with perfect stitches previews as a corner — while the same design exported
    as DST looks right, DST having no such section.

    A PES whose header declares zero block objects, wrapping a complete PEC
    block, is a well-established form that converters emit routinely. Readers
    fall back to the PEC block, which is also what the machine stitches from, so
    geometry and colours are preserved exactly.

    Returns True if rewritten.
    """
    path = Path(path)
    try:
        data = path.read_bytes()
    except OSError:
        return False
    if not data.startswith(b"#PES"):
        return False
    pec_offset = struct.unpack("<I", data[8:12])[0]
    if pec_offset <= 0 or pec_offset >= len(data):
        return False

    if hoop_code is None:
        w, h = prof.max_field_mm()
        hoop_code = PES_HOOP_100x100 if (w <= 100 and h <= 100) else PES_HOOP_130x180

    # Minimal #PES0001 header with distinct_block_objects = 0, mirroring
    # pyembroidery's own empty-pattern path. 22 bytes, then the PEC block.
    header = bytearray()
    header += b"#PES0001"
    header += struct.pack("<I", 22)
    header += struct.pack("<H", 0x01)       # scale to fit
    header += struct.pack("<H", hoop_code)  # hoop size
    header += struct.pack("<H", 0x0000)     # zero block objects
    header += struct.pack("<H", 0x0000)
    header += struct.pack("<H", 0x0000)
    assert len(header) == 22, len(header)

    path.write_bytes(bytes(header) + data[pec_offset:])
    return True


def read_pes_hoop(path: str | Path) -> int | None:
    """Hoop code from a PES header, or None if unreadable / not a known PES."""
    try:
        with Path(path).open("rb") as f:
            sig = f.read(8)
            offset = _HOOP_OFFSET.get(sig)
            if offset is None:
                return None
            f.seek(offset)
            data = f.read(2)
            if len(data) < 2:
                return None
            return struct.unpack("<H", data)[0]
    except OSError:
        return None


def convert(
    src: str | Path,
    dst: str | Path,
    *,
    pes_version: str | None = None,
    center: bool = False,
    scale: float | None = None,
    mirror_axis: str | None = None,
) -> Path:
    """Read `src`, optionally transform, write `dst`. Returns the output path."""
    src, dst = Path(src), Path(dst)
    pattern = pe.read(str(src))
    if pattern is None:
        raise ValueError(f"Could not read {src}")

    if mirror_axis:
        pattern = mirror(pattern, mirror_axis)

    if scale is not None:
        if scale <= 0:
            raise ValueError("scale must be positive")
        # Stitch coordinates scale, but stitch *count* does not — so density
        # changes inversely. Callers are warned in the CLI.
        pattern = pattern.get_pattern_scaled(scale)

    if center:
        pattern.move_center_to_origin()

    ext = dst.suffix.lower()
    if ext == ".pes":
        version = pes_version or prof.recommended_pes_version()
        if str(version) not in PES_VERSIONS:
            raise ValueError(
                f"PES version {version!r} not supported by the writer "
                f"(available: {', '.join(PES_VERSIONS)})"
            )
        return write_pes(pattern, dst, version)

    dst.parent.mkdir(parents=True, exist_ok=True)
    pe.write(pattern, str(dst), {})
    return dst


def mirror(pattern, axis: str = "x"):
    """Return a mirrored copy. `axis` is 'x' (left-right), 'y' (top-bottom), 'both'.

    Normal flatbed embroidery needs none of this: the fabric is hooped right side
    up, the needle works from above, and the design forms the right way round on
    the face. The SE700 even has an opt-in Mirror Image key on the panel, which
    would make no sense if every file needed pre-mirroring.

    It is genuinely needed when the stitched face will be viewed from the other
    side — reverse applique, stitching on the underside of a piece, or artwork
    destined for a transfer.
    """
    p = pattern.copy()
    sx = -1 if axis in ("x", "both") else 1
    sy = -1 if axis in ("y", "both") else 1
    for s in p.stitches:
        s[0] *= sx
        s[1] *= sy
    return p


def write_pes(pattern, path: str | Path, version: str | None = None) -> Path:
    """Write a PES using the origin convention Brother's software expects.

    pyembroidery centres a pattern on the origin, so stitches run -w/2..+w/2.
    Design Database Transfer reads PEC coordinates as running 0..width, so a
    centred design is drawn with its left and top halves off-canvas — only the
    bottom-right quadrant shows. Confirmed against DDT: shifting the design so
    it starts at (0, 0) renders correctly, while the identical centred file does
    not. DST is unaffected, which is why it always looked right.

    The pattern is copied before translating, so callers keep their original.
    """
    path = Path(path)
    p = pattern.copy()
    b = p.bounds()
    p.translate(-b[0], -b[1])
    settings = {"pes version": str(version or prof.recommended_pes_version())}
    path.parent.mkdir(parents=True, exist_ok=True)
    pe.write(p, str(path), settings)
    finalize_pes(path)
    return path


def pes_origin(path: str | Path) -> tuple[int, int] | None:
    """Minimum stitch coordinate of a PES/PEC, for checking the convention."""
    try:
        p = pe.read(str(path))
    except Exception:
        return None
    if p is None or not p.stitches:
        return None
    b = p.bounds()
    return int(b[0]), int(b[1])


def finalize_pes(path: str | Path, keep_pes_section: bool = False) -> None:
    """Make a pyembroidery PES safe for Brother software on this machine.

    Default is to strip the PES section entirely — see `rewrite_pes_pec_only`
    for why patching the hoop code alone is not enough.
    """
    if keep_pes_section:
        patch_pes_hoop(path)
    elif not rewrite_pes_pec_only(path):
        patch_pes_hoop(path)


def pes_signature(path: str | Path) -> str:
    """Read back the 8-byte PES version signature, e.g. '#PES0001'."""
    with Path(path).open("rb") as f:
        return f.read(8).decode("ascii", errors="replace")


def writable_extensions() -> list[str]:
    return sorted(f["extension"] for f in pe.supported_formats() if "writer" in f)
