/* LoRA parameter and QLoRA memory calculator (A3 chapter 11).
   Shapes are the published Llama 2 configurations (7B, 13B, 70B). Memory follows the accounting of chapter 2:
   base weights (bf16 or NF4 with double quantisation, 4.127 bits per weight, Dettmers et al., 2023), embeddings in bf16,
   fp32 adapter weights + gradients + Adam moments (16 bytes per adapter parameter), activations with gradient
   checkpointing (assumption: 34*s*b*h bytes for one layer, 2*s*b*h per layer boundary, fp32 logits), 1.5 GB overhead (assumption). */
(function () {
  "use strict";
  var root = document.getElementById("llm11-lora");
  if (!root) return;

  var NS = "http://www.w3.org/2000/svg";
  var MODELS = {
    b7:  { label: "Llama 2 7B shape",  h: 4096, ffn: 11008, L: 32, kv: 4096, V: 32000 },
    b13: { label: "Llama 2 13B shape", h: 5120, ffn: 13824, L: 40, kv: 5120, V: 32000 },
    b70: { label: "Llama 2 70B shape (grouped-query attention)", h: 8192, ffn: 28672, L: 80, kv: 1024, V: 32000 }
  };
  var TARGETS = {
    qv:   { label: "Attention q and v only", names: ["q", "v"] },
    attn: { label: "All attention (q, k, v, o)", names: ["q", "k", "v", "o"] },
    all:  { label: "All linear layers (attention + MLP)", names: ["q", "k", "v", "o", "gate", "up", "down"] }
  };
  var SEQ = 1024, BATCH = 4, OVERHEAD = 1.5, NF4_BITS = 4 + 8 / 64 + 32 / (64 * 256);

  var $ = function (s) { return root.querySelector(s); };
  var modelSel = $("[data-act=model]"), rankSel = $("[data-act=rank]"), tgtSel = $("[data-act=targets]");
  var baseSel = $("[data-act=base]"), capSel = $("[data-act=cap]");
  var svg = $(".lora-chart"), tbody = $(".lora-table tbody"), summary = $(".lora-summary");

  function el(tag, attrs, text) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function shapesOf(m) {
    return { q: [m.h, m.h], k: [m.h, m.kv], v: [m.h, m.kv], o: [m.h, m.h],
             gate: [m.h, m.ffn], up: [m.h, m.ffn], down: [m.ffn, m.h] };
  }
  function compute() {
    var m = MODELS[modelSel.value], r = parseInt(rankSel.value, 10), names = TARGETS[tgtSel.value].names;
    var sh = shapesOf(m), linear = 0, lora = 0, key;
    for (key in sh) linear += m.L * sh[key][0] * sh[key][1];
    names.forEach(function (n) { lora += m.L * r * (sh[n][0] + sh[n][1]); });
    var embed = 2 * m.V * m.h, total = linear + embed;
    var nf4 = baseSel.value === "nf4";
    var baseGB = linear * (nf4 ? NF4_BITS / 8 : 2) / 1e9;
    var parts = [
      { name: "Base linear weights", gb: baseGB, cls: "f-purple" },
      { name: "Embeddings (bf16)", gb: embed * 2 / 1e9, cls: "f-cyan" },
      { name: "Adapter + Adam state", gb: lora * 16 / 1e9, cls: "f-red" },
      { name: "Activations + logits", gb: (m.L * 2 * SEQ * BATCH * m.h + 34 * SEQ * BATCH * m.h + 4 * SEQ * BATCH * m.V) / 1e9, cls: "f-blue" },
      { name: "Overhead (assumed)", gb: OVERHEAD, cls: "f-yellow" }
    ];
    return { total: total, lora: lora, parts: parts, fullStates: total * 16 / 1e9, r: r };
  }
  function draw(parts, cap) {
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    var W = 700, H = 150, L = 14, R = 14, T = 34, barH = 44, sum = 0;
    parts.forEach(function (p) { sum += p.gb; });
    var maxV = Math.max(sum, cap) * 1.08, pw = W - L - R;
    function X(v) { return L + pw * v / maxV; }
    var x = 0;
    parts.forEach(function (p) {
      var w = X(p.gb) - L;
      if (w >= 0.5) svg.appendChild(el("rect", { x: X(x).toFixed(1), y: T, width: w.toFixed(1), height: barH, "class": p.cls }));
      x += p.gb;
    });
    svg.appendChild(el("line", { x1: X(cap), y1: T - 12, x2: X(cap), y2: T + barH + 12, "class": "line s-green sw-3" }));
    svg.appendChild(el("text", { x: X(cap) - 6, y: T - 16, "text-anchor": "end", "class": "t-xs tc-green t-bold" }, "GPU capacity " + cap + " GB"));
    svg.appendChild(el("text", { x: L, y: T + barH + 36, "class": "t-sm t-bold" }, "Total " + sum.toFixed(1) + " GB"));
    var lx = L, ly = T + barH + 60;
    parts.forEach(function (p) {
      svg.appendChild(el("rect", { x: lx, y: ly - 9, width: 10, height: 10, "class": p.cls }));
      svg.appendChild(el("text", { x: lx + 14, y: ly, "class": "t-xs t-muted" }, p.name));
      lx += 14 + p.name.length * 6.2 + 12;
    });
    svg.setAttribute("viewBox", "0 0 " + W + " " + H);
    return sum;
  }
  function run() {
    var res = compute(), cap = parseInt(capSel.value, 10);
    var sum = draw(res.parts, cap);
    tbody.textContent = "";
    var rows = [
      ["Adapter parameters", (res.lora / 1e6).toFixed(1) + " M"],
      ["Share of the whole model", (100 * res.lora / res.total).toFixed(2) + "%"],
      ["Adapter file (bf16)", (res.lora * 2 / 1e6).toFixed(0) + " MB"],
      ["Full fine-tuning model states, for comparison", res.fullStates.toFixed(0) + " GB"]
    ];
    rows.forEach(function (rw) {
      var tr = document.createElement("tr");
      rw.forEach(function (t) { var td = document.createElement("td"); td.textContent = t; tr.appendChild(td); });
      tbody.appendChild(tr);
    });
    var gap = sum - cap;
    summary.textContent = (gap <= 0 ? "Fits, with " + (-gap).toFixed(1) + " GB to spare" : "Does not fit: over by " + gap.toFixed(1) + " GB") +
      " (sequence " + SEQ + ", batch " + BATCH + ", gradient checkpointing; an estimate, not a measurement).";
    summary.className = "widget-out lora-summary " + (gap <= 0 ? "ok" : "bad");
  }
  [modelSel, rankSel, tgtSel, baseSel, capSel].forEach(function (e) { e.addEventListener("change", run); });
  run();
})();
