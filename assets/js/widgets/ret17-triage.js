/* RAG failure triage (chapter 17).
   Answers the questions of the chapter's trace-diagnosis procedure in order and reports the FIRST stage
   that failed, which is the stage to fix. The presets are the failing questions from the chapter's
   rag_failures.py run on its 13-passage constructed corpus. */
(function () {
  "use strict";
  var root = document.getElementById("ret17-triage");
  if (!root) return;

  function q(n) { return root.querySelector("[data-act=" + n + "]"); }
  var preset = q("preset"), flow = q("flow"), out = q("out");
  var keys = ["corpus", "retrieved", "prompt", "conflict", "fact", "abstain"];
  var sel = {}, i;
  keys.forEach(function (k) { sel[k] = q(k); });

  var PRESETS = [
    { name: "Return window: 30 days quoted, policy says 45", v: { corpus: 1, retrieved: 1, prompt: 1, conflict: 1, fact: 0, abstain: 0 } },
    { name: "Refund speed: right passage ranked 4th, top 3 used", v: { corpus: 1, retrieved: 0, prompt: 0, conflict: 0, fact: 0, abstain: 0 } },
    { name: "Stove burner head: answer is in the second sentence", v: { corpus: 1, retrieved: 1, prompt: 1, conflict: 0, fact: 0, abstain: 0 } },
    { name: "Gas cartridge on a plane: wording mismatch", v: { corpus: 1, retrieved: 0, prompt: 0, conflict: 0, fact: 0, abstain: 0 } },
    { name: "Shipping to Brazil: no such policy exists", v: { corpus: 0, retrieved: 0, prompt: 0, conflict: 0, fact: 0, abstain: 0 } },
    { name: "Student discount: nothing relevant, answered anyway", v: { corpus: 0, retrieved: 0, prompt: 0, conflict: 0, fact: 0, abstain: 0 } },
    { name: "Healthy: tent warranty answered correctly", v: { corpus: 1, retrieved: 1, prompt: 1, conflict: 0, fact: 1, abstain: 0 } },
    { name: "Healthy: unanswerable question, system abstained", v: { corpus: 0, retrieved: 0, prompt: 0, conflict: 0, fact: 0, abstain: 1 } }
  ];
  PRESETS.forEach(function (p, n) {
    var o = document.createElement("option"); o.value = n; o.textContent = p.name; preset.appendChild(o);
  });

  var STAGES = ["Evidence exists", "Retrieved", "In the prompt", "Not misled", "Answer"];
  var DIAG = {
    ok: ["Healthy", "good", "Nothing to fix for this request. Keep it in the regression set so it stays that way."],
    abst: ["Correct abstention", "good", "The sources do not contain the answer and the system said so. Count these as successes; see <a href=\"16-grounded-citations.html\">chapter 16</a>."],
    synth: ["Confident synthesis", "bad", "No evidence exists, yet the system answered. Fix: tell the model that refusing is allowed, abstain on weak retrieval scores, verify claims against spans (<a href=\"16-grounded-citations.html\">chapter 16</a>)."],
    miss: ["Missed retrieval", "bad", "The evidence exists but did not reach the top k. Fix: check the analyser and vocabulary gap (<a href=\"01-text-analysis.html\">1</a>, <a href=\"03-query-understanding.html\">3</a>), add dense plus lexical fusion (<a href=\"10-hybrid-search.html\">10</a>), contextualise chunks (<a href=\"14-chunking.html\">14</a>), rewrite the query (<a href=\"15-agentic-retrieval.html\">15</a>), check permission filters (<a href=\"12-filters-permissions.html\">12</a>), then raise k and rerank (<a href=\"08-rerankers.html\">8</a>)."],
    lost: ["Lost between retrieval and prompt", "bad", "It was retrieved but did not make it into the prompt. Fix: look at deduplication, the token budget and the reranker cut-off in the assembly step (<a href=\"13-rag-end-to-end.html\">chapter 13</a>)."],
    stale: ["Stale or conflicting source", "bad", "The right passage and a competing one were both in the prompt, and the answer followed the wrong one. Fix: version and date metadata, filter to what is in force, surface conflicts explicitly."],
    ignored: ["Evidence present but not used", "bad", "The right passage was in the prompt, nothing contradicted it and the answer still lacks the fact. Fix: fewer, better passages; put the best at the edges of the context; split the task or extract quotes first (<a href=\"16-grounded-citations.html\">chapter 16</a>)."],
    falseabs: ["False abstention", "bad", "The evidence was in the prompt and the system declined. Fix: loosen the abstention threshold using a risk-coverage curve, and check the prompt does not over-discourage answering."]
  };

  function v(k) { return parseInt(sel[k].value, 10); }
  function run() {
    var corpus = v("corpus"), retrieved = v("retrieved"), prompt = v("prompt"), conflict = v("conflict"), fact = v("fact"), abstain = v("abstain");
    var stage = -1, key;
    if (!corpus) { if (abstain) { key = "abst"; } else { key = "synth"; stage = 4; } }
    else if (!retrieved) { key = "miss"; stage = 1; }
    else if (!prompt) { key = "lost"; stage = 2; }
    else if (conflict && !fact) { key = "stale"; stage = 3; }
    else if (!fact) { key = abstain ? "falseabs" : "ignored"; stage = 4; }
    else { key = "ok"; }
    var html = "";
    STAGES.forEach(function (name, n) {
      var cls = "r17-ok";
      if (stage >= 0) cls = n < stage ? "r17-ok" : (n === stage ? "r17-bad" : "r17-na");
      if (!corpus && key === "abst") cls = "r17-na";
      if (!corpus && key === "synth") cls = n < 4 ? "r17-na" : "r17-bad";
      var state = cls === "r17-ok" ? "passed" : cls === "r17-bad" ? "FAILED" : "not reached";
      html += '<li class="' + cls + '"><b>' + (n + 1) + ". " + name + "</b>" + state + "</li>";
    });
    flow.innerHTML = html;
    var d = DIAG[key];
    out.innerHTML = '<p class="r17-diag ' + d[1] + '">' + d[0] + '</p><p class="r17-detail">' + d[2] + "</p>";
  }
  function load(n) {
    var p = PRESETS[n].v;
    keys.forEach(function (k) { sel[k].value = String(p[k]); });
    run();
  }
  preset.addEventListener("change", function () { load(parseInt(preset.value, 10)); });
  keys.forEach(function (k) { sel[k].addEventListener("change", run); });
  load(0);
})();
