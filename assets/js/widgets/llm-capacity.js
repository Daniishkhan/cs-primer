/* LLM decode capacity explorer (design chapter 20).
   A single replica of a dense transformer on g accelerators (tensor parallel). Decoding one token for every
   sequence in the batch is one "step". Step time is the larger of
     memory time  = (weight bytes + KV bytes read) / (g * bandwidth * efficiency)
     compute time = batch * 2 * params / (g * peak FLOP/s * efficiency)
   times a communication penalty when g > 1. ALL constants are ASSUMPTIONS for an illustrative 70B-parameter
   model with grouped-query attention and an 80 GB, 2 TB/s class accelerator; they are not measurements.
   The same arithmetic is in napkin20.py in the chapter. */
(function () {
  "use strict";

  var P = 70e9, LAYERS = 80, KV_HEADS = 8, HEAD_DIM = 128;
  var HBM = 80e9, BW = 2.0e12, PEAK = 312e12;
  var USABLE = 0.9, BW_EFF = 0.6, FLOP_EFF = 0.4, TP_PENALTY = 1.15;
  var PRECISIONS = [["fp16 (2 bytes)", 2], ["int8 (1 byte)", 1], ["int4 (0.5 byte)", 0.5]];
  var GPUS = [1, 2, 4, 8];
  var CTX = [512, 2000, 8000, 32000];
  var KV_BYTES = [["fp16 KV cache", 2], ["8-bit KV cache", 1]];

  function kvPerToken(kvBytes) { return 2 * LAYERS * KV_HEADS * HEAD_DIM * kvBytes; }

  function plan(bpp, g, ctx, kvBytes, batch) {
    var W = P * bpp, kv = kvPerToken(kvBytes);
    var free = g * HBM * USABLE - W;
    var maxByMem = free > 0 ? Math.floor(free / (ctx * kv)) : 0;
    var B = Math.min(batch, maxByMem);
    if (B < 1) return { fits: false, W: W, kv: kv, free: free, maxByMem: Math.max(0, maxByMem) };
    var memT = (W + B * ctx * kv) / (g * BW * BW_EFF);
    var cmpT = B * 2 * P / (g * PEAK * FLOP_EFF);
    var step = Math.max(memT, cmpT) * (g > 1 ? TP_PENALTY : 1);
    return { fits: true, W: W, kv: kv, free: free, maxByMem: maxByMem, B: B, memT: memT, cmpT: cmpT, step: step,
             bound: memT >= cmpT ? "memory bandwidth" : "compute", perStream: 1 / step, tps: B / step };
  }

  var core = { plan: plan, kvPerToken: kvPerToken };
  if (typeof module !== "undefined" && module.exports) module.exports = core;
  if (typeof document === "undefined") return;
  var root = document.getElementById("llm-capacity");
  if (!root) return;

  function el(tag, attrs, text) {
    var e = document.createElement(tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }
  var state = { prec: 0, g: 2, ctx: 1, kv: 0, batch: 5 };
  var BATCHES = [1, 2, 4, 8, 16, 32, 64, 128, 256, 512];

  var head = el("div", { "class": "widget-head" });
  head.appendChild(el("span", { "class": "widget-tag" }, "Try it"));
  head.appendChild(el("h4", { "class": "widget-title" }, "One replica: what limits decoding?"));
  root.appendChild(head);
  root.appendChild(el("p", { "class": "widget-help" },
    "A 70-billion-parameter dense model on 1 to 8 accelerators (assumed 80 GB, about 2 TB/s each). Raise the batch and watch the step time: it is nearly flat while weights dominate the memory traffic, then rises as the KV cache grows. Try int4 weights, a longer context, or a smaller KV cache."));

  var ctl = el("div", { "class": "dz-ctl" });
  var outs = {};
  function slider(key, label, n, fmtv) {
    var w = el("div");
    var lab = el("label", { "for": "lc-" + key }, label + ": ");
    var out = el("output", { "for": "lc-" + key });
    lab.appendChild(out);
    var inp = el("input", { type: "range", id: "lc-" + key, min: "0", max: String(n - 1), step: "1", value: String(state[key]) });
    inp.addEventListener("input", function () { state[key] = parseInt(inp.value, 10); update(); });
    w.appendChild(lab); w.appendChild(inp); ctl.appendChild(w);
    outs[key] = { out: out, fmt: fmtv };
  }
  slider("prec", "Weight precision", PRECISIONS.length, function (i) { return PRECISIONS[i][0]; });
  slider("g", "Accelerators per replica", GPUS.length, function (i) { return String(GPUS[i]); });
  slider("ctx", "Average context (tokens)", CTX.length, function (i) { return String(CTX[i]); });
  slider("kv", "KV cache precision", KV_BYTES.length, function (i) { return KV_BYTES[i][0]; });
  slider("batch", "Concurrent sequences (batch)", BATCHES.length, function (i) { return String(BATCHES[i]); });
  root.appendChild(ctl);

  var tiles = el("div", { "class": "dz-tiles", "aria-live": "polite" });
  root.appendChild(tiles);
  var status = el("p", { "class": "dz-status", "aria-live": "polite" });
  root.appendChild(status);
  root.appendChild(el("p", { "class": "dz-legend" },
    "Assumptions, not measurements: 60% of peak bandwidth, 40% of peak FLOP/s, a 15% penalty for tensor-parallel communication, 90% of memory usable. Quantisation can change quality; this model ignores that."));

  function tile(label, value, cls) {
    var d = el("div", { "class": "dz-tile " + (cls || "") });
    d.appendChild(el("small", {}, label)); d.appendChild(el("b", {}, value));
    return d;
  }
  function gb(v) { return (v / 1e9).toFixed(v >= 1e10 ? 0 : 1) + " GB"; }

  function update() {
    Object.keys(outs).forEach(function (k) { outs[k].out.textContent = outs[k].fmt(state[k]); });
    var r = plan(PRECISIONS[state.prec][1], GPUS[state.g], CTX[state.ctx], KV_BYTES[state.kv][1], BATCHES[state.batch]);
    tiles.textContent = "";
    tiles.appendChild(tile("Weights", gb(r.W)));
    tiles.appendChild(tile("KV cache per sequence", gb(r.kv * CTX[state.ctx]), r.kv * CTX[state.ctx] > 2e9 ? "warn" : ""));
    if (!r.fits) {
      tiles.appendChild(tile("Fits in memory?", "no", "bad"));
      status.textContent = r.free <= 0
        ? "The weights alone do not fit in the memory of this many accelerators. Use more accelerators or lower precision."
        : "The weights fit but not even one sequence of this length fits beside them. Shorten the context, shrink the KV cache or add accelerators.";
      return;
    }
    var capped = r.B < BATCHES[state.batch];
    tiles.appendChild(tile("Sequences held", String(r.B) + (capped ? " (memory cap)" : ""), capped ? "warn" : "good"));
    tiles.appendChild(tile("Step time", (r.step * 1000).toFixed(1) + " ms"));
    tiles.appendChild(tile("Per-user speed", r.perStream.toFixed(1) + " tok/s", r.perStream < 20 ? "warn" : "good"));
    tiles.appendChild(tile("Replica throughput", Math.round(r.tps).toLocaleString("en-US") + " tok/s"));
    tiles.appendChild(tile("Bound by", r.bound));
    status.textContent = r.bound === "memory bandwidth"
      ? "Memory bound: every step must read all the weights plus the KV cache of every sequence, so a bigger batch is almost free until the KV cache starts to dominate."
      : "Compute bound: the arithmetic per step now exceeds the time to read memory; a bigger batch no longer raises throughput.";
  }
  update();
})();
