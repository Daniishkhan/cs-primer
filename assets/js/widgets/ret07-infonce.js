/* InfoNCE explorer (retrieval chapter 07).
   One query, one positive passage, one hard negative and a number of random
   in-batch negatives. The loss is -ln softmax(sim / tau) at the positive. The
   gradient that pushes a negative away is proportional to that negative's
   softmax probability, so the widget shows how that push is shared between the
   hard negative and the random ones. Random negatives get fixed, seeded
   similarities around 0.10 (sd 0.10). */
(function () {
  "use strict";
  var root = document.getElementById("ret07-infonce");
  if (!root) return;

  var tauIn = root.querySelector("[data-act=tau]"), tauOut = root.querySelector("[data-act=tau-out]");
  var posIn = root.querySelector("[data-act=pos]"), posOut = root.querySelector("[data-act=pos-out]");
  var hardIn = root.querySelector("[data-act=hard]"), hardOut = root.querySelector("[data-act=hard-out]");
  var nIn = root.querySelector("[data-act=n]"), nOut = root.querySelector("[data-act=n-out]");
  var out = root.querySelector(".r7-out");
  var bars = root.querySelector(".r7-bars");
  var note = root.querySelector(".r7-note");

  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  var rng = mulberry32(7), rand = [];
  for (var i = 0; i < 255; i++) {
    var u = Math.max(rng(), 1e-12), v = rng();
    rand.push(0.10 + 0.10 * Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v));
  }

  function f(x, d) { return x.toFixed(d === undefined ? 3 : d); }
  function bar(label, share, cls) {
    var pct = (share * 100).toFixed(1);
    return "<div><div class=\"r7-bl\"><span>" + label + "</span><b>" + pct + "%</b></div>" +
      "<div class=\"r7-track\"><div class=\"r7-fill " + cls + "\" style=\"width:" + pct + "%\"></div></div></div>";
  }

  function update() {
    var tau = Math.pow(10, parseFloat(tauIn.value));
    var sp = parseFloat(posIn.value), sh = parseFloat(hardIn.value), n = parseInt(nIn.value, 10);
    tauOut.textContent = f(tau, 3);
    posOut.textContent = f(sp, 2);
    hardOut.textContent = f(sh, 2);
    nOut.textContent = String(n);
    var logits = [sp / tau, sh / tau], k;
    for (k = 0; k < n; k++) logits.push(rand[k] / tau);
    var mx = Math.max.apply(null, logits), sum = 0, e = [];
    for (k = 0; k < logits.length; k++) { e.push(Math.exp(logits[k] - mx)); sum += e[k]; }
    var pPos = e[0] / sum, pHard = e[1] / sum, pRand = 0;
    for (k = 2; k < e.length; k++) pRand += e[k] / sum;
    var loss = -Math.log(pPos);
    var neg = pHard + pRand;
    out.innerHTML =
      "<div><span>probability of the positive</span><b>" + f(pPos) + "</b></div>" +
      "<div><span>loss (-ln p)</span><b>" + f(loss) + "</b></div>" +
      "<div><span>candidates in the softmax</span><b>" + (n + 2) + "</b></div>";
    bars.innerHTML =
      "<p class=\"r7-cap\">Where the push-away gradient goes (shares of all probability not on the positive)</p>" +
      bar("the hard negative", neg > 0 ? pHard / neg : 0, "hard") +
      bar("all " + n + " random negatives together", neg > 0 ? pRand / neg : 0, "rand");
    var msg;
    if (pPos > 0.99) msg = "The positive already takes almost all the probability: the loss is near zero and the gradient has nothing to teach. This is the 'easy batch' that wastes a step.";
    else if (neg > 0 && pHard / neg > 0.8) msg = "The hard negative takes most of the push-away signal. Random negatives add candidates but little gradient: they are already far from the query.";
    else msg = "Try raising the hard negative's similarity, or lowering the temperature, and watch the share and the loss move.";
    if (tau < 0.03) msg += " A very low temperature makes the softmax nearly a hard maximum: any negative that scores above the positive dominates and training can become unstable.";
    note.textContent = msg;
  }
  [tauIn, posIn, hardIn, nIn].forEach(function (el) { el.addEventListener("input", update); });
  update();
})();
