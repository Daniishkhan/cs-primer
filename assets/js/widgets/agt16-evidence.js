/* Counting witnesses, not documents (agents chapter 16)
   The same cross-check rules as the chapter's research2.py: claims are grouped by (metric, year); a value is
   supported by distinct ORIGINS, so a news story quoting a report is not a second witness. Documents are the chapter's
   fictional Northvale corpus. */
(function () {
  "use strict";

  var DOCS = [
    { id: "d1", title: "Annual Accounts 2024", kind: "primary", from: null, claims: [["road repair spend", 2024, 4.2], ["road repair spend", 2023, 3.4]] },
    { id: "d2", title: "County Audit Office review", kind: "primary", from: null, claims: [["road repair spend", 2024, 4.2], ["road repair spend", 2023, 3.4]] },
    { id: "d3", title: "Courier: roads bill rises", kind: "news", from: "d1", claims: [["road repair spend", 2024, 4.2], ["road repair spend", 2023, 3.4]] },
    { id: "d8", title: "Regional Gazette", kind: "news", from: null, claims: [["road repair spend", 2024, 4.5]] },
    { id: "d4", title: "Roads and Rates blog", kind: "blog", from: null, claims: [["road repair spend", 2022, 3.1]] },
    { id: "d5", title: "Community forum thread", kind: "forum", from: null, claims: [["road repair spend", 2024, 6.0]] }
  ];
  var KEYS = [["road repair spend", 2024], ["road repair spend", 2023]];

  function evaluate(selected, countCopies) {
    var out = [];
    KEYS.forEach(function (k) {
      var byValue = {}, any = false;
      DOCS.forEach(function (d) {
        if (!selected[d.id]) return;
        d.claims.forEach(function (c) {
          if (c[0] !== k[0] || c[1] !== k[1]) return;
          any = true;
          var key = String(c[2]);
          byValue[key] = byValue[key] || { origins: {}, docs: [] };
          byValue[key].origins[countCopies ? d.id : (d.from || d.id)] = true;
          byValue[key].docs.push(d.id);
        });
      });
      var values = Object.keys(byValue);
      var status = "no evidence";
      if (values.length > 1) status = "conflict";
      else if (values.length === 1) status = Object.keys(byValue[values[0]].origins).length > 1 ? "corroborated" : "single source";
      out.push({ metric: k[0], year: k[1], byValue: byValue, values: values, status: status, any: any });
    });
    return out;
  }

  var core = { evaluate: evaluate, DOCS: DOCS };
  if (typeof module !== "undefined" && module.exports) module.exports = core;
  if (typeof document === "undefined") return;
  var root = document.getElementById("agt16-evidence");
  if (!root) return;

  function el(tag, attrs, text) {
    var e = document.createElement(tag), k;
    for (k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }

  var state = { sel: { d1: true, d2: false, d3: true, d8: false, d4: false, d5: false }, copies: false };
  var head = el("div", { "class": "widget-head" });
  head.appendChild(el("span", { "class": "widget-tag" }, "Try it"));
  head.appendChild(el("h4", { "class": "widget-title" }, "Which documents did the agent read?"));
  root.appendChild(head);
  root.appendChild(el("p", { "class": "widget-help" },
    "Tick the sources the agent opened. The board shows how well each claim is supported. Try ticking only the accounts and the Courier, which quotes the accounts, then add the audit office. Then tick the box at the bottom to see how counting documents instead of origins inflates confidence."));

  var list = el("div", { "class": "ag16-docs" });
  DOCS.forEach(function (d) {
    var lab = el("label", { "class": "ag16-doc" });
    var cb = el("input", { type: "checkbox", id: "agt16-" + d.id });
    cb.checked = !!state.sel[d.id];
    cb.addEventListener("change", function () { state.sel[d.id] = cb.checked; update(); });
    lab.appendChild(cb);
    lab.appendChild(el("span", { "class": "ag16-title" }, " " + d.title));
    lab.appendChild(el("span", { "class": "ag16-meta" }, d.kind + (d.from ? ", quotes " + d.from : "")));
    list.appendChild(lab);
  });
  root.appendChild(list);

  var cl = el("label", { "class": "ag16-copies" });
  var cc = el("input", { type: "checkbox", id: "agt16-copies" });
  cc.addEventListener("change", function () { state.copies = cc.checked; update(); });
  cl.appendChild(cc);
  cl.appendChild(document.createTextNode(" Count every document as a separate witness (the mistake)"));
  root.appendChild(cl);

  var board = el("div", { "class": "ag16-board", "aria-live": "polite" });
  root.appendChild(board);

  function update() {
    var res = evaluate(state.sel, state.copies);
    board.innerHTML = "";
    res.forEach(function (r) {
      var row = el("div", { "class": "ag16-row ag16-" + r.status.replace(" ", "-") });
      row.appendChild(el("strong", {}, r.metric + " " + r.year));
      var detail;
      if (!r.any) detail = "no evidence yet: do not state it";
      else detail = r.values.map(function (v) {
        var b = r.byValue[v], n = Object.keys(b.origins).length;
        return v + " million (" + n + (state.copies ? " document" : " independent origin") + (n === 1 ? "" : "s") + ": " + b.docs.join(", ") + ")";
      }).join("  versus  ");
      row.appendChild(el("span", {}, detail));
      row.appendChild(el("em", {}, r.status));
      board.appendChild(row);
    });
  }
  update();
})();
