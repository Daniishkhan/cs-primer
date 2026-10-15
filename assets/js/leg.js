/* A leg's step pages (loaded by main.js on pages with a .step-workspace).

   A leg is one program that grows one step at a time (taxi/code/project.py).
   A step page holds one workspace box:

     <div class="step-workspace" data-dir="../code/" data-step="7"
          data-files="check.py rides.csv"></div>

   It loads the program as it stands at that step (code/drills/s07.py,
   built by authoring/build_leg.py), shows it as project.py in the lab
   runner, opens the editor at the step's stub, and runs check.py 7 on
   Check. A pass marks the step (the chapter) complete in the course, so
   the sidebar, the roadmap and the hub all move. Nothing else is stored. */
(function () {
  "use strict";

  var box = document.querySelector(".step-workspace");
  if (!box || !window.NZ || !window.NZ.ensureRunner) return;
  var step = parseInt(box.getAttribute("data-step"), 10);
  var chapter = document.body.dataset.chapter;
  var course = document.body.dataset.course;

  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function (k) {
      if (k === "text") node.textContent = attrs[k];
      else if (k === "class") node.className = attrs[k];
      else node.setAttribute(k, attrs[k]);
    });
    (children || []).forEach(function (c) { if (c) node.appendChild(c); });
    return node;
  }

  box.setAttribute("data-edit", "project.py");
  box.setAttribute("data-edit-src", "drills/s" + (step < 10 ? "0" : "") + step + ".py");
  box.setAttribute("data-args", String(step));
  box.setAttribute("data-key", "nz-code:" + location.pathname + ":project.py");
  var result = el("div", { class: "drill-result", "aria-live": "polite" });
  box.parentNode.insertBefore(result, box.nextSibling);

  // Put the cursor on the step's stub in the editor. On load the page stays
  // where it is; the button under the signature box scrolls to it and focuses.
  function jumpToStub(cell, focus) {
    function place() {
      var cm = cell.cm;
      if (!cm) return false;
      var lines = cm.getValue().split("\n");
      var at = lines.findIndex(function (l) { return l.indexOf("TODO step " + step + ":") !== -1; });
      if (at === -1) at = lines.findIndex(function (l) { return /^\s*def |^class /.test(l); });
      if (at === -1) return true;
      cm.setCursor({ line: at, ch: lines[at].length }, null, { scroll: focus });   // no page jump on load
      if (focus) {
        cm.scrollIntoView({ line: Math.max(0, at - 6), ch: 0 }, 60);
        cm.scrollIntoView({ line: at, ch: 0 }, 60);
        cm.focus();
      }
      return true;
    }
    if (!cell.cm && typeof cell.toggleEdit === "function") cell.toggleEdit(true);
    var tries = 0, t = setInterval(function () { if (place() || ++tries > 60) clearInterval(t); }, 50);
  }

  var sig = document.querySelector('pre[data-title="your move"]');
  window.NZ.ensureRunner().then(function () { return window.NZ.workspace(box); }).then(function (cell) {
    if (!cell || box.classList.contains("is-local")) return;
    jumpToStub(cell, false);
    if (sig) {
      var jump = el("button", { type: "button", class: "theme-toggle", text: "Open the editor at this stub ↓" });
      jump.addEventListener("click", function () { jumpToStub(cell, true); });
      sig.parentNode.insertBefore(el("p", { class: "step-jump" }, [jump]), sig.nextSibling);
    }
  }).catch(function (e) {
    result.appendChild(el("p", { class: "drill-fail", text: "Could not load the runner: " + e.message }));
  });

  box.addEventListener("cell-done", function (ev) {
    var d = ev.detail || {};
    var out = d.stdout || "";
    var sum = /(\d+)\/(\d+) steps passing/.exec(out);
    result.textContent = "";
    if (d.stopped) { result.appendChild(el("p", { class: "drill-warn", text: "Stopped before the check finished." })); return; }
    if (sum && +sum[1] === +sum[2] && +sum[2] > 0 && !d.failed) {
      if (window.NZ.markDone && chapter) window.NZ.markDone(chapter);
      result.appendChild(el("p", { class: "drill-ok", text: "✔ Step " + step + " passed" + (d.ms ? " · " + (d.ms < 1000 ? Math.round(d.ms) + " ms" : (d.ms / 1000).toFixed(1) + " s") : "") + ". The numbers above are from the real rides." }));
      var next = document.querySelector("nav.pager a.next");
      if (next) {
        var go = el("a", { class: "btn primary", href: next.getAttribute("href"), text: "Next step →" });
        result.appendChild(go);
        go.focus();
      }
      return;
    }
    var why = (out.split("\n").find(function (l) { return /^\s*[✘…]/.test(l); }) || "").trim();
    result.appendChild(el("p", { class: "drill-fail", text: why ? "Not yet. " + why.replace(/^[✘…]\s*/, "") : "Not yet: the check did not pass. The output above says why." }));
  });
})();
