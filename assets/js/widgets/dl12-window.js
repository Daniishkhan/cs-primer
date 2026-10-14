/* Window explorer (A2 chapter 12).
   A training example for a language model is a window of T characters x and the same window
   shifted by one, y. One window gives T prediction problems at once: at position t the model sees
   x[0..t] and must predict y[t]. The grid shows which inputs each position may read (the causal mask). */
(function () {
  "use strict";
  var root = document.getElementById("dl12-window");
  if (!root) return;
  var NS = "http://www.w3.org/2000/svg";
  var q = function (sel) { return root.querySelector(sel); };
  var textIn = q("[data-act=text]"), tIn = q("[data-act=t]"), tOut = q("[data-act=t-out]"),
      offIn = q("[data-act=off]"), offOut = q("[data-act=off-out]"), batchBtn = q("[data-act=batch]");
  var svg = q(".dl12-chart"), out = q(".dl12-summary"), batchOut = q(".dl12-batch");
  var seed = 7;

  function el(tag, attrs, text) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function vis(c) { return c === "\n" ? "↵" : (c === " " ? "·" : c); }
  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function draw() {
    var text = textIn.value, T = parseInt(tIn.value, 10);
    var maxOff = Math.max(0, text.length - T - 1);
    offIn.max = String(maxOff);
    var off = Math.min(parseInt(offIn.value, 10) || 0, maxOff);
    tOut.textContent = String(T);
    offOut.textContent = String(off);
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    if (text.length < T + 1) {
      out.textContent = "Type at least " + (T + 1) + " characters: a window needs T inputs and one extra character for the last target.";
      return;
    }
    var x = text.substr(off, T), y = text.substr(off + 1, T);
    var cw = Math.min(40, Math.floor(600 / T)), left = 96, top = 8;
    var rowH = Math.max(14, Math.round(cw * 0.62));
    svg.setAttribute("viewBox", "0 0 720 " + (top + 92 + T * rowH + 12));
    svg.appendChild(el("text", { x: 10, y: top + 22, "class": "t-sm t-bold" }, "x (input)"));
    svg.appendChild(el("text", { x: 10, y: top + 56, "class": "t-sm t-bold" }, "y (target)"));
    var t, s;
    for (t = 0; t < T; t++) {
      svg.appendChild(el("rect", { x: left + t * cw, y: top, width: cw - 3, height: 30, rx: 5, "class": "fs-blue s-blue sw-1" }));
      svg.appendChild(el("text", { x: left + t * cw + (cw - 3) / 2, y: top + 20, "text-anchor": "middle", "class": "mono t-sm" }, vis(x.charAt(t))));
      svg.appendChild(el("rect", { x: left + t * cw, y: top + 34, width: cw - 3, height: 30, rx: 5, "class": "fs-yellow s-yellow sw-1" }));
      svg.appendChild(el("text", { x: left + t * cw + (cw - 3) / 2, y: top + 54, "text-anchor": "middle", "class": "mono t-sm" }, vis(y.charAt(t))));
    }
    var gy = top + 92;
    svg.appendChild(el("text", { x: 10, y: gy - 8, "class": "t-xs t-muted" }, "position t reads the blue cells and must output the yellow cell"));
    for (s = 0; s < T; s++) {
      svg.appendChild(el("text", { x: left - 8, y: gy + s * rowH + rowH * 0.72, "text-anchor": "end", "class": "t-xs t-muted" }, "t=" + s));
      for (t = 0; t < T; t++) {
        var cls = t <= s ? "f-blue" : "box";
        var r = el("rect", { x: left + t * cw, y: gy + s * rowH, width: cw - 3, height: rowH - 2, rx: 3, "class": cls, opacity: t <= s ? 0.55 : 0.25 });
        svg.appendChild(r);
      }
      svg.appendChild(el("rect", { x: left + T * cw + 2, y: gy + s * rowH, width: cw - 3, height: rowH - 2, rx: 3, "class": "f-yellow", opacity: 0.85 }));
      svg.appendChild(el("text", { x: left + T * cw + 2 + (cw - 3) / 2, y: gy + s * rowH + rowH * 0.72, "text-anchor": "middle", "class": "mono t-xs t-dark" }, vis(y.charAt(s))));
    }
    var k = Math.min(T - 1, 3);
    out.textContent = "This one window is " + T + " training examples. At t=" + k + " the model sees " + JSON.stringify(x.substr(0, k + 1)) +
      " and must predict " + JSON.stringify(y.charAt(k)) + "; at t=" + (T - 1) + " it sees all of x and must predict " + JSON.stringify(y.charAt(T - 1)) +
      ". Text offset " + off + ", so y starts one character later, at " + (off + 1) + ".";
  }

  function batch() {
    var text = textIn.value, T = parseInt(tIn.value, 10);
    var maxOff = text.length - T - 1;
    if (maxOff < 0) { batchOut.textContent = ""; return; }
    seed = (seed * 1103515245 + 12345) & 0x7fffffff;
    var rng = mulberry32(seed), lines = ["B = 4 random windows (offset, x):"], i;
    for (i = 0; i < 4; i++) {
      var o = Math.floor(rng() * (maxOff + 1));
      lines.push("  " + ("   " + o).slice(-4) + "  " + text.substr(o, T).split("").map(vis).join(""));
    }
    lines.push("The tensors would be x and y of shape (4, " + T + ").");
    batchOut.textContent = lines.join("\n");
  }

  [tIn, offIn].forEach(function (c) { c.addEventListener("input", draw); });
  textIn.addEventListener("input", draw);
  batchBtn.addEventListener("click", batch);
  draw();
})();
