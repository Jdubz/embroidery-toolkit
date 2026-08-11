"""Spec-driven builds, provenance, and a layout audit.

Two problems this solves, both observed in this repo rather than imagined.

**Sprawl.** Artwork accumulated in `images/` with no rule about what belonged
there: originals sat beside generated derivatives, a `lemon-cat` folder moved
under `Finals` mid-session and silently broke every path referring to it, and
19 throwaway review renders were filed next to the source SVGs. Nothing could
tell you which of 40 files still mattered.

**No provenance.** A `.pes` recorded nothing about where it came from. Which
artwork? At what size? With which settings, and which version of the tools? The
answer lived in a chat log or a project note written from memory, and when a
design was rebuilt six times in an afternoon the notes drifted from the files.

The fix is that **a design is declared, not remembered**. `designs/specs/<name>.json`
states its source and settings; `build()` executes exactly that and records what
it did. The layout is then enforceable, because every file is either declared,
generated from something declared, or sprawl.

    art/originals/    inbound artwork, exactly as received. Never generated.
    art/prepared/     derivatives, each produced by some spec's prepare step.
    designs/specs/    the declarations. Source of truth.
    designs/out/      .pes only, one per spec. This is the DDT staging folder,
                      which is why it stays flat and free of anything else.
    build/            everything else generated: proofs, reviews, manifest.
    photos/           stitch-out photographs. Evidence, not art.
    work/             scratch. Nothing here is ever read by tooling.

**Version identity comes from hashing the tool scripts**, not from git — this
working copy has a .gitignore but no repository, so there is no commit to name.
A build records the SHA-256 of every script that shaped it, so "which version
made this" is answerable by comparison rather than by trust.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SPECS = REPO / "designs" / "specs"
OUT = REPO / "designs" / "out"
PREPARED = REPO / "art" / "prepared"
ORIGINALS = REPO / "art" / "originals"
BUILD = REPO / "build"
MANIFEST = BUILD / "manifest.json"

#: Scripts whose contents change what a build produces. Hashed into every
#: record so a design can be tied to the exact tooling that made it.
TOOL_SCRIPTS = [
    "tools/svg_to_pes.ps1", "tools/svg_prep.py", "tools/satin_params.py",
    "tools/svg_subpath_filter.py", "tools/embroidery_tools/svgpath.py",
    "tools/embroidery_tools/measure.py", "tools/embroidery_tools/convert.py",
    "reference/machine-profile.json",
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(path: Path) -> str:
    """Repo-relative path for display, falling back to absolute.

    `relative_to` raises for anything outside the repo, and this is used inside
    error and warning messages — so raising here would replace a useful warning
    with a traceback from the reporting code itself.
    """
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return path.as_posix()


@lru_cache(maxsize=1)
def _external_version(cmd: tuple[str, ...], pattern: str = r"(.+)") -> str | None:
    try:
        r = subprocess.run(list(cmd), capture_output=True, text=True, timeout=30,
                           encoding="utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError):
        return None
    text = (r.stdout or r.stderr or "").strip()
    m = re.search(pattern, text.splitlines()[0]) if text else None
    return m.group(1).strip() if m else None


def script_hashes() -> dict[str, str]:
    """Hash only the scripts. Kept separate from `toolchain()` because staleness
    is checked once per design and must not pay for launching Inkscape to ask
    its version — that turned `audit` into three subprocess spawns."""
    return {p: sha256(REPO / p) for p in TOOL_SCRIPTS if (REPO / p).exists()}


def toolchain() -> dict:
    """Everything that can change a build's output, captured by identity."""
    inkstitch_ver = None
    vfile = Path(os.environ.get("APPDATA", "")) / "inkscape/extensions/inkstitch/inkstitch/VERSION"
    if vfile.exists():
        inkstitch_ver = vfile.read_text(encoding="utf-8", errors="replace").strip()
    try:
        import pyembroidery
        pyemb = getattr(pyembroidery, "__version__", "unknown")
    except Exception:
        pyemb = None
    return {
        "python": sys.version.split()[0],
        "pyembroidery": pyemb,
        "inkstitch": inkstitch_ver,
        "inkscape": _external_version(
            (r"C:\Program Files\Inkscape\bin\inkscape.exe", "--version"), r"(Inkscape [^\s]+)"),
        "scripts": script_hashes(),
    }


def validate_spec(spec: dict, where: str) -> None:
    """Fail on a malformed spec here, with the field named.

    Without this a missing key surfaces as a KeyError from somewhere inside the
    build, after the prepare step has already written a file.
    """
    if spec.get("name") != Path(where).stem:
        raise ValueError(f"{where}: name '{spec.get('name')}' must match the filename")
    b = spec.get("build")
    if not isinstance(b, dict):
        raise ValueError(f"{where}: missing 'build' section")
    for key in ("tool", "input", "artwork_mm"):
        if key not in b:
            raise ValueError(f"{where}: build is missing '{key}'")
    if b["tool"] != "svg_to_pes":
        raise ValueError(f"{where}: unknown build tool '{b['tool']}'")
    if not isinstance(b["artwork_mm"], (int, float)):
        raise ValueError(f"{where}: build.artwork_mm must be a number")
    if b.get("skip") is not None and not isinstance(b["skip"], list):
        raise ValueError(f"{where}: build.skip must be a list of hex colours")
    p = spec.get("prepare")
    if p is not None:
        if not isinstance(p, dict):
            raise ValueError(f"{where}: 'prepare' must be an object")
        for key in ("tool", "input", "output"):
            if key not in p:
                raise ValueError(f"{where}: prepare is missing '{key}'")
        if not (REPO / "tools" / f"{p['tool']}.py").exists():
            raise ValueError(f"{where}: no such prepare tool: tools/{p['tool']}.py")


def load_specs(names: list[str] | None = None) -> list[dict]:
    specs = []
    for p in sorted(SPECS.glob("*.json")):
        try:
            spec = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{rel(p)}: invalid JSON: {exc}") from None
        validate_spec(spec, rel(p))
        spec["_path"] = p
        specs.append(spec)
    if names:
        want = {n.lower() for n in names}
        specs = [s for s in specs if s["name"].lower() in want]
        missing = want - {s["name"].lower() for s in specs}
        if missing:
            raise ValueError(f"no spec for: {', '.join(sorted(missing))}")
    return specs


def _run(cmd: list[str], label: str, quiet: bool) -> str:
    """Run a build step and **show what it said**.

    Swallowing stdout here was a real loss, not a tidiness choice: the pipeline
    reports the satin underlay banding and the measured-vs-declared width
    cross-check on stdout, and that cross-check exists precisely to make a
    misreading loud. Captured and discarded, it could never fire.

    Decoded as UTF-8 rather than the console codepage, which mangled the em
    dashes in the pipeline's own output.
    """
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    out = (r.stdout or "").strip()
    if r.returncode != 0:
        tail = ((r.stderr or "") + "\n" + out).strip()[-800:]
        raise RuntimeError(f"{label} failed (exit {r.returncode}):\n{tail}")
    if not quiet:
        for line in out.splitlines():
            if line.strip():
                print(f"    {line.strip()}")
    if r.stderr and r.stderr.strip():
        for line in r.stderr.strip().splitlines():
            print(f"    ! {line.strip()}", file=sys.stderr)
    return out


def _prepare(spec: dict, quiet: bool) -> Path | None:
    step = spec.get("prepare")
    if not step:
        return None
    src, dst = REPO / step["input"], REPO / step["output"]
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not quiet:
        print(f"  prepare  {step['tool']}  -> {rel(dst)}")
    _run([sys.executable, str(REPO / "tools" / f"{step['tool']}.py"), str(src), str(dst),
          *[str(a) for a in step.get("args", [])]], step["tool"], quiet)
    if not dst.exists():
        raise RuntimeError(f"{step['tool']} reported success but wrote nothing to {rel(dst)}")
    return dst


def ps_args(spec: dict, src: Path, dst: Path) -> list[str]:
    """The svg_to_pes.ps1 command line for a spec. Pure, so it can be tested.

    `skip` is comma-joined into one argument on purpose: passing argv directly
    means PowerShell never gets to split it, so the .ps1 splits on commas
    itself. Sending each colour as its own `-Skip` would bind only the last.
    """
    b = spec["build"]
    args = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-File", str(REPO / "tools" / "svg_to_pes.ps1"),
            "-Svg", str(src), "-Out", str(dst), "-ArtworkMm", str(b["artwork_mm"])]
    if b.get("skip"):
        args += ["-Skip", ",".join(b["skip"])]
    for k, v in (b.get("options") or {}).items():
        if v is True:                     # a PowerShell [switch]
            args.append(f"-{k}")
        elif v is False or v is None:     # explicitly off, or "leave default"
            continue
        else:
            args += [f"-{k}", str(v)]
    return args


def _stitch_out(spec: dict, quiet: bool) -> Path:
    b = spec["build"]
    src, dst = REPO / b["input"], OUT / f"{spec['name']}.pes"
    dst.parent.mkdir(parents=True, exist_ok=True)
    args = ps_args(spec, src, dst)
    if not quiet:
        print(f"  build    svg_to_pes    -> {rel(dst)}")
    _run(args, "svg_to_pes", quiet)
    if not dst.exists():
        raise RuntimeError(f"svg_to_pes reported success but wrote nothing to {rel(dst)}")
    return dst


def measure(pes: Path) -> dict:
    from . import analyze
    info = analyze.describe(pes)
    findings = analyze.validate(info)
    return {
        "width_mm": round(info.width_mm, 1), "height_mm": round(info.height_mm, 1),
        "stitches": info.real_stitches, "colours": info.thread_count,
        "colour_changes": info.color_changes,
        "jumps": info.jumps, "trims": info.trims,
        "runtime_min": round(info.runtime_minutes(), 1),
        "cleanup_min": round(info.cleanup_minutes(), 1),
        # The numbers that have actually decided things here: needle penetrations
        # per mm2 at the peak, and mid-run stitches under the machine minimum.
        "density_max_per_mm2": info.density_max,
        "short_stitches_midrun": info.short_stitches_midrun,
        "findings": [f.code for f in findings],
        "worst": analyze.worst_severity(findings),
    }


def build_one(spec: dict, quiet: bool = False) -> dict:
    if not quiet:
        print(f"{spec['name']}")
    prepared = _prepare(spec, quiet)
    pes = _stitch_out(spec, quiet)
    inputs = [REPO / spec["build"]["input"]]
    if spec.get("prepare"):
        inputs.insert(0, REPO / spec["prepare"]["input"])
    if prepared and prepared not in inputs:
        inputs.append(prepared)
    return {
        "name": spec["name"],
        "built_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "spec": {"path": rel(spec["_path"]), "sha256": sha256(spec["_path"])},
        "inputs": [{"path": rel(p), "sha256": sha256(p)} for p in inputs if p.exists()],
        "output": {"path": rel(pes), "sha256": sha256(pes), "bytes": pes.stat().st_size},
        "toolchain": toolchain(),
        "measured": measure(pes),
    }


def read_manifest() -> dict:
    """Always returns a dict with a 'designs' mapping, whatever is on disk.

    A manifest that is missing, empty, hand-edited or from an older shape must
    degrade to "nothing is built" — every design then rebuilds, which is
    correct — rather than raising from a KeyError halfway through a build.
    """
    m: dict = {}
    if MANIFEST.exists():
        try:
            loaded = json.loads(MANIFEST.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                m = loaded
        except json.JSONDecodeError:
            print(f"warning: {rel(MANIFEST)} is not valid JSON; treating every "
                  f"design as unbuilt", file=sys.stderr)
    if not isinstance(m.get("designs"), dict):
        m["designs"] = {}
    return m


def write_manifest(m: dict) -> None:
    """Write atomically. This is the provenance record; a half-written manifest
    would claim designs are unbuilt and quietly lose their history."""
    BUILD.mkdir(parents=True, exist_ok=True)
    tmp = MANIFEST.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(m, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    os.replace(tmp, MANIFEST)


def is_stale(spec: dict, record: dict | None) -> str | None:
    """Why `spec` needs rebuilding, or None if the recorded build still stands."""
    if record is None:
        return "never built"
    pes = OUT / f"{spec['name']}.pes"
    if not pes.exists():
        return "output missing"
    if sha256(pes) != record["output"]["sha256"]:
        return "output changed on disk since it was built"
    if sha256(spec["_path"]) != record["spec"]["sha256"]:
        return "spec changed"
    for entry in record["inputs"]:
        p = REPO / entry["path"]
        if not p.exists():
            return f"input missing: {entry['path']}"
        if sha256(p) != entry["sha256"]:
            return f"input changed: {entry['path']}"
    now = script_hashes()
    was = record.get("toolchain", {}).get("scripts", {})
    changed = [k for k in set(now) | set(was) if now.get(k) != was.get(k)]
    if changed:
        return "toolchain changed: " + ", ".join(sorted(Path(c).name for c in changed))
    return None


# --------------------------------------------------------------------------- #
# Layout audit


def audit() -> list[tuple[str, str]]:
    """Every complaint about the tree, as (severity, message)."""
    issues: list[tuple[str, str]] = []
    specs = load_specs()
    manifest = read_manifest()
    by_name = {s["name"]: s for s in specs}

    # designs/out is the DDT staging folder: one .pes per spec, nothing else.
    for f in sorted(OUT.glob("*")) if OUT.exists() else []:
        if f.is_dir():
            issues.append(("error", f"{rel(f)}: designs/out must stay flat for DDT"))
        elif f.suffix.lower() != ".pes":
            issues.append(("error", f"{rel(f)}: only .pes belongs in designs/out "
                                    f"(generated extras go in build/)"))
        elif f.stem not in by_name:
            issues.append(("error", f"{rel(f)}: no spec declares this design"))

    for name, spec in by_name.items():
        why = is_stale(spec, manifest.get("designs", {}).get(name))
        if why:
            issues.append(("warn", f"{name}: {why}"))
        # A build input the spec's own prepare step generates is not missing —
        # it just has not been made yet, which the staleness check already says.
        made_here = {spec["prepare"]["output"]} if spec.get("prepare") else set()
        for key in ("prepare", "build"):
            step = spec.get(key)
            if not step or step["input"] in made_here:
                continue
            if not (REPO / step["input"]).exists():
                issues.append(("error", f"{name}: {key} input missing: {step['input']}"))

    # art/prepared is generated. Anything there that no spec produces is sprawl.
    declared = {s["prepare"]["output"] for s in specs if s.get("prepare")}
    for f in sorted(PREPARED.glob("*")) if PREPARED.exists() else []:
        if f.is_file() and rel(f) not in declared:
            issues.append(("warn", f"{rel(f)}: in art/prepared but no spec generates it"))

    # A proof older than the design it depicts is worse than no proof: it is the
    # gate that shows what will actually land on fabric, and a stale one shows
    # the previous build while looking current.
    for name, spec in by_name.items():
        pes = OUT / f"{name}.pes"
        proof = BUILD / "proofs" / f"{name}.proof.png"
        if not pes.exists():
            continue
        if not proof.exists():
            issues.append(("warn", f"{name}: no proof in build/proofs — "
                                   f"run: stitch proof designs/out/{name}.pes"))
        elif proof.stat().st_mtime < pes.stat().st_mtime:
            issues.append(("warn", f"{name}: proof is older than the design it shows"))

    # Legacy locations that the layout retired.
    for legacy in ("images", "designs/source"):
        if (REPO / legacy).exists():
            issues.append(("error", f"{legacy}/: retired location, see docs/13"))

    for f in sorted(REPO.glob("*")):
        if f.is_file() and f.suffix.lower() in (".png", ".jpg", ".jpeg", ".svg", ".webp", ".pes"):
            issues.append(("warn", f"{f.name}: loose asset in the repo root"))
    return issues
