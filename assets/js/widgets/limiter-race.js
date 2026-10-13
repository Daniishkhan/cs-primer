/* Rate-limiter race (design chapter 05).

   The same request trace is fed to five algorithms side by side:
   token bucket, leaky bucket (as a queue), fixed window, sliding log and
   sliding window counter. Each lane draws every request as a tick: green
   if admitted, red if rejected. Below the lanes a table shows how many
   were admitted, and the most requests admitted in ANY 1-second span (the
   number a client really experiences, and the one fixed windows get wrong).

   Model (simplified, deterministic, no randomness):
   - limit L requests per window of W = 1000 ms; bucket capacity = L, refill L per second
   - the token bucket starts full; the leaky bucket is a queue of size L draining L per second
     (it admits exactly what the token bucket admits, but delays requests; the worst wait is shown)
   - fixed windows are aligned to t = 0; the sliding window counter weights the previous window
   - one key, one limiter instance: no network, no store latency, no clock skew
   The same numbers are reproduced by the Python in the chapter (limit 10, preset 1).

   Pure functions are exported for testing under Node. */
(function () {
  "use strict";

  var W = 1000, HORIZON = 10000;

  function steady(step) { var a = [], t; for (t = 0; t < HORIZON; t += step) a.push(t); return a; }
  function burst(start, n, gap) { var a = [], i; for (i = 0; i < n; i++) a.push(start + gap * i); return a; }
  function sorted(a) { return a.sort(function (x, y) { return x - y; }); }

  var PRESETS = {
    bursts: { label: "Steady 6.7/s plus three bursts", make: function () {
      return sorted(steady(150).concat(burst(2000, 30, 10), burst(4900, 20, 10), burst(7000, 40, 10))); } },
    edge: { label: "Burst straddling a window edge", make: function (L) {
      return sorted(steady(250).concat(burst(5000 - L * 10, 2 * L, 10))); } },
    overload: { label: "Sustained 1.5x overload", make: function (L) {
      var gap = W / (1.5 * L), a = [], t;
      for (t = 0; t < HORIZON; t += gap) a.push(Math.round(t));
      return a; } }
  };

  function tokenBucket(ts, L) {
    var tokens = L, last = 0;
    return ts.map(function (t) {
      tokens = Math.min(L, tokens + (t - last) * L / W); last = t;
      if (tokens >= 1) { tokens -= 1; return true; }
      return false;
    });
  }

  function leaky(ts, L) {
    var level = 0, last = 0, worst = 0, ok = ts.map(function (t) {
      level = Math.max(0, level - (t - last) * L / W); last = t;
      if (level + 1 <= L) { level += 1; worst = Math.max(worst, level / L * W); return true; }
      return false;
    });
    ok.worstDelay = worst;
    return ok;
  }

  function fixedWindow(ts, L) {
    var cnt = 0, win = 0;
    return ts.map(function (t) {
      var w = Math.floor(t / W);
      if (w !== win) { win = w; cnt = 0; }
      if (cnt < L) { cnt++; return true; }
      return false;
    });
  }

  function slidingLog(ts, L) {
    var log = [], head = 0;
    return ts.map(function (t) {
      while (head < log.length && log[head] <= t - W) head++;
      if (log.length - head < L) { log.push(t); return true; }
      return false;
    });
  }

  function slidingCounter(ts, L) {
    var win = 0, cur = 0, prev = 0;
    return ts.map(function (t) {
      var w = Math.floor(t / W);
      if (w !== win) { prev = (w === win + 1) ? cur : 0; win = w; cur = 0; }
      var est = prev * (1 - (t % W) / W) + cur;
      if (est < L) { cur++; return true; }
      return false;
    });
  }

  function peakInAnyWindow(ts, ok) {
    var adm = [], i, j = 0, best = 0;
    for (i = 0; i < ts.length; i++) if (ok[i]) adm.push(ts[i]);
    for (i = 0; i < adm.length; i++) {
      while (adm[j] <= adm[i] - W) j++;
      best = Math.max(best, i - j + 1);
    }
    return best;
  }

  var ALGOS = [
    { id: "token", name: "Token bucket", fn: tokenBucket, state: "2 numbers (tokens, last refill)",
      note: "Allows a burst up to the bucket size, then the sustained rate. Up to about 2x the limit in one second." },
    { id: "leaky", name: "Leaky bucket (queue)", fn: leaky, state: "queue + 1 number",
      note: "Same admissions as the token bucket here, but requests wait in a queue so the output is smooth." },
    { id: "fixed", name: "Fixed window counter", fn: fixedWindow, state: "1 counter per window",
      note: "Cheapest. Resets at the edge, so a burst across the boundary can pass up to 2x the limit." },
    { id: "log", name: "Sliding window log", fn: slidingLog, state: "up to L timestamps",
      note: "Exact: never more than L in any window. Pays for it in memory." },
    { id: "swc", name: "Sliding window counter", fn: slidingCounter, state: "2 counters",
      note: "Approximates the log with two counters. Close to exact when traffic is spread evenly in each window." }
  ];

  function run(presetKey, L) {
    var ts = PRESETS[presetKey].make(L);
    return { ts: ts, rows: ALGOS.map(function (a) {
      var ok = a.fn(ts, L), n = 0, i;
      for (i = 0; i < ok.length; i++) if (ok[i]) n++;
      return { algo: a, ok: ok, admitted: n, rejected: ok.length - n, peak: peakInAnyWindow(ts, ok), worstDelay: ok.worstDelay };
    }) };
  }

  if (typeof module !== "undefined" && module.exports) {
    module.exports = { run: run, PRESETS: PRESETS, ALGOS: ALGOS };
  }

  var root = typeof document !== "undefined" ? document.getElementById("limiter-race") : null;
  if (!root) return;

  var NS = "http://www.w3.org/2000/svg";
  var VB_W = 760, LANE_H = 44, PAD = 8;
  var presetKey = "bursts", L = 10, cursor = HORIZON;

  function el(tag, attrs, text) {
    var e = document.createElement(tag), k;
    if (attrs) for (k in attrs) e.setAttribute(k, attrs[k]);
    if (text != null) e.textContent = text;
    return e;
  }
  function sv(tag, attrs) {
    var e = document.createElementNS(NS, tag), k;
    for (k in attrs) e.setAttribute(k, attrs[k]);
    return e;
  }
  function x(t) { return PAD + (VB_W - 2 * PAD) * t / HORIZON; }

  var head = el("div", { "class": "widget-head" });
  head.appendChild(el("span", { "class": "widget-tag" }, "Simulator"));
  head.appendChild(el("h4", { "class": "widget-title" }, "Limiter race: same traffic, five algorithms"));
  root.appendChild(head);
  root.appendChild(el("p", { "class": "widget-help" }, "Each tick is one request: green admitted, red rejected. Drag the time slider to see the running totals. Change the limit or the traffic and watch which algorithms agree."));

  var row = el("div", { "class": "widget-row" });
  var selLabel = el("label", null, "Traffic ");
  var sel = el("select", { "aria-label": "Traffic pattern" });
  Object.keys(PRESETS).forEach(function (k) { var o = el("option", { value: k }, PRESETS[k].label); sel.appendChild(o); });
  selLabel.appendChild(sel);
  var limLabel = el("label", null, "Limit per second ");
  var lim = el("input", { type: "number", min: "2", max: "50", value: String(L), "aria-label": "Limit per second", "class": "mono", style: "width:5em" });
  limLabel.appendChild(lim);
  row.appendChild(selLabel); row.appendChild(limLabel);
  root.appendChild(row);

  var lanes = el("div", { "class": "lr-lanes" });
  root.appendChild(lanes);

  var sliderRow = el("div", { "class": "widget-row" });
  var sLabel = el("label", { style: "flex:1;min-width:200px" }, "Time cursor ");
  var slider = el("input", { type: "range", min: "0", max: String(HORIZON), step: "50", value: String(HORIZON), "aria-label": "Time cursor in milliseconds" });
  sLabel.appendChild(slider);
  var tOut = el("span", { "class": "pill" }, "10.0 s");
  sliderRow.appendChild(sLabel); sliderRow.appendChild(tOut);
  root.appendChild(sliderRow);

  var out = el("div", { "class": "widget-out" });
  root.appendChild(out);

  var cursorLines = [];

  function render() {
    var res = run(presetKey, L), i;
    lanes.textContent = "";
    cursorLines = [];
    res.rows.forEach(function (r) {
      var box = el("div", { style: "margin-top:8px" });
      var cap = el("div", { style: "display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap;font-size:14px" });
      cap.appendChild(el("strong", null, r.algo.name));
      var cnt = el("span", { "class": "t-muted", "data-count": r.algo.id }, "");
      cap.appendChild(cnt);
      box.appendChild(cap);
      var s = sv("svg", { viewBox: "0 0 " + VB_W + " " + LANE_H, role: "img", "aria-label": r.algo.name + ": " + r.admitted + " admitted, " + r.rejected + " rejected, at most " + r.peak + " admitted in any one second" });
      s.appendChild(sv("rect", { x: 0, y: 0, width: VB_W, height: LANE_H, rx: 6, "class": "box2" }));
      var sec;
      for (sec = 1; sec < 10; sec++) {
        s.appendChild(sv("line", { x1: x(sec * W), y1: 2, x2: x(sec * W), y2: LANE_H - 2, "class": r.algo.id === "fixed" ? "line-dash" : "line-thin" }));
      }
      for (i = 0; i < res.ts.length; i++) {
        var ok = r.ok[i];
        s.appendChild(sv("line", { x1: x(res.ts[i]), x2: x(res.ts[i]), y1: ok ? 6 : 24, y2: ok ? 22 : 38, "class": ok ? "s-green" : "s-red", "stroke-width": 2 }));
      }
      var c = sv("line", { x1: x(cursor), x2: x(cursor), y1: 0, y2: LANE_H, "class": "s-yellow", "stroke-width": 2 });
      cursorLines.push(c); s.appendChild(c);
      box.appendChild(s);
      lanes.appendChild(box);
    });

    var tbl = "<div class=\"table-wrap\"><table><thead><tr><th>Algorithm</th><th>Admitted</th><th>Rejected</th><th>Peak in any 1 s</th><th>State per key</th></tr></thead><tbody>";
    res.rows.forEach(function (r) {
      tbl += "<tr><td><strong>" + r.algo.name + "</strong></td><td>" + r.admitted + "</td><td>" + r.rejected + "</td><td>" + r.peak +
        (r.peak > L ? ' <span class="pill red">&gt; limit</span>' : ' <span class="pill green">&le; limit</span>') + "</td><td>" + r.algo.state + "</td></tr>";
    });
    tbl += "</tbody></table></div>";
    var leaky = res.rows[1];
    out.innerHTML = tbl + '<p style="margin:8px 0 0">' + res.rows.map(function (r) { return "<strong>" + r.algo.name + ".</strong> " + r.algo.note; }).join(" ") +
      " In this run the leaky bucket's longest queueing delay was about " + Math.round(leaky.worstDelay) + " ms.</p>";
    window.__lrRes = res;
    updateCursor();
  }

  function updateCursor() {
    var res = window.__lrRes, i;
    tOut.textContent = (cursor / 1000).toFixed(1) + " s";
    cursorLines.forEach(function (c) { c.setAttribute("x1", x(cursor)); c.setAttribute("x2", x(cursor)); });
    res.rows.forEach(function (r) {
      var a = 0, b = 0;
      for (i = 0; i < res.ts.length && res.ts[i] <= cursor; i++) { if (r.ok[i]) a++; else b++; }
      var node = lanes.querySelector('[data-count="' + r.algo.id + '"]');
      if (node) node.textContent = a + " admitted, " + b + " rejected so far";
    });
  }

  sel.addEventListener("change", function () { presetKey = sel.value; render(); });
  lim.addEventListener("change", function () {
    var v = parseInt(lim.value, 10);
    if (!(v >= 2)) v = 2; if (v > 50) v = 50;
    L = v; lim.value = String(v); render();
  });
  slider.addEventListener("input", function () { cursor = parseInt(slider.value, 10); updateCursor(); });

  render();
})();
