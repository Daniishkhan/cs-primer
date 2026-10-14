/* Equations: typeset maths, and "equation anatomy" blocks that break a formula
   down. Loaded by main.js (loadEquations) on pages with [data-tex].

   Any element with data-tex is typeset with KaTeX (vendored). Its own HTML is
   the fallback, shown when JavaScript is off, while printing a page that never
   ran it, or if the TeX fails to parse:

     <div class="eq-display" data-tex="E = mc^2">E = mc<sup>2</sup></div>
     <span class="tex" data-tex="\sigma(z)">&sigma;(z)</span>        (inline)

   An anatomy block adds a reading, a legend of terms and a build-up:

     <figure class="eq">
       <div class="eq-display" data-tex="\htmlClass{eq-t1}{a} + \htmlClass{eq-t2}{b}">a + b</div>
       <p class="eq-read">In words: …</p>
       <dl class="eq-terms">
         <div data-term="t1"><dt data-tex="a">a</dt>
           <dd><span class="eq-type">scalar</span> What a is, in plain words.</dd></div>
       </dl>
       <ol class="eq-steps">
         <li data-tex="a" data-terms="t1">Caption for step 1.</li>
         <li data-tex="a + b" data-terms="t1 t2">Caption for step 2.</li>
       </ol>
     </figure>

   Terms t1 to t8 get a colour each. Hovering or focusing a legend row lights
   that term up in the equation (and the other way round). Each step shows its
   partial expression and caption, and dims the terms it has not reached yet.
*/
(function () {
  "use strict";

  var ASSETS = (window.NZ && window.NZ.assets) || "";
  var TERM = /^t[1-8]$/;

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }
  function loadCss(href) {
    if (document.querySelector('link[href="' + href + '"]')) return;
    var l = el("link");
    l.rel = "stylesheet";
    l.href = href;
    document.head.appendChild(l);
  }
  function loadScript(src) {
    return new Promise(function (ok, fail) {
      var s = el("script");
      s.src = src;
      s.onload = ok;
      s.onerror = function () { fail(new Error("could not load " + src)); };
      document.head.appendChild(s);
    });
  }

  /* ---------- typesetting ---------- */

  var OPTIONS = {
    throwOnError: true,
    strict: false,
    output: "htmlAndMathml",                  // MathML keeps it readable to screen readers
    trust: function (ctx) { return ctx.command === "\\htmlClass"; },
    macros: {
      "\\E": "\\mathbb{E}",
      "\\R": "\\mathbb{R}",
      "\\KL": "\\mathrm{KL}",
      "\\softmax": "\\operatorname{softmax}",
      "\\argmax": "\\operatorname*{arg\\,max}",
      "\\argmin": "\\operatorname*{arg\\,min}"
    }
  };

  // Renders tex into node; on a parse error the fallback HTML stays and the
  // node is flagged, so the page never shows a red KaTeX error to a reader.
  function typeset(node, tex, display) {
    var host = el("span", "eq-tex");
    try {
      window.katex.render(tex, host, Object.assign({ displayMode: display }, OPTIONS));
    } catch (e) {
      node.classList.add("eq-error");
      node.title = "Could not typeset: " + e.message;
      console.warn("equations.js:", e.message, "in", tex);
      return false;
    }
    node.textContent = "";
    node.appendChild(host);
    node.classList.add("eq-done");
    return true;
  }

  function isDisplay(node) {
    return node.classList.contains("eq-display") || node.tagName === "DIV" || node.tagName === "P";
  }

  /* ---------- anatomy: legend <-> equation highlighting ---------- */

  function termsIn(root, id) {
    return root.querySelectorAll(".eq-display .eq-" + id);
  }

  function linkLegend(fig) {
    var rows = Array.prototype.slice.call(fig.querySelectorAll(".eq-terms [data-term]"));
    function light(id, on) {
      fig.classList.toggle("eq-focus", on);
      termsIn(fig, id).forEach(function (n) { n.classList.toggle("eq-lit", on); });
      rows.forEach(function (r) { r.classList.toggle("eq-lit", on && r.dataset.term === id); });
    }
    rows.forEach(function (row) {
      var id = row.dataset.term;
      if (!TERM.test(id)) return;
      row.classList.add("eq-c-" + id);
      row.tabIndex = 0;
      row.addEventListener("mouseenter", function () { light(id, true); });
      row.addEventListener("mouseleave", function () { light(id, false); });
      row.addEventListener("focus", function () { light(id, true); });
      row.addEventListener("blur", function () { light(id, false); });
      termsIn(fig, id).forEach(function (n) {
        n.addEventListener("mouseenter", function () { light(id, true); });
        n.addEventListener("mouseleave", function () { light(id, false); });
      });
    });
  }

  /* ---------- anatomy: build-up stepper ---------- */

  function buildSteps(fig) {
    var list = fig.querySelector(".eq-steps");
    if (!list) return;
    var steps = Array.prototype.slice.call(list.children);
    var n = steps.length;
    if (!n) return;

    var box = el("div", "eq-build");
    var head = el("div", "eq-build-head");
    head.appendChild(el("span", "widget-tag", "Build it up"));
    var count = el("span", "stepper-count");
    head.appendChild(count);
    var expr = el("div", "eq-build-expr");
    var caption = el("div", "eq-build-caption");
    caption.setAttribute("aria-live", "polite");

    var controls = el("div", "stepper-controls");
    function btn(label, cls, aria) {
      var b = el("button", "btn small " + (cls || ""), label);
      b.type = "button";
      b.setAttribute("aria-label", aria);
      controls.appendChild(b);
      return b;
    }
    var prev = btn("← Back", "", "Previous step");
    var next = btn("Next →", "primary", "Next step");
    var all = btn("Show all", "", "Show the whole equation");
    var dots = el("div", "stepper-dots");
    steps.forEach(function (_, i) {
      var d = el("button");
      d.type = "button";
      d.setAttribute("aria-label", "Go to step " + (i + 1));
      d.addEventListener("click", function () { go(i + 1); });
      dots.appendChild(d);
    });
    controls.appendChild(dots);

    box.appendChild(head);
    box.appendChild(expr);
    box.appendChild(caption);
    box.appendChild(controls);
    list.parentNode.insertBefore(box, list);
    list.hidden = true;

    // Each step's expression is typeset once, into its own holder; inline
    // maths in captions is typeset in place before captions are cloned.
    var rendered = steps.map(function (li) {
      li.querySelectorAll("[data-tex]").forEach(function (node) {
        typeset(node, node.getAttribute("data-tex"), false);
      });
      var holder = el("div", "eq-build-tex");
      var tex = li.getAttribute("data-tex");
      if (tex) {
        holder.textContent = tex;
        typeset(holder, tex, true);
      }
      return holder;
    });

    var cur = 0;                                  // 0 = whole equation, no dimming
    function go(i) {
      cur = Math.max(0, Math.min(n, i));
      expr.textContent = "";
      caption.textContent = "";
      var reached = {};
      if (cur > 0) {
        var li = steps[cur - 1];
        expr.appendChild(rendered[cur - 1]);
        Array.prototype.forEach.call(li.childNodes, function (c) {
          caption.appendChild(c.cloneNode(true));
        });
        for (var k = 0; k < cur; k++) {
          (steps[k].dataset.terms || "").split(/\s+/).forEach(function (t) {
            if (TERM.test(t)) reached[t] = true;
          });
        }
      } else {
        caption.textContent = "Step through the equation one piece at a time, or hover a term in the legend.";
      }
      fig.classList.toggle("eq-stepping", cur > 0);
      for (var t = 1; t <= 8; t++) {
        var id = "t" + t;
        termsIn(fig, id).forEach(function (node) {
          node.classList.toggle("eq-dim", cur > 0 && !reached[id]);
        });
      }
      count.textContent = cur ? cur + " / " + n : n + " steps";
      prev.disabled = cur === 0;
      next.disabled = cur === n;
      next.textContent = cur === 0 ? "Start →" : "Next →";
      Array.prototype.forEach.call(dots.children, function (d, k) {
        d.classList.toggle("on", k + 1 === cur);
      });
    }
    prev.addEventListener("click", function () { go(cur - 1); });
    next.addEventListener("click", function () { go(cur + 1); });
    all.addEventListener("click", function () { go(0); });
    box.tabIndex = 0;
    box.addEventListener("keydown", function (e) {
      if (e.key === "ArrowRight") { go(cur + 1); e.preventDefault(); }
      if (e.key === "ArrowLeft") { go(cur - 1); e.preventDefault(); }
    });
    go(0);
  }

  /* ---------- boot ---------- */

  function run() {
    document.querySelectorAll("[data-tex]").forEach(function (node) {
      if (node.closest(".eq-steps")) return;     // step expressions render in buildSteps
      typeset(node, node.getAttribute("data-tex"), isDisplay(node) && node.tagName !== "DT");
    });
    document.querySelectorAll("figure.eq").forEach(function (fig) {
      linkLegend(fig);
      buildSteps(fig);
    });
  }

  loadCss(ASSETS + "vendor/katex/katex.min.css");
  (window.katex ? Promise.resolve() : loadScript(ASSETS + "vendor/katex/katex.min.js"))
    .then(run)
    .catch(function (e) { console.warn("equations.js:", e.message); });
})();
