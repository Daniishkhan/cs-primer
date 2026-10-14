/* Production-readiness gate board (A8 chapter 12).
   Six gates, three evidence items each. The stakes selector decides which gates are
   hard (any missing item blocks launch) and which are soft (launch with conditions).
   No randomness: the verdict is a pure function of the ticked boxes and the stakes. */
(function () {
  "use strict";
  var root = document.getElementById("aid12-gates");
  if (!root) return;

  var GATES = [
    { id: "quality", name: "Quality", items: [
      "Sealed-set result: interval lower end clears the signed bar",
      "Regression suite runs on every prompt or model change",
      "Top failure modes written up from sampled traces" ] },
    { id: "safety", name: "Safety", items: [
      "Red-team results, including injection, reviewed",
      "Guardrails and refusals tested on the customer's own cases",
      "Risky actions need human approval" ] },
    { id: "reliability", name: "Reliability", items: [
      "Load test at twice the expected peak",
      "Fallback tested for a model-provider outage",
      "SLOs and alerts defined and wired up" ] },
    { id: "security", name: "Security and privacy", items: [
      "Customer security review signed off",
      "Personal data handling and retention agreed in writing",
      "Access control and audit log in place" ] },
    { id: "ops", name: "Operations", items: [
      "Named owner and on-call rota",
      "Runbook for the five most likely failures",
      "Rollback rehearsed; spend alerts and caps set" ] },
    { id: "adoption", name: "Adoption", items: [
      "Users trained; a champion named in each team",
      "Feedback and override button feeds a reviewed log",
      "Success metrics baselined on the current process" ] }
  ];
  var HARD = {
    low:    { quality: 1, security: 1 },
    medium: { quality: 1, security: 1, safety: 1, ops: 1 },
    high:   { quality: 1, security: 1, safety: 1, ops: 1, reliability: 1, adoption: 1 }
  };
  var STAKES_TEXT = {
    low: "Low stakes: an internal drafting aid where a person always reads the output.",
    medium: "Medium stakes: output goes to customers after a person approves it.",
    high: "High stakes: the system acts, or its output is relied on, with money, health, rights or regulation involved."
  };

  var board = root.querySelector("[data-act=board]");
  var sel = root.querySelector("[data-act=stakes]");
  var stakesNote = root.querySelector("[data-act=stakes-note]");
  var verdict = root.querySelector(".aid12-verdict");
  var count = root.querySelector("[data-act=count]");
  var boxes = [];

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }

  GATES.forEach(function (g, gi) {
    var card = el("div", "aid12-gate");
    var head = el("div", "aid12-gate-head");
    var title = el("strong", "", g.name);
    var tag = el("span", "aid12-tag");
    head.appendChild(title); head.appendChild(tag);
    card.appendChild(head);
    g.items.forEach(function (text, ii) {
      var id = "aid12-" + gi + "-" + ii;
      var row = el("div", "aid12-item");
      var cb = document.createElement("input");
      cb.type = "checkbox"; cb.id = id;
      cb.addEventListener("change", update);
      var lab = el("label", "", text);
      lab.setAttribute("for", id);
      row.appendChild(cb); row.appendChild(lab);
      card.appendChild(row);
      boxes.push({ gate: g, box: cb });
    });
    g.card = card; g.tag = tag;
    board.appendChild(card);
  });

  function update() {
    var stakes = sel.value, hard = HARD[stakes];
    stakesNote.textContent = STAKES_TEXT[stakes];
    var total = 0, done = 0, blockers = [], conditions = [];
    GATES.forEach(function (g) {
      var have = 0;
      boxes.forEach(function (b) { if (b.gate === g && b.box.checked) have++; });
      total += g.items.length; done += have;
      var isHard = !!hard[g.id], complete = have === g.items.length;
      g.card.className = "aid12-gate " + (complete ? "pass" : (isHard ? "block" : "soft"));
      g.tag.textContent = (isHard ? "hard gate" : "soft gate") + " · " + have + "/" + g.items.length;
      if (!complete) (isHard ? blockers : conditions).push(g.name + " (" + (g.items.length - have) + " missing)");
    });
    count.textContent = done + " of " + total + " evidence items in hand";
    if (blockers.length) {
      verdict.textContent = "Not ready. Blocked by: " + blockers.join("; ") + "." +
        (conditions.length ? " Also open, but not blocking: " + conditions.join("; ") + "." : "");
      verdict.className = "widget-out aid12-verdict bad";
    } else if (conditions.length) {
      verdict.textContent = "Ready with conditions. Every hard gate is passed. Launch to a limited group and put dates and owners on: " + conditions.join("; ") + ".";
      verdict.className = "widget-out aid12-verdict warn";
    } else {
      verdict.textContent = "Ready. Every gate has its evidence. Launch in stages anyway, and keep the evidence current.";
      verdict.className = "widget-out aid12-verdict ok";
    }
  }

  sel.addEventListener("change", update);
  update();
})();
