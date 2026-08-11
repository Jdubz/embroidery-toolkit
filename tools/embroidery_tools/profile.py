"""Load the machine profile that every other module measures designs against."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PROFILE_PATH = REPO_ROOT / "reference" / "machine-profile.json"
PALETTE_PATH = REPO_ROOT / "reference" / "charts" / "brother-pec-thread-palette.csv"

# pyembroidery's native unit is 1/10 mm.
UNITS_PER_MM = 10.0
MM_PER_INCH = 25.4


@lru_cache(maxsize=1)
def load(path: Path | None = None) -> dict:
    """Return the parsed machine profile."""
    p = Path(path) if path else PROFILE_PATH
    if not p.is_file():
        raise FileNotFoundError(
            f"Machine profile not found at {p}. It is the source of truth for all "
            f"hoop and stitch limits, so tooling cannot run without it."
        )
    with p.open(encoding="utf-8") as f:
        return json.load(f)


def model_name(profile: dict | None = None) -> str:
    m = (profile or load())["machine"]
    return f"{m['brand']} {m['model']}"


def max_field_mm(profile: dict | None = None) -> tuple[float, float]:
    f = (profile or load())["embroidery"]["max_field_mm"]
    return float(f["width"]), float(f["height"])


def max_stitches(profile: dict | None = None) -> int:
    return int((profile or load())["embroidery"]["max_stitches_per_pattern"])


def design_limit(name: str, default=None, profile: dict | None = None):
    """One of the stitch-level limits from the profile's design_limits block.

    Separate from the envelope limits above because these constrain the
    stitches, not the design size, and because they are read from several
    places -- the tracer, the validator, and the Ink/Stitch generators -- which
    must not disagree.
    """
    return ((profile or load()).get("design_limits") or {}).get(name, default)


def min_stitch_mm(profile: dict | None = None) -> float:
    return float(design_limit("min_stitch_mm", 0.5, profile))


def readable_extensions(profile: dict | None = None) -> list[str]:
    return list((profile or load())["file_formats"]["embroidery_read"])


def recommended_pes_version(profile: dict | None = None) -> str:
    return str((profile or load())["pes"]["recommended_version"])


def units_to_mm(units: float) -> float:
    return units / UNITS_PER_MM


def mm_to_units(mm: float) -> float:
    return mm * UNITS_PER_MM


def mm_to_in(mm: float) -> float:
    return mm / MM_PER_INCH
