/* Loss and perplexity explorer (A2 chapter 14).
   Six positions of "the cat sat on the mat". For each, a slider sets the probability the model gave to the
   TRUE next token. Loss per position = -ln p; the training loss is the mean; perplexity = exp(mean loss).
   The last column is the gradient of the loss with respect to that token's own logit, p - 1. */
(function () {
  "use strict";
  var root = document.getElementById("dl14-surprise");
  if (!root) return;
  var NS = "http://www.w3.org/2000/svg";
  var q = function (sel) { return root.querySelector(sel); };
  var words = ["the", "cat", "sat", "on", "the", "mat"];
  var inputs = [], outs = [];
  var sliders = q(".dl14-sliders"), svg = q(".dl14-chart"), summary = q(".dl14-summary");
  var presets = { mixed: [0.30, 0.04, 0.12, 0.55, 0.60, 0.08], uniform: [0.02, 0.02, 0.02, 0.02, 0.02, 0.02], sure: [0.90, 0.90, 0.90, 0.90, 0.90, 0.90], oops: [0.90, 0.90, 0.001, 0.90, 0.90, 0.90] };

  function el(tag, attrs, text) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function pOf(v) { return Math.pow(10, -3 + 3 * v / 100); }          // slider 0..100 -> 0.001 .. 1
  function vOf(p) { return Math.round((Math.log(p) / Math.LN10 + 3) / 3 * 100); }

  words.forEach(function (w, i) {
    var d = document.createElement("div");
    var id = "dl14-p" + i;
    d.innerHTML = '<label for="' + id + '">p("' + w + '") at position ' + (i + 1) + ': <output></output></label><input id="' + id + '" type="range" min="0" max="100" step="1">';
    sliders.appendChild(d);
    inputs.push(d.querySelector("input")); outs.push(d.querySelector("output"));
    inputs[i].addEventListener("input", draw);
  });
  function setPreset(name) {
    presets[name].forEach(function (p, i) { inputs[i].value = String(vOf(p)); });
    draw();
  }
  function draw() {
    var ps = inputs.map(function (c) { return pOf(parseFloat(c.value)); });
    var losses = ps.map(function (p) { return -Math.log(p); });
    var mean = losses.reduce(function (a, b) { return a + b; }, 0) / losses.length;
    ps.forEach(function (p, i) { outs[i].textContent = p < 0.01 ? p.toFixed(3) : p.toFixed(2); });
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    var x0 = 150, bw = 380, maxL = 7, i;
    svg.appendChild(el("text", { x: 10, y: 16, "class": "t-xs t-muted" }, "position, loss = -ln p (nats)"));
    svg.appendChild(el("text", { x: x0 + bw + 20, y: 16, "class": "t-xs t-muted" }, "gradient on own logit (p - 1)"));
    for (i = 0; i < ps.length; i++) {
      var y = 26 + i * 30;
      svg.appendChild(el("text", { x: 10, y: y + 15, "class": "mono t-sm" }, (i + 1) + " " + words[i]));
      svg.appendChild(el("rect", { x: x0, y: y + 2, width: bw, height: 18, rx: 3, "class": "box" }));
      svg.appendChild(el("rect", { x: x0, y: y + 2, width: Math.max(1, bw * Math.min(losses[i], maxL) / maxL), height: 18, rx: 3, "class": losses[i] > 3 ? "f-red" : "f-blue" }));
      svg.appendChild(el("text", { x: x0 + 6, y: y + 15, "class": "mono t-xs t-dark" }, losses[i].toFixed(2)));
      svg.appendChild(el("text", { x: x0 + bw + 20, y: y + 15, "class": "mono t-sm" }, (ps[i] - 1).toFixed(3)));
    }
    var yl = 26 + ps.length * 30 + 6;
    svg.appendChild(el("line", { x1: x0, y1: yl, x2: x0 + bw, y2: yl, "class": "line-thin" }));
    svg.appendChild(el("rect", { x: x0 + bw * Math.min(mean, maxL) / maxL - 2, y: yl - 8, width: 4, height: 16, "class": "f-yellow" }));
    svg.appendChild(el("text", { x: 10, y: yl + 4, "class": "t-sm t-bold" }, "mean loss"));
    svg.appendChild(el("text", { x: x0 + bw + 20, y: yl + 4, "class": "mono t-sm t-bold" }, mean.toFixed(3)));
    var seq = Math.exp(-mean * ps.length);
    summary.textContent = "Mean loss " + mean.toFixed(3) + " nats = " + (mean / Math.LN2).toFixed(3) + " bits per token. Perplexity exp(loss) = " + Math.exp(mean).toFixed(2) +
      ": the model is as unsure as if it were choosing uniformly among " + Math.exp(mean).toFixed(1) + " equally likely tokens at every step. " +
      "The probability it gave to the whole sentence is " + (seq >= 0.0001 ? seq.toFixed(5) : seq.toExponential(2)) + ".";
  }
  Array.prototype.forEach.call(root.querySelectorAll("[data-preset]"), function (b) {
    b.addEventListener("click", function () { setPreset(b.getAttribute("data-preset")); });
  });
  setPreset("mixed");
})();
