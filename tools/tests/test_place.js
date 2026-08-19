/* Does the page put you back where you were?
 *
 * Parsing is not enough for this one: every failure mode here is behavioural.
 * The page ships inside a SANDBOXED FRAME, where touching localStorage can
 * throw SecurityError outright rather than returning null -- so the case that
 * matters most is the one a browser on your desk never shows you.
 *
 * Drives the page's own resolvePlace/rememberPlace, not a copy of them.
 */
const fs = require("fs");
const html = fs.readFileSync("tools/pattern_player.html", "utf8");
const built = fs.readFileSync("build/patterns/player.html", "utf8");
const OPEN = '<script type="application/json" id="library">';
const s0 = built.indexOf(OPEN), s1 = built.indexOf("<" + "/script>", s0);
const LIB = JSON.parse(built.slice(s0 + OPEN.length, s1).split("<").join("<"));

const a = html.indexOf('const KEY = "boxbound.place";');
const b = html.indexOf("function renderHelp(p){");
if (a < 0 || b < 0) { console.error("PLACE: could not locate the module"); process.exit(2); }
const SRC = html.slice(a, b);

const fails = [];
function harness(opts){
  opts = opts || {};
  const store = new Map();
  const win = {
    addEventListener: () => {},
    location: {hash: opts.hash || ""},
    history: {replaceState: (_a, _b, h) => { win.location.hash = h; }},
    localStorage: {
      getItem: k => { if (opts.throws) throw new Error("SecurityError");
                      return store.has(k) ? store.get(k) : null; },
      setItem: (k, v) => { if (opts.throws) throw new Error("SecurityError");
                           store.set(k, v); }
    }
  };
  if (opts.seed) store.set("boxbound.place", JSON.stringify(opts.seed));
  const TABS = ["Overview", "Comfort", "Materials", "Cut list", "Assembly",
                "Glossary", "Checks"];
  /* current and activeTab live in the page's outer scope. Declare them in
     front of the module so it can be exercised without dragging in render(),
     the DOM, and the whole library rendering path. */
  const NL = String.fromCharCode(10);
  const make = new Function("LIB", "TABS", "window", "location", "history",
    "localStorage", "render",
    "let current = 0; let activeTab = 0;" + NL + SRC + NL
    + "return {restorePlace, rememberPlace, resolvePlace, readHash, slug,"
    + "        place: () => ({current, activeTab}),"
    + "        set: (c, t) => { current = c; activeTab = t; }};");
  const api = make(LIB, TABS, win, win.location, win.history,
                   win.localStorage, () => {});
  return Object.assign(api, {win, TABS});
}

function check(name, ok, detail){
  if (!ok) fails.push(name + (detail ? " — " + detail : ""));
}

const names = LIB.patterns.map(p => p.name);
const hip = names.findIndex(n => n === "HipPack_10x7x4");

/* 1. a bare page starts at the first bag, overview */
let h = harness();
h.restorePlace();
check("a bare URL starts at the first pattern", h.place().current === 0
      && h.place().activeTab === 0, JSON.stringify(h.place()));

/* 2. the hash wins, and names the pattern rather than indexing it */
h = harness({hash: "#hippack-10x7x4/assembly"});
h.restorePlace();
check("the hash restores pattern and tab", h.place().current === hip
      && h.place().activeTab === 4, JSON.stringify(h.place()));

/* 3. localStorage covers a bare URL */
h = harness({seed: {pat: "hippack-10x7x4", tab: "glossary"}});
h.restorePlace();
check("storage restores when there is no hash", h.place().current === hip
      && h.place().activeTab === 5, JSON.stringify(h.place()));

/* 4. THE ONE THAT MATTERS: a sandboxed frame where storage throws */
h = harness({throws: true});
let threw = null;
try { h.restorePlace(); h.set(hip, 3); h.rememberPlace(); }
catch (e) { threw = e.message; }
check("storage throwing does not take the page down", threw === null, threw);
check("...and the hash still records the place in that case",
      h.win.location.hash === "#hippack-10x7x4/cut-list", h.win.location.hash);

/* 5. junk in the hash is ignored rather than crashing or blanking */
["#nonsense", "#hippack-10x7x4/not-a-tab", "#/", "#a/b/c/d"].forEach(bad => {
  const g = harness({hash: bad});
  let err = null;
  try { g.restorePlace(); } catch (e) { err = e.message; }
  check(`junk hash ${bad} is survivable`, err === null, err);
  const pl = g.place();
  check(`junk hash ${bad} lands somewhere real`,
        pl.current >= 0 && pl.current < LIB.patterns.length
        && pl.activeTab >= 0 && pl.activeTab < g.TABS.length, JSON.stringify(pl));
});

/* 6. round trip: whatever it writes, it can read back */
LIB.patterns.forEach((p, i) => {
  const g = harness();
  g.set(i, 4);
  g.rememberPlace();
  const back = harness({hash: g.win.location.hash});
  back.restorePlace();
  check(`round trip for ${p.name}`, back.place().current === i
        && back.place().activeTab === 4,
        `${g.win.location.hash} -> ${JSON.stringify(back.place())}`);
});

/* 7. an index would have been the wrong key: prove names are used */
h = harness();
h.set(hip, 0);
h.rememberPlace();
check("the hash names the bag, so adding a pattern cannot move it",
      /hippack/.test(h.win.location.hash), h.win.location.hash);

console.log(`place: ${LIB.patterns.length} patterns exercised`);
if (fails.length){ fails.forEach(f => console.log("  FAIL " + f)); process.exit(1); }
console.log("the page remembers where you were");
