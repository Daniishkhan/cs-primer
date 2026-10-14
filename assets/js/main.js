/* Builds the shared page chrome from CS_COURSES (catalog.js): hub, sidebar,
   mobile top bar, page eyebrow, table of contents, "mark complete" box,
   prev/next pager and cross-links between chapters, labs, case studies and
   design studios. Also handles the theme and sketch toggles, reading-progress
   bar and per-course progress storage.

   Page contract (data-root is always the site root):
     <body data-root="../.." data-course="net" data-chapter="03">  (<course>/chapters/)
     <body data-root="../.." data-course="net" data-lab="L1">      (<course>/labs/)
     <body data-root="../.." data-course="net" data-case="C6">     (<course>/cases/)
     <body data-root="../.." data-course="sys" data-studio="S1">   (<course>/studios/)
     <body data-root=".." data-course="net" data-page="course">    (course roadmap, <course>/index.html)
     <body data-root="." data-page="hub">                          (site hub, index.html)
     <div class="app"><aside id="sidebar" class="sidebar"></aside>
       <div class="main-col"><main class="content"><article class="prose">
         <header class="chapter-head"><h1>…</h1><p class="lede">…</p></header> …
*/
(function () {
  "use strict";

  var SITE = "Zero to Systems";
  // assets/ folder, from this script's own URL (runner.js and vendor files live there).
  var ASSETS = ((document.currentScript && document.currentScript.src) || "").replace(/js\/main\.js(?:[?#].*)?$/, "");
  var COURSES = window.CS_COURSES || [];
  var DEPTH = window.CS_DEPTH_LABEL || {};
  var body = document.body;
  var root = body.dataset.root || ".";
  var KIND_DIR = { chapter: "chapters", lab: "labs", "case": "cases", studio: "studios" };
  COURSES.forEach(function (co) {
    [["chapter", co.chapters], ["lab", co.labs], ["case", co.cases], ["studio", co.studios]].forEach(function (k) {
      (k[1] || []).forEach(function (c) { c.kind = k[0]; c.dir = KIND_DIR[k[0]]; c.course = co; });
    });
  });
  var course = COURSES.find(function (co) { return co.id === body.dataset.course; }) || null;
  var CHAPTERS = course ? course.chapters : [];
  var PARTS = course ? course.parts : [];
  var LABS = course ? course.labs || [] : [];
  var CASES = course ? course.cases || [] : [];
  var STUDIOS = course ? course.studios || [] : [];
  var COLLECTION = { chapter: CHAPTERS, lab: LABS, "case": CASES, studio: STUDIOS };
  var NOUN = { chapter: "chapter", lab: "lab", "case": "case study", studio: "design studio" };
  var currentKind = body.dataset.lab ? "lab" : body.dataset["case"] ? "case" : body.dataset.studio ? "studio" : body.dataset.chapter ? "chapter" : null;
  var currentId = body.dataset.chapter || body.dataset.lab || body.dataset["case"] || body.dataset.studio || null;
  var THEMES = { tokyo: "Tokyo Night", mocha: "Catppuccin Mocha", gruvbox: "Gruvbox Dark" };
  var THEME_ORDER = Object.keys(THEMES);

  /* ---------- storage (every access guarded: private mode can throw) ---------- */

  function load(key, fallback) {
    try { var v = localStorage.getItem(key); return v === null ? fallback : JSON.parse(v); }
    catch (e) { return fallback; }
  }
  function save(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch (e) { /* ignore */ }
  }

  /* Progress is stored per course. Networking predates courses, so its old
     key is copied over the first time. */
  function doneFor(co) {
    var v = load("cs-progress:" + co.id, null);
    if (v === null && co.id === "net") v = load("nz-progress", []);
    return new Set(v || []);
  }
  var done = course ? doneFor(course) : new Set();
  function setDone(id, isDone) {
    if (isDone) done.add(id); else done.delete(id);
    save("cs-progress:" + course.id, Array.from(done));
    refreshProgress();
  }

  /* ---------- helpers ---------- */

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
  function courseHome(co) { return root + "/" + co.dir + "/index.html"; }
  function href(ch) { return root + "/" + ch.course.dir + "/" + ch.dir + "/" + ch.file; }
  function chapterNum(ch) { return ch.kind === "chapter" ? String(parseInt(ch.id, 10)) : ch.id; }
  /* "3. Layers…", "Lab 1: Sockets…", "Case 6: When the map…", "Studio 1: …";
     pages from another course get that course's name in front. */
  function longLabel(ch) {
    var s;
    if (ch.kind === "lab") s = "Lab " + ch.id.slice(1) + ": " + ch.title;
    else if (ch.kind === "case") s = "Case " + ch.id.slice(1) + ": " + ch.title;
    else if (ch.kind === "studio") s = "Studio " + ch.id.slice(1) + ": " + ch.title;
    else s = chapterNum(ch) + ". " + ch.title;
    return ch.course !== course ? ch.course.title + ", " + s : s;
  }
  /* "05" = chapter 5 of this course; "net:05" = chapter 5 of another course. */
  function chapterById(id) {
    var co = course, m = /^(\w+):(.+)$/.exec(id);
    if (m) { co = COURSES.find(function (x) { return x.id === m[1]; }); id = m[2]; }
    return co ? (co.chapters || []).find(function (c) { return c.id === id; }) : null;
  }
  function slug(s) { return s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""); }

  var items = currentKind ? COLLECTION[currentKind] : [];
  var idx = items.findIndex(function (c) { return c.id === currentId; });
  var current = idx >= 0 ? items[idx] : null;

  /* ---------- theme ---------- */

  function currentTheme() {
    var t = document.documentElement.dataset.theme;
    return THEMES[t] ? t : "tokyo";
  }
  function applyTheme(t) {
    document.documentElement.dataset.theme = t;
    try { localStorage.setItem("nz-theme", t); } catch (e) { /* ignore */ }
    document.querySelectorAll(".theme-toggle .theme-name").forEach(function (n) { n.textContent = THEMES[t]; });
    document.dispatchEvent(new CustomEvent("nz:themechange", { detail: { theme: t } }));
  }

  /* ---------- sketch (hand-drawn diagrams, see sketch.js) ---------- */

  function sketchOn() { return document.documentElement.classList.contains("sketch"); }
  function applySketch(on) {
    document.documentElement.classList.toggle("sketch", on);
    save("nz-sketch", on);
    document.querySelectorAll(".sketch-toggle").forEach(function (b) {
      b.setAttribute("aria-pressed", String(on));
      b.querySelector(".sketch-name").textContent = on ? "Hand-drawn" : "Clean";
      b.querySelector(".sketch-icon").textContent = on ? "✎" : "▭";
    });
    document.dispatchEvent(new CustomEvent("nz:sketchchange", { detail: { on: on } }));
  }
  function sketchButton() {
    var on = sketchOn();
    var b = el("button", { class: "theme-toggle sketch-toggle", type: "button", title: "Diagram style: hand-drawn or clean", "aria-pressed": String(on) }, [
      el("span", { class: "sketch-icon", "aria-hidden": "true", text: on ? "✎" : "▭" }),
      el("span", { class: "sketch-name", text: on ? "Hand-drawn" : "Clean" })
    ]);
    b.addEventListener("click", function () { applySketch(!sketchOn()); });
    return b;
  }
  function loadSketch() {
    if (!document.querySelector("figure.diagram svg, .stepper svg")) return;
    document.head.appendChild(el("link", { rel: "stylesheet", href: "https://fonts.googleapis.com/css2?family=Shantell+Sans:wght@400;700&display=swap" }));
    ["/assets/vendor/rough.min.js", "/assets/js/sketch.js"].forEach(function (src) {
      var s = document.createElement("script");
      s.src = root + src; s.async = false;   // keep execution order
      document.body.appendChild(s);
    });
  }
  // Default on; set before anything renders so labels don't change font twice.
  document.documentElement.classList.toggle("sketch", load("nz-sketch", true) !== false);
  function themeButton() {
    var b = el("button", { class: "theme-toggle", type: "button", title: "Switch color theme" }, [
      el("span", { class: "theme-swatch", "aria-hidden": "true" }),
      el("span", { class: "theme-name", text: THEMES[currentTheme()] })
    ]);
    b.addEventListener("click", function () {
      applyTheme(THEME_ORDER[(THEME_ORDER.indexOf(currentTheme()) + 1) % THEME_ORDER.length]);
    });
    return b;
  }

  /* ---------- sidebar ---------- */

  function buildSidebar() {
    var side = document.getElementById("sidebar");
    if (!side) return;

    side.appendChild(el("a", { class: "all-courses", href: root + "/index.html", text: course ? "← All courses" : SITE }));
    if (!course) { buildHubNav(side); return; }

    var brandName = el("span", { class: "brand-name" }, [document.createTextNode(course.title), el("small", { text: course.subtitle })]);
    side.appendChild(el("a", { class: "brand", href: courseHome(course) }, [
      el("span", { class: "brand-mark", text: course.mark }), brandName
    ]));

    side.appendChild(el("div", { class: "progress-card", id: "progress-card" }));

    PARTS.forEach(function (part, p) {
      var list = el("ul", { class: "nav-list" });
      CHAPTERS.filter(function (c) { return c.part === p; }).forEach(function (c) {
        var a = el("a", { href: href(c), "data-id": c.id, title: DEPTH[c.depth] + ": " + c.blurb }, [
          el("span", { class: "nav-num", html: "<span>" + chapterNum(c) + "</span>" }),
          el("span", { class: "nav-title", text: c.title }),
          el("span", { class: "nav-depth " + c.depth, "aria-hidden": "true" })
        ]);
        if (c.id === currentId) { a.classList.add("active"); a.setAttribute("aria-current", "page"); }
        list.appendChild(el("li", null, [a]));
      });
      side.appendChild(el("nav", { class: "nav-part", "aria-label": part.title }, [
        el("p", { class: "nav-part-title", text: "Part " + p + " · " + part.title }),
        list
      ]));
    });

    [["lab", "Hands-on labs", LABS], ["case", "Case studies", CASES], ["studio", "Design studios", STUDIOS]].forEach(function (g) {
      if (!g[2].length) return;
      var list = el("ul", { class: "nav-list" });
      g[2].forEach(function (c) {
        var tip = c.kind === "case" ? c.pattern + ": " + c.blurb : "After Part " + c.afterPart + ": " + c.blurb;
        var a = el("a", { href: href(c), "data-id": c.id, title: tip }, [
          el("span", { class: "nav-num", html: "<span>" + c.id + "</span>" }),
          el("span", { class: "nav-title", text: c.title })
        ]);
        if (c.id === currentId) { a.classList.add("active"); a.setAttribute("aria-current", "page"); }
        list.appendChild(el("li", null, [a]));
      });
      var det = el("details", { class: "nav-part nav-group" }, [
        el("summary", { class: "nav-part-title", text: g[1] + " (" + g[2].length + ")" }), list
      ]);
      if (currentKind === g[0]) det.open = true;
      side.appendChild(det);
    });

    side.appendChild(sidebarFoot());

    var active = side.querySelector("a.active");
    // Scroll only the sidebar (scrollIntoView could also move the page or the off-canvas drawer).
    if (active) side.scrollTop = Math.max(0, active.offsetTop - side.clientHeight / 2);
  }

  function sidebarFoot() {
    var legend = el("div", { class: "legend", html:
      '<span><span class="nav-depth deep" style="display:inline-block"></span> Deep dive</span>' +
      '<span><span class="nav-depth core" style="display:inline-block"></span> Core</span>' +
      '<span><span class="nav-depth intro" style="display:inline-block"></span> Quick intro</span>' });

    return el("div", { class: "sidebar-foot" }, [
      course ? legend : null,
      el("a", { href: root + "/glossary.html", text: "📖  Glossary" }),
      course && (course.tools || []).length ? el("a", { href: root + "/" + course.dir + "/toolbox.html", text: "🧰  Toolbox" }) : null,
      el("a", { href: root + "/lab-machine.html", text: "🖥️  Your lab machine" }),
      el("a", { href: root + "/curriculum.html", text: "🗺️  Curriculum map" }),
      themeButton(),
      sketchButton()
    ]);
  }

  /* Hub and glossary: the sidebar lists the courses instead of chapters. */
  function buildHubNav(side) {
    [["The path", COURSES.filter(function (co) { return !co.track; })],
     ["Zero to AI Systems", COURSES.filter(function (co) { return co.track === "ai"; })]].forEach(function (grp) {
      if (!grp[1].length) return;
      var list = el("ul", { class: "nav-list" });
      grp[1].forEach(function (co) {
        var planned = co.status === "planned";
        var n = planned ? 0 : doneFor(co).size;
        var total = planned ? 0 : co.chapters.length + co.labs.length + co.cases.length + (co.studios || []).length;
        var a = el(planned ? "span" : "a", planned ? { class: "planned", title: "Coming soon: " + co.tagline } : { href: courseHome(co), title: co.tagline }, [
          el("span", { class: "nav-num", html: "<span>" + courseNum(co) + "</span>" }),
          el("span", { class: "nav-title", text: co.title }),
          el("span", { class: "nav-count", text: planned ? "soon" : n + "/" + total })
        ]);
        list.appendChild(el("li", null, [a]));
      });
      side.appendChild(el("nav", { class: "nav-part", "aria-label": grp[0] }, [el("p", { class: "nav-part-title", text: grp[0] }), list]));
    });
    side.appendChild(sidebarFoot());
  }

  /* Track-1 courses are numbered 0..7 by position; track-2 courses carry their own label ("A0"). */
  function courseNum(co) {
    return co.num || String(COURSES.filter(function (c) { return !c.track; }).indexOf(co));
  }

  function refreshProgress() {
    var card = document.getElementById("progress-card");
    var total = CHAPTERS.length;
    var n = CHAPTERS.filter(function (c) { return done.has(c.id); }).length;
    if (card) {
      card.innerHTML = "";
      card.appendChild(el("div", { text: n + " of " + total + " chapters complete" }));
      var bar = el("div", { class: "bar" }, [el("span")]);
      bar.firstChild.style.width = Math.round((n / total) * 100) + "%";
      card.appendChild(bar);
      var extra = [["Labs", LABS], ["Case studies", CASES], ["Studios", STUDIOS]].filter(function (g) { return g[1].length; }).map(function (g) {
        return g[0] + " " + g[1].filter(function (c) { return done.has(c.id); }).length + "/" + g[1].length;
      });
      if (extra.length) card.appendChild(el("div", { class: "progress-extra", text: extra.join(" · ") }));
    }
    document.querySelectorAll(".nav-list a[data-id]").forEach(function (a) {
      a.classList.toggle("done", done.has(a.dataset.id));
    });
    document.querySelectorAll("[data-done-id]").forEach(function (n) {
      var isDone = done.has(n.dataset.doneId);
      n.classList.toggle("done", isDone);
      n.textContent = isDone ? "✓" : n.dataset.label;
    });
    var btn = document.getElementById("complete-btn");
    if (btn && current) {
      var d = done.has(current.id);
      btn.textContent = d ? "✓ Completed" : "Mark " + NOUN[currentKind] + " complete";
      btn.className = "btn " + (d ? "success" : "primary");
    }
  }

  /* ---------- mobile top bar ---------- */

  function buildTopbar() {
    var col = document.querySelector(".main-col");
    if (!col) return;
    var menu = el("button", { class: "menu-btn", type: "button", "aria-label": "Open chapter list", text: "☰" });
    menu.addEventListener("click", function () { body.classList.toggle("nav-open"); });
    var title = current ? longLabel(current) : course ? course.title : SITE;
    col.insertBefore(el("div", { class: "topbar" }, [menu, el("div", { class: "topbar-title", text: title }), sketchButton(), themeButton()]), col.firstChild);
    var scrim = el("div", { class: "scrim" });
    scrim.addEventListener("click", function () { body.classList.remove("nav-open"); });
    body.appendChild(scrim);
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") body.classList.remove("nav-open"); });
  }

  /* ---------- chapter header + TOC ---------- */

  function buildChapterHead() {
    var head = document.querySelector(".chapter-head");
    var article = document.querySelector("article.prose");
    if (!head || !current || !article) return;

    var words = (article.textContent || "").trim().split(/\s+/).length;
    var minutes = Math.max(3, Math.round(words / 200));
    var eyebrow;
    if (current.kind === "lab") eyebrow = [
      el("span", { class: "part", text: "Hands-on lab · after Part " + current.afterPart + " · " + PARTS[current.afterPart].title }),
      el("span", { text: "Lab " + current.id.slice(1) }),
      el("span", { class: "badge lab", text: "Build it" }),
      el("span", { text: "≈ " + minutes + " min read, longer to build" })
    ];
    else if (current.kind === "studio") eyebrow = [
      el("span", { class: "part", text: "Design studio · after Part " + current.afterPart + " · " + PARTS[current.afterPart].title }),
      el("span", { text: "Studio " + current.id.slice(1) }),
      el("span", { class: "badge studio", text: "Design it" }),
      el("span", { text: "≈ " + minutes + " min read, longer to design" })
    ];
    else if (current.kind === "case") eyebrow = [
      el("span", { class: "part", text: "Case study " + current.id.slice(1) }),
      el("span", { class: "badge case", text: "Pattern: " + current.pattern }),
      el("span", { text: "≈ " + minutes + " min read" })
    ];
    else eyebrow = [
      el("span", { class: "part", text: "Part " + current.part + " · " + PARTS[current.part].title }),
      el("span", { text: "Chapter " + chapterNum(current) }),
      el("span", { class: "badge " + current.depth, text: DEPTH[current.depth] }),
      el("span", { text: "≈ " + minutes + " min read" })
    ];
    head.insertBefore(el("div", { class: "chapter-eyebrow" }, eyebrow), head.firstChild);

    // Labs and case studies list the chapters they build on.
    if (current.related && current.related.length) {
      var uses = el("p", { class: "builds-on" }, [el("span", { text: "Builds on: " })]);
      current.related.forEach(function (id, i) {
        var ch = chapterById(id);
        if (!ch) return;
        if (i) uses.appendChild(document.createTextNode(" · "));
        uses.appendChild(el("a", { href: href(ch), text: longLabel(ch) }));
      });
      head.appendChild(uses);
    }

    buildToc(article, head, "In this " + NOUN[currentKind]);
    document.title = current.title + " · " + course.title;
  }

  function buildToc(article, head, title) {
    var h2s = Array.prototype.slice.call(article.querySelectorAll(":scope > h2, :scope > section > h2"));
    h2s.forEach(function (h) { if (!h.id) h.id = slug(h.textContent); });
    if (h2s.length < 3) return;
    var ol = el("ol");
    h2s.forEach(function (h) {
      var label = h.cloneNode(true);
      var num = label.querySelector(".h-num"); if (num) num.remove();
      ol.appendChild(el("li", null, [el("a", { href: "#" + h.id, text: label.textContent.trim() })]));
    });
    head.parentNode.insertBefore(el("nav", { class: "toc", "aria-label": title }, [
      el("div", { class: "toc-title", text: title }), ol
    ]), head.nextSibling);
  }

  /* Standalone reference pages (toolbox, lab machine) get a TOC but no pager. */
  function buildReferenceHead() {
    var page = body.dataset.page;
    if (page !== "toolbox" && page !== "lab-machine" && page !== "curriculum") return;
    var head = document.querySelector(".chapter-head");
    var article = document.querySelector("article.prose");
    if (head && article) buildToc(article, head, "On this page");
  }

  /* ---------- footer: complete + pager ---------- */

  function buildFooter() {
    var article = document.querySelector("article.prose");
    if (!article || !current) return;

    if (current.kind === "chapter") crossLinks(article);

    var noun = NOUN[currentKind];
    var btn = el("button", { id: "complete-btn", type: "button", class: "btn primary" });
    btn.addEventListener("click", function () { setDone(current.id, !done.has(current.id)); });
    article.appendChild(el("div", { class: "complete-box" }, [
      el("p", { html: "<strong>Finished this " + noun + "?</strong> Mark it complete to track your progress (saved in this browser)." }),
      btn
    ]));

    var pager = el("nav", { class: "pager", "aria-label": "Page navigation" });
    var prev = items[idx - 1], next = items[idx + 1];
    if (!next && currentKind === "lab" && CASES.length) next = CASES[0];
    if (!next && (currentKind === "lab" || currentKind === "case") && STUDIOS.length) next = STUDIOS[0];
    if (prev) pager.appendChild(el("a", { class: "prev", href: href(prev) }, [
      el("small", { text: "← Previous" }), el("span", { class: "title", text: longLabel(prev) })
    ]));
    if (next) pager.appendChild(el("a", { class: "next", href: href(next) }, [
      el("small", { text: "Next →" }), el("span", { class: "title", text: longLabel(next) })
    ]));
    else pager.appendChild(el("a", { class: "next", href: root + "/glossary.html" }, [
      el("small", { text: "Next →" }), el("span", { class: "title", text: "Glossary" })
    ]));
    article.appendChild(pager);
    article.appendChild(el("p", { class: "site-foot", text: course.title + " · " + SITE + " · built for learning, one layer at a time." }));
  }

  /* At the end of a chapter: labs unlocked by finishing this part, and case
     studies that use this chapter. Generated from chapters.js. */
  function crossLinks(article) {
    var partChapters = CHAPTERS.filter(function (c) { return c.part === current.part; });
    var lastOfPart = partChapters[partChapters.length - 1] === current;
    var labs = lastOfPart ? LABS.filter(function (l) { return l.afterPart === current.part; }) : [];
    var studios = lastOfPart ? STUDIOS.filter(function (l) { return l.afterPart === current.part; }) : [];
    var cases = CASES.filter(function (c) { return (c.related || []).indexOf(current.id) !== -1; });
    function box(cls, title, intro, list) {
      var ul = el("ul");
      list.forEach(function (x) {
        ul.appendChild(el("li", null, [el("a", { href: href(x), text: longLabel(x) }), document.createTextNode(": " + x.blurb)]));
      });
      article.appendChild(el("div", { class: "callout " + cls }, [el("p", { class: "callout-title", text: title }), el("p", { text: intro }), ul]));
    }
    if (labs.length) box("lab", "Ready to build", "You now know enough for " + (labs.length > 1 ? "these labs" : "this lab") + ". Building it is the fastest way to make Part " + current.part + " stick.", labs);
    if (studios.length) box("studio", "Design it", "Put this part to work on an interview-style design problem. Sketch your own answer first, then compare.", studios);
    var tools = ((course.tools) || []).filter(function (t) { return t.chapters.indexOf(current.id) !== -1; });
    if (tools.length) {
      var tl = el("ul");
      tools.forEach(function (t) {
        tl.appendChild(el("li", null, [
          el("a", { href: root + "/" + course.dir + "/toolbox.html#" + t.id, text: t.name }),
          document.createTextNode((t.linux ? " (Linux) " : " ") + "· " + t.blurb)
        ]));
      });
      article.appendChild(el("div", { class: "callout tool" }, [el("p", { class: "callout-title", text: "Tools to try" }),
        el("p", { text: "Real tools that let you watch this chapter's ideas on your own machine. Each has a short guided exercise in the toolbox." }), tl]));
    }
    if (cases.length) box("world", "See it in the real world", "Case studies where this chapter's ideas do the heavy lifting:", cases);
  }

  /* ---------- landing page roadmap ---------- */

  function buildRoadmap() {
    var host = document.getElementById("roadmap");
    if (!host || !course) return;
    PARTS.forEach(function (part, p) {
      var grid = el("div", { class: "road-grid" });
      CHAPTERS.filter(function (c) { return c.part === p; }).forEach(function (c) {
        grid.appendChild(el("a", { class: "road-card", href: href(c) }, [
          el("div", { class: "top" }, [
            el("span", { class: "num", "data-done-id": c.id, "data-label": "Ch " + chapterNum(c), text: "Ch " + chapterNum(c) }),
            el("span", { class: "badge " + c.depth, text: DEPTH[c.depth] })
          ]),
          el("div", { class: "title", text: c.title }),
          el("div", { class: "blurb", text: c.blurb })
        ]));
      });
      host.appendChild(el("section", { class: "road-part" }, [
        el("span", { class: "road-dot", text: String(p) }),
        el("h2", { text: part.title }),
        el("p", { text: part.blurb }),
        grid
      ]));
    });

    var blurbs = course.roadmapBlurbs || {};
    [["Hands-on labs", blurbs.labs || "Build the ideas yourself in Python. Each lab says which part to finish first.", LABS, "L"],
     ["Case studies", blurbs.cases || "Real systems and real incidents, each built around one pattern.", CASES, "C"],
     ["Design studios", blurbs.studios || "Interview-style design problems that use what the course taught. Design first, then compare.", STUDIOS, "S"]].forEach(function (g) {
      if (!g[2].length) return;
      var grid = el("div", { class: "road-grid" });
      g[2].forEach(function (c) {
        grid.appendChild(el("a", { class: "road-card", href: href(c) }, [
          el("div", { class: "top" }, [
            el("span", { class: "num", "data-done-id": c.id, "data-label": c.id, text: c.id }),
            el("span", { class: "badge " + c.kind, text: c.kind === "case" ? c.pattern : "after Part " + c.afterPart })
          ]),
          el("div", { class: "title", text: c.title }),
          el("div", { class: "blurb", text: c.blurb })
        ]));
      });
      host.appendChild(el("section", { class: "road-part" }, [
        el("span", { class: "road-dot", text: g[3] }), el("h2", { text: g[0] }), el("p", { text: g[1] }), grid
      ]));
    });

    var cont = document.getElementById("continue-btn");
    if (cont) {
      cont.href = href(CHAPTERS[0]);
      var firstTodo = CHAPTERS.find(function (c) { return !done.has(c.id); });
      if (done.size && firstTodo) { cont.href = href(firstTodo); cont.textContent = "Continue: " + firstTodo.title + " →"; }
      else if (!firstTodo) { cont.href = root + "/glossary.html"; cont.textContent = "All done! Review the glossary →"; }
    }
  }

  /* ---------- site hub: one card per course ---------- */

  function buildHub() {
    var mainHost = document.getElementById("hub");
    var aiHost = document.getElementById("hub-ai");
    if (!mainHost && !aiHost) return;
    COURSES.forEach(function (co) {
      var host = co.track === "ai" ? aiHost : mainHost;
      if (!host) return;
      var planned = co.status === "planned";
      var top = el("div", { class: "top" }, [
        el("span", { class: "hub-mark", text: co.mark }),
        el("span", { class: "num", text: "Course " + courseNum(co) }),
        el("span", { class: "badge " + co.status, text: { done: "Ready", building: "New", planned: "Coming soon" }[co.status] })
      ]);
      var kids = [top, el("div", { class: "title", text: co.title }), el("div", { class: "sub", text: co.subtitle }), el("div", { class: "blurb", text: co.tagline })];
      if (!planned) {
        var d = doneFor(co);
        var counts = [[co.chapters, "chapters"], [co.labs, "labs"], [co.cases, "case studies"], [co.studios || [], "studios"]]
          .filter(function (g) { return g[0].length; })
          .map(function (g) { return g[0].length + " " + g[1]; }).join(" · ");
        var all = co.chapters.concat(co.labs, co.cases, co.studios || []);
        var n = all.filter(function (c) { return d.has(c.id); }).length;
        var bar = el("div", { class: "bar" }, [el("span")]);
        bar.firstChild.style.width = Math.round((n / all.length) * 100) + "%";
        kids.push(el("div", { class: "meta", text: counts }), bar, el("div", { class: "meta", text: n ? n + " of " + all.length + " done" : "Not started" }));
      }
      host.appendChild(el("li", { class: "hub-step" + (planned ? " planned" : "") }, [
        el(planned ? "div" : "a", planned ? { class: "road-card hub-card" } : { class: "road-card hub-card", href: courseHome(co) }, kids)
      ]));
    });
  }

  /* ---------- reading progress ---------- */

  function buildReadingBar() {
    var bar = el("div", { class: "reading-progress", "aria-hidden": "true" });
    body.appendChild(bar);
    var ticking = false;
    function update() {
      var h = document.documentElement;
      var max = h.scrollHeight - h.clientHeight;
      bar.style.transform = "scaleX(" + (max > 0 ? h.scrollTop / max : 0) + ")";
      ticking = false;
    }
    window.addEventListener("scroll", function () { if (!ticking) { ticking = true; requestAnimationFrame(update); } }, { passive: true });
    update();
  }

  /* ---------- go ---------- */

  /* Wide tables scroll inside their own box instead of widening the page on phones. */
  function wrapTables() {
    document.querySelectorAll("article table").forEach(function (t) {
      if (t.closest(".table-wrap, .widget")) return;
      var w = el("div", { class: "table-wrap" });
      t.parentNode.insertBefore(w, t);
      w.appendChild(t);
    });
  }

  /* ---------- syntax highlighting ----------
     Blocks written with hand-placed <span>s are left alone. Everything else is
     tokenized here, using the same classes (.kw .str .num .cmt ...) as the
     hand-highlighted blocks, so all themes colour them the same way. */

  var PY_KW = "and as assert async await break class continue def del elif else except finally for from global if import in is lambda nonlocal not or pass raise return try while with yield match case";
  var PY_BI = "print len range sum min max sorted enumerate zip map filter abs round int float str bytes bool list dict set tuple frozenset isinstance hasattr getattr setattr super type iter next any all open repr divmod hash id format reversed object property staticmethod classmethod Exception ValueError KeyError TimeoutError RuntimeError AssertionError IndexError StopIteration";
  var GEN_KW = "GET POST PUT PATCH DELETE HEAD OPTIONS function local end then if else elseif return for in do while func var let const type struct SELECT FROM WHERE INSERT INTO VALUES UPDATE SET DELETE CREATE TABLE INDEX ON AND OR NOT NULL BEGIN COMMIT ROLLBACK JOIN GROUP BY ORDER LIMIT RETURNING PRIMARY KEY UNIQUE";

  function wordSet(s) { var o = {}; s.split(" ").forEach(function (w) { o[w] = 1; }); return o; }
  var PY = { kw: wordSet(PY_KW), bi: wordSet(PY_BI) };
  var GEN = wordSet(GEN_KW);

  function esc(s) { return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }
  function wrap(cls, s) { return '<span class="' + cls + '">' + esc(s) + "</span>"; }

  // One ordered alternation: the first group that matches wins, so strings and
  // comments are consumed before anything inside them can look like a keyword.
  var PY_RE = new RegExp([
    /([rRbBuUfF]{0,2}"""[\s\S]*?"""|[rRbBuUfF]{0,2}'''[\s\S]*?''')/.source,   // 1 triple-quoted
    /(#[^\n]*)/.source,                                                          // 2 comment
    /([rRbBuUfF]{0,2}"(?:\\.|[^"\\\n])*"|[rRbBuUfF]{0,2}'(?:\\.|[^'\\\n])*')/.source, // 3 string
    /(@[A-Za-z_][\w.]*)/.source,                                                 // 4 decorator
    /(\b\d[\d_]*(?:\.\d[\d_]*)?(?:[eE][+-]?\d+)?j?\b|\b0[xXbBoO][\da-fA-F_]+\b)/.source, // 5 number
    /\b(def|class)(\s+)([A-Za-z_]\w*)/.source,                                   // 6,7,8 definition
    /([A-Za-z_]\w*)/.source                                                      // 9 word
  ].join("|"), "g");

  function highlightPython(src) {
    var out = "", last = 0, m;
    PY_RE.lastIndex = 0;
    while ((m = PY_RE.exec(src))) {
      out += esc(src.slice(last, m.index));
      last = PY_RE.lastIndex;
      if (m[1]) {
        // A triple-quoted string on its own line is a docstring: style it as prose.
        var before = src.slice(src.lastIndexOf("\n", m.index - 1) + 1, m.index);
        out += wrap(/^\s*$/.test(before) ? "doc" : "str", m[1]);
      } else if (m[2]) {
        // "# ── 1. Step ──" banners mark the sections that match the idea box.
        out += wrap(/^#\s*──/.test(m[2]) ? "cmt sec" : "cmt", m[2]);
      } else if (m[3]) out += wrap("str", m[3]);
      else if (m[4]) out += wrap("dec", m[4]);
      else if (m[5]) out += wrap("num", m[5]);
      else if (m[6]) out += wrap("kw", m[6]) + m[7] + wrap("fn", m[8]);
      else {
        var w = m[9];
        if (w === "True" || w === "False" || w === "None") out += wrap("const", w);
        else if (w === "self" || w === "cls") out += wrap("hl3", w);
        else if (PY.kw[w]) out += wrap("kw", w);
        else if (PY.bi[w]) out += wrap("bi", w);
        else out += esc(w);
      }
    }
    return out + esc(src.slice(last));
  }

  // API shapes, sketches, Lua/SQL/YAML and the like: strings, numbers, comments,
  // HTTP verbs and a few common keywords. Good enough to make structure visible.
  var GEN_RE = /("(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])*')|((?:^|\s)(?:#|--|\/\/)[^\n]*)|(\b\d[\d_,.]*\b)|([A-Za-z_][\w]*)/gm;
  function highlightGeneric(src) {
    var out = "", last = 0, m;
    GEN_RE.lastIndex = 0;
    while ((m = GEN_RE.exec(src))) {
      out += esc(src.slice(last, m.index));
      last = GEN_RE.lastIndex;
      if (m[1]) out += wrap("str", m[1]);
      else if (m[2]) {
        var lead = m[2].match(/^\s*/)[0];
        out += esc(lead) + wrap("cmt", m[2].slice(lead.length));
      } else if (m[3]) out += wrap("num", m[3]);
      else out += GEN[m[4]] ? wrap("kw", m[4]) : esc(m[4]);
    }
    return out + esc(src.slice(last));
  }

  // Shell sessions: "$ cmd   # note" lines, everything else is output.
  function highlightShell(src) {
    return src.split("\n").map(function (line) {
      if (/^\s*#/.test(line)) return wrap("cmt", line);
      var p = line.match(/^(\s*[$>] )(.*)$/);
      if (!p) return wrap("out", line);
      var c = p[2].match(/^(.*?)(\s+#\s.*)?$/);
      return wrap("prompt", p[1]) + wrap("cmd", c[1]) + (c[2] ? wrap("cmt", c[2]) : "");
    }).join("\n");
  }

  function languageOf(pre, src) {
    var title = (pre.getAttribute("data-title") || "").toLowerCase();
    if (/\.py\b/.test(title) || title === "python3") return "py";
    if (/output|^surfaces?$/.test(title)) return null;
    if (/^\s*\$ /m.test(src)) return "sh";
    if (/^(import |from \w+ import |def |class |print\()/m.test(src)) return "py";
    if (/\.(lua|sql|go|ya?ml|m3u8|tla|cfg|js|mmd)\b|api|sketch|shape|pseudocode|illustrative|promql|specification/.test(title)) return "gen";
    return null;
  }

  // Runnable code cells (runner.js) are loaded only on pages that have scripts.
  function loadRunner() {
    if (!ASSETS || !document.querySelector('article pre[data-title*=".py"]')) return;
    window.NZ = { assets: ASSETS, highlightPython: highlightPython };
    var s = document.createElement("script");
    s.src = ASSETS + "js/runner.js";
    document.body.appendChild(s);
  }

  function highlightCode() {
    document.querySelectorAll("pre").forEach(function (pre) {
      var code = pre.querySelector("code") || pre;
      if (code.querySelector("span")) return;                // hand-highlighted already
      var src = code.textContent;
      var lang = languageOf(pre, src);
      if (lang === "py") code.innerHTML = highlightPython(src);
      else if (lang === "sh") code.innerHTML = highlightShell(src);
      else if (lang === "gen") code.innerHTML = highlightGeneric(src);
    });
  }

  function init() {
    highlightCode();
    loadRunner();
    wrapTables();
    buildSidebar();
    buildTopbar();
    buildChapterHead();
    buildReferenceHead();
    buildFooter();
    buildRoadmap();
    buildHub();
    buildReadingBar();
    refreshProgress();
    loadSketch();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
