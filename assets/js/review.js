/* Review: spaced practice on the quiz questions of every page.

   Questions come from assets/js/review-data.js (built by
   authoring/build_study.py). Each question sits in a Leitner box: right moves
   it up a box and spaces it further out, wrong sends it back to box 1. A
   session is the questions due today first, then new ones, ten at a time.
   Scope: what you have marked complete (default), one course, or everything.
   State lives in localStorage under "cs-review"; the "Your data" section
   exports and imports everything the site stores, so it can move between
   browsers and machines.
*/
(function () {
  "use strict";

  var ALL = window.CS_REVIEW || [];
  var COURSES = window.CS_COURSES || [];
  var ROOT = document.body.getAttribute("data-root") || ".";
  var DAYS = [0, 1, 3, 7, 16, 35, 80];          // wait after reaching box n
  var SESSION = 10;
  var LETTERS = "ABCDEFGH";
  var today = Math.floor(Date.now() / 86400000);

  function load(key, fallback) {
    try { var v = localStorage.getItem(key); return v === null ? fallback : JSON.parse(v); }
    catch (e) { return fallback; }
  }
  function save(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch (e) { /* private mode */ }
  }
  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }
  // Question text, options and explanations are the site's own page HTML.
  function rich(tag, cls, markup) {
    var n = el(tag, cls);
    n.innerHTML = markup;
    return n;
  }

  var state = load("cs-review", {});           // id -> [box, due day, seen, right]

  function doneIds() {
    var done = {};
    COURSES.forEach(function (co) {
      var ids = load("cs-progress:" + co.id, []);
      if (co.id === "net") ids = ids.concat(load("nz-progress", []));
      ids.forEach(function (id) { done[co.id + ":" + id] = true; });
    });
    return done;
  }

  function pool(scope) {
    if (scope === "all") return ALL;
    if (scope === "done") {
      var done = doneIds();
      return ALL.filter(function (q) { return done[q.c + ":" + q.i]; });
    }
    return ALL.filter(function (q) { return q.c === scope; });
  }

  // A stable daily shuffle: new questions vary by day, not on every reload.
  function shuffled(list, seed) {
    var a = list.slice(), s = seed;
    for (var i = a.length - 1; i > 0; i--) {
      s = (s * 1103515245 + 12345) % 2147483648;
      var j = s % (i + 1), t = a[i];
      a[i] = a[j];
      a[j] = t;
    }
    return a;
  }

  function session(scope) {
    var p = pool(scope);
    var due = p.filter(function (q) { return state[q.id] && state[q.id][1] <= today; })
      .sort(function (x, y) { return state[x.id][1] - state[y.id][1]; });
    var fresh = shuffled(p.filter(function (q) { return !state[q.id]; }), today);
    return due.concat(fresh).slice(0, SESSION);
  }

  function stats(scope) {
    var p = pool(scope), seen = 0, due = 0, solid = 0;
    p.forEach(function (q) {
      var s = state[q.id];
      if (!s) return;
      seen++;
      if (s[1] <= today) due++;
      if (s[0] >= 4) solid++;
    });
    return { total: p.length, seen: seen, due: due, solid: solid };
  }

  /* ---------- the page ---------- */

  var host = document.getElementById("review");
  var pick = el("select", "review-scope");
  pick.setAttribute("aria-label", "What to review");
  var summary = el("p", "review-stats");
  var card = el("div", "review-card");
  var scope = load("cs-review-scope", "done");

  function option(value, text) {
    var o = el("option", null, text);
    o.value = value;
    pick.appendChild(o);
  }

  function fillScopes() {
    pick.textContent = "";
    option("done", "What I've marked complete (" + pool("done").length + " questions)");
    COURSES.forEach(function (co) {
      var n = pool(co.id).length;
      if (n) option(co.id, (co.num ? co.num + " " : "") + co.title + " (" + n + ")");
    });
    option("all", "Everything (" + ALL.length + ")");
    pick.value = scope;
    if (pick.value !== scope) pick.value = scope = "done";
  }

  function showStats() {
    var s = stats(scope);
    summary.textContent = s.total
      ? s.seen + " of " + s.total + " questions seen · " + s.due + " due today · " + s.solid + " solid (box 4 or higher)"
      : "";
  }

  function start() {
    var list = session(scope);
    var at = 0, right = 0;
    card.textContent = "";
    if (!list.length) {
      card.appendChild(el("p", "review-empty", scope === "done"
        ? "Nothing to review yet: mark chapters complete as you finish them (the button at the end of each page), or pick a course above."
        : "Nothing due in this set today. Come back tomorrow, or pick another set."));
      return;
    }

    function ask() {
      var q = list[at];
      card.textContent = "";
      var meta = el("p", "review-meta");
      meta.appendChild(document.createTextNode((at + 1) + " of " + list.length + " · "));
      var src = el("a", null, q.p);
      src.href = ROOT + "/" + q.h;
      meta.appendChild(src);
      var box = state[q.id] ? state[q.id][0] : 0;
      meta.appendChild(document.createTextNode(box ? " · box " + box : " · new"));
      card.appendChild(meta);
      card.appendChild(rich("p", "q-text", q.q));
      var opts = el("ol", "q-options review-options");
      var explain = rich("div", "q-explain", q.x);
      explain.hidden = true;
      var next = el("button", "btn primary", at + 1 < list.length ? "Next →" : "Finish");
      next.type = "button";
      next.hidden = true;
      q.o.forEach(function (markup, k) {
        var li = el("li");
        var b = el("button", "review-option");
        b.type = "button";
        b.appendChild(el("span", "review-letter", LETTERS[k]));
        b.appendChild(rich("span", null, markup));
        b.addEventListener("click", function () { answer(k); });
        li.appendChild(b);
        opts.appendChild(li);
      });
      card.appendChild(opts);
      card.appendChild(explain);
      card.appendChild(next);
      if (window.NZ && window.NZ.typeset) window.NZ.typeset(card);
      var done = false;

      function answer(k) {
        if (done) return;
        done = true;
        var ok = k === q.a;
        if (ok) right++;
        var s = state[q.id] || [0, today, 0, 0];
        var b = ok ? Math.min(s[0] + 1, DAYS.length - 1) : 1;
        state[q.id] = [b, today + DAYS[b], s[2] + 1, s[3] + (ok ? 1 : 0)];
        save("cs-review", state);
        Array.prototype.forEach.call(opts.querySelectorAll("button"), function (btn, j) {
          btn.disabled = true;
          if (j === q.a) btn.classList.add("is-right");
          else if (j === k) btn.classList.add("is-wrong");
        });
        explain.hidden = false;
        next.hidden = false;
        next.focus();
        showStats();
      }
      next.addEventListener("click", function () {
        at++;
        if (at < list.length) ask();
        else finish();
      });
    }

    function finish() {
      card.textContent = "";
      card.appendChild(el("p", "review-done", right + " of " + list.length + " right."));
      card.appendChild(el("p", null, right === list.length
        ? "Those move further out; you will see them again in a few days."
        : "The ones you missed come back tomorrow; follow the page links to reread them first."));
      var again = el("button", "btn primary", "Another " + SESSION);
      again.type = "button";
      again.addEventListener("click", start);
      card.appendChild(again);
      showStats();
    }
    ask();
  }

  pick.addEventListener("change", function () {
    scope = pick.value;
    save("cs-review-scope", scope);
    showStats();
    start();
  });

  var bar = el("div", "review-bar");
  bar.appendChild(pick);
  host.appendChild(bar);
  host.appendChild(summary);
  host.appendChild(card);
  fillScopes();
  showStats();
  start();

  /* ---------- your data: export and import ---------- */

  var data = document.getElementById("your-data");
  if (!data) return;
  var PREFIX = /^(cs-|nz-)/;
  var msg = el("p", "review-stats");
  var exp = el("button", "btn", "⬇ Export my progress");
  exp.type = "button";
  exp.addEventListener("click", function () {
    var dump = {};
    for (var i = 0; i < localStorage.length; i++) {
      var k = localStorage.key(i);
      if (PREFIX.test(k)) dump[k] = localStorage.getItem(k);
    }
    var blob = new Blob([JSON.stringify({ site: "zero-to-systems", saved: new Date().toISOString(), data: dump }, null, 1)],
      { type: "application/json" });
    var a = el("a");
    a.href = URL.createObjectURL(blob);
    a.download = "zero-to-systems-progress-" + new Date().toISOString().slice(0, 10) + ".json";
    document.body.appendChild(a);
    a.click();
    a.remove();
    msg.textContent = "Saved " + Object.keys(dump).length + " entries.";
  });
  var file = el("input");
  file.type = "file";
  file.accept = "application/json,.json";
  file.hidden = true;
  var imp = el("button", "btn", "⬆ Import from a file");
  imp.type = "button";
  imp.addEventListener("click", function () { file.click(); });
  file.addEventListener("change", function () {
    var f = file.files && file.files[0];
    if (!f) return;
    f.text().then(function (t) {
      var parsed = JSON.parse(t);
      var entries = parsed && parsed.data ? parsed.data : {};
      var n = 0;
      Object.keys(entries).forEach(function (k) {
        if (PREFIX.test(k) && typeof entries[k] === "string") {
          localStorage.setItem(k, entries[k]);
          n++;
        }
      });
      msg.textContent = "Imported " + n + " entries. Reloading…";
      setTimeout(function () { location.reload(); }, 800);
    }).catch(function () { msg.textContent = "That file is not a progress export from this site."; });
  });
  var row = el("div", "review-bar");
  row.appendChild(exp);
  row.appendChild(imp);
  data.appendChild(row);
  data.appendChild(file);
  data.appendChild(msg);
})();
