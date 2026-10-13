/* Cache simulator (systems chapter 2).
   Memory: 64 cells in 16 cache lines of 4 cells. Cache: a few lines, fully
   associative, least-recently-used (LRU) eviction. The user picks an access
   pattern and steps or plays it. Each access is a hit (line already in the
   cache, illustrative cost 1 ns) or a miss (line fetched from RAM, 100 ns).
   All DOM text is set with textContent. No libraries, no storage. */
(function () {
  "use strict";
  var root = document.getElementById("cache-sim");
  if (!root) return;

  var LINE = 4, LINES = 16, CELLS = LINE * LINES;
  var HIT_NS = 1, MISS_NS = 100, PLAY_MS = 450, PLAY_MAX = 128, STRIP_MAX = 64;
  var SMALL_SET = [0, 5, 9, 1, 10, 4, 2, 8]; // touches lines 0, 1, 2 only

  var PATTERNS = {
    seq:    function (i) { return i % CELLS; },
    stride: function (i) { return (i * LINE) % CELLS; },
    random: function (i, rng) { return Math.floor(rng() * CELLS); },
    small:  function (i) { return SMALL_SET[i % SMALL_SET.length]; }
  };

  function q(act) { return root.querySelector('[data-act="' + act + '"]'); }
  var patSel = q("pattern"), sizeSel = q("size");
  var stepBtn = q("step"), playBtn = q("play"), runBtn = q("run64"), resetBtn = q("reset");
  var memEl = q("mem"), cacheEl = q("cache"), stripEl = q("strip");
  var logEl = q("log"), statsEl = q("stats");

  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }

  var st, timer = null, cellEls = [], lineEls = [], slotEls = [], playedThisRun = 0;

  /* ---- build the static memory grid once ---- */
  function buildMemory() {
    memEl.textContent = "";
    cellEls = []; lineEls = [];
    for (var l = 0; l < LINES; l++) {
      var box = el("div", "cs-line");
      box.appendChild(el("span", "cs-line-tag", "line " + l));
      var row = el("div", "cs-cells");
      for (var c = 0; c < LINE; c++) {
        var addr = l * LINE + c;
        var cell = el("span", "cs-cell", String(addr));
        row.appendChild(cell);
        cellEls[addr] = cell;
      }
      box.appendChild(row);
      memEl.appendChild(box);
      lineEls[l] = box;
    }
  }

  function buildCache() {
    cacheEl.textContent = "";
    slotEls = [];
    for (var s = 0; s < st.size; s++) {
      var slot = el("div", "cs-slot");
      var name = el("span", "cs-slot-name", "slot " + s);
      var val = el("span", "cs-slot-val", "empty");
      var tag = el("span", "cs-slot-tag", "");
      slot.appendChild(name); slot.appendChild(val); slot.appendChild(tag);
      cacheEl.appendChild(slot);
      slotEls.push({ box: slot, val: val, tag: tag });
    }
  }

  function reset() {
    stop();
    st = {
      size: parseInt(sizeSel.value, 10),
      n: 0, hits: 0, misses: 0,
      slots: [], // {line, used}
      cur: -1, rng: mulberry32(2024), pat: patSel.value
    };
    for (var i = 0; i < st.size; i++) st.slots.push({ line: -1, used: 0 });
    stripEl.textContent = "";
    logEl.textContent = "Press Step to make the first memory access.";
    buildCache();
    render();
  }

  function findSlot(line) {
    for (var i = 0; i < st.slots.length; i++) if (st.slots[i].line === line) return i;
    return -1;
  }

  function access() {
    var addr = PATTERNS[st.pat](st.n, st.rng);
    var line = Math.floor(addr / LINE);
    st.n++;
    st.cur = addr;
    var idx = findSlot(line), msg;
    if (idx >= 0) {
      st.hits++;
      st.slots[idx].used = st.n;
      msg = "Access " + st.n + ": cell " + addr + " (line " + line + "). HIT: line " + line + " was already in the cache. Cost 1 ns.";
      addStrip(true);
    } else {
      st.misses++;
      var victim = -1, i;
      for (i = 0; i < st.slots.length; i++) if (st.slots[i].line === -1) { victim = i; break; }
      var evicted = -1;
      if (victim < 0) {
        victim = 0;
        for (i = 1; i < st.slots.length; i++) if (st.slots[i].used < st.slots[victim].used) victim = i;
        evicted = st.slots[victim].line;
      }
      st.slots[victim].line = line;
      st.slots[victim].used = st.n;
      msg = "Access " + st.n + ": cell " + addr + " (line " + line + "). MISS: fetched line " + line + " from RAM into slot " + victim +
        (evicted >= 0 ? ", evicting least-recently-used line " + evicted : "") + ". Cost 100 ns.";
      addStrip(false);
    }
    logEl.textContent = msg;
    render();
  }

  function addStrip(hit) {
    var s = el("span", "cs-tick " + (hit ? "hit" : "miss"));
    s.title = hit ? "hit" : "miss";
    stripEl.appendChild(s);
    while (stripEl.childNodes.length > STRIP_MAX) stripEl.removeChild(stripEl.firstChild);
  }

  function render() {
    var inCache = {}, i;
    for (i = 0; i < st.slots.length; i++) if (st.slots[i].line >= 0) inCache[st.slots[i].line] = true;
    for (i = 0; i < LINES; i++) lineEls[i].className = "cs-line" + (inCache[i] ? " cached" : "");
    for (i = 0; i < CELLS; i++) cellEls[i].className = "cs-cell" + (i === st.cur ? " cur" : "");

    var lru = -1;
    var full = st.slots.every(function (s) { return s.line >= 0; });
    if (full) {
      lru = 0;
      for (i = 1; i < st.slots.length; i++) if (st.slots[i].used < st.slots[lru].used) lru = i;
    }
    for (i = 0; i < slotEls.length; i++) {
      var s = st.slots[i], v = slotEls[i];
      v.val.textContent = s.line >= 0 ? "line " + s.line : "empty";
      v.tag.textContent = (i === lru) ? "next to evict" : (s.line >= 0 && s.used === st.n ? "just used" : "");
      v.box.className = "cs-slot" + (s.line >= 0 ? " full" : "") + (i === lru ? " lru" : "");
    }

    var total = st.hits * HIT_NS + st.misses * MISS_NS;
    var rate = st.n ? Math.round((st.hits / st.n) * 1000) / 10 : 0;
    var noCache = st.n * MISS_NS;
    var avg = st.n ? (total / st.n).toFixed(1) : "0";
    statsEl.textContent = "";
    var items = [
      ["Hits", String(st.hits)],
      ["Misses", String(st.misses)],
      ["Hit rate", rate.toFixed(1) + "%"],
      ["Total time", total + " ns"],
      ["Average", avg + " ns/access"],
      ["If every access went to RAM", noCache + " ns"]
    ];
    items.forEach(function (it) {
      var d = el("div", "cs-stat");
      d.appendChild(el("span", "cs-stat-k", it[0]));
      d.appendChild(el("span", "cs-stat-v", it[1]));
      statsEl.appendChild(d);
    });
  }

  /* ---- playback ---- */
  function stop() {
    if (timer) { clearInterval(timer); timer = null; }
    if (playBtn) playBtn.textContent = "Play";
  }
  function play() {
    if (timer) { stop(); return; }
    playedThisRun = 0;
    playBtn.textContent = "Pause";
    timer = setInterval(function () {
      access();
      playedThisRun++;
      if (playedThisRun >= PLAY_MAX) { stop(); logEl.textContent += " (Stopped after " + PLAY_MAX + " accesses. Reset to start over.)"; }
    }, PLAY_MS);
  }

  stepBtn.addEventListener("click", function () { stop(); access(); });
  playBtn.addEventListener("click", play);
  runBtn.addEventListener("click", function () {
    stop();
    for (var i = 0; i < 64; i++) access();
    logEl.textContent = "Ran 64 accesses. " + st.hits + " hits, " + st.misses + " misses so far. Look at the strip: green = hit, red = miss.";
  });
  resetBtn.addEventListener("click", reset);
  patSel.addEventListener("change", reset);
  sizeSel.addEventListener("change", reset);

  buildMemory();
  reset();
})();
