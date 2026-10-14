/* Group-relative advantage explorer (A3 chapter 14).
   Eight sampled answers to one prompt; click a cell to mark it correct or wrong (reward 1 or 0).
   Shows the advantage each sample receives under three rules: GRPO (reward minus group mean, divided by
   the group's standard deviation; Shao et al., 2024), mean only (the Dr. GRPO choice; Liu et al., 2025) and
   leave-one-out (RLOO; Ahmadian et al., 2024). Population standard deviation is used. */
(function () {
  "use strict";
  var root = document.getElementById("llm14-group");
  if (!root) return;

  var NS = "http://www.w3.org/2000/svg";
  var G = 8;
  var $ = function (s) { return root.querySelector(s); };
  var cellsBox = $(".grp-cells"), ruleSel = $("[data-act=rule]"), svg = $(".grp-chart"), out = $(".grp-out");
  var rewards = [1, 0, 0, 0, 0, 0, 0, 0];
  var cells = [];

  function el(tag, attrs, text) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function advantages(rule) {
    var s = 0, i, a = [];
    for (i = 0; i < G; i++) s += rewards[i];
    var mu = s / G, v = 0;
    for (i = 0; i < G; i++) v += (rewards[i] - mu) * (rewards[i] - mu);
    var sd = Math.sqrt(v / G);
    for (i = 0; i < G; i++) {
      if (rule === "loo") a.push(rewards[i] - (s - rewards[i]) / (G - 1));
      else if (rule === "mean") a.push(rewards[i] - mu);
      else a.push(sd > 0 ? (rewards[i] - mu) / sd : 0);
    }
    return { a: a, mu: mu, sd: sd, k: s };
  }
  function draw() {
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    var W = 700, H = 240, L = 40, T = 20, B = 36, ph = H - T - B, mid = T + ph / 2, yMax = 3;
    var res = advantages(ruleSel.value), bw = (W - L - 20) / G, i;
    svg.appendChild(el("line", { x1: L, y1: mid, x2: W - 10, y2: mid, "class": "line-thin" }));
    [-2, 0, 2].forEach(function (t) {
      svg.appendChild(el("text", { x: L - 6, y: mid - t * (ph / 2) / yMax + 4, "text-anchor": "end", "class": "t-xs t-muted" }, String(t)));
    });
    for (i = 0; i < G; i++) {
      var h = res.a[i] * (ph / 2) / yMax, x = L + i * bw + bw * 0.2;
      svg.appendChild(el("rect", { x: x, y: h >= 0 ? mid - h : mid, width: bw * 0.6, height: Math.abs(h), "class": rewards[i] ? "f-green" : "f-red", opacity: 0.85 }));
      svg.appendChild(el("text", { x: x + bw * 0.3, y: H - 14, "text-anchor": "middle", "class": "t-xs t-muted" }, "#" + (i + 1)));
      svg.appendChild(el("text", { x: x + bw * 0.3, y: (h >= 0 ? mid - h - 5 : mid - h + 13), "text-anchor": "middle", "class": "t-xs" }, res.a[i].toFixed(2)));
    }
    svg.setAttribute("viewBox", "0 0 " + W + " " + H);
    var sum = 0; for (i = 0; i < G; i++) sum += Math.abs(res.a[i]);
    var msg;
    if (res.k === 0 || res.k === G) {
      msg = "All " + G + " answers got the same reward, so every advantage is zero (under leave-one-out, too). This prompt contributes no gradient: the model learns nothing from it this step.";
      out.className = "widget-out grp-out dead";
    } else {
      msg = res.k + " of " + G + " correct: mean reward " + res.mu.toFixed(3) + ", standard deviation " + res.sd.toFixed(3) + ". Total |advantage| = " + sum.toFixed(2) + ". ";
      msg += ruleSel.value === "grpo" ? "Dividing by the standard deviation makes rare successes and rare failures stand out: the odd one out gets a large advantage."
        : ruleSel.value === "mean" ? "Without the division the advantages stay on the reward scale, so prompts with a split group are not boosted over the others."
        : "Leave-one-out compares each answer with the mean of the other seven, which keeps the gradient unbiased but scales every advantage by G/(G−1).";
      out.className = "widget-out grp-out live";
    }
    out.textContent = msg;
  }
  function paint() {
    cells.forEach(function (b, i) {
      b.className = "grp-cell " + (rewards[i] ? "ok" : "no");
      b.textContent = "#" + (i + 1) + (rewards[i] ? " correct" : " wrong");
      b.setAttribute("aria-pressed", rewards[i] ? "true" : "false");
    });
    draw();
  }
  for (var i = 0; i < G; i++) {
    (function (j) {
      var b = document.createElement("button");
      b.type = "button";
      b.addEventListener("click", function () { rewards[j] = rewards[j] ? 0 : 1; paint(); });
      cellsBox.appendChild(b); cells.push(b);
    })(i);
  }
  ruleSel.addEventListener("change", draw);
  paint();
})();
