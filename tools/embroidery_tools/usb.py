"""Stage validated designs onto a USB drive for the machine.

The machine reads designs from the root of a FAT32 drive; a top-level BROTHER
folder also works and keeps things tidy. Staging refuses to copy anything that
fails validation, because a design the machine will not list is worse than no
design at all — you find out standing at the machine.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from . import analyze
from . import profile as prof


@dataclass
class StageResult:
    source: Path
    target: Path | None
    copied: bool
    findings: list
    reason: str = ""


def find_removable_drives() -> list[dict]:
    """List removable volumes on Windows. Returns [] on other platforms."""
    import sys

    if not sys.platform.startswith("win"):
        return []

    import ctypes
    import string

    drives = []
    bitmask = ctypes.windll.kernel32.GetLogicalDrives()
    for i, letter in enumerate(string.ascii_uppercase):
        if not (bitmask >> i) & 1:
            continue
        root = f"{letter}:\\"
        # 2 == DRIVE_REMOVABLE
        if ctypes.windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(root)) != 2:
            continue
        name_buf = ctypes.create_unicode_buffer(261)
        fs_buf = ctypes.create_unicode_buffer(261)
        ok = ctypes.windll.kernel32.GetVolumeInformationW(
            ctypes.c_wchar_p(root), name_buf, 261, None, None, None, fs_buf, 261
        )
        free = total = 0
        try:
            usage = shutil.disk_usage(root)
            free, total = usage.free, usage.total
        except OSError:
            pass
        drives.append(
            {
                "root": root,
                "label": name_buf.value if ok else "",
                "filesystem": fs_buf.value if ok else "",
                "free_bytes": free,
                "total_bytes": total,
            }
        )
    return drives


def stage(
    sources: list[str | Path],
    destination: str | Path,
    *,
    subfolder: str | None = "BROTHER",
    force: bool = False,
) -> list[StageResult]:
    """Validate then copy each design to the destination drive.

    `force` copies despite validation errors. Warnings never block.
    """
    dest_root = Path(destination)
    if not dest_root.exists():
        raise FileNotFoundError(f"Destination {dest_root} does not exist")

    target_dir = dest_root / subfolder if subfolder else dest_root
    results: list[StageResult] = []

    for src in sources:
        src = Path(src)
        if not src.is_file():
            results.append(
                StageResult(src, None, False, [], reason="source file not found")
            )
            continue

        try:
            info = analyze.describe(src)
            findings = analyze.validate(info)
        except Exception as exc:  # unreadable file — report, do not abort the batch
            results.append(
                StageResult(src, None, False, [], reason=f"unreadable: {exc}")
            )
            continue

        blocking = [f for f in findings if f.severity == analyze.ERROR]
        if blocking and not force:
            results.append(
                StageResult(
                    src,
                    None,
                    False,
                    findings,
                    reason=f"{len(blocking)} blocking issue(s); use --force to override",
                )
            )
            continue

        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / src.name
        shutil.copy2(src, target)
        results.append(StageResult(src, target, True, findings))

    return results


def check_destination(destination: str | Path) -> list[str]:
    """Warn about a destination that the machine may not read."""
    warnings: list[str] = []
    dest = Path(destination)
    machine = prof.load()

    for d in find_removable_drives():
        if Path(d["root"]) == Path(str(dest.anchor)):
            fs = (d["filesystem"] or "").upper()
            want = machine["usb"]["filesystem"].upper()
            if fs and fs != want:
                warnings.append(
                    f"Drive {d['root']} is formatted {fs}; the machine expects {want}."
                )
            break
    else:
        if dest.anchor:
            warnings.append(
                f"{dest.anchor} is not a removable drive — staging to it anyway."
            )
    return warnings
