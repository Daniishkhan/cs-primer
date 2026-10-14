/* KV-cache memory calculator (A3 chapter 18).
   Shapes of the Llama 3 models are from Table 3 of the Llama 3 report (Llama Team, 2024): layers, attention heads,
   key/value heads (8), model width, FFN width, vocabulary 128,256 in the released models.
   KV bytes per token = 2 x layers x kv_heads x head_dim x bytes per number.
   Weights = parameters x bytes per weight (parameters counted from the shapes, untied embeddings).
   GPU memory and bandwidth are the NVIDIA datasheet values for L4 (24 GB, 300 GB/s), A100 80GB SXM (2,039 GB/s)
   and H100 SXM (3.35 TB/s). Overhead of 2 GB for activations and the CUDA context is an assumption.
   Decode time is a lower bound: bytes moved per step divided by bandwidth (weights once, every cache once). */
(function () {
  "use strict";
  var root = document.getElementById("llm18-kvcalc");
  if (!root) return;
  var NS = "http://www.w3.org/2000/svg";
  var MODELS = {
    b8:   { label: "Llama 3 8B",   L: 32,  H: 32,  D: 4096,  F: 14336, kv: 8,  V: 128256 },
    b70:  { label: "Llama 3 70B",  L: 80,  H: 64,  D: 8192,  F: 28672, kv: 8,  V: 128256 },
    b405: { label: "Llama 3 405B", L: 126, H: 128, D: 16384, F: 53248, kv: 8,  V: 128256 }
  };
  var GPUS = {
    l4:   { label: "24 GB, L4 (300 GB/s)", gb: 24, bw: 300e9 },
    a100: { label: "80 GB, A100 SXM (2,039 GB/s)", gb: 80, bw: 2039e9 },
    h100: { label: "80 GB, H100 SXM (3,350 GB/s)", gb: 80, bw: 3350e9 }
  };
  var OVERHEAD = 2e9;
  var $ = function (s) { return root.querySelector(s); };
  var modelSel = $("[data-act=model]"), kvSel = $("[data-act=kvheads]"), dtSel = $("[data-act=kvtype]"),
      wSel = $("[data-act=wtype]"), ctxSel = $("[data-act=ctx]"), batchIn = $("[data-act=batch]"),
      batchOut = $("[data-act=batch-out]"), gpuSel = $("[data-act=gpu]");
  var svg = $(".kvc-chart"), tbody = $(".kvc-table tbody"), summary = $(".kvc-summary");

  function el(tag, attrs, text) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function gb(x) { return (x / 1e9).toFixed(x < 1e10 ? 2 : 1) + " GB"; }
  function fmt(n) { return Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ","); }

  function compute() {
    var m = MODELS[modelSel.value], g = GPUS[gpuSel.value];
    var kvHeads = kvSel.value === "native" ? m.kv : parseInt(kvSel.value, 10);
    var hd = m.D / m.H;
    var kvBytes = parseFloat(dtSel.value), wBytes = parseFloat(wSel.value);
    var ctx = parseInt(ctxSel.value, 10), batch = parseInt(batchIn.value, 10);
    var perTok = 2 * m.L * kvHeads * hd * kvBytes;
    var attn = 2 * m.D * m.D + 2 * m.D * kvHeads * hd;       // q, o square; k, v are D x (kv_heads * head_dim)
    var params = m.L * (attn + 3 * m.D * m.F + 2 * m.D) + 2 * m.V * m.D + m.D;
    var weights = params * wBytes, perSeq = perTok * ctx, kvTotal = perSeq * batch;
    var cap = g.gb * 1e9, room = cap - weights - OVERHEAD;
    var maxSeq = room > 0 ? Math.floor(room / perSeq) : 0;
    var step = (weights + kvTotal) / g.bw;
    return { m: m, g: g, kvHeads: kvHeads, perTok: perTok, params: params, weights: weights, perSeq: perSeq,
             kvTotal: kvTotal, cap: cap, maxSeq: maxSeq, step: step, batch: batch, ctx: ctx, room: room };
  }

  function draw(r) {
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    var W = 700, L = 14, T = 38, barH = 40, pw = W - 2 * L;
    var parts = [
      { name: "Weights", v: r.weights, cls: "f-purple" },
      { name: "Overhead (assumed)", v: OVERHEAD, cls: "f-yellow" },
      { name: "KV cache", v: r.kvTotal, cls: "f-cyan" }
    ];
    var sum = r.weights + OVERHEAD + r.kvTotal, maxV = Math.max(sum, r.cap) * 1.04;
    var X = function (v) { return L + pw * v / maxV; };
    var x = 0;
    parts.forEach(function (p) {
      var w = X(p.v) - L;
      if (w > 0.5) svg.appendChild(el("rect", { x: X(x).toFixed(1), y: T, width: w.toFixed(1), height: barH, "class": p.cls }));
      x += p.v;
    });
    svg.appendChild(el("line", { x1: X(r.cap), y1: T - 12, x2: X(r.cap), y2: T + barH + 12, "class": "line s-green sw-3" }));
    svg.appendChild(el("text", { x: X(r.cap) - 6, y: T - 16, "text-anchor": "end", "class": "t-xs tc-green t-bold" }, "GPU memory " + r.g.gb + " GB"));
    svg.appendChild(el("text", { x: L, y: T + barH + 34, "class": "t-sm t-bold" }, "Needed " + gb(sum)));
    var lx = L, ly = T + barH + 58;
    parts.forEach(function (p) {
      svg.appendChild(el("rect", { x: lx, y: ly - 9, width: 10, height: 10, "class": p.cls }));
      svg.appendChild(el("text", { x: lx + 14, y: ly, "class": "t-xs t-muted" }, p.name + " " + gb(p.v)));
      lx += 14 + (p.name.length + 9) * 6.2 + 14;
    });
    svg.setAttribute("viewBox", "0 0 " + W + " 140");
    return sum;
  }

  function run() {
    batchOut.textContent = batchIn.value;
    var r = compute(), sum = draw(r);
    tbody.textContent = "";
    var rows = [
      ["Parameters (from the shapes)", (r.params / 1e9).toFixed(2) + " B"],
      ["KV heads used / bytes per number", r.kvHeads + " / " + dtSel.value],
      ["KV cache per token", fmt(r.perTok / 1024) + " KiB"],
      ["KV cache per sequence at this context", gb(r.perSeq)],
      ["Sequences of this length that fit (after weights and overhead)", r.maxSeq > 0 ? fmt(r.maxSeq) : "none"],
      ["Lower bound on one decode step (bytes moved / bandwidth)", (r.step * 1000).toFixed(1) + " ms"],
      ["Upper bound on tokens/s per sequence, and in total", (1 / r.step).toFixed(1) + " and " + fmt(r.batch / r.step)]
    ];
    rows.forEach(function (rw) {
      var tr = document.createElement("tr");
      rw.forEach(function (t) { var td = document.createElement("td"); td.textContent = t; tr.appendChild(td); });
      tbody.appendChild(tr);
    });
    var over = sum - r.cap;
    var msg;
    if (r.room <= 0) msg = "The weights alone do not fit on this GPU.";
    else if (over > 0) msg = "Does not fit: over by " + gb(over) + ". At most " + r.maxSeq + " sequences of " + fmt(r.ctx) + " tokens fit.";
    else msg = "Fits, with " + gb(-over) + " to spare. Up to " + r.maxSeq + " sequences of " + fmt(r.ctx) + " tokens would fit.";
    summary.textContent = msg + " (An estimate: no paging overhead, no activations beyond the 2 GB assumed.)";
    summary.className = "widget-out kvc-summary " + (over <= 0 && r.room > 0 ? "ok" : "bad");
  }
  [modelSel, kvSel, dtSel, wSel, ctxSel, gpuSel].forEach(function (e) { e.addEventListener("change", run); });
  batchIn.addEventListener("input", run);
  run();
})();
