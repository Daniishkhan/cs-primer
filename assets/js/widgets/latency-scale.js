/* "If 1 nanosecond were 1 second" (chapter 13).
   Shows typical latencies on a log-scale bar, in real units or in
   human-scale time (1 ns -> 1 s). Numbers are rough orders of magnitude. */
(function () {
  "use strict";
  var root = document.getElementById("latency-scale");
  if (!root) return;

  var ITEMS = [
    { name: "L1 cache reference", ns: 1, cls: "c-cpu" },
    { name: "Main memory (RAM) reference", ns: 100, cls: "c-mem" },
    { name: "SSD random read", ns: 100e3, cls: "c-disk" },
    { name: "Round trip inside one data center", ns: 500e3, cls: "c-net" },
    { name: "Spinning-disk seek", ns: 10e6, cls: "c-disk" },
    { name: "Round trip across a continent", ns: 40e6, cls: "c-net" },
    { name: "Round trip across an ocean", ns: 150e6, cls: "c-net" }
  ];
  var LOG_MAX = Math.log10(150e6);
  var mode = "real";

  function fmt(n, digits) {
    var s = n >= 100 ? String(Math.round(n)) : n.toFixed(digits === undefined ? 1 : digits);
    return s.replace(/\.0$/, "");
  }
  function plural(v, unit) { return fmt(v) + " " + unit + (fmt(v) === "1" ? "" : "s"); }

  function real(ns) {
    if (ns < 1e3) return fmt(ns) + " ns";
    if (ns < 1e6) return fmt(ns / 1e3) + " µs";
    return fmt(ns / 1e6) + " ms";
  }
  function human(ns) {
    var s = ns; // 1 ns -> 1 s
    if (s < 60) return plural(s, "second");
    if (s < 3600) return plural(s / 60, "minute");
    if (s < 86400) return plural(s / 3600, "hour");
    if (s < 86400 * 365) return plural(s / 86400, "day");
    return plural(s / (86400 * 365), "year");
  }

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }

  var rowsBox = root.querySelector(".ls-rows");
  var vals = [];
  ITEMS.forEach(function (it) {
    var row = el("div", "ls-row");
    row.appendChild(el("div", "ls-name", it.name));
    var track = el("div", "ls-track");
    var bar = el("div", "ls-bar " + it.cls);
    var w = Math.max(2, ((Math.log10(it.ns) + 0.3) / (LOG_MAX + 0.3)) * 100);
    bar.style.width = w.toFixed(1) + "%";
    track.appendChild(bar);
    row.appendChild(track);
    var v = el("div", "ls-val");
    vals.push(v);
    row.appendChild(v);
    rowsBox.appendChild(row);
  });

  var note = root.querySelector(".ls-note");
  function render() {
    ITEMS.forEach(function (it, i) { vals[i].textContent = mode === "real" ? real(it.ns) : human(it.ns); });
    note.textContent = mode === "real"
      ? "Real durations. Rough orders of magnitude: your hardware and network will differ."
      : "Human scale: pretend 1 nanosecond lasts 1 second. A memory read now takes minutes; an ocean crossing takes years.";
    Array.prototype.forEach.call(root.querySelectorAll(".ls-toggle .btn"), function (b) {
      b.setAttribute("aria-pressed", b.getAttribute("data-mode") === mode ? "true" : "false");
    });
  }
  Array.prototype.forEach.call(root.querySelectorAll(".ls-toggle .btn"), function (b) {
    b.addEventListener("click", function () { mode = b.getAttribute("data-mode"); render(); });
  });
  render();
})();
