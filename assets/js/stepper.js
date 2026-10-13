/* Generic step-through animation for diagrams.

   <div class="widget stepper" data-autoplay-ms="2200">
     <div class="widget-head"><span class="widget-tag">Step through</span><h4 class="widget-title">TCP handshake</h4></div>
     <svg viewBox="…">
       <g>always visible</g>
       <g data-steps="2-4">visible on steps 2, 3 and 4</g>
       <g data-steps="3-">visible from step 3 onward</g>
       <g data-steps="1,5">visible on steps 1 and 5</g>
       <g data-steps="2-" data-active="2">visible from 2, glows on step 2</g>
     </svg>
     <ol class="stepper-captions">
       <li>Caption for step 1</li>
       <li>Caption for step 2</li> …
     </ol>
   </div>

   Steps are 1-based and the number of steps is the number of captions.
   Controls (back / next / play / dots) are added automatically.
   Arrow keys work while the widget has focus.
*/
(function () {
  "use strict";

  function parseSet(spec, max) {
    var set = new Set();
    String(spec).split(",").forEach(function (part) {
      part = part.trim();
      if (!part) return;
      var m = part.match(/^(\d*)\s*-\s*(\d*)$/);
      if (m) {
        var a = m[1] ? parseInt(m[1], 10) : 1;
        var b = m[2] ? parseInt(m[2], 10) : max;
        for (var i = a; i <= b; i++) set.add(i);
      } else set.add(parseInt(part, 10));
    });
    return set;
  }

  function setup(w) {
    var captions = Array.prototype.slice.call(w.querySelectorAll(".stepper-captions > li"));
    var n = captions.length;
    if (!n) return;
    var list = w.querySelector(".stepper-captions");
    var box = document.createElement("div");
    box.className = "stepper-caption-box";
    box.setAttribute("aria-live", "polite");
    list.parentNode.insertBefore(box, list);
    box.appendChild(list);

    var shown = Array.prototype.slice.call(w.querySelectorAll("[data-steps]")).map(function (node) {
      return { node: node, set: parseSet(node.dataset.steps, n) };
    });
    var active = Array.prototype.slice.call(w.querySelectorAll("[data-active]")).map(function (node) {
      return { node: node, set: parseSet(node.dataset.active, n) };
    });

    var controls = document.createElement("div");
    controls.className = "stepper-controls";
    function btn(label, cls, aria) {
      var b = document.createElement("button");
      b.type = "button"; b.className = "btn small " + (cls || ""); b.textContent = label;
      if (aria) b.setAttribute("aria-label", aria);
      controls.appendChild(b); return b;
    }
    var first = btn("⏮", "", "First step");
    var prev = btn("← Back", "", "Previous step");
    var next = btn("Next →", "primary", "Next step");
    var play = btn("▶ Play", "", "Play automatically");
    var dots = document.createElement("div");
    dots.className = "stepper-dots";
    captions.forEach(function (_, i) {
      var d = document.createElement("button");
      d.type = "button"; d.setAttribute("aria-label", "Go to step " + (i + 1));
      d.addEventListener("click", function () { stop(); go(i + 1); });
      dots.appendChild(d);
    });
    controls.appendChild(dots);
    var count = document.createElement("span");
    count.className = "stepper-count";
    controls.appendChild(count);
    box.parentNode.insertBefore(controls, box.nextSibling);

    var step = 1, timer = null;
    var delay = parseInt(w.dataset.autoplayMs || "2400", 10);

    function go(s) {
      step = Math.max(1, Math.min(n, s));
      shown.forEach(function (x) { x.node.classList.toggle("step-hidden", !x.set.has(step)); });
      active.forEach(function (x) { x.node.classList.toggle("step-active", x.set.has(step)); });
      captions.forEach(function (c, i) { c.classList.toggle("current", i === step - 1); });
      Array.prototype.forEach.call(dots.children, function (d, i) { d.classList.toggle("on", i < step); });
      count.textContent = step + " / " + n;
      prev.disabled = first.disabled = step === 1;
      next.disabled = step === n && !timer;
      w.dispatchEvent(new CustomEvent("stepchange", { detail: { step: step, total: n } }));
    }
    function stop() { if (timer) { clearInterval(timer); timer = null; play.textContent = "▶ Play"; } next.disabled = step === n; }
    function start() {
      if (step === n) go(1);
      play.textContent = "⏸ Pause";
      timer = setInterval(function () { if (step >= n) stop(); else go(step + 1); }, delay);
    }

    first.addEventListener("click", function () { stop(); go(1); });
    prev.addEventListener("click", function () { stop(); go(step - 1); });
    next.addEventListener("click", function () { stop(); go(step + 1); });
    play.addEventListener("click", function () { if (timer) stop(); else start(); });
    w.tabIndex = w.tabIndex >= 0 ? w.tabIndex : 0;
    w.addEventListener("keydown", function (e) {
      if (e.target !== w) return;
      if (e.key === "ArrowRight") { e.preventDefault(); stop(); go(step + 1); }
      if (e.key === "ArrowLeft") { e.preventDefault(); stop(); go(step - 1); }
    });
    go(1);
  }

  function init() { document.querySelectorAll(".stepper").forEach(setup); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
