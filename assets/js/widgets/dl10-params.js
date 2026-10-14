/* Transformer parameter calculator (A2 chapter 10).
   Counts the weights of a decoder-only Transformer from its width, depth and design choices,
   using the formulas of the chapter: attention 4C^2, MLP 8C^2 (GELU, hidden 4C) or 3*C*d_ff (SwiGLU),
   norms, token embeddings (optionally tied with the output head) and an optional learned position table. */
(function () {
  "use strict";
  var root = document.getElementById("dl10-params");
  if (!root) return;
  var NS = "http://www.w3.org/2000/svg";
  var q = function (sel) { return root.querySelector(sel); };
  var presetSel = q("[data-act=preset]"), cIn = q("[data-act=c]"), lIn = q("[data-act=l]"), vSel = q("[data-act=v]"),
      mlpSel = q("[data-act=mlp]"), biasChk = q("[data-act=bias]"), tieChk = q("[data-act=tie]"), posChk = q("[data-act=pos]");
  var cOut = q("[data-act=c-out]"), lOut = q("[data-act=l-out]");
  var svg = q(".dl10-chart"), tbl = q(".dl10-table");

  var PRESETS = {
    gpt2s: { c: 768, l: 12, v: 50257, mlp: "gelu", bias: true, tie: true, pos: true },
    gpt2m: { c: 1024, l: 24, v: 50257, mlp: "gelu", bias: true, tie: true, pos: true },
    gpt2l: { c: 1280, l: 36, v: 50257, mlp: "gelu", bias: true, tie: true, pos: true },
    gpt2xl: { c: 1600, l: 48, v: 50257, mlp: "gelu", bias: true, tie: true, pos: true },
    llama7: { c: 4096, l: 32, v: 32000, mlp: "swiglu", bias: false, tie: false, pos: false }
  };

  function el(tag, attrs, text) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function fmt(n) {
    var s = String(Math.round(n)), out = "", i;
    for (i = 0; i < s.length; i++) { if (i && (s.length - i) % 3 === 0) out += ","; out += s.charAt(i); }
    return out;
  }
  function human(n) {
    if (n >= 1e9) return (n / 1e9).toFixed(2) + " B";
    return (n / 1e6).toFixed(1) + " M";
  }

  function setPreset(name) {
    var p = PRESETS[name];
    if (!p) return;
    cIn.value = p.c; lIn.value = p.l; vSel.value = String(p.v); mlpSel.value = p.mlp;
    biasChk.checked = p.bias; tieChk.checked = p.tie; posChk.checked = p.pos;
  }

  function compute() {
    var C = parseInt(cIn.value, 10), L = parseInt(lIn.value, 10), V = parseInt(vSel.value, 10);
    var swiglu = mlpSel.value === "swiglu", bias = biasChk.checked, tie = tieChk.checked, pos = posChk.checked;
    var dff = swiglu ? Math.ceil(8 * C / 3 / 256) * 256 : 4 * C;
    var attn = 4 * C * C + (bias ? 4 * C : 0);
    var mlp = swiglu ? 3 * C * dff + (bias ? 2 * dff + C : 0) : 2 * C * dff + (bias ? dff + C : 0);
    var norms = 2 * (bias ? 2 * C : C);
    var emb = V * C * (tie ? 1 : 2) + (pos ? 1024 * C : 0);
    var fin = bias ? 2 * C : C;
    var total = L * (attn + mlp + norms) + emb + fin;
    return { C: C, L: L, V: V, dff: dff, attn: L * attn, mlp: L * mlp, norms: L * norms + fin, emb: emb, total: total, block: attn + mlp + norms };
  }

  function draw() {
    cOut.textContent = cIn.value; lOut.textContent = lIn.value;
    var r = compute();
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    var x = 10, W = 680, segs = [["attention", r.attn, "f-blue"], ["MLP", r.mlp, "f-purple"], ["embeddings", r.emb, "f-orange"], ["norms", r.norms, "f-teal"]];
    var i, s;
    for (i = 0; i < segs.length; i++) {
      var w = W * segs[i][1] / r.total;
      svg.appendChild(el("rect", { x: x, y: 20, width: Math.max(w, 0.5), height: 34, "class": segs[i][2] }));
      if (w > 62) svg.appendChild(el("text", { x: x + w / 2, y: 42, "text-anchor": "middle", "class": "t-xs t-bold t-dark" }, Math.round(100 * segs[i][1] / r.total) + "%"));
      x += w;
    }
    var lx = 10;
    for (i = 0; i < segs.length; i++) {
      svg.appendChild(el("rect", { x: lx, y: 74, width: 12, height: 12, "class": segs[i][2] }));
      s = el("text", { x: lx + 18, y: 85, "class": "t-xs" }, segs[i][0]);
      svg.appendChild(s);
      lx += 28 + segs[i][0].length * 7;
    }
    var rows = [
      ["Hidden width of the MLP", fmt(r.dff)],
      ["Parameters per block", fmt(r.block)],
      ["Attention (all layers)", fmt(r.attn)],
      ["MLP (all layers)", fmt(r.mlp)],
      ["Embeddings (and head if untied)", fmt(r.emb)],
      ["Total", fmt(r.total) + " (" + human(r.total) + ")"],
      ["Weights alone in 16-bit numbers", (r.total * 2 / 1e9).toFixed(2) + " GB"]
    ];
    tbl.innerHTML = "";
    rows.forEach(function (row) {
      var tr = document.createElement("tr"), a = document.createElement("td"), b = document.createElement("td");
      a.textContent = row[0]; b.textContent = row[1]; tr.appendChild(a); tr.appendChild(b); tbl.appendChild(tr);
    });
  }

  presetSel.addEventListener("change", function () { if (presetSel.value !== "custom") setPreset(presetSel.value); draw(); });
  [cIn, lIn].forEach(function (c) { c.addEventListener("input", function () { presetSel.value = "custom"; draw(); }); });
  [vSel, mlpSel, biasChk, tieChk, posChk].forEach(function (c) { c.addEventListener("change", function () { presetSel.value = "custom"; draw(); }); });
  setPreset("gpt2s");
  draw();
})();
