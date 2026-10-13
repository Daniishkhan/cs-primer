/* Design studio pages: autosaved notes, a self-check rubric and a count of
   worked answers revealed. Everything is saved only in this browser.

   Markup:
     <textarea class="studio-notes" aria-label="…"></textarea>  (one per page; autosaves)
     <section class="stage"> … <details class="reveal"><summary>…</summary> … </details></section>
     <ul class="rubric"><li>Point to check</li> …</ul>              (becomes checkboxes)
     <p class="studio-status" id="studio-status"></p>              (optional summary line) */
(function () {
  "use strict";
  var body = document.body;
  var key = "cs-studio:" + (body.dataset.course || "") + ":" + (body.dataset.studio || location.pathname);

  function load(k, fallback) {
    try { var v = localStorage.getItem(k); return v === null ? fallback : JSON.parse(v); }
    catch (e) { return fallback; }
  }
  function save(k, v) {
    try { localStorage.setItem(k, JSON.stringify(v)); return true; } catch (e) { return false; }
  }

  /* ---------- notes ---------- */
  document.querySelectorAll("textarea.studio-notes").forEach(function (ta, i) {
    var k = key + ":notes" + (i ? i : "");
    ta.value = load(k, "");
    var status = document.createElement("p");
    status.className = "studio-saved";
    status.setAttribute("aria-live", "polite");
    ta.parentNode.insertBefore(status, ta.nextSibling);
    var timer = null;
    ta.addEventListener("input", function () {
      clearTimeout(timer);
      timer = setTimeout(function () {
        status.textContent = save(k, ta.value) ? "Saved in this browser." : "Couldn't save (private browsing?). Copy your notes somewhere safe.";
      }, 400);
    });
    if (ta.value) status.textContent = "Your saved notes are loaded.";
  });

  /* ---------- rubric ---------- */
  var ticks = load(key + ":rubric", {});
  document.querySelectorAll("ul.rubric").forEach(function (ul, u) {
    Array.prototype.forEach.call(ul.children, function (li, i) {
      var id = u + "-" + i;
      var box = document.createElement("input");
      box.type = "checkbox";
      box.id = "rubric-" + id;
      box.checked = !!ticks[id];
      var label = document.createElement("label");
      label.htmlFor = box.id;
      while (li.firstChild) label.appendChild(li.firstChild);
      li.appendChild(box);
      li.appendChild(label);
      box.addEventListener("change", function () {
        ticks[id] = box.checked;
        save(key + ":rubric", ticks);
        summary();
      });
    });
  });

  /* ---------- progress line ---------- */
  var reveals = document.querySelectorAll("details.reveal");
  function summary() {
    var out = document.getElementById("studio-status");
    if (!out) return;
    var opened = Array.prototype.filter.call(reveals, function (d) { return d.open; }).length;
    var boxes = document.querySelectorAll("ul.rubric input");
    var checked = Array.prototype.filter.call(boxes, function (b) { return b.checked; }).length;
    out.textContent = "Worked answers opened: " + opened + " of " + reveals.length + " · Rubric: " + checked + " of " + boxes.length + " covered.";
  }
  reveals.forEach(function (d) { d.addEventListener("toggle", summary); });
  summary();
})();
