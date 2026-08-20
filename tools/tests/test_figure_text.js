/* Does any figure lay text on top of other text?
 *
 * Every generated figure places its labels at absolute x/y. Nothing stops two
 * of them landing in the same place, and when they do the drawing is not
 * merely untidy -- it is unreadable, which is worse than having no drawing.
 *
 * Estimates each label's box from its font-size, its length and its anchor,
 * then looks for pairs that overlap. Approximate on purpose: it is looking for
 * collisions, not typesetting.
 */
const fs = require("fs");
const html = fs.readFileSync("tools/pattern_player.html", "utf8");

class N {
  constructor(tag){ this.tagName = tag; this.attrs = {}; this.children = [];
                    this._text = null; }
  setAttribute(k, v){ this.attrs[k] = String(v); }
  getAttribute(k){ return this.attrs[k]; }
  appendChild(c){ this.children.push(c); return c; }
  set textContent(v){ this._text = v; }
  get textContent(){ return this._text; }
  set innerHTML(v){ this._html = v; this.children = []; }
  get firstElementChild(){ return this.children[0] || null; }
  texts(out){ out = out || [];
    if (this.tagName === "text" && this._text) out.push(this);
    this.children.forEach(c => c.texts(out));
    return out; }
}
global.document = { createElementNS: (ns, t) => new N(t), createElement: t => new N(t) };

const built = fs.readFileSync("build/patterns/player.html", "utf8");
const OPEN = '<script type="application/json" id="library">';
const s0 = built.indexOf(OPEN), s1 = built.indexOf("<" + "/script>", s0);
const LIB = JSON.parse(built.slice(s0 + OPEN.length, s1).split("\\u003c").join("<"));

const a = html.indexOf("const SVGNS =");
const b = html.indexOf("function cards(items, kind, docs){");
const run = new Function("LIB", html.slice(a, b) + "\nreturn {buildFigure};")(LIB);

/* A text node's approximate box. The fonts here are narrow-ish sans and mono;
   0.55em per character is close enough to catch a collision without pretending
   to be a text engine. */
function box(t){
  const size = parseFloat(t.attrs["font-size"] || "12");
  const w = (t.textContent || "").length * size * 0.55;
  const x = parseFloat(t.attrs.x || "0"), y = parseFloat(t.attrs.y || "0");
  const anchor = t.attrs["text-anchor"] || "start";
  const x0 = anchor === "middle" ? x - w / 2 : anchor === "end" ? x - w : x;
  return {x0, x1: x0 + w, y0: y - size * 0.8, y1: y + size * 0.25,
          s: t.textContent, size};
}
const overlaps = (p, q) =>
  p.x0 < q.x1 - 1 && q.x0 < p.x1 - 1 && p.y0 < q.y1 - 1 && q.y0 < p.y1 - 1;

const fails = [];
let checked = 0, labels = 0;

function inspect(what, node){
  if (!node || node._html) return;          /* embedded docs are hand-drawn */
  checked++;
  const boxes = node.texts().map(box);
  labels += boxes.length;
  /* A label wider than the drawing is the other half of the same fault: the
     viewBox scales to the container, so anything past its right edge is simply
     cut off mid-word. */
  const vb = (node.attrs.viewBox || "0 0 0 0").split(/\s+/).map(Number);
  boxes.forEach(t => {
    if (t.x1 > vb[0] + vb[2] + 1)
      fails.push(`${what}: "${t.s.slice(0, 44)}" runs `
                 + `${Math.round(t.x1 - vb[0] - vb[2])}px past the right edge`);
    if (t.y1 > vb[1] + vb[3] + 1)
      fails.push(`${what}: "${t.s.slice(0, 44)}" is below the bottom edge`);
  });
  for (let i = 0; i < boxes.length; i++)
    for (let j = i + 1; j < boxes.length; j++)
      if (overlaps(boxes[i], boxes[j]))
        fails.push(`${what}: "${boxes[i].s}" overlaps "${boxes[j].s}"`);
}

for (const p of LIB.patterns){
  current = p.name;
  for (const st of p.assembly || [])
    for (const spec of st.figures || [])
      inspect(`${p.name} step ${st.n} [${spec.kind || spec.id}]`,
              run.buildFigure(spec, p));
  for (const t of LIB.glossary || [])
    if (t.figure)
      inspect(`glossary "${t.term}" [${t.figure.kind || t.figure.id}]`,
              run.buildFigure(t.figure, p));
}

console.log(`figure text: ${labels} labels across ${checked} generated figures`);
if (fails.length){
  const seen = new Set();
  fails.filter(f => !seen.has(f) && seen.add(f))
       .slice(0, 25).forEach(f => console.log("  FAIL " + f));
  console.log(`  ${fails.length} overlapping pair(s)`);
  process.exit(1);
}
console.log("no figure lays a label on another");
