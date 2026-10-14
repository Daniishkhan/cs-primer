/* Smoke-test power explorer (A8 chapter 05).
   A small test runs N cases and "passes" if at least a chosen share come out right.
   You set the system's true accuracy, N and the bar. The widget draws the exact
   binomial distribution of the observed score (no randomness), shades the passing
   region, and reports how often this test would pass the system, how often it would
   pass a clearly worse one (true accuracy 15 points lower), and how often it would
   fail a system exactly as good as the bar. */
(function () {
  "use strict";
  var root = document.getElementById("aid05-falsify");
  if (!root) return;

  var NS = "http://www.w3.org/2000/svg";
  function q(n) { return root.querySelector("[data-act=" + n + "]"); }
  var ctl = { acc: q("acc"), n: q("n"), bar: q("bar") };
  var outs = { acc: q("acc-out"), n: q("n-out"), bar: q("bar-out") };
  var svg = root.querySelector(".aid05-chart");
  var tbody = root.querySelector(".aid05-table tbody");
  var verdict = root.querySelector(".aid05-verdict");

  var LF = [0];
  for (var i = 1; i <= 200; i++) LF.push(LF[i - 1] + Math.log(i));

  function pmf(n, p) {
    var out = [], k;
    for (k = 0; k <= n; k++) {
      if (p <= 0) { out.push(k === 0 ? 1 : 0); continue; }
      if (p >= 1) { out.push(k === n ? 1 : 0); continue; }
      out.push(Math.exp(LF[n] - LF[k] - LF[n - k] + k * Math.log(p) + (n - k) * Math.log(1 - p)));
    }
    return out;
  }
  function pPass(n, p, need) {
    var d = pmf(n, p), s = 0;
    for (var k = need; k <= n; k++) s += d[k];
    return Math.min(1, s);
  }
  function pct(x) { return (x * 100).toFixed(x < 0.1 && x > 0 ? 1 : 0) + "%"; }
  function el(tag, attrs) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    return e;
  }
  function row(label, value, cls) {
    var tr = document.createElement("tr"), a = document.createElement("td"), b = document.createElement("td");
    a.textContent = label; b.textContent = value; if (cls) b.className = cls;
    tr.appendChild(a); tr.appendChild(b); tbody.appendChild(tr);
  }

  function update() {
    var acc = parseFloat(ctl.acc.value), n = parseInt(ctl.n.value, 10), bar = parseFloat(ctl.bar.value);
    outs.acc.textContent = Math.round(acc * 100) + "%";
    outs.n.textContent = String(n);
    outs.bar.textContent = Math.round(bar * 100) + "%";
    var need = Math.ceil(bar * n - 1e-9);
    var d = pmf(n, acc), W = 700, H = 170, L = 8, R = 8, T = 10, B = 28;
    var max = 0, k;
    for (k = 0; k <= n; k++) if (d[k] > max) max = d[k];
    var bw = (W - L - R) / (n + 1);
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    for (k = 0; k <= n; k++) {
      var h = max ? (d[k] / max) * (H - T - B) : 0;
      var r = el("rect", { x: L + k * bw + 0.5, y: H - B - h, width: Math.max(1, bw - 1), height: h });
      r.setAttribute("fill", k >= need ? "var(--green)" : "var(--surface-3)");
      svg.appendChild(r);
    }
    var lx = L + need * bw;
    svg.appendChild(el("line", { x1: lx, x2: lx, y1: T, y2: H - B, stroke: "var(--yellow)", "stroke-width": 2, "stroke-dasharray": "5 4" }));
    var t1 = el("text", { x: Math.min(W - 150, lx + 6), y: T + 12, fill: "var(--text-muted)", "font-size": 12 });
    t1.textContent = "pass if " + need + " or more of " + n + " are right"; svg.appendChild(t1);
    var t2 = el("text", { x: L, y: H - 8, fill: "var(--text-faint)", "font-size": 12 }); t2.textContent = "0 right"; svg.appendChild(t2);
    var t3 = el("text", { x: W - R, y: H - 8, fill: "var(--text-faint)", "font-size": 12, "text-anchor": "end" }); t3.textContent = n + " right"; svg.appendChild(t3);

    var pThis = pPass(n, acc, need), worse = Math.max(0.01, acc - 0.15), pWorse = pPass(n, worse, need);
    var pAtBar = pPass(n, Math.min(0.999, bar), need);
    tbody.textContent = "";
    row("Chance the test passes a system with true accuracy " + Math.round(acc * 100) + "%", pct(pThis));
    row("Chance it passes a system 15 points worse (" + Math.round(worse * 100) + "%): a false pass", pct(pWorse), pWorse > 0.1 ? "aid05-bad" : "aid05-ok");
    row("Chance it fails a system exactly at the bar (" + Math.round(bar * 100) + "%): a false fail", pct(1 - pAtBar), (1 - pAtBar) > 0.3 ? "aid05-bad" : "aid05-ok");
    var msg;
    if (pWorse <= 0.1 && (1 - pAtBar) <= 0.3) msg = "A decent test: it rarely passes a clearly worse system and does not often fail one that meets the bar.";
    else if (pWorse <= 0.1) msg = "Good for killing, weak for confirming: it rarely passes a bad system, but a system that just meets the bar fails it often. Treat a pass as 'worth a bigger test', not 'proved'.";
    else msg = "Too easy to pass: a system 15 points worse would get through " + pct(pWorse) + " of the time. Add cases or raise the bar before trusting a pass.";
    verdict.textContent = msg;
    verdict.className = "widget-out aid05-verdict " + (pWorse <= 0.1 && (1 - pAtBar) <= 0.3 ? "ok" : pWorse <= 0.1 ? "warn" : "bad");
  }
  for (var c in ctl) ctl[c].addEventListener("input", update);
  update();
})();
