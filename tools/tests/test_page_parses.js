/* Does the built page actually PARSE?
 *
 * This exists because it did not, and nothing here said so. The figure test
 * only ever evaluated the slice of script between two markers, so a syntax
 * error anywhere else shipped clean through every check and showed up as
 * "Uncaught SyntaxError" in a browser console -- with the page completely
 * BLANK, because one bad token kills the whole script block.
 *
 * The specific break was an escape losing its backslash on the way into the
 * file, so a split("\n\n") ended up spanning two real lines. Nothing about
 * that is visible in the generator, the packages, or any python check: the
 * page is only a template until a browser parses it, so a parser is the only
 * thing that can have an opinion.
 *
 * Parse every <script> the page carries, and parse the JSON one as JSON.
 */
const fs = require("fs");
const vm = require("vm");

const path = "build/patterns/player.html";
const html = fs.readFileSync(path, "utf8");
const fails = [];
let scripts = 0, json = 0;

const RE = /<script([^>]*)>([\s\S]*?)<\/script>/g;
let m;
while ((m = RE.exec(html)) !== null) {
  const attrs = m[1] || "";
  const body = m[2];
  /* Pad with the newlines that precede it, so the parser's line numbers are
     the file's line numbers -- an error reported at "line 12 of the block" is
     useless when the block starts at 316. */
  const lead = html.slice(0, m.index + m[0].indexOf(">") + 1).split("\n").length - 1;
  if (/application\/json/.test(attrs)) {
    json++;
    try { JSON.parse(body); }
    catch (e) { fails.push(`json block at line ${lead + 1}: ${e.message}`); }
    continue;
  }
  scripts++;
  try {
    new vm.Script("\n".repeat(lead) + body, {filename: path});
  } catch (e) {
    const where = (e.stack || "").split("\n").slice(0, 3).join(" | ");
    fails.push(`script: ${e.message}\n         ${where}`);
  }
}

if (!scripts) fails.push("no script block found at all -- the regex is wrong");
if (!json) fails.push("no embedded library found");

console.log(`parsed ${scripts} script block(s) and ${json} json block(s)`);
if (fails.length) { fails.forEach(f => console.log("  FAIL " + f)); process.exit(1); }
console.log("the built page parses");
