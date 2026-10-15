/* Practice: one drill at a time (practice.html).

   A drill is one function of one lab milestone: the rest of the lab's
   solution is already in the file, the checker runs in the browser
   (runner.js), and the chapter is the reference you open afterwards.
   Drills come in practice order from assets/js/drills-data.js, built by
   authoring/build_drills.py: a warm-up phase, then each artifact's labs,
   then every other lab. Each lab's details (task, hints, solution,
   explanation, need-to-know card, every function's signature and
   docstring) are fetched from its drills/lab.json.

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
  function shortName(qual) { return qual.split(".").pop(); }

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
    lab.phase = q.phase || (q.artifact ? q.artifact : "more");
    lab.artifact = q.artifact || null;
    lab.artifactNum = q.artifactNum || null;
    lab.artifactTitle = q.artifactTitle || null;
    lab.prereq = !!q.prereq;
    lab.milestones.forEach(function (m, i) {
      m.drills = [];
      m.write.forEach(function (fn, k) {
        var d = { id: q.key + ":" + m.n + ":" + (k + 1), lab: lab, milestone: m, n: m.n, mIndex: i, k: k + 1, K: m.write.length, fn: fn };
        m.drills.push(d);
        DRILLS.push(d);
      });
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
  function phaseTitle(lab) {
    if (lab.phase === "warmup") return "Warm-up";
    if (lab.artifact) return "Artifact " + lab.artifactNum;
    return "More labs";
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
      el("span", { class: "stat" }, [el("strong", { text: String(done) }), document.createTextNode(" of " + DRILLS.length + " functions written")]),
      el("span", { class: "stat" }, [el("strong", { text: String(s) }), document.createTextNode(" day streak")])
    ];
    var warm = DRILLS.filter(function (d) { return d.lab.phase === "warmup"; });
    if (warm.length) {
      var w = warm.filter(isDone).length;
      bits.push(el("span", { class: "stat" + (w === warm.length ? " complete" : "") }, [el("strong", { text: "Warm-up" }), document.createTextNode(": " + w + " of " + warm.length)]));
    }
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
      var gid = lab.phase;
      var g = groups.find(function (x) { return x.id === gid; });
      if (!g) {
        var title = gid === "warmup" ? "Warm-up: the foundations, one function at a time"
          : lab.artifact ? "Artifact " + lab.artifactNum + ": " + lab.artifactTitle : "More labs, in course order";
        g = { id: gid, title: title, labs: [] };
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
        lab.milestones.forEach(function (m) {
          var first = m.drills.find(function (d) { return !isDone(d); }) || m.drills[0];
          var li = el("li", { class: (m.drills.every(isDone) ? "done" : "") + (current && current.milestone === m ? " current" : "") }, [
            el("a", { href: "#" + first.id, text: "Milestone " + m.n + ": " + m.title })
          ]);
          var steps = el("span", { class: "queue-steps" });
          m.drills.forEach(function (d) {
            steps.appendChild(el("a", { href: "#" + d.id, class: "step" + (isDone(d) ? " done" : "") + (current === d ? " current" : ""), text: shortName(d.fn), title: d.fn }));
          });
          li.appendChild(steps);
          ul.appendChild(li);
        });
        var det = el("details", { class: "queue-lab" + (k === drills.length ? " complete" : "") }, [
          el("summary", null, [
            el("span", { class: "queue-lab-title", text: lab.num + " Lab " + lab.lab.slice(1) + ": " + lab.title + (lab.prereq ? " (builds up to the next lab)" : "") }),
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
      // Revalidate rather than trust the HTTP cache: a new deploy's cards show up at once.
      labCache[lab.key] = fetch(root + "/" + lab.dir + "drills/lab.json", { cache: "no-cache" }).then(function (r) {
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
  // Cards link from the site root already.
  function fromRoot(html) {
    return (html || "").replace(/(href|src)="(?!(?:[a-z]+:|#|\/|\.\/))/g, '$1="' + root + "/");
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

  // Put the cursor on the stub's "raise NotImplementedError" line, in the editor.
  function jumpToStub(cell, drill, focus) {
    if (!cell) return;
    function place() {
      var cm = cell.cm;
      if (!cm) return false;
      var lines = cm.getValue().split("\n");
      var marker = "TODO milestone " + drill.n + ": " + drill.fn;
      var at = lines.findIndex(function (l) { return l.indexOf(marker) !== -1; });
      if (at === -1) {
        var name = shortName(drill.fn).replace(/[$()*+.?[\\\]^{|}]/g, "\\$&");
        at = lines.findIndex(function (l) { return new RegExp("^\\s*def\\s+" + name + "\\s*\\(").test(l); });
      }
      if (at === -1) return true;
      cm.setCursor({ line: at, ch: lines[at].length });
      if (focus) {                       // the button scrolls to it; on load the card stays in view
        cm.scrollIntoView({ line: Math.max(0, at - 6), ch: 0 }, 60);
        cm.scrollIntoView({ line: at, ch: 0 }, 60);
        cm.focus();
      }
      return true;
    }
    if (!cell.cm && typeof cell.toggleEdit === "function") cell.toggleEdit();
    var tries = 0, t = setInterval(function () { if (place() || ++tries > 60) clearInterval(t); }, 50);
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
      var fn = (m.functions || []).find(function (f) { return f.name === drill.fn; }) || { name: drill.fn, signature: "", doc: "", file: "m" + drill.n + "-" + drill.k + ".py" };
      host.textContent = "";
      var lab = drill.lab;
      var pos = DRILLS.indexOf(drill);

      // Eyebrow and title
      host.appendChild(el("div", { class: "chapter-eyebrow" }, [
        el("span", { class: "part", text: phaseTitle(lab) + " · " + lab.num + " Lab " + lab.lab.slice(1) + ": " + lab.title }),
        el("span", { text: "Milestone " + drill.n + " of " + lab.milestones.length + " · step " + drill.k + " of " + drill.K }),
        isDone(drill) ? el("span", { class: "badge track", text: "✓ passed" }) : null
      ]));
      host.appendChild(el("h2", { id: "drill-title" }, [document.createTextNode("Write "), el("code", { text: shortName(drill.fn) })]));
      host.appendChild(el("p", { class: "drill-write", html: "Milestone " + drill.n + ": " + m.title + ". "
        + (drill.K > 1 ? "This milestone has " + drill.K + " functions; this drill is <code>" + fn.name + "</code>. " : "")
        + "Everything else in the file is already written." }));

      // Need to know (per milestone)
      var card;
      if (m.card) {
        card = el("div", { class: "drill-card" }, [el("p", { class: "callout-title", text: "Need to know" })]);
        card.insertAdjacentHTML("beforeend", fromRoot(m.card));
      } else {
        var paras = (m.explain.match(/<p>[\s\S]*?<\/p>/g) || []).slice(0, 2).join("");
        card = el("div", { class: "drill-card" }, [el("p", { class: "callout-title", text: "From the lab" })]);
        card.insertAdjacentHTML("beforeend", rebase(paras || "<p>Read the task below, then the lab's explanation if you need it.</p>", lab));
      }
      if (m.explain && m.explain.length > 60) {
        var more = el("details", { class: "deeper" }, [el("summary", { text: "The lab's full explanation of this milestone" })]);
        more.insertAdjacentHTML("beforeend", rebase(m.explain, lab));
        card.appendChild(more);
      }
      host.appendChild(card);
      typeset(card);

      // The function: its contract from the stub
      var sig = el("div", { class: "drill-fn" }, [el("h3", { text: "The function" })]);
      sig.appendChild(el("pre", { class: "drill-sig" }, [el("code", { text: (fn.signature || ("def " + shortName(drill.fn) + "(...):")) + (fn.doc ? '\n    """' + fn.doc.replace(/\n/g, "\n    ") + '"""' : "") })]));
      var jump = el("button", { type: "button", class: "theme-toggle", text: "Open the editor at this function" });
      jump.addEventListener("click", function () { jumpToStub(currentCell, drill, true); });
      sig.appendChild(jump);
      host.appendChild(sig);

      // The task (per milestone)
      var task = el("div", { class: "drill-task" }, [el("h3", { text: "The milestone's task" })]);
      task.insertAdjacentHTML("beforeend", rebase(m.task, lab));
      if (m.checkpoint) task.insertAdjacentHTML("beforeend", '<p class="checkpoint">' + rebase(m.checkpoint, lab) + "</p>");
      host.appendChild(task);
      if (m.provided && m.provided.length) {
        var others = m.write.filter(function (w) { return w !== drill.fn; });
        host.appendChild(el("details", { class: "deeper drill-have" }, [
          el("summary", { text: "What the file already has (" + (m.provided.length + others.length) + " functions)" }),
          el("p", { class: "mono-list", text: m.provided.concat(others).join("  ·  ") })
        ]));
      }

      // The workspace: the drill file, saved and checked as starter.py
      var box = el("div", {
        class: "drill-ws", "data-dir": root + "/" + lab.dir, "data-edit": "starter.py",
        "data-edit-src": "drills/" + fn.file, "data-files": details.files,
        "data-args": String(drill.n), "data-key": "nz-code:practice:" + drill.id
      });
      host.appendChild(box);
      var result = el("div", { class: "drill-result", "aria-live": "polite" });
      host.appendChild(result);

      // Help: hints, the solution (per milestone)
      var help = el("div", { class: "drill-help" });
      var hintBtn = el("button", { type: "button", class: "theme-toggle", text: "Show a hint" });
      var hints = el("ul", { class: "drill-hints" });
      var hintKey = lab.key + ":" + drill.n;
      var shown = state.hints[hintKey] || 0;
      function showHints(k) {
        shown = Math.min(k, m.hints.length);
        state.hints[hintKey] = shown;
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
        var sol = el("details", { class: "deeper drill-solution" }, [el("summary", null, [document.createTextNode("Solution for the whole milestone "), el("span", { class: "hint", text: "spoiler" })])]);
        sol.insertAdjacentHTML("beforeend", rebase(m.solution, lab));
        help.appendChild(sol);
      }
      host.appendChild(help);

      // Where to read more, and navigation
      var links = [el("a", { href: root + "/" + lab.page + (m.anchor ? "#" + m.anchor : ""), text: "the lab's explanation of this milestone" })]
        .concat(chapterLinks(lab));
      var more2 = el("p", { class: "drill-more" }, [document.createTextNode("Read more: ")]);
      links.forEach(function (a, i) { if (i) more2.appendChild(document.createTextNode(" · ")); more2.appendChild(a); });
      host.appendChild(more2);
      var prev = DRILLS[pos - 1], next = DRILLS[pos + 1];
      var nav = el("nav", { class: "drill-nav" }, [
        prev ? el("a", { class: "btn", href: "#" + prev.id, text: "← Previous" }) : el("span"),
        el("a", { class: "btn", href: "#" + (next ? next.id : DRILLS[0].id), text: isDone(drill) ? "Next →" : "Skip for now →" })
      ]);
      host.appendChild(nav);
      updateAttempts();

      // Mount the runner, open the editor at the function
      window.NZ.ensureRunner().then(function () { return window.NZ.workspace(box); }).then(function (cell) {
        if (currentDrill !== drill) return;
        currentCell = cell || null;
        if (box.classList.contains("is-local")) {
          var mark = el("button", { type: "button", class: "theme-toggle", text: "I passed it locally: mark done" });
          mark.addEventListener("click", function () { pass(drill, result, nav, "Marked as passed locally."); });
          result.appendChild(el("p", { text: "This lab needs processes or threads, so run it with python3 check.py " + drill.n + " on your machine or the lab VM." }));
          result.appendChild(mark);
        } else if (!isDone(drill)) {
          jumpToStub(cell, drill);
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
      document.title = "Write " + shortName(drill.fn) + " · Practice · Zero to AI Systems";
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
    var left = drill.milestone.drills.filter(function (d) { return !isDone(d); }).length;
    if (left) result.appendChild(el("p", { class: "drill-why", text: left + (left === 1 ? " function" : " functions") + " left in this milestone." }));
    else {
      var why = el("p", { class: "drill-why" }, [document.createTextNode("Milestone done. Now the why, if you want it: ")]);
      var links = [el("a", { href: root + "/" + drill.lab.page + (drill.milestone.anchor ? "#" + drill.milestone.anchor : ""), text: "the lab's explanation" })].concat(chapterLinks(drill.lab));
      links.forEach(function (a, i) { if (i) why.appendChild(document.createTextNode(" · ")); why.appendChild(a); });
      result.appendChild(why);
    }
    var btn = el("a", { class: "btn primary", href: "#" + (next ? next.id : drill.id), text: next ? "Next: write " + shortName(next.fn) + " →" : "Every drill is done" });
    result.appendChild(btn);
    btn.focus();
    var nextLink = nav.querySelector("a:last-child");
    if (nextLink) nextLink.textContent = "Next →";
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
    var d = byId(id);
    if (!d && /^[^:]+:L\d+:\d+$/.test(id)) d = byId(id + ":1");     // an old milestone link
    return d;
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
