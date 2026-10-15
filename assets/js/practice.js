/* Practice: one drill at a time (practice.html).

   A drill is one lab milestone turned into "write this one function": the
   rest of the lab's solution is already in the file, the checker runs in
   the browser (runner.js), and the chapter is the reference you open after.
   The drills and their order come from assets/js/drills-data.js, built by
   authoring/build_drills.py; each lab's details (task, hints, solution,
   explanation, need-to-know card) are fetched from its drills/lab.json.

   Progress lives in localStorage under "cs-drills" (done drills with dates,
   attempts, hints shown) and joins the Review page's export. When every
   drill of a lab passes, the lab is marked complete in the course too. */
(function () {
  "use strict";

  var DATA = window.CS_DRILLS || { labs: {}, queue: [] };
  var ARTIFACTS = window.CS_ARTIFACTS || [];
  var COURSES = window.CS_COURSES || [];
  var root = document.body.dataset.root || ".";
  var ASSETS = root + "/assets/";
  var KEY = "cs-drills";

  function load(k, fallback) {
    try { var v = localStorage.getItem(k); return v === null ? fallback : JSON.parse(v); }
    catch (e) { return fallback; }
  }
  function save(k, v) {
    try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* private mode */ }
  }
  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function (k) {
      if (k === "text") node.textContent = attrs[k];
      else if (k === "html") node.innerHTML = attrs[k];
      else if (k === "class") node.className = attrs[k];
      else node.setAttribute(k, attrs[k]);
    });
    (children || []).forEach(function (c) { if (c) node.appendChild(c); });
    return node;
  }

  var state = load(KEY, {}) || {};
  state.done = state.done || {};
  state.attempts = state.attempts || {};
  state.hints = state.hints || {};
  function persist() { save(KEY, state); }

  /* ---------- the flat, ordered list of drills ---------- */

  var DRILLS = [];
  DATA.queue.forEach(function (q) {
    var lab = DATA.labs[q.key];
    if (!lab) return;
    lab.key = q.key;
    lab.artifact = q.artifact || null;
    lab.artifactNum = q.artifactNum || null;
    lab.artifactTitle = q.artifactTitle || null;
    lab.milestones.forEach(function (m, i) {
      DRILLS.push({ id: q.key + ":" + m.n, lab: lab, n: m.n, index: i, title: m.title, write: m.write });
    });
  });
  function byId(id) { return DRILLS.find(function (d) { return d.id === id; }) || null; }
  function isDone(d) { return !!state.done[d.id]; }
  function nextUndone(from) {
    var start = from ? DRILLS.indexOf(from) + 1 : 0;
    for (var i = 0; i < DRILLS.length; i++) {
      var d = DRILLS[(start + i) % DRILLS.length];
      if (!isDone(d)) return d;
    }
    return null;
  }

  /* ---------- streak ---------- */

  function dayKey(date) { return date.getFullYear() + "-" + (date.getMonth() + 1) + "-" + date.getDate(); }
  function streak() {
    var days = {};
    Object.keys(state.done).forEach(function (id) { days[dayKey(new Date(state.done[id]))] = true; });
    var n = 0, d = new Date();
    if (!days[dayKey(d)]) d.setDate(d.getDate() - 1);     // today not yet, yesterday counts
    while (days[dayKey(d)]) { n++; d.setDate(d.getDate() - 1); }
    return n;
  }

  /* ---------- status strip ---------- */

  function renderStatus() {
    var host = document.getElementById("practice-status");
    if (!host) return;
    host.textContent = "";
    var done = DRILLS.filter(isDone).length;
    var s = streak();
    var bits = [
      el("span", { class: "stat" }, [el("strong", { text: String(done) }), document.createTextNode(" of " + DRILLS.length + " drills done")]),
      el("span", { class: "stat" }, [el("strong", { text: String(s) }), document.createTextNode(s === 1 ? " day streak" : " day streak")])
    ];
    ARTIFACTS.forEach(function (a) {
      var mine = DRILLS.filter(function (d) { return d.lab.artifact === a.id; });
      if (!mine.length) return;
      var k = mine.filter(isDone).length;
      bits.push(el("span", { class: "stat" + (k === mine.length ? " complete" : "") }, [
        el("strong", { text: "Artifact " + a.num }), document.createTextNode(": " + k + " of " + mine.length)]));
    });
    bits.forEach(function (b) { host.appendChild(b); });
  }

  /* ---------- the queue ---------- */

  function renderQueue(current) {
    var host = document.getElementById("queue");
    if (!host) return;
    host.textContent = "";
    var groups = [];
    DATA.queue.forEach(function (q) {
      var lab = DATA.labs[q.key];
      if (!lab) return;
      var gid = q.artifact || "more";
      var g = groups.find(function (x) { return x.id === gid; });
      if (!g) {
        g = { id: gid, title: q.artifact ? "Artifact " + q.artifactNum + ": " + q.artifactTitle : "More labs, in course order", labs: [] };
        groups.push(g);
      }
      g.labs.push(lab);
    });
    groups.forEach(function (g) {
      var sec = el("section", { class: "queue-group" }, [el("h3", { text: g.title })]);
      g.labs.forEach(function (lab) {
        var drills = DRILLS.filter(function (d) { return d.lab === lab; });
        var k = drills.filter(isDone).length;
        var ul = el("ul", { class: "queue-list" });
        drills.forEach(function (d) {
          var a = el("a", { href: "#" + d.id, text: "Milestone " + d.n + ": " + d.title });
          ul.appendChild(el("li", { class: (isDone(d) ? "done" : "") + (current && d.id === current.id ? " current" : "") }, [a]));
        });
        var det = el("details", { class: "queue-lab" + (k === drills.length ? " complete" : "") }, [
          el("summary", null, [
            el("span", { class: "queue-lab-title", text: lab.num + " Lab " + lab.lab.slice(1) + ": " + lab.title }),
            el("span", { class: "queue-count", text: k + " / " + drills.length })
          ]),
          ul
        ]);
        if (current && current.lab === lab) det.open = true;
        sec.appendChild(det);
      });
      host.appendChild(sec);
    });
  }

  /* ---------- loading a lab's details, the runner, equations ---------- */

  var labCache = {};
  function labDetails(lab) {
    if (!labCache[lab.key]) {
      labCache[lab.key] = fetch(root + "/" + lab.dir + "drills/lab.json").then(function (r) {
        if (!r.ok) throw new Error(r.status + " " + lab.dir + "drills/lab.json");
        return r.json();
      });
    }
    return labCache[lab.key];
  }
  // Lab pages link relative to <course>/labs/; the drill page sits at the root.
  function rebase(html, lab) {
    var base = lab.page.replace(/[^/]+$/, "");
    return (html || "").replace(/(href|src)="(?!(?:[a-z]+:|#|\/))([^"]*)"/g, function (_, attr, url) {
      return attr + '="' + root + "/" + base + url + '"';
    });
  }
  var eqPromise = null;
  function ensureEquations() {
    var NZ = window.NZ || {};
    if (NZ.typeset) return Promise.resolve();
    if (!eqPromise) eqPromise = new Promise(function (resolve, reject) {
      if (!document.querySelector('script[src$="js/equations.js"]')) {
        window.NZ = window.NZ || {};
        window.NZ.assets = ASSETS;
        var s = document.createElement("script");
        s.src = ASSETS + "js/equations.js";
        s.onerror = function () { reject(new Error("equations.js did not load")); };
        document.body.appendChild(s);
      }
      var tries = 0, t = setInterval(function () {
        if (window.NZ && window.NZ.typeset) { clearInterval(t); resolve(); }
        else if (++tries > 200) { clearInterval(t); reject(new Error("KaTeX did not load")); }
      }, 50);
    });
    return eqPromise;
  }
  function typeset(node) {
    if (!node.querySelector("[data-tex]")) return;
    ensureEquations().then(function () { window.NZ.typeset(node); }).catch(function (e) { console.warn("practice.js:", e.message); });
  }

  /* ---------- one drill ---------- */

  var currentDrill = null;
  var currentCell = null;

  function chapterLinks(lab) {
    var course = COURSES.find(function (c) { return c.id === lab.course; });
    if (!course) return [];
    return (lab.related || []).map(function (id) {
      var ch = course.chapters.find(function (c) { return c.id === id; });
      return ch ? el("a", { href: root + "/" + course.dir + "/chapters/" + ch.file, text: parseInt(ch.id, 10) + ". " + ch.title }) : null;
    }).filter(Boolean);
  }

  function render(drill) {
    var host = document.getElementById("drill");
    if (!host || !drill) return;
    currentDrill = drill;
    currentCell = null;
    state.last = drill.id;
    persist();
    host.textContent = "";
    host.appendChild(el("p", { class: "lab-ws-note", text: "Loading the drill…" }));
    renderQueue(drill);
    labDetails(drill.lab).then(function (details) {
      if (currentDrill !== drill) return;
      var m = details.milestones.find(function (x) { return x.n === drill.n; });
      if (!m) throw new Error("milestone " + drill.n + " missing from lab.json");
      host.textContent = "";
      var lab = drill.lab;
      var pos = DRILLS.indexOf(drill);

      // Eyebrow and title
      var eyebrow = el("div", { class: "chapter-eyebrow" }, [
        el("span", { class: "part", text: (lab.artifact ? "Artifact " + lab.artifactNum + " · " : "") + lab.num + " Lab " + lab.lab.slice(1) + ": " + lab.title }),
        el("span", { text: "Drill " + (drill.index + 1) + " of " + lab.milestones.length }),
        isDone(drill) ? el("span", { class: "badge track", text: "✓ passed" }) : null
      ]);
      host.appendChild(eyebrow);
      host.appendChild(el("h2", { id: "drill-title", text: "Milestone " + drill.n + ": " + drill.title }));
      host.appendChild(el("p", { class: "drill-write", html: "Write " + m.write.map(function (w) { return "<code>" + w + "</code>"; }).join(", ") + ". Everything else in the file is already written." }));

      // Need to know
      var card;
      if (m.card) {
        card = el("div", { class: "drill-card" }, [el("p", { class: "callout-title", text: "Need to know" })]);
        card.insertAdjacentHTML("beforeend", rebase(m.card, lab));
      } else {
        var paras = (m.explain.match(/<p>[\s\S]*?<\/p>/g) || []).slice(0, 2).join("");
        card = el("div", { class: "drill-card" }, [el("p", { class: "callout-title", text: "From the lab" })]);
        card.insertAdjacentHTML("beforeend", rebase(paras || "<p>Read the task below, then the lab's explanation if you need it.</p>", lab));
        if (m.explain.length > paras.length + 20) {
          var more = el("details", { class: "deeper" }, [el("summary", { text: "The lab's full explanation of this milestone" })]);
          more.insertAdjacentHTML("beforeend", rebase(m.explain, lab));
          card.appendChild(more);
        }
      }
      host.appendChild(card);
      typeset(card);

      // The task
      var task = el("div", { class: "drill-task" }, [el("h3", { text: "Your task" })]);
      task.insertAdjacentHTML("beforeend", rebase(m.task, lab));
      if (m.checkpoint) task.insertAdjacentHTML("beforeend", '<p class="checkpoint">' + rebase(m.checkpoint, lab) + "</p>");
      host.appendChild(task);
      if (m.provided && m.provided.length) {
        host.appendChild(el("details", { class: "deeper drill-have" }, [
          el("summary", { text: "What the file already has (" + m.provided.length + " functions)" }),
          el("p", { class: "mono-list", text: m.provided.join("  ·  ") })
        ]));
      }

      // The workspace: the drill file, saved and checked as starter.py
      var box = el("div", {
        class: "drill-ws", "data-dir": root + "/" + lab.dir, "data-edit": "starter.py",
        "data-edit-src": "drills/m" + drill.n + ".py", "data-files": details.files,
        "data-args": String(drill.n), "data-key": "nz-code:practice:" + drill.id
      });
      host.appendChild(box);
      var result = el("div", { class: "drill-result", "aria-live": "polite" });
      host.appendChild(result);

      // Help: hints, the solution
      var help = el("div", { class: "drill-help" });
      var hintBtn = el("button", { type: "button", class: "theme-toggle", text: "Show a hint" });
      var hints = el("ul", { class: "drill-hints" });
      var shown = state.hints[drill.id] || 0;
      function showHints(k) {
        shown = Math.min(k, m.hints.length);
        state.hints[drill.id] = shown;
        persist();
        hints.textContent = "";
        m.hints.slice(0, shown).forEach(function (h) { hints.appendChild(el("li", { html: rebase(h, lab) })); });
        hintBtn.textContent = shown >= m.hints.length ? "No more hints" : "Show a hint (" + (shown + 1) + " of " + m.hints.length + ")";
        hintBtn.disabled = shown >= m.hints.length;
        typeset(hints);
      }
      hintBtn.addEventListener("click", function () { showHints(shown + 1); });
      help.appendChild(el("div", { class: "drill-help-row" }, [hintBtn, el("span", { class: "drill-attempts" })]));
      help.appendChild(hints);
      if (m.hints.length) showHints(shown); else hintBtn.hidden = true;
      if (m.solution) {
        var sol = el("details", { class: "deeper drill-solution" }, [el("summary", null, [document.createTextNode("Solution "), el("span", { class: "hint", text: "spoiler" })])]);
        sol.insertAdjacentHTML("beforeend", rebase(m.solution, lab));
        help.appendChild(sol);
      }
      host.appendChild(help);

      // Where to read more, and navigation
      var links = [el("a", { href: root + "/" + lab.page + (m.anchor ? "#" + m.anchor : ""), text: "the lab's explanation of this milestone" })]
        .concat(chapterLinks(lab));
      var more = el("p", { class: "drill-more" }, [document.createTextNode("Read more: ")]);
      links.forEach(function (a, i) { if (i) more.appendChild(document.createTextNode(" · ")); more.appendChild(a); });
      host.appendChild(more);
      var prev = DRILLS[pos - 1], next = DRILLS[pos + 1];
      var nav = el("nav", { class: "drill-nav" }, [
        prev ? el("a", { class: "btn", href: "#" + prev.id, text: "← Previous" }) : el("span"),
        el("a", { class: "btn", href: "#" + (next ? next.id : DRILLS[0].id), text: isDone(drill) ? "Next drill →" : "Skip for now →" })
      ]);
      host.appendChild(nav);
      updateAttempts();

      // Mount the runner
      window.NZ.ensureRunner().then(function () { return window.NZ.workspace(box); }).then(function (cell) {
        if (currentDrill !== drill) return;
        currentCell = cell || null;
        if (box.classList.contains("is-local")) {
          var mark = el("button", { type: "button", class: "theme-toggle", text: "I passed it locally: mark done" });
          mark.addEventListener("click", function () { pass(drill, result, nav, "Marked as passed locally."); });
          result.appendChild(el("p", { text: "This lab needs processes or threads, so run it with python3 check.py " + drill.n + " on your machine or the lab VM." }));
          result.appendChild(mark);
        }
      }).catch(function (e) {
        result.appendChild(el("p", { class: "drill-fail", text: "Could not load the runner: " + e.message }));
      });

      box.addEventListener("cell-done", function (ev) {
        if (currentDrill !== drill) return;
        var d = ev.detail || {};
        var out = d.stdout || "";
        var sum = /(\d+)\/(\d+) milestones passing/.exec(out);
        if (d.stopped) { showResult(result, "warn", "Stopped before the check finished."); return; }
        if (sum && +sum[1] === +sum[2] && +sum[2] > 0 && !d.failed) {
          pass(drill, result, nav, "Passed" + (d.ms ? " · " + (d.ms < 1000 ? Math.round(d.ms) + " ms" : (d.ms / 1000).toFixed(1) + " s") : ""));
          return;
        }
        state.attempts[drill.id] = (state.attempts[drill.id] || 0) + 1;
        persist();
        updateAttempts();
        var why = (out.split("\n").find(function (l) { return /^\s*[✘…]/.test(l); }) || "").trim();
        showResult(result, "fail", why ? "Not yet. " + why.replace(/^[✘…]\s*/, "") : "Not yet: the check did not pass. The output above says why.");
        if (state.attempts[drill.id] >= 2 && shown < Math.min(1, m.hints.length)) showHints(1);
      });

      function updateAttempts() {
        var n = state.attempts[drill.id] || 0;
        var span = help.querySelector(".drill-attempts");
        if (span) span.textContent = n ? n + (n === 1 ? " attempt" : " attempts") : "";
      }
      document.title = "Drill: " + drill.title + " · Practice · Zero to AI Systems";
      window.scrollTo({ top: 0 });
    }).catch(function (e) {
      host.textContent = "";
      host.appendChild(el("p", { class: "drill-fail", text: "Could not load this drill (" + e.message + "). Serve the site over http, not file://." }));
    });
  }

  function showResult(result, kind, text) {
    result.textContent = "";
    result.appendChild(el("p", { class: "drill-" + kind, text: text }));
  }

  function pass(drill, result, nav, text) {
    var first = !isDone(drill);
    if (first) {
      state.done[drill.id] = new Date().toISOString();
      persist();
      markLabProgress(drill.lab);
    }
    var next = nextUndone(drill);
    result.textContent = "";
    result.appendChild(el("p", { class: "drill-ok", text: "✔ " + text }));
    var why = el("p", { class: "drill-why" }, [document.createTextNode("Now the why, if you want it: ")]);
    var links = [el("a", { href: root + "/" + drill.lab.page, text: "the lab's explanation" })].concat(chapterLinks(drill.lab));
    links.forEach(function (a, i) { if (i) why.appendChild(document.createTextNode(" · ")); why.appendChild(a); });
    result.appendChild(why);
    var btn = el("a", { class: "btn primary", href: "#" + (next ? next.id : drill.id), text: next ? "Next drill →" : "Every drill is done" });
    result.appendChild(btn);
    btn.focus();
    var nextLink = nav.querySelector("a:last-child");
    if (nextLink) nextLink.textContent = "Next drill →";
    renderStatus();
    renderQueue(drill);
  }

  // Every drill of a lab passed: the lab counts as complete in its course.
  function markLabProgress(lab) {
    var all = DRILLS.filter(function (d) { return d.lab === lab; });
    if (!all.every(isDone)) return;
    var k = "cs-progress:" + lab.course;
    var ids = load(k, []) || [];
    if (ids.indexOf(lab.lab) === -1) { ids.push(lab.lab); save(k, ids); }
  }

  /* ---------- routing ---------- */

  function fromHash() {
    var id = decodeURIComponent(location.hash.replace(/^#/, ""));
    return byId(id);
  }
  function go() {
    var d = fromHash();
    if (!d) {
      var last = state.last ? byId(state.last) : null;
      d = (last && !isDone(last)) ? last : (nextUndone(null) || DRILLS[0]);
      if (d) { history.replaceState(null, "", "#" + d.id); }
    }
    if (d) render(d);
  }
  window.addEventListener("hashchange", go);
  renderStatus();
  if (!DRILLS.length) {
    var host = document.getElementById("drill");
    if (host) host.textContent = "No drills yet: run python3 authoring/build_drills.py.";
    return;
  }
  go();
})();
