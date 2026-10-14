/* BM25 explorer (retrieval chapter 02).
   Eight short documents (the same ones used in the chapter's Python listings),
   a query box and sliders for k1 and b. Every document is scored with the
   Lucene-style BM25 formula and drawn as a stacked bar, one segment per query
   term, so you can see which term earned which share of the score. A small
   plot shows how the term-frequency component saturates for three document
   lengths. */
(function () {
  "use strict";
  var root = document.getElementById("ret02-bm25");
  if (!root) return;

  var DOCS = [
    ["d1", "Late payment fees apply when an invoice is paid after the due date. The late payment fee is 2 percent per month."],
    ["d2", "To dispute an invoice, contact billing within 30 days. Include the invoice number and a short description of the dispute."],
    ["d3", "Our refund policy: refunds are issued to the original payment method. Refunds take 5 to 10 working days."],
    ["d4", "Payment methods accepted: credit card, bank transfer and direct debit. Card payment is processed immediately."],
    ["d5", "Annual report. The company reported revenue growth, new products, hiring, office moves, a new brand, partnerships, sustainability goals, board changes and a long list of other matters. Late in the year a payment platform was launched. Customers can now pay invoices online. Further detail on payment, tax, audit, risk, governance, remuneration and the outlook can be found in the notes that follow this summary section of the report."],
    ["d6", "Invoice template: invoice number, invoice date, customer, line items, tax, total and payment terms."],
    ["d7", "Holiday calendar for staff. Offices are closed on public holidays. Request leave through the HR portal."],
    ["d8", "Tax invoice requirements: the invoice must show the supplier tax number, the date and the total tax charged."]
  ];
  var COLOURS = ["var(--blue)", "var(--orange)", "var(--green)", "var(--purple)", "var(--pink)"];
  var NS = "http://www.w3.org/2000/svg";

  function tok(s) { return s.toLowerCase().match(/[a-z0-9]+/g) || []; }

  var docs = DOCS.map(function (d) {
    var t = tok(d[1]), tf = {};
    t.forEach(function (w) { tf[w] = (tf[w] || 0) + 1; });
    return { id: d[0], len: t.length, tf: tf };
  });
  var N = docs.length, avg = 0, df = {};
  docs.forEach(function (d) { avg += d.len; for (var w in d.tf) df[w] = (df[w] || 0) + 1; });
  avg /= N;

  function idf(t) { var n = df[t] || 0; return Math.log(1 + (N - n + 0.5) / (n + 0.5)); }

  var q = root.querySelector("[data-act=query]");
  var k1In = root.querySelector("[data-act=k1]"), k1Out = root.querySelector("[data-act=k1-out]");
  var bIn = root.querySelector("[data-act=b]"), bOut = root.querySelector("[data-act=b-out]");
  var rows = root.querySelector(".r2-rows");
  var legend = root.querySelector(".r2-legend");
  var curve = root.querySelector(".r2-curve");
  var summary = root.querySelector(".r2-summary");

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function s(tag, attrs, text) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }

  function render() {
    var k1 = parseFloat(k1In.value), b = parseFloat(bIn.value);
    k1Out.textContent = k1.toFixed(1);
    bOut.textContent = b.toFixed(2);
    var terms = [];
    tok(q.value).forEach(function (t) { if (terms.indexOf(t) < 0) terms.push(t); });
    terms = terms.slice(0, 5);

    var scored = docs.map(function (d) {
      var parts = terms.map(function (t) {
        var tf = d.tf[t] || 0;
        if (!tf) return 0;
        return idf(t) * tf * (k1 + 1) / (tf + k1 * (1 - b + b * d.len / avg));
      });
      var total = 0; parts.forEach(function (p) { total += p; });
      return { d: d, parts: parts, total: total };
    }).filter(function (r) { return r.total > 0; });
    scored.sort(function (a, c) { return c.total - a.total; });

    legend.innerHTML = "";
    terms.forEach(function (t, i) {
      var item = el("span");
      var sw = el("i"); sw.style.background = COLOURS[i];
      item.appendChild(sw);
      item.appendChild(document.createTextNode(t + " (df " + (df[t] || 0) + ", idf " + idf(t).toFixed(2) + ")"));
      legend.appendChild(item);
    });

    rows.innerHTML = "";
    var max = scored.length ? scored[0].total : 1;
    scored.forEach(function (r) {
      var row = el("div", "r2-row");
      row.appendChild(el("div", "r2-id", r.d.id));
      var col = el("div");
      var bar = el("div", "r2-bar");
      r.parts.forEach(function (p, i) {
        if (!p) return;
        var seg = el("div", "r2-seg");
        seg.style.width = (100 * p / max).toFixed(1) + "%";
        seg.style.background = COLOURS[i];
        bar.appendChild(seg);
      });
      col.appendChild(bar);
      var meta = el("div", "r2-meta");
      var b1 = el("b", "", r.total.toFixed(3));
      meta.appendChild(b1);
      meta.appendChild(document.createTextNode("  length " + r.d.len + " terms, tf: " +
        terms.map(function (t) { return t + "=" + (r.d.tf[t] || 0); }).join(", ")));
      col.appendChild(meta);
      row.appendChild(col);
      rows.appendChild(row);
    });
    if (!scored.length) rows.appendChild(el("p", "widget-help", terms.length ? "No document contains any of these terms." : "Type a query."));

    var top = scored.length ? scored[0] : null;
    summary.textContent = top
      ? "Top result: " + top.d.id + " with " + top.total.toFixed(3) + ". Average document length is " + avg.toFixed(1) + " terms; d5 has " + docs[4].len + "."
      : "";

    drawCurve(k1, b);
  }

  function drawCurve(k1, b) {
    while (curve.firstChild) curve.removeChild(curve.firstChild);
    var W = 700, H = 230, L = 46, R = 12, T = 14, B = 36;
    var pw = W - L - R, ph = H - T - B, maxTf = 20, maxY = 6;
    function X(tf) { return L + pw * tf / maxTf; }
    function Y(v) { return T + ph - ph * Math.min(v, maxY) / maxY; }
    curve.appendChild(s("line", { x1: L, y1: T + ph, x2: W - R, y2: T + ph, "class": "line-thin" }));
    curve.appendChild(s("line", { x1: L, y1: T, x2: L, y2: T + ph, "class": "line-thin" }));
    [0, 2, 4, 6].forEach(function (v) {
      curve.appendChild(s("text", { x: L - 6, y: Y(v) + 4, "text-anchor": "end", "class": "t-xs t-faint" }, String(v)));
    });
    [0, 5, 10, 15, 20].forEach(function (v) {
      curve.appendChild(s("text", { x: X(v), y: T + ph + 16, "text-anchor": "middle", "class": "t-xs t-faint" }, String(v)));
    });
    curve.appendChild(s("text", { x: L + pw / 2, y: H - 4, "text-anchor": "middle", "class": "t-xs t-muted" }, "term frequency in the document (tf)"));
    curve.appendChild(s("text", { x: 12, y: T + ph / 2, "text-anchor": "middle", "class": "t-xs t-muted", transform: "rotate(-90 12 " + (T + ph / 2) + ")" }, "tf component"));
    // asymptote k1+1
    var asy = k1 + 1;
    if (asy <= maxY) {
      curve.appendChild(s("line", { x1: L, y1: Y(asy), x2: W - R, y2: Y(asy), "class": "line-dash s-yellow" }));
      curve.appendChild(s("text", { x: W - R - 4, y: Y(asy) - 5, "text-anchor": "end", "class": "t-xs tc-yellow t-bold" }, "ceiling k1+1 = " + asy.toFixed(1)));
    }
    var series = [
      { r: 0.5, cls: "s-green", label: "short (0.5 x average)" },
      { r: 1, cls: "s-blue", label: "average" },
      { r: 3, cls: "s-red", label: "long (3 x average)" }
    ];
    series.forEach(function (sr, i) {
      var d = "";
      for (var tf = 0; tf <= maxTf; tf += 0.25) {
        var v = tf === 0 ? 0 : tf * (k1 + 1) / (tf + k1 * (1 - b + b * sr.r));
        d += (d ? "L" : "M") + X(tf).toFixed(1) + "," + Y(v).toFixed(1);
      }
      curve.appendChild(s("path", { d: d, fill: "none", "class": "sw-2 " + sr.cls }));
      curve.appendChild(s("text", { x: L + 10, y: T + 14 + i * 14, "class": "t-xs t-bold " + sr.cls.replace("s-", "tc-") }, sr.label));
    });
  }

  [q, k1In, bIn].forEach(function (c) { c.addEventListener("input", render); });
  var reset = root.querySelector("[data-act=reset]");
  if (reset) reset.addEventListener("click", function () { k1In.value = "1.2"; bIn.value = "0.75"; render(); });
  render();
})();
