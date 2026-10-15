/* Glossary hover cards for the AI path (loaded by main.js on AI-track pages).

   Two kinds of word get a card:
     - every <span class="term"> (a term defined right here), and
     - the first plain mention, on this page, of a multi-word term or an
       acronym from the glossary (a term defined somewhere else).
   Hover, focus or tap shows a one-line definition and where it is taught.
   The data (assets/js/glossary-data.js, built by authoring/build_glossary.py)
   is about 0.5 MB, so it is fetched after the page has rendered. */
(function () {
  "use strict";

  var NZ = window.NZ || {};
  var ASSETS = NZ.assets || "";
  var root = document.body.dataset.root || ".";
  var COURSES = window.CS_COURSES || [];
  var here = document.body.dataset.course;
  var AI = COURSES.filter(function (c) { return c.track === "ai"; }).map(function (c) { return c.id; });
  var hereRank = AI.indexOf(here);

  // Single everyday words make noisy links, so plain mentions only match
  // multi-word terms ("fitness landscape") and acronyms ("MCTS").
  function linkable(term) {
    if (/\s|-/.test(term) && term.length >= 6) return true;
    return /^[A-Z][A-Z0-9]{1,6}s?$/.test(term) || /^[A-Z]+[a-z]*[A-Z]+/.test(term);
  }
  // "Fitness function" and "Fitness function (open-ended)" share one key.
  function keyOf(term) { return term.replace(/\s*\(.*\)\s*$/, "").toLowerCase(); }

  // Which entry to show when several courses define the same term: this
  // page's chapter, then this course, then the nearest earlier AI course.
  function best(list) {
    var page = location.pathname.split("/").slice(-3).join("/");
    function score(e) {
      if (page.indexOf(e[2]) !== -1 || e[2].indexOf(page) !== -1) return -1000;
      if (e[3] === here) return -500;
      var r = AI.indexOf(e[3]);
      if (r === -1) return 100;                        // first path: still useful
      return r <= hereRank ? hereRank - r : 50 + r;    // earlier courses first
    }
    return list.slice().sort(function (a, b) { return score(a) - score(b); })[0];
  }

  function chapterLabel(e) {
    var co = COURSES.find(function (c) { return c.id === e[3]; });
    if (!co) return "Glossary";
    var file = e[2].split("/").pop();
    var ch = (co.chapters || []).find(function (c) { return c.file === file; });
    var name = co.id === here ? "This course" : co.title;
    return name + (ch ? ", chapter " + parseInt(ch.id, 10) : "");
  }

  /* ---------- the card ---------- */

  var card = document.createElement("div");
  card.className = "gl-card";
  card.setAttribute("role", "tooltip");
  card.hidden = true;
  document.body.appendChild(card);
  var hideTimer = null, owner = null;

  function show(target, entry, others) {
    clearTimeout(hideTimer);
    owner = target;
    card.innerHTML = "";
    var t = document.createElement("p");
    t.className = "gl-term";
    t.textContent = entry[0];
    if (entry[4]) {
      var b = document.createElement("span");
      b.className = "gl-track";
      b.textContent = "artifact " + entry[4].split(" ").map(function (a) { return a.slice(1); }).join(", ");
      b.title = "Taught in a chapter the artifact track uses";
      t.appendChild(b);
    }
    var d = document.createElement("p");
    d.className = "gl-def";
    d.textContent = entry[1];
    var links = document.createElement("p");
    links.className = "gl-links";
    var a = document.createElement("a");
    a.href = root + "/" + entry[2];
    a.textContent = chapterLabel(entry) + " →";
    links.appendChild(a);
    if (others > 0) {
      links.appendChild(document.createTextNode(" · "));
      var g = document.createElement("a");
      g.href = root + "/glossary.html?q=" + encodeURIComponent(keyOf(entry[0]));
      g.textContent = others + " more in the glossary";
      links.appendChild(g);
    }
    card.appendChild(t);
    card.appendChild(d);
    card.appendChild(links);
    card.hidden = false;
    var r = target.getBoundingClientRect();
    var w = Math.min(360, window.innerWidth - 24);
    card.style.width = w + "px";
    var left = Math.max(12, Math.min(r.left + window.scrollX, window.scrollX + window.innerWidth - w - 12));
    card.style.left = left + "px";
    var below = r.bottom + window.scrollY + 8;
    var h = card.offsetHeight;
    var fitsBelow = r.bottom + 8 + h < window.innerHeight;
    card.style.top = (fitsBelow ? below : r.top + window.scrollY - h - 8) + "px";
  }
  function hideSoon() {
    clearTimeout(hideTimer);
    hideTimer = setTimeout(function () { card.hidden = true; owner = null; }, 180);
  }
  card.addEventListener("mouseenter", function () { clearTimeout(hideTimer); });
  card.addEventListener("mouseleave", hideSoon);
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") { card.hidden = true; owner = null; } });
  document.addEventListener("click", function (e) {
    if (owner && !card.contains(e.target) && !owner.contains(e.target)) { card.hidden = true; owner = null; }
  });

  function attach(node, entry, others) {
    node.classList.add("gl-has");
    if (!node.hasAttribute("tabindex")) node.setAttribute("tabindex", "0");
    node.addEventListener("mouseenter", function () { show(node, entry, others); });
    node.addEventListener("mouseleave", hideSoon);
    node.addEventListener("focus", function () { show(node, entry, others); });
    node.addEventListener("blur", hideSoon);
    // Touch: the first tap shows the card instead of doing nothing visible.
    node.addEventListener("click", function () {
      if (owner === node && !card.hidden) { card.hidden = true; owner = null; }
      else show(node, entry, others);
    });
  }

  /* ---------- annotate the page ---------- */

  function annotate(data) {
    var byKey = {};
    data.forEach(function (e) { (byKey[keyOf(e[0])] = byKey[keyOf(e[0])] || []).push(e); });
    function lookup(text) {
      var k = text.trim().toLowerCase();
      return byKey[k] || byKey[k.replace(/(es|s)$/, "")] || byKey[k.replace(/s$/, "")] || null;
    }

    // 1. Terms defined on this page.
    var definedHere = {};
    document.querySelectorAll("article .term").forEach(function (span) {
      var list = lookup(span.textContent);
      definedHere[span.textContent.trim().toLowerCase()] = 1;
      if (list) attach(span, best(list), list.length - 1);
    });

    // 2. The first plain mention of a term defined elsewhere.
    var keys = Object.keys(byKey).filter(function (k) {
      return !definedHere[k] && byKey[k].some(function (e) { return linkable(e[0].replace(/\s*\(.*\)\s*$/, "")); });
    });
    if (!keys.length) return;
    keys.sort(function (a, b) { return b.length - a.length; });
    var re = new RegExp("(^|[^\\w-])(" + keys.map(function (k) {
      return k.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    }).join("|") + ")(s|es)?(?![\\w-])", "gi");

    var SKIP = "a, code, pre, kbd, .term, .gl-has, h1, h2, h3, h4, .callout-title, svg, figure, .quiz, .sources, .toc, .pager, .chapter-eyebrow, .builds-on, .complete-box, .terminal, .widget, .stepper, .road-card, button";
    var seen = {};
    var blocks = document.querySelectorAll("article.prose p, article.prose li, article.prose dd, article.prose td, article.prose figcaption");
    blocks.forEach(function (block) {
      if (block.closest(SKIP)) return;
      var walker = document.createTreeWalker(block, NodeFilter.SHOW_TEXT, {
        acceptNode: function (n) {
          return n.parentElement && n.parentElement.closest(SKIP) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT;
        }
      });
      var texts = [];
      while (walker.nextNode()) texts.push(walker.currentNode);
      texts.forEach(function (node) {
        var s = node.nodeValue, m, last = 0, frag = null;
        re.lastIndex = 0;
        while ((m = re.exec(s))) {
          var word = m[2], k = word.toLowerCase();
          var list = byKey[k];
          if (!list || seen[k]) continue;
          // Terms with two or more capitals (MCTS, ZeRO, PyTorch) match only
          // with the same capitals: "zero" in prose is not ZeRO.
          var base = list[0][0].replace(/\s*\(.*\)\s*$/, "");
          if (/[A-Z].*[A-Z]/.test(base) && word !== base) continue;
          seen[k] = 1;
          frag = frag || document.createDocumentFragment();
          var start = m.index + m[1].length;
          frag.appendChild(document.createTextNode(s.slice(last, start)));
          var span = document.createElement("span");
          span.className = "gl-mention";
          span.textContent = s.slice(start, start + word.length + (m[3] || "").length);
          attach(span, best(list), list.length - 1);
          frag.appendChild(span);
          last = start + span.textContent.length;
        }
        if (frag) {
          frag.appendChild(document.createTextNode(s.slice(last)));
          node.parentNode.replaceChild(frag, node);
        }
      });
    });
  }

  function load() {
    if (window.CS_GLOSSARY) { annotate(window.CS_GLOSSARY); return; }
    var s = document.createElement("script");
    s.src = ASSETS + "js/glossary-data.js";
    s.onload = function () { if (window.CS_GLOSSARY) annotate(window.CS_GLOSSARY); };
    document.body.appendChild(s);
  }
  if ("requestIdleCallback" in window) window.requestIdleCallback(load, { timeout: 1500 });
  else setTimeout(load, 300);
})();
