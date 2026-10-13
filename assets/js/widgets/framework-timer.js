/* Design-session timer (design chapter 01).

   Walks through the eight phases of the design framework for a 45 or 60 minute
   session. Each phase has a time budget (a share of the total), a few prompts of
   what to say or ask, and a typical mistake to avoid. Start the clock, press
   "Next phase" when you move on, and the widget tells you whether you are ahead
   or behind. At the end it lists planned versus actual minutes per phase.

   The shares below are the author's opinion for a generic session, not a rule:
   weight deep dives more if the interviewer steers you there. A "fast demo"
   switch runs the clock 30 times faster so you can see the behaviour in a minute.

   Pure functions (budgets) are exported for testing under Node. */
(function () {
  "use strict";

  var PHASES = [
    { name: "Clarify requirements", w: 5,
      say: ["Who are the users, and what is the one core action?", "What is in scope for today? What is explicitly out?", "What matters most: latency, availability, consistency, cost?", "Repeat back the requirements and get a nod."],
      trap: "Starting to draw boxes before you know what the product does." },
    { name: "Estimate", w: 4,
      say: ["Say the assumptions aloud: DAU, actions per user, object size.", "Derive average and peak QPS, storage per year, bandwidth.", "Name the decision each number drives: one box or many? cache or not?"],
      trap: "Computing numbers that never change a decision." },
    { name: "API", w: 4,
      say: ["List three to five endpoints with the key fields.", "Which calls must be idempotent? Where does pagination appear?", "Who authenticates, and what is the unit of rate limiting?"],
      trap: "Designing every endpoint instead of the three that matter." },
    { name: "Data model", w: 4,
      say: ["Entities, primary keys, and the main access patterns.", "Which store for which data, and why that one?", "What is the partition key, and could it become hot?"],
      trap: "Picking a database by brand name instead of by access pattern." },
    { name: "High-level design", w: 8,
      say: ["Draw clients, edge, services, stores, queues. Label the arrows.", "Walk the write path, then the read path, with real numbers.", "Say where each estimate shows up on the diagram."],
      trap: "A box for every technology you know, none of them justified." },
    { name: "Deep dives", w: 12,
      say: ["Pick the hardest one or two parts and say why they are hard.", "Compare two or three options in a sentence each.", "Recommend one, and say what would change your mind."],
      trap: "Going deep on a solved problem while the real risk goes unmentioned." },
    { name: "Failure & operations", w: 4,
      say: ["What breaks first? What is the blast radius?", "What would you alert on, and how do you roll out safely?", "What degrades gracefully, and what must fail closed?"],
      trap: "Skipping this because time ran out. Save four minutes for it." },
    { name: "Trade-offs & wrap-up", w: 4,
      say: ["Name what you gave up and what you would revisit at 10x.", "Summarise in three sentences.", "Invite the interviewer to probe wherever they like."],
      trap: "Trailing off. End with a clear summary and the open risks." }
  ];

  function budgets(totalMin) {
    var sum = 0, i, out = [];
    PHASES.forEach(function (p) { sum += p.w; });
    for (i = 0; i < PHASES.length; i++) out.push(Math.round(PHASES[i].w / sum * totalMin * 60));
    return out;
  }
  function fmt(sec) {
    var neg = sec < 0, s = Math.abs(Math.round(sec)), m = Math.floor(s / 60), r = s % 60;
    return (neg ? "+" : "") + m + ":" + (r < 10 ? "0" : "") + r;
  }

  var core = { budgets: budgets, fmt: fmt, PHASES: PHASES };
  if (typeof module !== "undefined" && module.exports) module.exports = core;
  if (typeof document === "undefined") return;
  var root = document.getElementById("framework-timer");
  if (!root) return;

  var total = 45, idx = 0, used = [], elapsed = 0, running = false, finished = false, fast = false, timer = null, last = 0;
  var plan = budgets(total);

  function el(tag, attrs, text) {
    var e = document.createElement(tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }

  var head = el("div", { "class": "widget-head" });
  head.appendChild(el("span", { "class": "widget-tag" }, "Practice timer"));
  head.appendChild(el("h4", { "class": "widget-title" }, "Pace a design session"));
  root.appendChild(head);
  root.appendChild(el("p", { "class": "widget-help" }, "Choose a session length, press Start, and press Next phase whenever you move on. Use it with a friend, or alone out loud."));

  var row1 = el("div", { "class": "widget-row" });
  var lenLab = el("label", { "for": "ft-len" }, "Session length ");
  var lenSel = el("select", { id: "ft-len" });
  [45, 60].forEach(function (m) { lenSel.appendChild(el("option", { value: String(m) }, m + " minutes")); });
  var fastLab = el("label", { "class": "ft-fast" });
  var fastBox = el("input", { type: "checkbox", id: "ft-fast" });
  fastLab.appendChild(fastBox); fastLab.appendChild(document.createTextNode(" Fast demo (30x)"));
  row1.appendChild(lenLab); row1.appendChild(lenSel); row1.appendChild(fastLab);
  root.appendChild(row1);

  var bar = el("div", { "class": "ft-bar", role: "img", "aria-label": "Phase timeline" });
  root.appendChild(bar);

  var clock = el("div", { "class": "ft-clock", "aria-live": "off" });
  var phaseName = el("div", { "class": "ft-phase" });
  var timeBig = el("div", { "class": "ft-time" });
  var timeSub = el("div", { "class": "ft-sub" });
  clock.appendChild(phaseName); clock.appendChild(timeBig); clock.appendChild(timeSub);
  root.appendChild(clock);

  var status = el("p", { "class": "ft-status", "aria-live": "polite" });
  root.appendChild(status);

  var prompts = el("div", { "class": "widget-out ft-prompts" });
  root.appendChild(prompts);

  var row2 = el("div", { "class": "widget-row" });
  var bStart = el("button", { type: "button", "class": "btn primary" }, "Start");
  var bPrev = el("button", { type: "button", "class": "btn" }, "Previous");
  var bNext = el("button", { type: "button", "class": "btn" }, "Next phase");
  var bReset = el("button", { type: "button", "class": "btn" }, "Reset");
  [bStart, bPrev, bNext, bReset].forEach(function (b) { row2.appendChild(b); });
  root.appendChild(row2);

  var summary = el("div", { "class": "widget-out ft-summary" });
  summary.hidden = true;
  root.appendChild(summary);

  function elapsedTotal() {
    var s = 0, i;
    for (i = 0; i < (finished ? PHASES.length : idx); i++) s += used[i] || 0;
    return s + (finished ? 0 : elapsed);
  }
  function plannedBefore(i) { var s = 0, j; for (j = 0; j < i; j++) s += plan[j]; return s; }

  function renderBar() {
    bar.textContent = "";
    PHASES.forEach(function (p, i) {
      var seg = el("div", { "class": "ft-seg" + (i < idx || finished ? " done" : "") + (i === idx && !finished ? " now" : "") });
      seg.style.flexGrow = String(plan[i]);
      var fill = el("div", { "class": "ft-fill" });
      var frac = i < idx || finished ? Math.min(1, (used[i] || 0) / plan[i]) : (i === idx ? Math.min(1, elapsed / plan[i]) : 0);
      fill.style.width = (frac * 100).toFixed(1) + "%";
      if ((i < idx || finished) && (used[i] || 0) > plan[i]) seg.classList.add("over");
      if (i === idx && elapsed > plan[i]) seg.classList.add("over");
      seg.title = p.name + ": " + fmt(plan[i]);
      seg.appendChild(fill);
      seg.appendChild(el("span", { "class": "ft-n" }, String(i + 1)));
      bar.appendChild(seg);
    });
  }

  function render() {
    renderBar();
    prompts.textContent = "";
    if (finished) {
      phaseName.textContent = "Session complete";
      timeBig.textContent = fmt(elapsedTotal());
      timeSub.textContent = "total time used, of " + fmt(total * 60) + " planned";
      status.textContent = "";
      var s = summary; s.hidden = false; s.textContent = "";
      s.appendChild(el("strong", {}, "Planned vs actual"));
      var ul = el("ul", {});
      var worst = -1, wi = -1;
      PHASES.forEach(function (p, i) {
        var d = (used[i] || 0) - plan[i];
        if (d > worst) { worst = d; wi = i; }
        ul.appendChild(el("li", {}, p.name + ": planned " + fmt(plan[i]) + ", used " + fmt(used[i] || 0) + (d > 5 ? " (over)" : (d < -5 ? " (under)" : ""))));
      });
      s.appendChild(ul);
      s.appendChild(el("p", {}, wi >= 0 && worst > 5 ? "Biggest overrun: " + PHASES[wi].name + ". Ask what you could have said in half the time." : "You stayed on pace. Now check that your answers, not just the clock, were good."));
      bStart.disabled = true; bNext.disabled = true; bPrev.disabled = true;
      return;
    }
    summary.hidden = true;
    bStart.disabled = false; bNext.disabled = false; bPrev.disabled = idx === 0;
    var p = PHASES[idx], left = plan[idx] - elapsed;
    phaseName.textContent = (idx + 1) + ". " + p.name;
    timeBig.textContent = fmt(left);
    timeBig.className = "ft-time" + (left < 0 ? " over" : "");
    timeSub.textContent = left < 0 ? "over this phase's budget of " + fmt(plan[idx]) : "left of " + fmt(plan[idx]) + " for this phase";
    var ahead = plannedBefore(idx) + Math.min(elapsed, plan[idx]) - elapsedTotal();
    if (!running && elapsedTotal() === 0) status.textContent = "Press Start to begin phase 1.";
    else if (idx === PHASES.length - 1 && left < 0) status.textContent = "Wrap up now.";
    else if (ahead > 20) status.textContent = "You are about " + fmt(ahead) + " ahead of the plan. Spend the spare time on a deep dive.";
    else if (ahead < -20) status.textContent = "You are about " + fmt(-ahead) + " behind. Shorten the earlier phases next time.";
    else status.textContent = "On pace.";
    var ul2 = el("ul", {});
    p.say.forEach(function (t) { ul2.appendChild(el("li", {}, t)); });
    prompts.appendChild(el("strong", {}, "Say or ask:"));
    prompts.appendChild(ul2);
    prompts.appendChild(el("p", { "class": "ft-trap" }, "Common trap: " + p.trap));
    bStart.textContent = running ? "Pause" : (elapsedTotal() > 0 ? "Resume" : "Start");
  }

  function tick() {
    var now = Date.now(), dt = (now - last) / 1000;
    last = now;
    elapsed += dt * (fast ? 30 : 1);
    render();
  }
  function stop() { running = false; if (timer) { clearInterval(timer); timer = null; } }
  function go() { running = true; last = Date.now(); timer = setInterval(tick, 250); }

  bStart.addEventListener("click", function () { if (running) { stop(); } else { go(); } render(); });
  bNext.addEventListener("click", function () {
    used[idx] = elapsed; elapsed = 0;
    if (idx === PHASES.length - 1) { finished = true; stop(); } else { idx++; }
    render();
  });
  bPrev.addEventListener("click", function () {
    if (idx === 0) return;
    idx--; elapsed = used[idx] || 0; used[idx] = 0; render();
  });
  bReset.addEventListener("click", function () { stop(); idx = 0; used = []; elapsed = 0; finished = false; render(); });
  lenSel.addEventListener("change", function () { total = parseInt(lenSel.value, 10); plan = budgets(total); render(); });
  fastBox.addEventListener("change", function () { fast = fastBox.checked; });

  render();
})();
