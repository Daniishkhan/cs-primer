/* RAG request budget (retrieval chapter 13).
   One request through the pipeline: how many tokens reach the model, what that costs, how long the
   first token takes, and how stage success rates multiply. All constants are illustrative
   assumptions (the same ones as the chapter's budget13.py listing), not measurements.
   Stages are treated as independent, which real pipelines are not; the product is a rough guide. */
(function () {
  "use strict";
  var root = document.getElementById("ret13-budget");
  if (!root) return;

  function q(n) { return root.querySelector("[data-act=" + n + "]"); }
  var ids = ["k", "chunk", "pin", "rerank", "s1", "s2", "s3", "s4"];
  var el = {}, out = {}, i;
  for (i = 0; i < ids.length; i++) { el[ids[i]] = q(ids[i]); out[ids[i]] = q(ids[i] + "-out"); }
  var stats = root.querySelector(".r13-stats");
  var chart = root.querySelector(".r13-chart");
  var note = root.querySelector(".r13-note");

  var SYSTEM = 200, QUESTION = 30, ANSWER = 200, POUT = 15;
  var NAMES = ["evidence retrieved", "right chunks kept", "answer faithful", "citations valid"];

  function pct(x) { return (x * 100).toFixed(0) + "%"; }
  function row(a, b) { return '<div class="r13-row"><span>' + a + '</span><b>' + b + '</b></div>'; }

  function update() {
    var k = parseInt(el.k.value, 10), chunk = parseInt(el.chunk.value, 10), pin = parseFloat(el.pin.value);
    var rr = el.rerank.checked;
    var s = [1, 2, 3, 4].map(function (n) { return parseInt(el["s" + n].value, 10) / 100; });
    out.k.textContent = k;
    out.chunk.textContent = chunk + " tokens";
    out.pin.textContent = "$" + pin.toFixed(2) + " per million";
    for (i = 1; i <= 4; i++) out["s" + i].textContent = pct(s[i - 1]);

    var tin = SYSTEM + QUESTION + k * chunk;
    var cost = tin * pin / 1e6 + ANSWER * POUT / 1e6;
    var ttft = 15 + 20 + (rr ? 150 : 0) + 5 + 250 + tin * 0.05;
    var run = 1, runs = [], j;
    for (j = 0; j < 4; j++) { run *= s[j]; runs.push(run); }

    stats.innerHTML =
      row("Tokens in the prompt", tin.toLocaleString()) +
      row("Cost per request", "$" + cost.toFixed(4)) +
      row("Cost per million requests", "$" + Math.round(cost * 1e6).toLocaleString()) +
      row("Time to first token", Math.round(ttft) + " ms") +
      row("Fully good answers (product of stages)", pct(run)) +
      row("Bad answers per 1,000 requests", Math.round((1 - run) * 1000));

    var W = 560, H = 150, L = 128, T = 8, rowH = 32, barW = W - L - 54, svg = "";
    for (j = 0; j < 4; j++) {
      var y = T + j * rowH;
      svg += '<text x="' + (L - 8) + '" y="' + (y + 17) + '" text-anchor="end" class="r13-lbl">' + NAMES[j] + '</text>' +
             '<rect x="' + L + '" y="' + (y + 4) + '" width="' + barW + '" height="18" class="r13-track"/>' +
             '<rect x="' + L + '" y="' + (y + 4) + '" width="' + (barW * runs[j]).toFixed(1) + '" height="18" class="r13-bar' + (j === 3 ? ' r13-last' : '') + '"/>' +
             '<text x="' + (L + barW + 6) + '" y="' + (y + 18) + '" class="r13-lbl">' + pct(runs[j]) + '</text>';
    }
    chart.innerHTML = svg;
    chart.setAttribute("viewBox", "0 0 " + W + " " + H);

    var weakest = 0;
    for (j = 1; j < 4; j++) if (s[j] < s[weakest]) weakest = j;
    note.textContent = "Bars show the running product after each stage. The weakest stage is \"" + NAMES[weakest] +
      "\" at " + pct(s[weakest]) + ". Raising the chunk count raises cost and latency steadily, but it only helps if the evidence stage is the one that is failing.";
  }
  Object.keys(el).forEach(function (n) { el[n].addEventListener("input", update); el[n].addEventListener("change", update); });
  update();
})();
