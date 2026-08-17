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
_HEX = re.compile(r"[0-9A-Fa-f]{6}")

SPECS = REPO / "designs" / "specs"
OUT = REPO / "designs" / "out"
#: Renders of the finished piece on its own cloth, one per design, named to
#: parallel designs/out/<Name>.pes exactly. Kept out of designs/out/ because
#: that directory is the Design Database Transfer staging folder and holds .pes
#: and nothing else.
PREVIEWS = REPO / "designs" / "previews"
PREPARED = REPO / "art" / "prepared"
ORIGINALS = REPO / "art" / "originals"
BUILD = REPO / "build"
MANIFEST = BUILD / "manifest.json"

#: Scripts whose contents change what a build produces. Hashed into every
#: record so a design can be tied to the exact tooling that made it.
TOOL_SCRIPTS = [
    "tools/svg_to_pes.ps1", "tools/svg_prep.py", "tools/satin_params.py",
    "tools/svg_subpath_filter.py", "tools/svg_knockout.py", "tools/svg_recolor.py",
    "tools/svg_dark_invert.py", "tools/svg_offset.py", "tools/svg_stroke.py",
    "tools/svg_edit.py", "tools/embroidery_tools/svggeom.py",
    "tools/embroidery_tools/svgdoc.py", "tools/embroidery_tools/svgops.py",
    # The raster path. Only designs whose spec names inkstitch_pipeline use
    # these, but the hash list is per-repo rather than per-design, so they mark
    # everything stale — same as svg_subpath_filter, which only Scream uses.
    "tools/inkstitch_pipeline.ps1", "tools/color_separate.py", "tools/svg_merge.py",
    "tools/embroidery_tools/svgpath.py",
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
    if b["tool"] not in ("svg_to_pes", "inkstitch_pipeline"):
        raise ValueError(f"{where}: unknown build tool '{b['tool']}'")
    if b["tool"] == "inkstitch_pipeline":
        # Vector sources go through svg_to_pes, which is the better path in every
        # way; this one exists for artwork that only ever was pixels. Layers are
        # not optional, and color_separate treats any colour that is in neither
        # --layer nor --skip as background, so a missing layer is silently
        # unstitched rather than an error.
        if not (b.get("options") or {}).get("Layer"):
            raise ValueError(f"{where}: inkstitch_pipeline needs build.options.Layer, "
                             "e.g. [\"E6B10C:fill\", \"25270A:auto\"], bottom layer first")
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

    # Last, so a structurally broken spec reports the structural fault first.
    #
    # The cloth is a DESIGN INPUT, not a note. Every design here uses bare fabric
    # as a colour, so the same stitch file on different cloth is a different
    # picture — and until this field existed the fabric was recorded nowhere but
    # the filename, which meant nothing could render a design as it will actually
    # look. It also decides fill density; see `_cloth_kind`.
    if not isinstance(spec.get("cloth"), str) or not _HEX.fullmatch(spec["cloth"]):
        raise ValueError(
            f"{where}: missing 'cloth' — the fabric colour this design is stitched "
            "on, as RRGGBB. It is what the preview is rendered against and what "
            "selects the fill density, and the design name is not a substitute.")

    # Optional, and it defaults to the included 4x4 rather than being required —
    # every design here so far is a 4x4 design. Declare it for anything stitched
    # in a smaller frame: the file does not record the hoop and the machine does
    # not detect it, so a spec is the only place the fact can live, and without
    # it a design too big for its frame validates clean.
    if spec.get("hoop") is not None:
        from . import profile as _prof
        if not isinstance(spec["hoop"], str) or _prof.hoop(spec["hoop"]) is None:
            known = ", ".join(str(h.get("id")) for h in _prof.hoops())
            raise ValueError(
                f"{where}: unknown 'hoop' {spec['hoop']!r} — the machine profile "
                f"knows {known}. Add the frame to reference/machine-profile.json "
                f"if you own one it does not list.")


def _in_dependency_order(specs: list[dict]) -> list[dict]:
    """Order specs so one reading another's prepare output builds after it.

    A design may take a sibling's prepared derivative as its own input —
    IHeartScreaming_on_black reads the SVG that IHeartScreaming_on_white's
    prepare step writes, so the sub-minimum vein surgery declared once applies
    to both. Filename order happened to satisfy that and was relied on. It is
    not a rule: renaming either design can invert it silently, and the dependent
    build then digitizes the *previous* run's intermediate — reproducible-looking
    output from a stale input, which is the exact failure the manifest exists to
    prevent. Ordering is derived from the declarations instead.
    """
    produced = {s["prepare"]["output"]: s["name"] for s in specs if s.get("prepare")}
    deps = {}
    for s in specs:
        need = set()
        for key in ("prepare", "build"):
            step = s.get(key)
            owner = produced.get(step["input"]) if step else None
            if owner and owner != s["name"]:
                need.add(owner)
        deps[s["name"]] = need

    ordered: list[dict] = []
    done: set[str] = set()
    remaining = list(specs)
    while remaining:
        ready = sorted((s for s in remaining if deps[s["name"]] <= done),
                       key=lambda s: s["name"])
        if not ready:
            stuck = ", ".join(sorted(s["name"] for s in remaining))
            raise ValueError(f"prepare inputs and outputs form a cycle among: {stuck}")
        ordered += ready
        done |= {s["name"] for s in ready}
        remaining = [s for s in remaining if s["name"] not in done]
    return ordered


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
    specs = _in_dependency_order(specs)
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


def _luminance(hexc: str) -> float:
    r, g, b = (int(hexc[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _cloth_kind(spec: dict) -> str:
    """'dark' or 'light', derived from the declared cloth colour.

    Derived rather than declared twice. The validated 0.4 mm fill density covers
    on white and speckles on black — the cloth between rows is invisible on
    cream and a dark dot at every penetration on black — so a light thread on
    dark cloth needs `fill_density_mm_dark`. That decision follows entirely from
    the fabric, and stating it separately is a second place to get it wrong: a
    spec that says `_on_black` and forgets the density is exactly the file that
    came off the machine speckled.

    `build.options.Cloth` still wins, because 'knits' is a property of the
    fabric that no colour can imply.

    Absent `cloth` reads as light rather than raising: `validate_spec` already
    rejects a spec without it, and this stays callable on a hand-built dict so
    `ps_args` remains the pure, testable function it is documented to be.
    """
    return "dark" if _luminance(spec.get("cloth") or "FFFFFF") < 128 else "light"


def _options(b: dict) -> list[str]:
    """Free-form `options` mapped onto PowerShell parameters.

    A list is comma-joined for the same reason `skip` is — see ps_args.
    """
    args: list[str] = []
    for k, v in (b.get("options") or {}).items():
        if v is True:                     # a PowerShell [switch]
            args.append(f"-{k}")
        elif v is False or v is None:     # explicitly off, or "leave default"
            continue
        elif isinstance(v, list):
            if v:
                args += [f"-{k}", ",".join(str(x) for x in v)]
        else:
            args += [f"-{k}", str(v)]
    return args


def ps_args(spec: dict, src: Path, dst: Path) -> list[str]:
    """The build command line for a spec. Pure, so it can be tested.

    `skip` is comma-joined into one argument on purpose: passing argv directly
    means PowerShell never gets to split it, so the .ps1 splits on commas
    itself. Sending each colour as its own `-Skip` would bind only the last —
    and PowerShell actually refuses a repeated parameter outright.
    """
    b = spec["build"]
    if b["tool"] == "inkstitch_pipeline":
        # Raster source. `artwork_mm` is the width of the whole CANVAS here, not
        # of the drawing inside it: color_separate scales the image, and the ink
        # usually has margin around it. The stitched size lands in the
        # manifest's `measured`, which is the number to trust.
        args = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-File", str(REPO / "tools" / "inkstitch_pipeline.ps1"),
                "-Image", str(src), "-Out", str(dst), "-WidthMm", str(b["artwork_mm"])]
        if b.get("skip"):
            args += ["-Skip", ",".join(b["skip"])]
        return args + _options(b)

    args = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-File", str(REPO / "tools" / "svg_to_pes.ps1"),
            "-Svg", str(src), "-Out", str(dst), "-ArtworkMm", str(b["artwork_mm"])]
    if b.get("skip"):
        args += ["-Skip", ",".join(b["skip"])]
    opts = _options(b)
    # Derived from the declared cloth unless the spec overrides it. Only passed
    # when it differs from svg_prep's default, so a light-cloth command line is
    # unchanged from before this existed.
    if "-Cloth" not in opts and _cloth_kind(spec) != "light":
        args += ["-Cloth", _cloth_kind(spec)]
    return args + opts


def _stitch_out(spec: dict, quiet: bool) -> Path:
    b = spec["build"]
    src, dst = REPO / b["input"], OUT / f"{spec['name']}.pes"
    dst.parent.mkdir(parents=True, exist_ok=True)
    tool = b["tool"]
    args = ps_args(spec, src, dst)
    if not quiet:
        print(f"  build    {tool:<13s}-> {rel(dst)}")
    _run(args, tool, quiet)
    if not dst.exists():
        raise RuntimeError(f"{tool} reported success but wrote nothing to {rel(dst)}")
    return dst


def measure(pes: Path, cloth: str | None = None, hoop: str | None = None) -> dict:
    from . import analyze
    info = analyze.describe(pes)
    findings = analyze.validate(info, cloth=cloth, hoop=hoop)
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


def preview_path(name: str) -> Path:
    return PREVIEWS / f"{name}.png"


def _preview(spec: dict, pes: Path, quiet: bool) -> Path | None:
    """Render the finished piece on its own cloth, beside every build.

    Human review is the only check that has ever caught the defects this repo
    keeps hitting — the yellow LemonCat eyes, the solid-block PissMuffy, the
    white keyline haloes around both Muffy faces. All were clean in `validate`,
    and all were obvious the moment they were drawn on the right fabric. So this
    is not optional output: it is generated on every build, at the same name as
    the .pes, so a design and its picture cannot drift apart.

    A render failure must not fail the build — the .pes is the deliverable and it
    is already written and measured by this point.
    """
    from . import preview as pv
    dst = preview_path(spec["name"])
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        pv.render_realistic(pes, dst, fabric="#" + spec["cloth"], px_per_mm=12.0)
    except Exception as exc:                       # noqa: BLE001 - see docstring
        print(f"  preview  FAILED ({exc.__class__.__name__}: {exc})")
        return None
    if not quiet:
        print(f"  preview  on #{spec['cloth']}  -> {rel(dst)}")
    return dst


def build_one(spec: dict, quiet: bool = False) -> dict:
    if not quiet:
        print(f"{spec['name']}")
    prepared = _prepare(spec, quiet)
    pes = _stitch_out(spec, quiet)
    _preview(spec, pes, quiet)
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
        "measured": measure(pes, spec.get("cloth"), spec.get("hoop")),
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

        # Same rule for the preview, and it matters more: the proof shows thread
        # at scale on nothing, the preview shows the piece on the cloth it is
        # actually for. A stale one is a picture of the previous build.
        prev = preview_path(name)
        if not prev.exists():
            issues.append(("warn", f"{name}: no preview in designs/previews — "
                                   f"run: stitch build {name}"))
        elif prev.stat().st_mtime < pes.stat().st_mtime:
            issues.append(("warn", f"{name}: preview is older than the design it shows"))

    # designs/previews parallels designs/out one-for-one. Anything else there is
    # a leftover from a renamed or deleted design and will be reviewed as if it
    # were current.
    for f in sorted(PREVIEWS.glob("*")) if PREVIEWS.exists() else []:
        if f.is_file() and f.stem not in by_name:
            issues.append(("warn", f"{rel(f)}: preview for a design no spec declares"))

    # Legacy locations that the layout retired.
    for legacy in ("images", "designs/source"):
        if (REPO / legacy).exists():
            issues.append(("error", f"{legacy}/: retired location, see docs/13"))

    for f in sorted(REPO.glob("*")):
        if f.is_file() and f.suffix.lower() in (".png", ".jpg", ".jpeg", ".svg", ".webp", ".pes"):
            issues.append(("warn", f"{f.name}: loose asset in the repo root"))
    return issues
