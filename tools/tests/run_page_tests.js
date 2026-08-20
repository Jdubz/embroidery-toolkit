/* Everything that can only be checked by running the page.
 *
 * The python suite checks the DATA. None of it can tell you whether the built
 * page parses, whether a figure draws, or whether the glossary matcher fires
 * -- and a page with one bad token renders completely blank while every other
 * check stays green. Run this after `pattern_player.py`.
 *
 *   node tools/tests/run_page_tests.js
 */
const {execFileSync} = require("child_process");
const path = require("path");

/* Order matters: if the page does not parse, the rest are meaningless,
   so a failure here stops the run rather than burying the cause in noise. */
const SUITES = ["test_page_parses.js", "test_figures.js", "test_glossary.js",
                "test_place.js", "test_figure_text.js"];

let failed = 0;
for (const s of SUITES) {
  process.stdout.write(`\n-- ${s.replace(/^test_|\.js$/g, "")} `
                       + "-".repeat(Math.max(0, 46 - s.length)) + "\n");
  try {
    process.stdout.write(execFileSync(process.execPath,
      [path.join(__dirname, s)], {encoding: "utf8"}));
  } catch (e) {
    process.stdout.write((e.stdout || "") + (e.stderr || ""));
    failed++;
    if (s === SUITES[0]) {
      console.log("\nthe page does not parse -- nothing else here is meaningful");
      process.exit(1);
    }
  }
}
console.log(failed ? `\n${failed} suite(s) failed` : "\nall page suites pass");
process.exit(failed ? 1 : 0);
