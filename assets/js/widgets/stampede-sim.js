/* Cache stampede simulator (data chapter 14).

   Model (deterministic, simulated clock, tick = 0.1 s, horizon = 60 s):
   - K hot keys are all warmed at t = 0, each with a TTL. Requests arrive at a constant total
     rate, spread evenly over the keys (fractional arrivals are carried between ticks).
   - A fresh key is a hit. An expired key is a miss. Rebuilding a value takes REGEN seconds
     on an idle database, plus the time the database needs to drain its backlog.
   - The database is a fluid queue: capacity C queries per second; the backlog is the number
     of queries issued but not yet served.
   - No protection: every request that finds the key expired issues its own database query,
     until the first rebuild finishes and the key is filled again.
   - Single-flight: the first miss starts one rebuild; the other requests wait for it.
   - Serve stale: the first miss starts one rebuild; everyone is answered instantly with the
     old value in the meantime.
   - Jittered TTL: each fill gets a TTL of +-20% around the nominal one.
   - Early refresh: a fresh key is rebuilt in the background when a request draws
     -REGEN * ln(u) >= time left until expiry (the XFetch rule: the closer to expiry, the likelier).
   Not modelled: DB timeouts and retries (which make real stampedes worse), network latency,
   cache eviction, and the different cost of different queries. */
(function () {
  "use strict";
  var root = document.getElementById("stampede-sim");
  if (!root) return;

  var NS = "http://www.w3.org/2000/svg";
  var DT = 0.1, HORIZON = 60, BUCKET = 0.5, TPB = Math.round(BUCKET / DT), REGEN = 1.0;
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  /* ---------- pure simulation ---------- */
  function simulate(p) {
    var rng = mulberry32(7);
    var keys = [], i;
    function ttlFor() { return p.jitter ? p.ttl * (0.8 + 0.4 * rng()) : p.ttl; }
    for (i = 0; i < p.keys; i++) keys.push({ expires: ttlFor(), done: -1, carry: 0 });
    var backlog = 0, nTicks = Math.round(HORIZON / DT);
    var q = new Array(nTicks), slow = new Array(nTicks), misses = new Array(nTicks), blog = new Array(nTicks);
    var worstWait = 0;
    for (var k = 0; k < nTicks; k++) {
      var t = k * DT, queries = 0, slowReq = 0, missReq = 0;
      for (i = 0; i < keys.length; i++) {
        var key = keys[i];
        if (key.done >= 0 && t >= key.done - 1e-9) { key.expires = t + ttlFor(); key.done = -1; }
        key.carry += p.rate / p.keys * DT;
        var n = Math.floor(key.carry + 1e-9); key.carry -= n;
        function startRefresh() {
          key.done = t + REGEN + backlog / p.cap;
          queries += 1; backlog += 1;
        }
        if (t < key.expires - 1e-9) {                      /* fresh: hit */
          if (p.early && key.done < 0) {
            for (var r = 0; r < n; r++) {
              if (-REGEN * Math.log(1 - rng()) >= key.expires - t) { startRefresh(); break; }
            }
          }
        } else if (n > 0 || key.done >= 0) {                /* expired */
          if (p.stale) {
            if (key.done < 0) startRefresh();
          } else if (p.single) {
            if (key.done < 0) startRefresh();
            if (n > 0) { missReq += n; slowReq += n; worstWait = Math.max(worstWait, key.done - t); }
          } else {
            if (n > 0) {
              if (key.done < 0) key.done = t + REGEN + backlog / p.cap;
              queries += n; backlog += n; missReq += n; slowReq += n;
              worstWait = Math.max(worstWait, key.done - t);
            }
          }
        }
      }
      backlog = Math.max(0, backlog - p.cap * DT);
      q[k] = queries; slow[k] = slowReq; misses[k] = missReq; blog[k] = backlog;
    }
    /* aggregate into 0.5 s buckets: queries per second */
    var nb = HORIZON / BUCKET, load = [], bq = [], b;
    for (b = 0; b < nb; b++) {
      var s = 0, m = 0;
      for (var j = 0; j < TPB; j++) { s += q[b * TPB + j]; m = Math.max(m, blog[b * TPB + j]); }
      load.push(s / BUCKET); bq.push(m);
    }
    return { load: load, backlog: bq, q: q, slow: slow, misses: misses, blog: blog, worstWait: worstWait, nb: nb };
  }

  /* ---------- UI ---------- */
  function $(sel) { return root.querySelector(sel); }
  var inRate = $("[data-in=rate]"), inTtl = $("[data-in=ttl]"), inKeys = $("[data-in=keys]"), inCap = $("[data-in=cap]");
  var outRate = $("[data-out=rate]"), outTtl = $("[data-out=ttl]"), outKeys = $("[data-out=keys]"), outCap = $("[data-out=cap]");
  var cbSingle = $("[data-tog=single]"), cbJitter = $("[data-tog=jitter]"), cbEarly = $("[data-tog=early]"), cbStale = $("[data-tog=stale]");
  var playBtn = $("[data-act=play]"), stepBtn = $("[data-act=step]"), endBtn = $("[data-act=end]"), resetBtn = $("[data-act=reset]");
  var svg = $(".ss-chart"), verdict = $(".ss-verdict"), clockEl = $(".ss-clock");
  var stat = {};
  Array.prototype.forEach.call(root.querySelectorAll("[data-stat]"), function (e) { stat[e.getAttribute("data-stat")] = e; });

  var res = null, params = null, tNow = HORIZON, running = false, raf = 0, lastTs = 0;

  function read() {
    return { rate: +inRate.value, ttl: +inTtl.value, keys: +inKeys.value, cap: +inCap.value,
      single: cbSingle.checked, jitter: cbJitter.checked, early: cbEarly.checked, stale: cbStale.checked };
  }
  function el(tag, attrs, text) {
    var e = document.createElementNS(NS, tag);
    for (var a in attrs) e.setAttribute(a, attrs[a]);
    if (text !== undefined) e.textContent = text;
    return e;
  }

  function draw() {
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    var W = 640, H = 230, L = 52, R = 12, T = 16, B = 40, pw = W - L - R, ph = H - T - B;
    var shown = Math.min(res.nb, Math.floor(tNow / BUCKET + 1e-9));
    var maxV = params.cap * 1.25, i;
    for (i = 0; i < res.nb; i++) if (res.load[i] > maxV) maxV = res.load[i];
    maxV = Math.ceil(maxV / 50) * 50;
    function y(v) { return T + ph - v / maxV * ph; }
    svg.appendChild(el("line", { x1: L, y1: T + ph, x2: W - R, y2: T + ph, "class": "line-thin" }));
    svg.appendChild(el("line", { x1: L, y1: T, x2: L, y2: T + ph, "class": "line-thin" }));
    svg.appendChild(el("text", { x: L - 6, y: T + 10, "text-anchor": "end", "class": "t-xs t-faint" }, String(maxV)));
    svg.appendChild(el("text", { x: L - 6, y: T + ph, "text-anchor": "end", "class": "t-xs t-faint" }, "0"));
    svg.appendChild(el("text", { x: L, y: T + ph + 16, "class": "t-xs t-faint" }, "0 s"));
    svg.appendChild(el("text", { x: W - R, y: T + ph + 16, "text-anchor": "end", "class": "t-xs t-faint" }, HORIZON + " s"));
    svg.appendChild(el("text", { x: L + pw / 2, y: H - 6, "text-anchor": "middle", "class": "t-xs t-muted" }, "database queries per second (0.5 s buckets)"));
    var bw = pw / res.nb;
    for (i = 0; i < shown; i++) {
      var v = res.load[i];
      if (v <= 0) continue;
      var x = L + i * bw, under = Math.min(v, params.cap);
      svg.appendChild(el("rect", { x: x.toFixed(1), y: y(under).toFixed(1), width: Math.max(1, bw - 0.6).toFixed(1), height: (T + ph - y(under)).toFixed(1), "class": "f-blue" }));
      if (v > params.cap) svg.appendChild(el("rect", { x: x.toFixed(1), y: y(v).toFixed(1), width: Math.max(1, bw - 0.6).toFixed(1), height: (y(params.cap) - y(v)).toFixed(1), "class": "f-red" }));
    }
    svg.appendChild(el("line", { x1: L, y1: y(params.cap), x2: W - R, y2: y(params.cap), "class": "line-dash s-yellow" }));
    svg.appendChild(el("text", { x: W - R - 4, y: y(params.cap) - 5, "text-anchor": "end", "class": "t-xs tc-yellow t-bold" }, "DB capacity " + params.cap + "/s"));
    if (shown < res.nb) svg.appendChild(el("line", { x1: L + shown * bw, y1: T, x2: L + shown * bw, y2: T + ph, "class": "line-thin" }));
    svg.setAttribute("aria-label", "Bar chart of database queries per second over 60 simulated seconds. Peak so far " +
      Math.round(peak(shown)) + " per second against a capacity of " + params.cap + ".");
  }
  function peak(shown) { var m = 0; for (var i = 0; i < shown; i++) if (res.load[i] > m) m = res.load[i]; return m; }

  function fmt(n) { return String(Math.round(n)); }
  function update() {
    var ticks = Math.min(res.q.length, Math.round(tNow / DT));
    var total = 0, slow = 0, miss = 0, maxBl = 0, over = 0, i;
    for (i = 0; i < ticks; i++) { total += res.q[i]; slow += res.slow[i]; miss += res.misses[i]; if (res.blog[i] > maxBl) maxBl = res.blog[i]; }
    var shown = Math.min(res.nb, Math.floor(tNow / BUCKET + 1e-9)), pk = peak(shown);
    for (i = 0; i < shown; i++) if (res.load[i] > params.cap) over += BUCKET;
    var arrivals = params.rate * tNow;
    clockEl.textContent = "t = " + tNow.toFixed(1) + " s";
    stat.peak.textContent = fmt(pk) + " /s";
    stat.total.textContent = fmt(total);
    stat.over.textContent = over.toFixed(1) + " s";
    stat.backlog.textContent = fmt(maxBl);
    stat.slow.textContent = fmt(slow) + (arrivals > 0 ? " (" + (slow / arrivals * 100).toFixed(1) + "%)" : "");
    var v, cls;
    if (tNow < 1) { v = "Press Run (or Jump to end) to watch the keys expire."; cls = ""; }
    else if (pk > params.cap) {
      v = "Stampede: at expiry the database was asked for " + fmt(pk) + " queries per second but can serve only " + params.cap +
        ". The excess queues up (peak backlog " + fmt(maxBl) + " queries, so rebuilds and requests take longer and longer).";
      cls = "bad";
    } else if (slow > 0) {
      v = "The database is safe: the peak stays under its capacity. But " + fmt(slow) + " requests had to wait for a rebuild (worst wait about " +
        res.worstWait.toFixed(1) + " s). Serve-stale or early refresh would hide that wait.";
      cls = "warn";
    } else {
      v = "Flat: no request waited on the database, and the load is just one rebuild per key per TTL.";
      cls = "ok";
    }
    verdict.textContent = v;
    verdict.className = "ss-verdict " + cls;
    draw();
  }

  function recompute(keepTime) {
    params = read();
    outRate.textContent = params.rate + " req/s";
    outTtl.textContent = params.ttl + " s";
    outKeys.textContent = String(params.keys);
    outCap.textContent = params.cap + " q/s";
    res = simulate(params);
    if (!keepTime) tNow = HORIZON;
    update();
  }
  function stop() {
    running = false;
    verdict.setAttribute("aria-live", "polite");
    if (raf) { cancelAnimationFrame(raf); raf = 0; }
    playBtn.textContent = "Run";
    playBtn.setAttribute("aria-pressed", "false");
  }
  function frame(ts) {
    if (!running) return;
    tNow = Math.min(HORIZON, tNow + Math.min(0.1, (ts - lastTs) / 1000) * 8);
    lastTs = ts;
    update();
    if (tNow >= HORIZON) { stop(); return; }
    raf = requestAnimationFrame(frame);
  }
  function play() {
    if (reduce) { stop(); tNow = HORIZON; update(); return; }
    if (tNow >= HORIZON) tNow = 0;
    running = true;
    verdict.setAttribute("aria-live", "off");
    playBtn.textContent = "Pause";
    playBtn.setAttribute("aria-pressed", "true");
    lastTs = performance.now();
    raf = requestAnimationFrame(frame);
  }

  [inRate, inTtl, inKeys, inCap, cbSingle, cbJitter, cbEarly, cbStale].forEach(function (c) {
    c.addEventListener("input", function () { recompute(true); });
    c.addEventListener("change", function () { recompute(true); });
  });
  playBtn.addEventListener("click", function () { if (running) stop(); else play(); });
  stepBtn.addEventListener("click", function () { stop(); tNow = Math.min(HORIZON, Math.floor(tNow / 5) * 5 + 5); update(); });
  endBtn.addEventListener("click", function () { stop(); tNow = HORIZON; update(); });
  resetBtn.addEventListener("click", function () { stop(); tNow = 0; update(); });

  recompute(false);
})();
