/* Success-metric negotiator (A8 chapter 02).
   A classifier scores 2,000 clauses a batch; 10% are truly risky. Risky and safe
   scores are two bell curves (sd 0.15). You move the decision threshold, the model
   quality, the team's review capacity and the recall target the customer wants.
   The widget shows whether any threshold satisfies both signed numbers.
   Expected values are computed analytically, so there is no randomness. */
(function () {
  "use strict";
  var root = document.getElementById("aid02-threshold");
  if (!root) return;

  var NS = "http://www.w3.org/2000/svg";
  var VOLUME = 2000, PREV = 0.10, SD = 0.15, COST_MISS = 400, COST_REVIEW = 6, CENTRE = 0.525;

  function q(name) { return root.querySelector("[data-act=" + name + "]"); }
  var ctl = { thr: q("thr"), gap: q("gap"), cap: q("cap"), rec: q("rec") };
  var outs = { thr: q("thr-out"), gap: q("gap-out"), cap: q("cap-out"), rec: q("rec-out") };
  var svg = root.querySelector(".aid02-chart");
  var tbody = root.querySelector(".aid02-table tbody");
  var verdict = root.querySelector(".aid02-verdict");

  function erf(x) { // Abramowitz and Stegun 7.1.26
    var s = x < 0 ? -1 : 1; x = Math.abs(x);
    var t = 1 / (1 + 0.3275911 * x);
    var y = 1 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * Math.exp(-x * x);
    return s * y;
  }
  function cdf(x, m) { return 0.5 * (1 + erf((x - m) / (SD * Math.SQRT2))); }
  function pdf(x, m) { var z = (x - m) / SD; return Math.exp(-0.5 * z * z) / (SD * Math.sqrt2pi); }
  Math.sqrt2pi = Math.sqrt(2 * Math.PI);

  function stats(t, gap) {
    var mr = CENTRE + gap / 2, ms = CENTRE - gap / 2;
    var recall = 1 - cdf(t, mr), fpr = 1 - cdf(t, ms);
    var risky = VOLUME * PREV, safe = VOLUME * (1 - PREV);
    var caught = risky * recall, falseFlags = safe * fpr, flagged = caught + falseFlags;
    var missed = risky - caught;
    return { recall: recall, flagged: flagged, caught: caught, missed: missed,
      precision: flagged ? caught / flagged : 1, cost: missed * COST_MISS + flagged * COST_REVIEW };
  }

  function s(tag, attrs, text) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }

  function draw(t, gap) {
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    var W = 700, H = 200, L = 30, R = 10, T = 12, B = 30, pw = W - L - R, ph = H - T - B;
    var mr = CENTRE + gap / 2, ms = CENTRE - gap / 2;
    var peak = pdf(ms, ms) * 1.05 / 1; // both curves have the same height
    function X(v) { return L + pw * v; }
    function path(m, wt) {
      var d = "";
      for (var i = 0; i <= 100; i++) {
        var v = i / 100, y = T + ph - ph * (pdf(v, m) * wt) / peak;
        d += (i ? "L" : "M") + X(v).toFixed(1) + "," + y.toFixed(1);
      }
      return d;
    }
    svg.appendChild(s("line", { x1: L, y1: T + ph, x2: W - R, y2: T + ph, "class": "line-thin" }));
    [0, 0.25, 0.5, 0.75, 1].forEach(function (v) {
      svg.appendChild(s("text", { x: X(v), y: T + ph + 15, "text-anchor": "middle", "class": "t-xs t-faint" }, v.toFixed(2)));
    });
    svg.appendChild(s("text", { x: L + pw / 2, y: H - 2, "text-anchor": "middle", "class": "t-xs t-muted" }, "model score (shapes are per-class densities; the risky class is drawn at full height for clarity)"));
    svg.appendChild(s("path", { d: path(ms, 1), fill: "none", "class": "s-blue sw-2" }));
    svg.appendChild(s("path", { d: path(mr, 1), fill: "none", "class": "s-red sw-2" }));
    svg.appendChild(s("text", { x: X(ms), y: T + 8, "text-anchor": "middle", "class": "t-xs tc-blue t-bold" }, "safe clauses"));
    svg.appendChild(s("text", { x: X(mr), y: T + 8, "text-anchor": "middle", "class": "t-xs tc-red t-bold" }, "risky clauses"));
    svg.appendChild(s("line", { x1: X(t), y1: T + 14, x2: X(t), y2: T + ph, "class": "line-dash s-yellow sw-2" }));
    svg.appendChild(s("text", { x: X(t) + (t > 0.8 ? -6 : 6), y: T + 26, "text-anchor": t > 0.8 ? "end" : "start", "class": "t-xs t-bold" }, "threshold " + t.toFixed(2)));
    svg.setAttribute("viewBox", "0 0 " + W + " " + H);
  }

  function row(label, value, ok) {
    var tr = document.createElement("tr");
    var a = document.createElement("td"); a.textContent = label;
    var b = document.createElement("td"); b.textContent = value;
    if (ok === true) b.className = "aid02-ok"; if (ok === false) b.className = "aid02-bad";
    tr.appendChild(a); tr.appendChild(b); tbody.appendChild(tr);
  }

  function update() {
    var t = parseFloat(ctl.thr.value), gap = parseFloat(ctl.gap.value);
    var cap = parseInt(ctl.cap.value, 10), rec = parseFloat(ctl.rec.value);
    outs.thr.textContent = t.toFixed(2); outs.gap.textContent = gap.toFixed(2);
    outs.cap.textContent = String(cap); outs.rec.textContent = Math.round(rec * 100) + "%";
    var r = stats(t, gap);
    draw(t, gap);
    tbody.textContent = "";
    row("Recall of risky clauses (target " + Math.round(rec * 100) + "%)", (r.recall * 100).toFixed(1) + "%", r.recall >= rec);
    row("Clauses flagged for review (capacity " + cap + ")", String(Math.round(r.flagged)), r.flagged <= cap);
    row("Risky clauses missed per batch", r.missed.toFixed(1));
    row("Precision of the flags", (r.precision * 100).toFixed(1) + "%");
    row("Expected cost per batch (miss " + COST_MISS + ", review " + COST_REVIEW + ")", Math.round(r.cost).toLocaleString());
    var lo = null, hi = null;
    for (var v = 0.15; v <= 0.95; v += 0.005) {
      var x = stats(v, gap);
      if (x.recall >= rec && x.flagged <= cap) { if (lo === null) lo = v; hi = v; }
    }
    var ok = r.recall >= rec && r.flagged <= cap;
    if (lo === null) {
      verdict.textContent = "No threshold meets both numbers at this model quality. The two promises conflict: raise capacity, lower the recall target, or improve the model. Better to find this out before signing.";
    } else if (ok) {
      verdict.textContent = "Both signed numbers are met. Thresholds that work at this quality run from " + lo.toFixed(3) + " to " + hi.toFixed(3) + ".";
    } else {
      verdict.textContent = "This threshold breaks a signed number, but thresholds from " + lo.toFixed(3) + " to " + hi.toFixed(3) + " would meet both.";
    }
    verdict.className = "widget-out aid02-verdict " + (lo === null ? "bad" : ok ? "ok" : "warn");
  }

  for (var k in ctl) ctl[k].addEventListener("input", update);
  update();
})();
