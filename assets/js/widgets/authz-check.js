/* Relationship-based authorization check (security chapter 8).

   A small set of relation tuples (object, relation, subject) in the style of Google's Zanzibar
   (Pang et al., USENIX ATC 2019), plus rewrite rules. Pick an object, a relation and a user; the
   widget runs the check and highlights the tuples on the path that grants access. Untick a tuple to
   simulate removing it and run the check again: access that depended on it disappears.
   Rewrite rules used (the same as the chapter's Python example):
     doc#owner   : direct
     doc#editor  : direct, or owner
     doc#viewer  : direct, or editor, or viewer of the document's parent folder
     folder#viewer, group#member : direct (a subject may itself be a userset such as group:eng#member)
   Simplifications: no caching, no consistency tokens, no negative rules (exclusion), cycles are cut.
   Missing path means deny (default deny). State is in memory only. */
(function () {
  "use strict";
  var root = document.getElementById("authz-check");
  if (!root) return;
  function h(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }

  var TUPLES = [
    ["doc:plan",      "parent", "folder:q3"],
    ["folder:q3",     "viewer", "group:eng#member"],
    ["doc:plan",      "editor", "user:alice"],
    ["group:eng",     "member", "user:bob"],
    ["group:eng",     "member", "group:interns#member"],
    ["group:interns", "member", "user:dave"],
    ["doc:secret",    "owner",  "user:carol"],
    ["doc:secret",    "parent", "folder:hr"],
    ["folder:hr",     "viewer", "user:erin"]
  ];
  var on = TUPLES.map(function () { return true; });
  var OBJECTS = ["doc:plan", "doc:secret"];
  var RELS = ["viewer", "editor", "owner"];
  var USERS = ["user:alice", "user:bob", "user:carol", "user:dave", "user:erin", "user:mallory"];
  var REWRITES = {
    "doc#owner":   [["this"]],
    "doc#editor":  [["this"], ["computed", "owner"]],
    "doc#viewer":  [["this"], ["computed", "editor"], ["ttu", "parent", "viewer"]],
    "folder#viewer": [["this"]],
    "group#member": [["this"]]
  };
  var st = { obj: "doc:plan", rel: "viewer", user: "user:dave" };

  /* returns an array of {idx, text} describing the first successful derivation, or null */
  function check(obj, rel, user, seen) {
    var key = obj + "#" + rel;
    if (seen[key]) return null;
    var seen2 = {}; for (var k in seen) seen2[k] = true; seen2[key] = true;
    var rules = REWRITES[obj.split(":")[0] + "#" + rel] || [];
    for (var i = 0; i < rules.length; i++) {
      var rule = rules[i];
      if (rule[0] === "this") {
        for (var t = 0; t < TUPLES.length; t++) {
          var tp = TUPLES[t];
          if (!on[t] || tp[0] !== obj || tp[1] !== rel) continue;
          if (tp[2] === user) return [{ idx: t, text: obj + "#" + rel + " lists " + user + " directly" }];
          if (tp[2].indexOf("#") >= 0) {
            var parts = tp[2].split("#");
            var sub = check(parts[0], parts[1], user, seen2);
            if (sub) return [{ idx: t, text: obj + "#" + rel + " includes everyone in " + tp[2] }].concat(sub);
          }
        }
      } else if (rule[0] === "computed") {
        var c = check(obj, rule[1], user, seen2);
        if (c) return [{ idx: -1, text: obj + "#" + rel + " is implied by " + obj + "#" + rule[1] }].concat(c);
      } else if (rule[0] === "ttu") {
        for (var u = 0; u < TUPLES.length; u++) {
          var tt = TUPLES[u];
          if (!on[u] || tt[0] !== obj || tt[1] !== rule[1]) continue;
          var d = check(tt[2], rule[2], user, seen2);
          if (d) return [{ idx: u, text: obj + "#" + rel + " inherits from " + tt[2] + "#" + rule[2] + " (via " + rule[1] + ")" }].concat(d);
        }
      }
    }
    return null;
  }

  var head = h("div", "widget-head");
  head.appendChild(h("span", "widget-tag", "Explore"));
  head.appendChild(h("h4", "widget-title", "Check: can this user do this to that object?"));
  root.appendChild(head);

  var row = h("div", "widget-row az-row");
  function sel(label, opts, key) {
    var l = h("label", "az-ctl"); l.appendChild(h("span", "az-l", label));
    var s = h("select");
    opts.forEach(function (o) { var op = h("option", null, o); op.value = o; s.appendChild(op); });
    s.value = st[key];
    s.addEventListener("change", function () { st[key] = s.value; render(); });
    l.appendChild(s); row.appendChild(l);
  }
  sel("Object", OBJECTS, "obj"); sel("Relation", RELS, "rel"); sel("User", USERS, "user");
  root.appendChild(row);

  var out = h("div", "widget-out az-out"); out.setAttribute("aria-live", "polite"); root.appendChild(out);
  var wrap = h("div", "az-wrap"); root.appendChild(wrap);
  root.appendChild(h("p", "widget-help", "Highlighted rows are the tuples the grant depends on. Untick a row to delete that tuple, and watch the answer change on the very next check. Anything with no path is denied."));

  function render() {
    var path = check(st.obj, st.rel, st.user, {});
    out.textContent = "";
    var head2 = h("p");
    head2.appendChild(h("span", "pill " + (path ? "green" : "red"), path ? "ALLOW" : "DENY"));
    head2.appendChild(document.createTextNode(" check(" + st.obj + "#" + st.rel + ", " + st.user + ")" + (path ? "" : ": no path in the graph, so default deny")));
    out.appendChild(head2);
    if (path) {
      var ol = h("ol", "az-path");
      path.forEach(function (p) { ol.appendChild(h("li", null, p.text)); });
      out.appendChild(ol);
    }
    var used = {}; (path || []).forEach(function (p) { if (p.idx >= 0) used[p.idx] = true; });
    wrap.textContent = "";
    var tb = h("table", "az-table");
    var hr = h("tr"); ["On", "Object", "Relation", "Subject"].forEach(function (t) { hr.appendChild(h("th", null, t)); });
    tb.appendChild(hr);
    TUPLES.forEach(function (tp, i) {
      var tr = h("tr", used[i] ? "az-hit" : "");
      var td0 = h("td"); var cb = h("input"); cb.type = "checkbox"; cb.checked = on[i];
      cb.setAttribute("aria-label", "tuple " + tp.join(" ") + " enabled");
      cb.addEventListener("change", function () { on[i] = cb.checked; render(); });
      td0.appendChild(cb); tr.appendChild(td0);
      tp.forEach(function (c) { tr.appendChild(h("td", "mono", c)); });
      tb.appendChild(tr);
    });
    wrap.appendChild(tb);
  }
  render();
})();
