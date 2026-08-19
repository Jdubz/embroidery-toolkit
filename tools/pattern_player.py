#!/usr/bin/env python
"""Build the pattern player: one self-contained HTML file, all data inlined.

    py tools/pattern_player.py                # build build/patterns/player.html
    py tools/pattern_player.py --check        # validate only, exit non-zero on error
    py tools/pattern_player.py --open         # build, then open it

It reads `build/patterns/*.json` -- the packages written by
`bag_pattern.py --package` -- and NOTHING else. No Markdown is parsed here and
no geometry is computed here: a package already carries every figure twice (a
float for the renderer, a fraction for the human) and every supporting document
inlined as text. If the player needs something it does not have, the generator
grows a key.

Everything is inlined because the page has to work with no network at all --
opened from disk, mailed to someone, or published as an artifact behind a
content-security policy that blocks every external request. That constraint is
also why the Markdown is rendered in the browser rather than here: adding a
document to a pattern stays a path in a spec instead of a change to this file.
"""

from __future__ import annotations

import argparse
import json
import sys
import webbrowser
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PACKAGES = REPO / "build" / "patterns"
TEMPLATE = REPO / "tools" / "pattern_player.html"
OUTPUT = PACKAGES / "player.html"

SCHEMA_VERSION = "1.0"
PLACEHOLDER = "__LIBRARY_JSON__"

#: Every key the player dereferences without guarding. A package missing one of
#: these renders a blank panel rather than an error, which is the failure mode
#: worth catching here: the page still looks finished.
REQUIRED = ("schema_version", "name", "title", "description", "summary",
            "finished", "interior", "flags", "geometry", "materials",
            "cut_list", "layouts", "takeoff", "hardware", "assembly",
            "stitch_schedule", "tools", "checklist", "thickness", "peak_mm",
            "comfort", "assembly_load", "sources", "model3d", "checks", "notes",
            "open_questions", "docs", "embroidery", "provenance")
REQUIRED_GEOMETRY = ("ring", "panel_w", "panel_h", "gusset_w", "sa", "flange",
                     "show", "coil_c")

#: The order patterns appear in the dropdown: smallest first, so the list reads
#: as a size ladder rather than as an alphabet.
def _order(pkg: dict) -> tuple:
    f = pkg["finished"]
    return (f["w"]["in"] * f["h"]["in"] * f["d"]["in"], pkg["name"])


def load_packages() -> list[dict]:
    paths = sorted(p for p in PACKAGES.glob("*.json"))
    if not paths:
        raise FileNotFoundError(
            f"no packages in {PACKAGES.relative_to(REPO).as_posix()} -- "
            "run: py tools/bag_pattern.py --all --package")
    return [json.loads(p.read_text(encoding="utf-8")) for p in paths]


def validate(pkgs: list[dict]) -> list[str]:
    """Structural problems only. Geometry is the generator's business."""
    bad = []
    for p in pkgs:
        n = p.get("name", "<unnamed>")
        if p.get("schema_version") != SCHEMA_VERSION:
            bad.append(f"{n}: schema_version {p.get('schema_version')!r}, "
                       f"this player speaks {SCHEMA_VERSION!r}")
        for k in REQUIRED:
            if k not in p:
                bad.append(f"{n}: missing {k!r}")
        for k in REQUIRED_GEOMETRY:
            if k not in p.get("geometry", {}):
                bad.append(f"{n}: geometry has no {k!r}")
        for d in p.get("docs", []):
            if not d.get("body", "").strip():
                bad.append(f"{n}: doc {d.get('path')!r} is empty -- "
                           "the file exists but nothing was inlined")
        m3 = p.get("model3d", {})
        if not m3.get("features"):
            bad.append(f"{n}: model3d has no features, so the preview is a bare box")
        for c in p.get("checks", []):
            if not c["ok"]:
                bad.append(f"{n}: FAILED check -- {c['name']}: {c['detail']}")
    return bad


def library(pkgs: list[dict]) -> dict:
    """Everything the page needs, in one object.

    `help` is the quick-help rail: the technique and reference notes shared by
    every pattern, deduplicated by path. Pattern-specific documents stay on
    their own package and are appended to the rail by the page.

    Document *bodies* are hoisted into one `docs` map keyed by path. Every
    package carries its own copy on disk, deliberately -- a package has to be
    readable alone. But the construction's three shared notes appear in all
    four, so inlining them per pattern would put the same 30 KB in the page
    four times.
    """
    ordered = sorted(pkgs, key=_order)
    bodies: dict[str, str] = {}
    #: Quick help groups by kind: how to do the operation, then what the family
    #: is, then the embroidery side -- which is a different domain in this repo
    #: and belongs at the bottom of the rail rather than mixed through it.
    KIND_ORDER = {"technique": 0, "reference": 1, "embroidery": 2}
    help_docs, seen = [], set()
    for p in ordered:
        for d in p["docs"]:
            bodies.setdefault(d["path"], d.get("body", ""))
            if d["kind"] in KIND_ORDER and d["path"] not in seen:
                seen.add(d["path"])
                help_docs.append({k: v for k, v in d.items() if k != "body"})
    help_docs.sort(key=lambda d: (KIND_ORDER[d["kind"]], d["title"]))

    # The glossary is identical on every package -- shared vocabulary, not a
    # property of any one bag. Hoist it the same way doc bodies are hoisted.
    glossary = next((p["glossary"] for p in ordered if p.get("glossary")), [])
    # Photographs are base64 and by far the heaviest thing here. Hoisting them
    # is not a tidiness point: inlined per pattern they would ship four times.
    photos = next((p["photos"] for p in ordered if p.get("photos")), {})

    thin = []
    for p in ordered:
        q = dict(p)
        q["docs"] = [{k: v for k, v in d.items() if k != "body"} for d in p["docs"]]
        q.pop("glossary", None)
        q.pop("photos", None)
        thin.append(q)

    return {"schema_version": SCHEMA_VERSION, "patterns": thin,
            "help": help_docs, "docs": bodies, "glossary": glossary,
            "photos": photos}


def build(pkgs: list[dict]) -> Path:
    tpl = TEMPLATE.read_text(encoding="utf-8")
    if PLACEHOLDER not in tpl:
        raise ValueError(f"{TEMPLATE.name} has no {PLACEHOLDER} placeholder")
    # `<` only ever appears inside a JSON string, so escaping it is still valid
    # JSON -- and it is what stops a stray `</script>` in a Markdown document
    # closing the tag the data lives in.
    blob = json.dumps(library(pkgs), ensure_ascii=False).replace("<", "\\u003c")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUTPUT.with_suffix(".html.tmp")
    tmp.write_text(tpl.replace(PLACEHOLDER, blob), encoding="utf-8")
    tmp.replace(OUTPUT)
    return OUTPUT


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true",
                    help="validate the packages and exit; write nothing")
    ap.add_argument("--open", action="store_true", help="open the result")
    args = ap.parse_args(argv)

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    pkgs = load_packages()
    problems = validate(pkgs)
    for p in problems:
        print(f"  FAIL  {p}", file=sys.stderr)

    if args.check:
        print(f"{len(pkgs)} package(s) checked, {len(problems)} problem(s)")
        return 1 if problems else 0

    out = build(pkgs)
    kb = out.stat().st_size / 1024
    print(f"{out.relative_to(REPO).as_posix()}   {kb:.0f} KB   "
          f"{len(pkgs)} pattern(s), {len(library(pkgs)['help'])} help note(s)")
    for p in sorted(pkgs, key=_order):
        bad = sum(1 for c in p["checks"] if not c["ok"])
        print(f"  {p['title']:<28} {len(p['assembly'])} steps  "
              f"{len(p['cut_list'])} pieces  {len(p['docs'])} docs  "
              + ("all checks pass" if not bad else f"{bad} CHECK(S) FAILED"))
    if args.open:
        webbrowser.open(out.as_uri())
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
