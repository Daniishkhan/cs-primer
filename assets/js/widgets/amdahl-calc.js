/* Amdahl's law calculator (systems chapter 21).
   Inputs: the parallel fraction p of a 100-second job and a worker count n.
   Outputs: new runtime, speedup = 1 / ((1-p) + p/n), the n -> infinity limit
   1 / (1-p), and two bars showing the serial and parallel parts before and
   after. All DOM text is set with textContent. No libraries, no storage. */
(function () {
  "use strict";
  var root = document.getElementById("amdahl-calc");
  if (!root) return;
  function q(act) { return root.querySelector('[data-act="' + act + '"]'); }
  var pIn = q("p"), nIn = q("n"), pOut = q("p-out"), nOut = q("n-out");
  var before = q("before"), after = q("after"), stats = q("stats"), note = q("note");
  var WORKERS = [1, 2, 4, 8, 16, 32, 64, 128, 256, 1024, 100000];

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function fmt(x) { return (Math.round(x * 100) / 100).toFixed(2); }
  function bar(host, serial, par, scale) {
    host.textContent = "";
    var s = el("div", "am-seg am-ser", serial >= 8 ? fmt(serial) + " s" : "");
    var p = el("div", "am-seg am-par", par >= 8 ? fmt(par) + " s" : "");
    s.style.width = (serial / scale * 100) + "%";
    p.style.width = (par / scale * 100) + "%";
    host.appendChild(s); host.appendChild(p);
  }
  function update() {
    var p = parseInt(pIn.value, 10) / 100;
    var n = WORKERS[parseInt(nIn.value, 10)];
    var serial = 100 * (1 - p), par = 100 * p;
    var newPar = par / n, total = serial + newPar;
    var speed = 100 / total;
    var limit = p >= 1 ? Infinity : 1 / (1 - p);
    pOut.textContent = Math.round(p * 100) + "% parallel";
    nOut.textContent = n.toLocaleString("en-US") + (n === 1 ? " worker" : " workers");
    bar(before, serial, par, 100);
    bar(after, serial, newPar, 100);
    stats.textContent = "";
    [["New runtime", fmt(total) + " s"],
     ["Speedup", fmt(speed) + "x"],
     ["Limit with endless workers", limit === Infinity ? "no limit" : fmt(limit) + "x"],
     ["Efficiency (speedup / workers)", (speed / n * 100 < 0.1 ? "<0.1" : fmt(speed / n * 100)) + "%"]
    ].forEach(function (kv) {
      var c = el("div", "am-stat");
      c.appendChild(el("span", "am-stat-k", kv[0]));
      c.appendChild(el("span", "am-stat-v", kv[1]));
      stats.appendChild(c);
    });
    note.textContent = p >= 1
      ? "With nothing serial, the speedup equals the worker count (an idealisation that no real system reaches)."
      : "The orange part never shrinks: " + fmt(serial) + " s of serial work caps you at " + fmt(limit) + "x, however many workers you add.";
  }
  pIn.addEventListener("input", update);
  nIn.addEventListener("input", update);
  update();
})();
