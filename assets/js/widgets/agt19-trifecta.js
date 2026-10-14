/* The lethal trifecta checker (agents chapter 19).
   Three legs (private data, untrusted content, a way out) and three controls. The verdict follows the chapter's rule:
   data theft needs all three legs to be effective at once; a control either removes a leg or only narrows it. */
(function () {
  "use strict";

  var PRESETS = [
    { id: "mail", name: "Email assistant that reads your inbox and can send mail", a: 1, b: 1, c: 1,
      note: "Inbound mail is written by strangers, the inbox is private, and sending mail is a way out." },
    { id: "code", name: "Coding agent in a sandbox with no network, reading public issues", a: 1, b: 1, c: 0,
      note: "It sees private source and untrusted issue text, but nothing it can do reaches the outside world." },
    { id: "docs", name: "Public documentation Q&A bot with no access to user data", a: 0, b: 1, c: 1,
      note: "Anyone can feed it text and it can emit links, but there is nothing private to steal." },
    { id: "support", name: "Support agent with an order database that replies to customers", a: 1, b: 1, c: 1,
      note: "The customer's message is untrusted, the database is private, and the reply goes back to the customer, who may be the attacker." }
  ];
  var LEGS = [
    { key: "a", label: "Access to private data" },
    { key: "b", label: "Exposure to untrusted content" },
    { key: "c", label: "A way to communicate externally" }
  ];
  var CONTROLS = [
    { key: "quarantine", label: "Quarantine: untrusted text is read only by a model with no tools or data", cuts: "b" },
    { key: "egress", label: "Egress allow-list: outbound requests only to hosts you control", narrows: "c" },
    { key: "approve", label: "A person approves every outbound action after untrusted input", narrows: "c" }
  ];

  function verdict(s) {
    var eff = { a: s.a, b: s.b, c: s.c }, narrowed = [], cut = [];
    CONTROLS.forEach(function (k) {
      if (!s[k.key]) return;
      if (k.cuts && eff[k.cuts]) { eff[k.cuts] = 0; cut.push(k.label.split(":")[0]); }
      if (k.narrows && eff[k.narrows]) narrowed.push(k.label.split(":")[0]);
    });
    var present = eff.a + eff.b + eff.c;
    if (present < 3) return { level: "ok", legs: eff, text: present + " of 3 legs effective. There is no complete exfiltration path, because the attacker's instructions cannot reach private data and a way out in the same session. Other harms (wrong answers, misuse of write tools) remain." };
    if (narrowed.length) return { level: "warn", legs: eff, text: "All three legs are still present, but the way out is narrowed (" + narrowed.join(", ") + "). Residual risk: an allow-listed service the attacker can also read, or an approval prompt a tired person clicks through. Treat this as risk reduction, not a fix." };
    return { level: "bad", legs: eff, text: "All three legs are effective. An instruction hidden in untrusted content can make the agent read private data and send it out. Remove a leg, or do not run this combination." };
  }

  if (typeof module !== "undefined" && module.exports) module.exports = { verdict: verdict, PRESETS: PRESETS };
  if (typeof document === "undefined") return;
  var root = document.getElementById("agt19-trifecta");
  if (!root) return;

  var NS = "http://www.w3.org/2000/svg";
  function el(tag, attrs, text) {
    var e = document.createElement(tag), k;
    for (k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function sv(tag, attrs, text) {
    var e = document.createElementNS(NS, tag), k;
    for (k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }

  var state = { a: 1, b: 1, c: 1, quarantine: 0, egress: 0, approve: 0 };
  root.appendChild(el("div", { "class": "widget-head" })).innerHTML = '<span class="widget-tag">Try it</span><h4 class="widget-title">Does this agent have the lethal trifecta?</h4>';
  root.appendChild(el("p", { "class": "widget-help" }, "Pick a preset or set the three legs yourself, then switch on controls and watch the verdict. The presets are illustrations, not audits of any product."));

  var sel = el("select", { id: "agt19-preset", "aria-label": "Preset agent" });
  sel.appendChild(el("option", { value: "" }, "Custom (set the legs below)"));
  PRESETS.forEach(function (p) { sel.appendChild(el("option", { value: p.id }, p.name)); });
  var row = el("div", { "class": "widget-row" });
  row.appendChild(sel);
  root.appendChild(row);

  var note = el("p", { "class": "widget-help ag19-note" });
  root.appendChild(note);

  var boxes = el("div", { "class": "ag19-cols" });
  var c1 = el("fieldset", { "class": "ag19-set" }), c2 = el("fieldset", { "class": "ag19-set" });
  c1.appendChild(el("legend", {}, "Legs"));
  c2.appendChild(el("legend", {}, "Controls"));
  var inputs = {};
  function check(parent, key, label) {
    var l = el("label", { "class": "ag19-check" });
    var i = el("input", { type: "checkbox" });
    i.addEventListener("change", function () { state[key] = i.checked ? 1 : 0; sel.value = ""; note.textContent = ""; update(); });
    l.appendChild(i); l.appendChild(document.createTextNode(" " + label));
    parent.appendChild(l); inputs[key] = i;
  }
  LEGS.forEach(function (g) { check(c1, g.key, g.label); });
  CONTROLS.forEach(function (k) { check(c2, k.key, k.label); });
  boxes.appendChild(c1); boxes.appendChild(c2);
  root.appendChild(boxes);

  var svg = sv("svg", { viewBox: "0 0 300 214", "class": "ag19-venn", role: "img", "aria-label": "Three overlapping circles for the three legs; the centre is shaded when all three are effective." });
  root.appendChild(svg);
  var out = el("div", { "class": "widget-out", "aria-live": "polite" });
  root.appendChild(out);

  sel.addEventListener("change", function () {
    var p = PRESETS.filter(function (x) { return x.id === sel.value; })[0];
    if (!p) { note.textContent = ""; return; }
    state.a = p.a; state.b = p.b; state.c = p.c; state.quarantine = state.egress = state.approve = 0;
    note.textContent = p.note; update();
  });

  function update() {
    var v = verdict(state), k;
    for (k in inputs) inputs[k].checked = !!state[k];
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    var pos = { a: [105, 85, "Private data"], b: [195, 85, "Untrusted content"], c: [150, 150, "Way out"] };
    ["a", "b", "c"].forEach(function (key) {
      var on = v.legs[key];
      svg.appendChild(sv("circle", { cx: pos[key][0], cy: pos[key][1], r: 58, "class": "ag19-circle" + (on ? " on" : " off") }));
    });
    svg.appendChild(sv("text", { x: 70, y: 40, "class": "ag19-lbl" }, pos.a[2]));
    svg.appendChild(sv("text", { x: 230, y: 40, "class": "ag19-lbl", "text-anchor": "middle" }, pos.b[2]));
    svg.appendChild(sv("text", { x: 150, y: 190, "class": "ag19-lbl", "text-anchor": "middle" }, pos.c[2]));
    if (v.level === "bad") svg.appendChild(sv("circle", { cx: 150, cy: 108, r: 13, "class": "ag19-core" }));
    out.className = "widget-out ag19-" + v.level;
    out.textContent = v.text;
  }
  inputs.a.checked = true;
  update();
})();
