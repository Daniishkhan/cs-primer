/* Claim-strength checker (A8 chapter 17).
   Two systems are scored on the same number of test cases. The widget computes a 95% Wilson
   interval for each and a Newcombe interval for the difference (treating the two samples as
   independent, which is slightly conservative for a paired test), then suggests the strongest
   sentence a status report can honestly write. No randomness. */
(function () {
  "use strict";
  var root = document.getElementById("aid17-claims");
  if (!root) return;
  function q(n) { return root.querySelector("[data-act=" + n + "]"); }
  var nIn = q("n"), aIn = q("a"), bIn = q("b");
  var nOut = q("n-out"), aOut = q("a-out"), bOut = q("b-out");
  var bar = q("bar"), table = q("table"), words = q("words");
  var Z = 1.96;

  function wilson(p, n) {
    var d = 1 + Z * Z / n;
    var c = (p + Z * Z / (2 * n)) / d;
    var h = Z * Math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / d;
    return [c - h, c + h];
  }
  function pct(x) { return (100 * x).toFixed(1) + "%"; }
  function signed(x) { return (x >= 0 ? "+" : "") + (100 * x).toFixed(1) + " pt"; }

  function update() {
    var n = +nIn.value, a = +aIn.value / 100, b = +bIn.value / 100;
    nOut.textContent = n + " cases";
    aOut.textContent = (+aIn.value) + "%";
    bOut.textContent = (+bIn.value) + "%";
    var ka = Math.round(a * n), kb = Math.round(b * n);
    var pa = ka / n, pb = kb / n;
    var ia = wilson(pa, n), ib = wilson(pb, n);
    var d = pb - pa;
    var lo = d - Math.sqrt(Math.pow(pb - ib[0], 2) + Math.pow(ia[1] - pa, 2));
    var hi = d + Math.sqrt(Math.pow(ib[1] - pb, 2) + Math.pow(pa - ia[0], 2));
    table.innerHTML = "";
    [["Baseline", ka, pa, ia], ["New system", kb, pb, ib]].forEach(function (r) {
      var tr = document.createElement("tr");
      [r[0], r[1] + " of " + n, pct(r[2]), pct(r[3][0]) + " to " + pct(r[3][1])].forEach(function (t) {
        var td = document.createElement("td"); td.textContent = t; tr.appendChild(td);
      });
      table.appendChild(tr);
    });
    var tr2 = document.createElement("tr");
    ["Difference", "", signed(d), signed(lo) + " to " + signed(hi)].forEach(function (t) {
      var td = document.createElement("td"); td.textContent = t; tr2.appendChild(td);
    });
    table.appendChild(tr2);

    // bar: range of the difference on a -30..+30 point axis
    var scale = 30, left = Math.max(0, Math.min(100, 50 + 50 * (100 * lo) / scale));
    var right = Math.max(0, Math.min(100, 50 + 50 * (100 * hi) / scale));
    var dot = Math.max(0, Math.min(100, 50 + 50 * (100 * d) / scale));
    bar.innerHTML = "";
    var track = document.createElement("div"); track.className = "aid17-track";
    var span = document.createElement("div"); span.className = "aid17-span " + (lo > 0 ? "good" : (hi < 0 ? "bad" : "flat"));
    span.style.left = left + "%"; span.style.width = Math.max(0.8, right - left) + "%";
    var mid = document.createElement("div"); mid.className = "aid17-zero";
    var pt = document.createElement("div"); pt.className = "aid17-dot"; pt.style.left = dot + "%";
    track.appendChild(span); track.appendChild(mid); track.appendChild(pt); bar.appendChild(track);
    var ax = document.createElement("div"); ax.className = "aid17-axis";
    ax.innerHTML = "<span>-30 pt</span><span>0</span><span>+30 pt</span>";
    bar.appendChild(ax);

    var text, cls;
    if (lo > 0) {
      text = "Supportable: \"The new system scored " + pct(pb) + " against " + pct(pa) + " on the same " + n + " cases; the difference is " + signed(d) + " (95% interval " + signed(lo) + " to " + signed(hi) + ").\"";
      cls = "ok";
    } else if (hi < 0) {
      text = "Supportable, and bad news: \"The new system scored lower than the baseline, " + signed(d) + " (95% interval " + signed(lo) + " to " + signed(hi) + "). We recommend not switching.\"";
      cls = "bad";
    } else {
      text = "Not yet supportable: \"improved\". Write: \"The new system scored " + pct(pb) + " against " + pct(pa) + ", but with " + n + " cases the interval for the difference (" + signed(lo) + " to " + signed(hi) + ") includes zero. We cannot yet tell them apart; " + (Math.round(n * 2.5)) + " or more cases would narrow it.\"";
      cls = "warn";
    }
    words.textContent = text;
    words.className = "widget-out aid17-words " + cls;
  }
  [nIn, aIn, bIn].forEach(function (e) { e.addEventListener("input", update); });
  update();
})();
