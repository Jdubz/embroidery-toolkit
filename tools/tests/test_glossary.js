/* Does the glossary actually fire on the step text?
   A term that never matches is a definition nobody will ever be offered, and
   an undefined word in a step is the thing this whole file exists to prevent.
   Both are measured here rather than assumed. */
const fs = require("fs");
const built = fs.readFileSync("build/patterns/player.html", "utf8");
const OPEN = '<script type="application/json" id="library">';
const s0 = built.indexOf(OPEN), s1 = built.indexOf("<" + "/script>", s0);
const LIB = JSON.parse(built.slice(s0 + OPEN.length, s1).split("\u003c").join("<"));

const terms = LIB.glossary || [];
const names = [];
const byName = new Map();
terms.forEach(t => [t.term].concat(t.aka || []).forEach(n => {
  names.push(n); byName.set(n.toLowerCase(), t);
}));
names.sort((a, b) => b.length - a.length);
const esc = s => s.replace(new RegExp("[" + "\\.*+?^${}()|[\\]\\\\" + "]", "g"), "\\$&");
const RE = new RegExp("\\b(" + names.map(esc).join("|") + ")\\b", "gi");

/* every step body, across every bag */
const bodies = [];
LIB.patterns.forEach(p => (p.assembly || []).forEach(st => {
  if (st.body) bodies.push([p.name, st.n, st.title, st.body]);
}));

const hit = new Map();
bodies.forEach(([, , , body]) => {
  RE.lastIndex = 0; let m;
  while ((m = RE.exec(body)) !== null){
    const t = byName.get(m[1].toLowerCase());
    if (t) hit.set(t.term, (hit.get(t.term) || 0) + 1);
  }
});

const fails = [];
const dead = terms.filter(t => !hit.has(t.term)).map(t => t.term);
console.log(`glossary: ${terms.length} terms, ${hit.size} of them fire in step text`);

/* A term defined but never used anywhere in the corpus is dead weight. Step
   bodies are not the whole corpus, so check the technique notes too before
   calling one dead. */
/* A term may earn its place purely by contrast -- "welt" exists to say this
   family never cuts one. So a [[cross-reference]] from another definition
   counts as a use, as does an appearance in a technique note. */
const docs = (Object.values(LIB.docs || {}).join(" ")
              + " " + terms.map(t => t.body || "").join(" ")).toLowerCase();
const reallyDead = dead.filter(n => {
  const t = terms.find(x => x.term === n);
  return ![t.term].concat(t.aka || []).some(a => docs.includes(a.toLowerCase()));
});
if (reallyDead.length)
  fails.push("defined but used nowhere at all: " + reallyDead.join(", "));
else if (dead.length)
  console.log("  (only in the technique notes: " + dead.join(", ") + ")");

/* Longest-first must win: "reverse coil" must not be matched as "coil". */
RE.lastIndex = 0;
const probe = "a reverse coil and a bar-tack and a lap join";
const got = [...probe.matchAll(RE)].map(m => m[1].toLowerCase());
["reverse coil", "bar-tack", "lap join"].forEach(w => {
  if (!got.includes(w)) fails.push(`"${w}" did not win over its substring (got ${got})`);
});

/* Cross-references inside definitions must resolve. */
terms.forEach(t => {
  [...(t.body || "").matchAll(/\[\[([^\]]+)\]\]/g)].forEach(m => {
    if (!byName.has(m[1].toLowerCase()))
      fails.push(`${t.term}: [[${m[1]}]] is not a term`);
  });
});

/* Every step should offer at least one definition -- a step full of jargon
   with nothing linked means the vocabulary missed that operation entirely. */
const bare = bodies.filter(([, , , body]) => { RE.lastIndex = 0; return !RE.test(body); })
                   .map(([n, i, t]) => `${n} step ${i} "${t.slice(0, 30)}"`);
if (bare.length) fails.push("steps with no term linked: " + bare.join("; "));

if (fails.length){ fails.forEach(f => console.log("  FAIL " + f)); process.exit(1); }
console.log("glossary links verified");
