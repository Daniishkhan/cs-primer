/* Ranking metrics playground (retrieval chapter 04).
   Click a result to cycle its relevance grade (0 to 3). Set the cut-off k and
   how many judged relevant documents were never retrieved. The widget shows
   precision@k, recall@k, reciprocal rank, average precision and nDCG@k with
   linear and exponential gains, using the same definitions as the chapter's
   Python listing. */
(function () {
  "use strict";
  var root = document.getElementById("ret04-metrics");
  if (!root) return;

  var N = 10;
  var grades = [3, 0, 2, 0, 0, 1, 0, 2, 0, 0];
  var PRESETS = {
    chapter: { g: [3, 0, 2, 0, 0, 1, 0, 2, 0, 0], miss: 2 },
    perfect: { g: [3, 2, 2, 1, 1, 0, 0, 0, 0, 0], miss: 0 },
    last: { g: [0, 0, 0, 0, 0, 0, 0, 1, 2, 3], miss: 0 },
    one: { g: [0, 0, 0, 1, 0, 0, 0, 0, 0, 0], miss: 0 }
  };

  var kIn = root.querySelector("[data-act=k]"), kOut = root.querySelector("[data-act=k-out]");
  var mIn = root.querySelector("[data-act=miss]"), mOut = root.querySelector("[data-act=miss-out]");
  var strip = root.querySelector(".r4-strip");
  var out = root.querySelector(".r4-out");
  var note = root.querySelector(".r4-note");
  var cells = [];
  var LABEL = ["not relevant", "marginal", "good", "perfect"];

  function build() {
    for (var i = 0; i < N; i++) {
      var b = document.createElement("button");
      b.type = "button";
      b.className = "r4-cell";
      b.setAttribute("data-i", String(i));
      strip.appendChild(b);
      cells.push(b);
      b.addEventListener("click", function (e) {
        var j = parseInt(e.currentTarget.getAttribute("data-i"), 10);
        grades[j] = (grades[j] + 1) % 4;
        update();
      });
    }
  }

  function dcg(list, k, exp) {
    var s = 0;
    for (var i = 0; i < Math.min(k, list.length); i++) {
      var g = exp ? Math.pow(2, list[i]) - 1 : list[i];
      s += g / (Math.log(i + 2) / Math.LN2);
    }
    return s;
  }
  function f(x) { return x.toFixed(3); }

  function update() {
    var k = parseInt(kIn.value, 10), miss = parseInt(mIn.value, 10);
    kOut.textContent = String(k);
    mOut.textContent = String(miss);
    var relShown = 0, i;
    for (i = 0; i < N; i++) if (grades[i] >= 1) relShown++;
    var nRel = relShown + miss;
    var hits = 0, rr = 0, ap = 0;
    for (i = 0; i < N; i++) {
      if (grades[i] >= 1) {
        hits++;
        if (!rr) rr = 1 / (i + 1);
        ap += hits / (i + 1);
      }
    }
    ap = nRel ? ap / nRel : 0;
    var hitsK = 0;
    for (i = 0; i < k; i++) if (grades[i] >= 1) hitsK++;
    var all = grades.slice();
    for (i = 0; i < miss; i++) all.push(1);
    all.sort(function (a, b) { return b - a; });
    var nd = [false, true].map(function (exp) {
      var ideal = dcg(all, k, exp);
      return ideal ? dcg(grades, k, exp) / ideal : 0;
    });
    for (i = 0; i < N; i++) {
      var c = cells[i];
      c.className = "r4-cell g" + grades[i] + (i < k ? "" : " out");
      c.innerHTML = "<span class=\"r4-rank\">rank " + (i + 1) + "</span><b>" + grades[i] + "</b><span class=\"r4-lab\">" + LABEL[grades[i]] + "</span>";
      c.setAttribute("aria-label", "Rank " + (i + 1) + ", grade " + grades[i] + ", " + LABEL[grades[i]] + ". Click to change.");
    }
    out.innerHTML =
      "<div><span>precision@" + k + "</span><b>" + f(hitsK / k) + "</b></div>" +
      "<div><span>recall@" + k + "</span><b>" + (nRel ? f(hitsK / nRel) : "n/a") + "</b></div>" +
      "<div><span>reciprocal rank</span><b>" + f(rr) + "</b></div>" +
      "<div><span>average precision</span><b>" + f(ap) + "</b></div>" +
      "<div><span>nDCG@" + k + " (linear)</span><b>" + f(nd[0]) + "</b></div>" +
      "<div><span>nDCG@" + k + " (2<sup>g</sup>&minus;1)</span><b>" + f(nd[1]) + "</b></div>";
    var msg = nRel + " relevant documents exist for this query (" + relShown + " shown, " + miss + " never retrieved). ";
    if (!nRel) msg = "No relevant document exists, so recall and AP are undefined; evaluation sets usually drop such queries. ";
    else if (rr === 1 && hitsK / k < 0.5) msg += "Reciprocal rank is perfect because the first result is relevant, yet precision is low: the metrics ask different questions.";
    else if (hitsK === nRel && rr < 0.5) msg += "Recall is complete but the first relevant result is far down: good for a reranker's input, poor for a user who reads the top.";
    else msg += "Try moving a good result up one place and see which numbers change and which do not.";
    note.textContent = msg;
  }

  kIn.addEventListener("input", update);
  mIn.addEventListener("input", update);
  Array.prototype.forEach.call(root.querySelectorAll("[data-preset]"), function (btn) {
    btn.addEventListener("click", function () {
      var p = PRESETS[btn.getAttribute("data-preset")];
      grades = p.g.slice();
      mIn.value = String(p.miss);
      update();
    });
  });
  build();
  update();
})();
