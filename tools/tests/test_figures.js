/* Render every declared step figure headlessly.
   A figure that throws, or that comes back empty, is a figure the reader
   never sees -- and buildFigure() catches to protect the live page, so
   nothing on the page would ever say so. This is what says so. */
const fs = require("fs");
const html = fs.readFileSync("tools/pattern_player.html", "utf8");

/* --- the smallest DOM these functions actually touch ------------------- */
class N {
  constructor(tag){ this.tagName = tag; this.attrs = {}; this.children = [];
                    this._text = null; this.className = ""; }
  setAttribute(k, v){ this.attrs[k] = String(v); }
  getAttribute(k){ return this.attrs[k]; }
  appendChild(c){ this.children.push(c); return c; }
  set textContent(v){ this._text = v; }
  get textContent(){ return this._text; }
  set innerHTML(v){ this._html = v;
    const m = /<svg\b/.test(v);
    this.children = m ? [Object.assign(new N("svg"), {_html: v})] : []; }
  get firstElementChild(){ return this.children[0] || null; }
  count(){ return 1 + this.children.reduce((a, c) => a + c.count(), 0); }
}
global.document = { createElementNS: (ns, t) => new N(t),
                    createElement: t => new N(t) };

/* --- pull the figure library out of the page --------------------------- */
const a = html.indexOf("const SVGNS =");
const b = html.indexOf("function cards(items, kind, docs){");
if (a < 0 || b < 0) { console.error("FIGURES: could not locate the library"); process.exit(2); }
const lib = html.slice(a, b);

/* The library ships inside a <script id="library"> block in the built page.
   Read it from there, so this checks exactly what a reader loads. */
const built = fs.readFileSync("build/patterns/player.html", "utf8");
const OPEN = '<script type="application/json" id="library">';
const s0 = built.indexOf(OPEN);
const s1 = built.indexOf("<" + "/script>", s0);
if (s0 < 0 || s1 < 0){ console.error("FIGURES: no embedded library"); process.exit(2); }
const LIB = JSON.parse(built.slice(s0 + OPEN.length, s1).split("\u003c").join("<"));
let current = null;
const run = new Function("LIB", "getCurrent", lib
  + "\nreturn {buildFigure, FIG_KINDS};")(LIB, () => current);

let checked = 0, bad = [];
for (const p of LIB.patterns){
  current = p.name;
  for (const st of p.assembly || []){
    for (const spec of st.figures || []){
      checked++;
      let node = null, err = null;
      try { node = run.buildFigure(spec, p); } catch (e){ err = e.message; }
      const what = `${p.name} step ${st.n} "${st.title.slice(0, 34)}" `
                 + `[${spec.kind || spec.id}]`;
      if (err) bad.push(`${what}: threw — ${err}`);
      else if (!node) bad.push(`${what}: produced nothing`);
      /* A doc-embedded figure arrives as raw markup through innerHTML, which
         this shim does not parse -- measure the markup. A generated one is a
         real node tree, so count it. */
      else if (spec.doc){
        const src = (node._html || "");
        if (src.length < 400 || !/<\/svg>/.test(src))
          bad.push(`${what}: markup looks truncated (${src.length} chars)`);
      }
      else if (node.count() < 6) bad.push(`${what}: only ${node.count()} nodes`);
      else if (spec.kind){
        const s = JSON.stringify(node);
        if (/undefined|NaN|\[object/.test(s))
          bad.push(`${what}: renders undefined/NaN`);
      }
    }
  }
}
/* Glossary figures too. A generated one is drawn for whichever bag is open,
   so it has to hold for ALL of them -- a term is shared, a bag is not. */
for (const p of LIB.patterns){
  current = p.name;
  for (const t of LIB.glossary || []){
    if (!t.figure) continue;
    checked++;
    let node = null, err = null;
    try { node = run.buildFigure(t.figure, p); } catch (e){ err = e.message; }
    const what = `glossary "${t.term}" on ${p.name} `
               + `[${t.figure.kind || t.figure.id}]`;
    if (err) bad.push(`${what}: threw — ${err}`);
    else if (!node) bad.push(`${what}: produced nothing`);
    else if (t.figure.doc){
      const src = node._html || "";
      if (src.length < 400) bad.push(`${what}: markup truncated`);
    }
    else if (node.count() < 6) bad.push(`${what}: only ${node.count()} nodes`);
    else if (/undefined|NaN/.test(JSON.stringify(node)))
      bad.push(`${what}: renders undefined/NaN`);
  }
}

/* Two steps showing the SAME picture is worse than one showing none: it
   teaches the reader that the figure is decoration and stops them looking.
   Four drawings were reused verbatim on this bag before anyone noticed --
   including one that contradicted its own step's stitch line. */
for (const p of LIB.patterns){
  current = p.name;
  const bySig = new Map();
  for (const st of p.assembly || []){
    for (const spec of st.figures || []){
      let node = null;
      try { node = run.buildFigure(spec, p); } catch (e) { continue; }
      if (!node) continue;
      const sig = JSON.stringify(node);
      if (!bySig.has(sig)) bySig.set(sig, []);
      bySig.get(sig).push(`${st.n} "${st.title.slice(0, 26)}"`);
    }
  }
  for (const [, steps] of bySig)
    if (steps.length > 1)
      bad.push(`${p.name}: identical drawing on steps ${steps.join(" and ")}`);
}

console.log(`figures rendered: ${checked}`);
if (bad.length){ bad.forEach(m => console.log("  FAIL " + m)); process.exit(1); }
console.log("all figures render");
