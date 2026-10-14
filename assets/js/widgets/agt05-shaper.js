/* Tool-response shaper (agents chapter 05).
   One tool, one question: "what is the largest overdue invoice for this customer?". You choose which fields the tool returns,
   how many rows per page and whether it can filter by status, and the widget reports how many tokens come back and whether the
   agent could actually answer. The 60 invoices are generated from a fixed seed. Tokens are estimated as characters / 4, a rough
   stand-in for a real tokeniser. The 25,000-token line is the default response cap Anthropic's "Writing effective tools for
   agents" post describes for Claude Code; it is drawn here only as a reference mark. */
(function () {
  "use strict";

  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function makeInvoices(n, seed) {
    var rnd = mulberry32(seed), rows = [], i, k, st = ["paid", "paid", "open", "overdue"];
    for (i = 0; i < n; i++) {
      var items = [];
      for (k = 1; k <= 3; k++) items.push({ sku: "plan-" + k, qty: 1, unit_cents: 900 * k });
      rows.push({
        id: "inv_" + (3000 + i), status: st[Math.floor(rnd() * 4)], amount_cents: 900 + Math.floor(rnd() * 19100),
        currency: "GBP", created_at: "2026-0" + (1 + i % 9) + "-" + (10 + i % 18),
        line_items: items,
        billing_address: { line1: "12 Mill Lane", city: "Leeds", postcode: "LS1 4AB", country: "GB" },
        audit_trail: [{ at: "2026-01-01T09:00:00Z", actor: "system", event: "created" }, { at: "2026-01-01T09:00:01Z", actor: "system", event: "emailed" },
                      { at: "2026-01-02T09:00:00Z", actor: "system", event: "reminder" }, { at: "2026-01-09T09:00:00Z", actor: "system", event: "reminder" }]
      });
    }
    return rows;
  }

  function evaluate(rows, o) {
    var pool = o.filter ? rows.filter(function (r) { return r.status === "overdue"; }) : rows;
    var page = pool.slice(0, o.limit);
    var out = page.map(function (r) {
      var x = {}; o.fields.forEach(function (f) { x[f] = r[f]; }); return x;
    });
    var body = { invoices: out, total_matching: pool.length };
    var text = JSON.stringify(body);
    var overdueAll = rows.filter(function (r) { return r.status === "overdue"; });
    var seen = page.filter(function (r) { return r.status === "overdue"; }).length;
    var needs = ["id", "status", "amount_cents"].filter(function (f) { return o.fields.indexOf(f) < 0; });
    var best = overdueAll.reduce(function (a, b) { return b.amount_cents > a.amount_cents ? b : a; }, overdueAll[0]);
    return { text: text, tokens: Math.ceil(text.length / 4), needsMissing: needs, overdueSeen: seen,
             overdueTotal: overdueAll.length, rows: page.length, best: best };
  }

  var core = { makeInvoices: makeInvoices, evaluate: evaluate };
  if (typeof module !== "undefined" && module.exports) module.exports = core;
  if (typeof document === "undefined") return;
  var root = document.getElementById("agt05-shaper");
  if (!root) return;

  function el(tag, attrs, text) {
    var e = document.createElement(tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }
  var ALL = ["id", "status", "amount_cents", "currency", "created_at", "line_items", "billing_address", "audit_trail"];
  var rows = makeInvoices(60, 7);
  var state = { fields: ["id", "status", "amount_cents"], limit: 10, filter: false };
  var CAP = 25000;

  var head = el("div", { "class": "widget-head" });
  head.appendChild(el("span", { "class": "widget-tag" }, "Try it"));
  head.appendChild(el("h4", { "class": "widget-title" }, "Shape one tool response"));
  root.appendChild(head);
  root.appendChild(el("p", { "class": "widget-help" },
    "The agent's question is: what is the largest overdue invoice for this customer? The customer has 60 invoices. Choose what the tool returns " +
    "and watch the size of the result and whether the question can still be answered."));

  var ctl = el("div", { "class": "ag05-ctl" });
  var fset = el("fieldset", { "class": "ag05-fields" });
  fset.appendChild(el("legend", {}, "Fields returned per invoice"));
  var boxes = {};
  ALL.forEach(function (f) {
    var lab = el("label", { "class": "ag05-check" });
    var cb = el("input", { type: "checkbox", id: "agt05-f-" + f });
    cb.checked = state.fields.indexOf(f) >= 0;
    cb.addEventListener("change", function () {
      state.fields = ALL.filter(function (g) { return boxes[g].checked; });
      update();
    });
    boxes[f] = cb;
    lab.appendChild(cb);
    lab.appendChild(document.createTextNode(" " + f));
    fset.appendChild(lab);
  });
  ctl.appendChild(fset);

  var w1 = el("div");
  var l1 = el("label", { "for": "agt05-limit" }, "Rows per page: ");
  var o1 = el("output", { id: "agt05-limit-out" });
  l1.appendChild(o1);
  var sl = el("input", { type: "range", id: "agt05-limit", min: 1, max: 60, step: 1, value: state.limit });
  sl.addEventListener("input", function () { state.limit = parseInt(sl.value, 10); update(); });
  w1.appendChild(l1); w1.appendChild(sl);
  var w2 = el("div");
  var l2 = el("label", { "class": "ag05-check" });
  var fc = el("input", { type: "checkbox", id: "agt05-filter" });
  fc.addEventListener("change", function () { state.filter = fc.checked; update(); });
  l2.appendChild(fc);
  l2.appendChild(document.createTextNode(" tool accepts status=overdue and the agent uses it"));
  w2.appendChild(l2);
  var side = el("div"); side.appendChild(w1); side.appendChild(w2);
  ctl.appendChild(side);
  root.appendChild(ctl);

  var bar = el("div", { "class": "ag05-bar", "aria-hidden": "true" });
  var fill = el("div", { "class": "ag05-fill" });
  bar.appendChild(fill);
  root.appendChild(bar);
  var out = el("div", { "class": "widget-out", "aria-live": "polite" });
  root.appendChild(out);
  var pre = el("pre", { "class": "ag05-sample" });
  root.appendChild(pre);

  function update() {
    var r = evaluate(rows, state);
    o1.textContent = String(state.limit);
    var pct = Math.min(100, r.tokens / CAP * 100);
    fill.style.width = Math.max(1, pct).toFixed(1) + "%";
    out.textContent = "";
    function line(t, cls) { var p = el("p", cls ? { "class": cls } : {}, t); out.appendChild(p); }
    line("Result size: about " + r.tokens.toLocaleString("en-GB") + " tokens (" + r.rows + " rows). The bar is the share of a 25,000-token reference cap.");
    if (r.needsMissing.length) {
      line("Cannot answer: the result lacks " + r.needsMissing.join(", ") + ".", "ag05-bad");
    } else if (r.overdueSeen < r.overdueTotal) {
      line("Might answer wrongly: only " + r.overdueSeen + " of the customer's " + r.overdueTotal + " overdue invoices are in this page, so the largest one may be missing. A good tool says so and offers a filter or the next page.", "ag05-warn");
    } else {
      line("Can answer: all " + r.overdueTotal + " overdue invoices are visible. The largest is " + r.best.id + " at " + r.best.amount_cents + " cents.", "ag05-good");
    }
    if (r.tokens > CAP) line("Over the reference cap: a real harness would truncate this, and the end of the data would be lost.", "ag05-bad");
    pre.textContent = r.text.length > 360 ? r.text.slice(0, 360) + " ..." : r.text;
  }
  update();
})();
