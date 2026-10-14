/* Acceptance-verdict calculator (A8 chapter 06).
   You enter the number of gold-set cases, the share the system got right and the
   acceptance bar. The widget computes the Wilson 95% interval, draws it against the
   bar, applies the rule "accept if the interval's lower end reaches the bar, reject
   if its upper end falls below it, otherwise say there is not enough evidence", and
   reports how many cases would be needed to settle the question if the observed rate
   held. No randomness; the calculation is exact. */
(function () {
  "use strict";
  var root = document.getElementById("aid06-verdict");
  if (!root) return;

  function q(n) { return root.querySelector("[data-act=" + n + "]"); }
  var ctl = { n: q("n"), acc: q("acc"), bar: q("bar") };
  var outs = { n: q("n-out"), acc: q("acc-out"), bar: q("bar-out") };
  var track = root.querySelector(".aid06-track");
  var axis = root.querySelector(".aid06-axis");
  var summary = root.querySelector(".aid06-summary");
  var LO = 0.6, HI = 1.0;

  function wilson(k, n) {
    var z = 1.96, p = k / n, d = 1 + z * z / n;
    var c = (p + z * z / (2 * n)) / d;
    var h = z * Math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d;
    return [c - h, c + h];
  }
  function pos(x) { return Math.max(0, Math.min(100, (x - LO) / (HI - LO) * 100)) + "%"; }
  function pc(x, d) { return (x * 100).toFixed(d === undefined ? 1 : d) + "%"; }

  function settle(rate, bar) {
    for (var n = 10; n <= 20000; n += (n < 1000 ? 5 : 50)) {
      if (wilson(Math.round(rate * n), n)[0] >= bar) return n;
    }
    return null;
  }

  function update() {
    var n = parseInt(ctl.n.value, 10), acc = parseFloat(ctl.acc.value), bar = parseFloat(ctl.bar.value);
    outs.n.textContent = String(n);
    outs.acc.textContent = pc(acc, 0);
    outs.bar.textContent = pc(bar, 0);
    var k = Math.round(acc * n), iv = wilson(k, n), lo = iv[0], hi = iv[1];
    track.style.setProperty("--lo", pos(lo));
    track.style.setProperty("--hi", pos(hi));
    track.style.setProperty("--pt", pos(k / n));
    track.style.setProperty("--bar", pos(bar));
    var verdict, cls, extra = "";
    if (lo >= bar) { verdict = "ACCEPT: the whole interval is at or above the bar."; cls = "ok"; }
    else if (hi < bar) { verdict = "REJECT: even the best end of the interval is below the bar."; cls = "bad"; }
    else {
      verdict = "NOT ENOUGH EVIDENCE: the interval straddles the bar."; cls = "warn";
      if (k / n > bar) {
        var s = settle(k / n, bar);
        extra = s ? " If the observed " + pc(k / n, 1) + " held up, roughly " + s + " cases would be enough to clear the bar." : " At this rate the bar cannot be cleared with a realistic number of cases.";
      } else extra = " The observed rate is below the bar, so more cases would more likely confirm a miss than a pass.";
    }
    summary.textContent = k + " of " + n + " right = " + pc(k / n, 1) + ". 95% interval " + pc(lo) + " to " + pc(hi) + ". " + verdict + extra;
    summary.className = "widget-out aid06-summary " + cls;
  }
  for (var c in ctl) ctl[c].addEventListener("input", update);
  axis.innerHTML = "<span>60%</span><span>70%</span><span>80%</span><span>90%</span><span>100%</span>";
  update();
})();
