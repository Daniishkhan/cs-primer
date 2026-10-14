/* Training-memory calculator (A3 chapter 02).
   Model state (weights, gradients, optimiser) follows the bytes-per-parameter accounting of the ZeRO paper
   (Rajbhandari et al., 2019). Activation memory follows Korthikanti et al. (2022), equation 1, for 16-bit
   activations without tensor parallelism. Logits and a fixed overhead are our own rough additions. */
(function () {
  "use strict";
  var root = document.getElementById("llm02-memory");
  if (!root) return;

  var NS = "http://www.w3.org/2000/svg";
  var MODELS = {
    small: { label: "GPT-2 small (L12, h768)", L: 12, h: 768, a: 12, V: 50257 },
    xl13:  { label: "1.3B (L24, h2048)", L: 24, h: 2048, a: 16, V: 50257 },
    b7:    { label: "7B-class (L32, h4096)", L: 32, h: 4096, a: 32, V: 32000 },
    b13:   { label: "13B-class (L40, h5120)", L: 40, h: 5120, a: 40, V: 32000 },
    b70:   { label: "70B-class (L80, h8192)", L: 80, h: 8192, a: 64, V: 32000 }
  };
  /* bytes per parameter: weights, gradients, optimiser; trainable = fraction of parameters that get gradients */
  var RECIPES = {
    mixed:  { label: "Mixed precision + Adam (2+2+12)", w: 2, g: 2, o: 12, train: 1 },
    bf16:   { label: "bf16 weights, fp32 Adam, no master copy (2+2+8)", w: 2, g: 2, o: 8, train: 1 },
    adam8:  { label: "8-bit Adam, no master copy (2+2+2)", w: 2, g: 2, o: 2, train: 1 },
    lora:   { label: "LoRA: frozen bf16 base, 0.5% trainable (assumption)", w: 2, g: 2, o: 12, train: 0.005 },
    qlora:  { label: "QLoRA: 4-bit base (0.5 B/param), 0.5% trainable (assumption)", w: 0.5, g: 2, o: 12, train: 0.005 }
  };
  var OVERHEAD_GB = 1.5; /* assumption: CUDA context, allocator fragmentation, temporary buffers */

  var $ = function (sel) { return root.querySelector(sel); };
  var modelSel = $("[data-act=model]"), recSel = $("[data-act=recipe]"), modeSel = $("[data-act=mode]"), capSel = $("[data-act=cap]");
  var seqIn = $("[data-act=seq]"), seqOut = $("[data-act=seq-out]"), batIn = $("[data-act=batch]"), batOut = $("[data-act=batch-out]");
  var svg = $(".mem-chart"), tbody = $(".mem-table tbody"), summary = $(".mem-summary");

  function el(tag, attrs, text) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }

  function compute() {
    var m = MODELS[modelSel.value], r = RECIPES[recSel.value];
    var s = parseInt(seqIn.value, 10), b = parseInt(batIn.value, 10), mode = modeSel.value;
    var P = 12 * m.L * m.h * m.h + m.V * m.h;
    var perLayerNone = s * b * m.h * (34 + 5 * m.a * s / m.h);
    var perLayerSel = s * b * m.h * 34;
    var act;
    if (mode === "none") act = m.L * perLayerNone;
    else if (mode === "selective") act = m.L * perLayerSel;
    else act = m.L * 2 * s * b * m.h + perLayerNone;
    var parts = [
      { name: "Weights", gb: P * r.w / 1e9, cls: "f-purple" },
      { name: "Gradients", gb: P * r.train * r.g / 1e9, cls: "f-orange" },
      { name: "Optimiser state", gb: P * r.train * r.o / 1e9, cls: "f-red" },
      { name: "Activations", gb: act / 1e9, cls: "f-blue" },
      { name: "Logits (fp32)", gb: 4 * s * b * m.V / 1e9, cls: "f-cyan" },
      { name: "Overhead (assumed)", gb: OVERHEAD_GB, cls: "f-yellow" }
    ];
    return { P: P, parts: parts };
  }

  function draw(parts, cap) {
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    var W = 700, H = 150, L = 14, R = 14, T = 34, barH = 44;
    var total = 0; parts.forEach(function (p) { total += p.gb; });
    var maxV = Math.max(total, cap) * 1.08;
    var pw = W - L - R;
    function X(v) { return L + pw * v / maxV; }
    var x = 0;
    parts.forEach(function (p) {
      var w = X(p.gb) - L;
      if (w < 0.5) return;
      svg.appendChild(el("rect", { x: X(x).toFixed(1), y: T, width: w.toFixed(1), height: barH, "class": p.cls }));
      x += p.gb;
    });
    svg.appendChild(el("rect", { x: L, y: T, width: pw * total / maxV, height: barH, fill: "none", "class": "s-blue", "stroke-width": 1 }));
    svg.appendChild(el("line", { x1: X(cap), y1: T - 12, x2: X(cap), y2: T + barH + 12, "class": "line s-green sw-3" }));
    svg.appendChild(el("text", { x: X(cap) - 6, y: T - 16, "text-anchor": "end", "class": "t-xs tc-green t-bold" }, "GPU capacity " + cap + " GB"));
    svg.appendChild(el("text", { x: L, y: T + barH + 36, "class": "t-sm t-bold" }, "Total " + total.toFixed(1) + " GB"));
    /* legend */
    var lx = L, ly = T + barH + 60;
    parts.forEach(function (p) {
      svg.appendChild(el("rect", { x: lx, y: ly - 9, width: 10, height: 10, "class": p.cls }));
      svg.appendChild(el("text", { x: lx + 14, y: ly, "class": "t-xs t-muted" }, p.name));
      lx += 14 + p.name.length * 6.2 + 12;
    });
    svg.setAttribute("viewBox", "0 0 " + W + " " + H);
    return total;
  }

  function run() {
    seqOut.textContent = seqIn.value; batOut.textContent = batIn.value;
    var res = compute(), cap = parseInt(capSel.value, 10);
    var total = draw(res.parts, cap);
    tbody.textContent = "";
    res.parts.forEach(function (p) {
      var tr = document.createElement("tr");
      [p.name, p.gb.toFixed(2) + " GB", (100 * p.gb / total).toFixed(0) + "%"].forEach(function (t) {
        var td = document.createElement("td"); td.textContent = t; tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    var gap = total - cap;
    summary.textContent = (res.P / 1e9).toFixed(2) + "B parameters (12·L·h² + V·h). " +
      (gap <= 0 ? "Fits, with " + (-gap).toFixed(1) + " GB to spare." : "Does not fit: over by " + gap.toFixed(1) + " GB.");
    summary.className = "widget-out mem-summary " + (gap <= 0 ? "ok" : "bad");
  }

  [modelSel, recSel, modeSel, capSel].forEach(function (e) { e.addEventListener("change", run); });
  [seqIn, batIn].forEach(function (e) { e.addEventListener("input", run); });
  run();
})();
