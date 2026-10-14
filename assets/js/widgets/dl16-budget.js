/* Training budget calculator (A2 chapter 16).
   Given a model shape, a recipe and a GPU, estimates the parameters, the memory for model states and
   activations, whether one GPU holds it, and the FLOPs and GPU-hours for a token budget.
   Formulas are those of the chapter: 16 bytes per parameter of model states, Korthikanti et al. (2022)
   activation memory sbh(34 + 5as/h), and 6ND (plus the attention-score term) for compute. */
(function () {
  "use strict";
  var root = document.getElementById("dl16-budget");
  if (!root) return;
  var NS = "http://www.w3.org/2000/svg";
  var q = function (sel) { return root.querySelector(sel); };
  var preset = q("[data-act=preset]"), cIn = q("[data-act=c]"), lIn = q("[data-act=l]"), sIn = q("[data-act=s]"),
      bIn = q("[data-act=b]"), gpuSel = q("[data-act=gpu]"), recSel = q("[data-act=rec]"), flashChk = q("[data-act=flash]"),
      dIn = q("[data-act=d]"), mfuIn = q("[data-act=mfu]");
  var outs = { c: q("[data-act=c-out]"), l: q("[data-act=l-out]"), s: q("[data-act=s-out]"), b: q("[data-act=b-out]"), mfu: q("[data-act=mfu-out]") };
  var svg = q(".dl16-chart"), tbl = q(".dl16-table"), verdict = q(".dl16-verdict");
  var GB = 1e9, V = 128256, KV = 8;
  var GPUS = { a24: { gb: 24, flops: 0, name: "24 GB card" }, a40: { gb: 40, flops: 312e12, name: "A100 40 GB" },
               a80: { gb: 80, flops: 312e12, name: "A100 80 GB" }, h80: { gb: 80, flops: 989e12, name: "H100 80 GB" } };
  var PRESETS = {
    s125: { c: 768, l: 12, s: 1024, b: 8, d: 10 }, b1: { c: 2048, l: 24, s: 2048, b: 4, d: 20 },
    l8: { c: 4096, l: 32, s: 8192, b: 1, d: 15000 }, l70: { c: 8192, l: 80, s: 8192, b: 1, d: 15000 }
  };

  function el(tag, attrs, text) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function ffn(c) { return Math.ceil(3.5 * c / 256) * 256; }
  function heads(c) { return Math.max(1, Math.round(c / 128)); }
  function fmtSci(x) { var e = Math.floor(Math.log(x) / Math.LN10); return (x / Math.pow(10, e)).toFixed(2) + "e" + e; }
  function fmtN(n) { return n >= 1e9 ? (n / 1e9).toFixed(2) + " B" : (n / 1e6).toFixed(0) + " M"; }

  function compute() {
    var C = +cIn.value, L = +lIn.value, S = +sIn.value, B = +bIn.value, D = +dIn.value * 1e9, mfu = +mfuIn.value / 100;
    var H = heads(C), kvDim = Math.min(KV, H) * (C / H), F = ffn(C);
    var block = 2 * C * C + 2 * C * kvDim + 3 * C * F + 2 * C;
    var N = L * block + 2 * V * C + C;
    var states = 16 * N;
    var perLayer = S * B * C * (34 + (flashChk.checked ? 0 : 5 * H * S / C));
    var act = recSel.value === "full" ? L * 2 * S * B * C : L * perLayer;
    act += 2 * S * B * V * 2;                       // logits in 16-bit and their gradient: the output head's own cost
    var gpu = GPUS[gpuSel.value];
    var flopsTok = 6 * (N - V * C) + 12 * L * C * S;
    var total = flopsTok * D;
    var gpuHours = gpu.flops ? total / (gpu.flops * mfu) / 3600 : 0;
    return { C: C, L: L, N: N, states: states, act: act, gpu: gpu, total: total, gpuHours: gpuHours, flopsTok: flopsTok, F: F, H: H };
  }

  function draw() {
    var k;
    for (k in outs) outs[k].textContent = ({ c: cIn, l: lIn, s: sIn, b: bIn, mfu: mfuIn })[k].value;
    var r = compute(), used = r.states + r.act, cap = r.gpu.gb * GB;
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    var scale = 680 / Math.max(used, cap * 1.0), x = 10;
    var segs = [["model states", r.states, "f-purple"], ["activations", r.act, "f-cyan"]];
    segs.forEach(function (s) {
      var w = s[1] * scale;
      svg.appendChild(el("rect", { x: x, y: 20, width: Math.max(w, 0.5), height: 34, "class": s[2] }));
      if (w > 90) svg.appendChild(el("text", { x: x + w / 2, y: 42, "text-anchor": "middle", "class": "t-xs t-bold t-dark" }, (s[1] / GB).toFixed(1) + " GB"));
      x += w;
    });
    var cx = 10 + cap * scale;
    svg.appendChild(el("line", { x1: cx, y1: 10, x2: cx, y2: 64, "class": "line s-red sw-2" }));
    svg.appendChild(el("text", { x: Math.min(cx, 640), y: 80, "text-anchor": cx > 640 ? "end" : "middle", "class": "t-xs tc-red" }, "GPU memory: " + r.gpu.gb + " GB"));
    svg.appendChild(el("rect", { x: 10, y: 88, width: 12, height: 12, "class": "f-purple" }));
    svg.appendChild(el("text", { x: 28, y: 99, "class": "t-xs" }, "weights, gradients, master copy, Adam"));
    svg.appendChild(el("rect", { x: 290, y: 88, width: 12, height: 12, "class": "f-cyan" }));
    svg.appendChild(el("text", { x: 308, y: 99, "class": "t-xs" }, "activations (one microbatch)"));
    var fits = used <= cap;
    verdict.className = "dl16-verdict " + (fits ? "ok" : "bad");
    verdict.textContent = fits ? "Fits on one GPU, with " + ((cap - used) / GB).toFixed(1) + " GB to spare (before framework overhead and fragmentation)."
      : "Does not fit: " + (used / GB).toFixed(1) + " GB needed against " + r.gpu.gb + " GB. Shard the states, recompute activations or use a smaller microbatch.";
    var rows = [
      ["Parameters", fmtN(r.N) + " (" + Math.round(r.N).toLocaleString("en-GB") + ")"],
      ["Model states, 16 bytes each", (r.states / GB).toFixed(1) + " GB"],
      ["Activations", (r.act / GB).toFixed(1) + " GB"],
      ["FLOPs per training token", fmtSci(r.flopsTok)],
      ["Total training FLOPs", fmtSci(r.total)],
      ["GPU-hours at this MFU", r.gpu.flops ? Math.round(r.gpuHours).toLocaleString("en-GB") : "n/a for this card"]
    ];
    tbl.innerHTML = "";
    rows.forEach(function (row) {
      var tr = document.createElement("tr"), a = document.createElement("td"), b = document.createElement("td");
      a.textContent = row[0]; b.textContent = row[1]; tr.appendChild(a); tr.appendChild(b); tbl.appendChild(tr);
    });
  }

  function setPreset(name) {
    var p = PRESETS[name];
    if (!p) return;
    cIn.value = p.c; lIn.value = p.l; sIn.value = p.s; bIn.value = p.b; dIn.value = p.d;
  }
  preset.addEventListener("change", function () { if (preset.value !== "custom") setPreset(preset.value); draw(); });
  [cIn, lIn, sIn, bIn, dIn, mfuIn].forEach(function (c) {
    var f = function () { preset.value = "custom"; draw(); };
    c.addEventListener("input", f); c.addEventListener("change", f);
  });
  [gpuSel, recSel, flashChk].forEach(function (c) { c.addEventListener("change", draw); });
  setPreset("l8");
  draw();
})();
