/* Check the maths on pages: every data-tex must typeset with the vendored
   KaTeX and the same options as assets/js/equations.js, and every
   figure.eq must follow the anatomy contract (authoring/guide.md, Equations).

     node authoring/check_tex.js page.html [more.html ...]
     node authoring/check_tex.js --json page.html      (for check_page.py)

   Prints "file:line: ERROR|WARN message" lines; exit status 1 on any ERROR.
*/
"use strict";
const fs = require("fs");
const path = require("path");

const ROOT = path.dirname(__dirname);
const katex = require(path.join(ROOT, "assets/vendor/katex/katex.min.js"));

// Same macros as the browser: read them out of equations.js, not a copy.
const eqSrc = fs.readFileSync(path.join(ROOT, "assets/js/equations.js"), "utf8");
const macros = new Function("return " + eqSrc.match(/macros: (\{[\s\S]*?\n {4}\})/)[1])();
const OPTIONS = {
  throwOnError: true, strict: false, macros,
  trust: (ctx) => ctx.command === "\\htmlClass",
};

const ENT = { amp: "&", lt: "<", gt: ">", quot: '"', apos: "'", nbsp: " " };
function unescape(s) {
  return s.replace(/&(#x[0-9a-f]+|#\d+|\w+);/gi, (m, e) => {
    if (e[0] === "#") return String.fromCodePoint(e[1] === "x" || e[1] === "X" ? parseInt(e.slice(2), 16) : +e.slice(1));
    return ENT[e] !== undefined ? ENT[e] : m;
  });
}
const lineOf = (src, i) => src.slice(0, i).split("\n").length;

function check(file) {
  const src = fs.readFileSync(file, "utf8");
  const rel = path.relative(ROOT, path.resolve(file));
  const out = [];
  const say = (i, level, msg) => out.push({ file: rel, line: lineOf(src, i), level, msg });

  for (const m of src.matchAll(/data-tex="([^"]*)"/g)) {
    const tex = unescape(m[1]);
    if (!tex.trim()) { say(m.index, "ERROR", "empty data-tex"); continue; }
    try {
      katex.renderToString(tex, OPTIONS);
    } catch (e) {
      say(m.index, "ERROR", "TeX does not typeset: " + e.message.replace(/^KaTeX parse error: /, ""));
    }
  }

  for (const m of src.matchAll(/<figure class="eq"[^>]*>([\s\S]*?)<\/figure>/g)) {
    const body = m[1];
    const display = (body.match(/class="eq-display" data-tex="([^"]*)"/) || [])[1];
    if (!display) { say(m.index, "ERROR", "figure.eq without a .eq-display[data-tex]"); continue; }
    if (!/class="eq-read"/.test(body)) say(m.index, "ERROR", 'figure.eq needs a <p class="eq-read"> (the equation in words)');
    const tex = unescape(display);
    const terms = [...body.matchAll(/data-term="([^"]*)"/g)].map((t) => t[1]);
    for (const t of terms) {
      if (!/^t[1-8]$/.test(t)) say(m.index, "ERROR", `data-term="${t}": use t1 to t8`);
      else if (!tex.includes(`\\htmlClass{eq-${t}}`)) say(m.index, "ERROR", `legend term ${t} is not tagged in the equation (\\htmlClass{eq-${t}}{...})`);
    }
    for (const t of tex.matchAll(/\\htmlClass\{eq-(t\d)\}/g)) {
      if (!terms.includes(t[1])) say(m.index, "WARN", `equation tags ${t[1]} but the legend has no row for it`);
    }
    if (!/class="eq-type"/.test(body)) say(m.index, "WARN", "legend rows should start with an eq-type pill (scalar, vector, function, ...)");
    const steps = (body.match(/<ol class="eq-steps">([\s\S]*?)<\/ol>/) || [])[1];
    if (steps === undefined) say(m.index, "WARN", "figure.eq has no eq-steps build-up");
    else if (/<li(?![^>]*data-tex)/.test(steps)) say(m.index, "ERROR", "every eq-steps <li> needs a data-tex");
  }

  for (const m of src.matchAll(/<p style="text-align:\s*center">/g)) {
    say(m.index, "WARN", 'HTML equation not yet converted to <div class="eq-display" data-tex="...">');
  }
  return out;
}

const args = process.argv.slice(2);
const json = args[0] === "--json";
const files = json ? args.slice(1) : args;
const all = files.flatMap(check);
if (json) console.log(JSON.stringify(all));
else for (const r of all) console.log(`${r.file}:${r.line}: ${r.level} ${r.msg}`);
process.exit(all.some((r) => r.level === "ERROR") ? 1 : 0);
