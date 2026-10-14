/* How many queries do I need? (retrieval chapter 05)
   Paired comparison of two systems on the same queries. Inputs: the number of
   queries, the standard deviation of the per-query score difference, and the
   smallest improvement worth detecting. Uses the normal approximation:
   half-width = 1.96 * sd / sqrt(n); detectable difference at 80% power and
   5% significance = 2.8 * sd / sqrt(n); queries needed = (2.8 * sd / delta)^2. */
(function () {
  "use strict";
  var root = document.getElementById("ret05-power");
  if (!root) return;
  var nIn = root.querySelector("[data-act=n]"), nOut = root.querySelector("[data-act=n-out]");
  var sIn = root.querySelector("[data-act=sd]"), sOut = root.querySelector("[data-act=sd-out]");
  var dIn = root.querySelector("[data-act=delta]"), dOut = root.querySelector("[data-act=delta-out]");
  var out = root.querySelector(".r5-out");
  var bar = root.querySelector(".r5-bar");
  var note = root.querySelector(".r5-note");

  function f(x, d) { return x.toFixed(d === undefined ? 3 : d); }

  function update() {
    var n = parseInt(nIn.value, 10), sd = parseFloat(sIn.value), delta = parseFloat(dIn.value);
    nOut.textContent = String(n);
    sOut.textContent = f(sd, 2);
    dOut.textContent = f(delta, 3);
    var se = sd / Math.sqrt(n);
    var half = 1.96 * se;
    var mde = 2.8 * se;
    var need = Math.ceil(Math.pow(2.8 * sd / delta, 2));
    out.innerHTML =
      "<div><span>standard error of the mean difference</span><b>" + f(se) + "</b></div>" +
      "<div><span>95% interval half-width</span><b>&plusmn; " + f(half) + "</b></div>" +
      "<div><span>smallest reliably detectable gain</span><b>" + f(mde) + "</b></div>" +
      "<div><span>queries needed for a gain of " + f(delta) + "</span><b>" + need + "</b></div>";
    // interval drawn on a fixed scale of -0.15 .. +0.15 around an observed gain equal to delta
    var scale = 0.3, lo = delta - half, hi = delta + half;
    function pos(v) { return Math.max(0, Math.min(100, (v + 0.15) / scale * 100)); }
    var l = pos(lo), h = pos(hi);
    var cls = lo > 0 ? "ok" : "bad";
    bar.innerHTML = "<div class=\"r5-zero\" style=\"left:" + pos(0) + "%\"></div>" +
      "<div class=\"r5-ci " + cls + "\" style=\"left:" + l + "%;width:" + Math.max(1, h - l) + "%\"></div>" +
      "<div class=\"r5-dot\" style=\"left:" + pos(delta) + "%\"></div>";
    note.textContent = lo > 0
      ? "If you observed a gain of " + f(delta) + " with " + n + " queries, the interval stays above zero: the gain is distinguishable from noise."
      : "If you observed a gain of " + f(delta) + " with " + n + " queries, the interval reaches below zero (the line at 0): you could not tell it from noise.";
  }
  [nIn, sIn, dIn].forEach(function (el) { el.addEventListener("input", update); });
  update();
})();
