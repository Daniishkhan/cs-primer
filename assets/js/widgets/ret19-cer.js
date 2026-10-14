/* Error-rate explorer (retrieval chapter 19).
   Aligns an OCR hypothesis with the reference by edit distance, colours substitutions, deletions
   and insertions, and reports character and word error rates and whether the numbers survived. */
(function () {
  "use strict";
  var root = document.getElementById("ret19-cer");
  if (!root) return;

  var PRESETS = [
    { label: "Classical slips: letters for digits", ref: "Invoice 4021 total 1,590.00 due 30 June", hyp: "Invoice 402l total 1,59O.OO due 30 June" },
    { label: "Fluent but wrong: one digit changed", ref: "Invoice 4021 total 1,590.00 due 30 June", hyp: "Invoice 4021 total 1,580.00 due 30 June" },
    { label: "Silent omission: a clause vanishes", ref: "Payment is due in 30 days. Late fees of 1.5% a month apply. Disputes go to arbitration.", hyp: "Payment is due in 30 days. Disputes go to arbitration." },
    { label: "Perfect copy", ref: "Net weight 250 g", hyp: "Net weight 250 g" },
    { label: "Write your own", ref: "", hyp: "" }
  ];

  function q(n) { return root.querySelector("[data-act=" + n + "]"); }
  var selP = q("preset"), inR = q("ref"), inH = q("hyp");
  var out = root.querySelector(".r19-align"), stats = root.querySelector(".r19-stats"), note = root.querySelector(".r19-note");

  function align(a, b) {
    var n = a.length, m = b.length, d = [], i, j;
    for (i = 0; i <= n; i++) { d.push([]); for (j = 0; j <= m; j++) d[i].push(0); }
    for (i = 0; i <= n; i++) d[i][0] = i;
    for (j = 0; j <= m; j++) d[0][j] = j;
    for (i = 1; i <= n; i++) for (j = 1; j <= m; j++) {
      d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
    }
    var ops = [];
    i = n; j = m;
    while (i > 0 || j > 0) {
      if (i > 0 && j > 0 && a[i - 1] === b[j - 1] && d[i][j] === d[i - 1][j - 1]) { ops.push(["ok", a[i - 1], b[j - 1]]); i--; j--; }
      else if (i > 0 && j > 0 && d[i][j] === d[i - 1][j - 1] + 1) { ops.push(["sub", a[i - 1], b[j - 1]]); i--; j--; }
      else if (i > 0 && d[i][j] === d[i - 1][j] + 1) { ops.push(["del", a[i - 1], ""]); i--; }
      else { ops.push(["ins", "", b[j - 1]]); j--; }
    }
    ops.reverse();
    return { dist: d[n][m], ops: ops };
  }

  function esc(s) { return s.replace(/&/g, "&amp;").replace(/</g, "&lt;"); }
  function span(cls, s) { return '<span class="r19-ch ' + cls + '">' + esc(s === " " ? "·" : s) + "</span>"; }
  function numbers(s) { return (s.match(/\d[\d,.]*\d|\d/g) || []).join(" "); }

  function row(k, v) { return '<div class="r19-row"><span>' + k + "</span><b>" + v + "</b></div>"; }

  function update() {
    var ref = inR.value, hyp = inH.value;
    var ca = align(ref.split(""), hyp.split(""));
    var wa = align(ref.split(/\s+/).filter(Boolean), hyp.split(/\s+/).filter(Boolean));
    var r = "", h = "", s = 0, dl = 0, ins = 0, k, op;
    for (k = 0; k < ca.ops.length; k++) {
      op = ca.ops[k];
      if (op[0] === "ok") { r += span("", op[1]); h += span("", op[2]); }
      else if (op[0] === "sub") { s++; r += span("r19-sub", op[1]); h += span("r19-sub", op[2]); }
      else if (op[0] === "del") { dl++; r += span("r19-del", op[1]); }
      else { ins++; h += span("r19-ins", op[2]); }
    }
    out.innerHTML = "<div><b>reference</b>" + r + "</div><div><b>OCR output</b>" + h + "</div>";
    var nref = ref.length, nw = ref.split(/\s+/).filter(Boolean).length;
    var cerV = nref ? ca.dist / nref : 0, werV = nw ? wa.dist / nw : 0;
    var nr = numbers(ref), nh = numbers(hyp);
    stats.innerHTML = row("Character error rate", (cerV * 100).toFixed(1) + "%") +
      row("Substitutions / deletions / insertions", s + " / " + dl + " / " + ins) +
      row("Word error rate", (werV * 100).toFixed(1) + "%") +
      row("Numbers identical to the reference?", nr === nh ? "yes" : "NO");
    note.textContent = nr === nh ? "Every number survived." :
      "Numbers in the reference: " + (nr || "none") + ". Numbers in the output: " + (nh || "none") + ". A low error rate can still hide a wrong amount.";
  }

  var i;
  for (i = 0; i < PRESETS.length; i++) {
    var o = document.createElement("option"); o.value = String(i); o.textContent = PRESETS[i].label; selP.appendChild(o);
  }
  function load() {
    var p = PRESETS[parseInt(selP.value, 10)];
    if (p.ref || p.hyp) { inR.value = p.ref; inH.value = p.hyp; }
    update();
  }
  selP.addEventListener("change", load);
  inR.addEventListener("input", update);
  inH.addEventListener("input", update);
  load();
})();
