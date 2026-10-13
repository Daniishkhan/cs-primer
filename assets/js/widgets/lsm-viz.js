/* LSM tree visualiser (data chapter 5).

   - Put/Delete go to a WAL (just a byte counter here) and into a sorted
     memtable. When the memtable holds LIMIT distinct keys it is flushed as a
     new immutable, sorted L0 SSTable with its own Bloom filter, and the WAL
     is discarded.
   - Get checks the memtable, then the SSTables newest to oldest. For each
     file it asks the Bloom filter first: "definitely not here" skips the
     file; "maybe here" costs one file read, which may still be a false
     positive. The first hit (value or tombstone) ends the search.
   - Compact merges every SSTable into one L1 run: newest value per key wins;
     overwritten values and tombstones are dropped. (Full merge, so dropping
     tombstones is safe.)
   - Counters: write amplification = (WAL + flush + compaction bytes) / user
     bytes; read amplification = files read per get.
   The Bloom filters are deliberately small (6 bits per key, 2 hashes, about
   8% false positives) so that you can actually see a false positive.
   Everything is deterministic: "Random 5" cycles a fixed pseudo-random
   sequence. */
(function () {
  "use strict";
  var root = document.getElementById("lsm-viz");
  if (!root) return;

  var POOL = ["ant", "bee", "cat", "dog", "eel", "fox", "gnu", "hen", "ibis", "jay", "kiwi", "lynx"];
  var BITS_PER_KEY = 6, MIN_BITS = 24, HASHES = 2;
  var S;

  function fresh(limit) {
    return { limit: limit || 4, mem: new Map(), walRecs: 0, walCur: 0, ssts: [], nextId: 1, rng: 12345, ctr: 0,
             userB: 0, walB: 0, flushB: 0, compB: 0, gets: 0, filesRead: 0, last: null, trace: null, out: [] };
  }
  S = fresh(4);

  root.className = "widget";
  root.innerHTML =
    '<div class="widget-head"><span class="widget-tag">Interactive</span><h4 class="widget-title">LSM tree: memtable, SSTables and Bloom filters</h4></div>' +
    '<p class="widget-help">Put keys until the memtable fills and flushes to an SSTable. Then Get a key and read the trace: which Bloom filters said “definitely not here”, and which files were really read. Try Get on a key that does not exist, then Compact.</p>' +
    '<form class="lv-form" data-role="form" autocomplete="off">' +
    '<label class="lv-field"><span>Key</span><input type="text" class="mono" data-role="key" maxlength="10" value="cat" spellcheck="false"></label>' +
    '<label class="lv-field"><span>Value</span><input type="text" class="mono" data-role="val" maxlength="10" value="v1" spellcheck="false"></label>' +
    '<button type="submit" class="btn small primary">Put</button>' +
    '<button type="button" class="btn small" data-act="get">Get</button>' +
    '<button type="button" class="btn small" data-act="del">Delete</button></form>' +
    '<div class="lv-tools" role="group" aria-label="Actions">' +
    '<button type="button" class="btn small" data-act="rand">Random 5</button>' +
    '<button type="button" class="btn small" data-act="flush">Flush memtable</button>' +
    '<button type="button" class="btn small" data-act="compact">Compact</button>' +
    '<button type="button" class="btn small" data-act="reset">Reset</button>' +
    '<label class="lv-size">Memtable holds <select data-role="limit" aria-label="Memtable size in keys"><option>3</option><option selected>4</option><option>6</option></select> keys</label></div>' +
    '<div class="lv-stats" data-role="stats"></div>' +
    '<div class="lv-card mem"><h5>Memtable (RAM, sorted)</h5><div class="lv-chips" data-role="mem"></div><p class="lv-wal" data-role="wal"></p></div>' +
    '<div><div class="lv-runs" data-role="runs"></div></div>' +
    '<div class="widget-out lv-out" data-role="out" aria-live="polite"></div>';

  function q(role) { return root.querySelector('[data-role="' + role + '"]'); }
  var keyIn = q("key"), valIn = q("val"), limitSel = q("limit");
  var elStats = q("stats"), elMem = q("mem"), elWal = q("wal"), elRuns = q("runs"), elOut = q("out");

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function bytes(s) {
    try { return new TextEncoder().encode(s).length; } catch (e) { return s.length; }
  }
  function entryBytes(k, e) { return bytes(k) + (e.del ? 1 : bytes(e.v)); }
  function clean(s) { return (s || "").replace(/^\s+|\s+$/g, ""); }

  /* ---- Bloom filter ---- */
  function fnv(str, seed) {
    var h = (2166136261 ^ seed) >>> 0;
    for (var i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 16777619) >>> 0; }
    return h >>> 0;
  }
  function positions(key, m) {
    var h1 = fnv(key, 0), h2 = fnv(key, 40503) | 1, out = [];
    for (var i = 0; i < HASHES; i++) out.push((h1 + i * h2) % m);
    return out;
  }
  function makeBloom(entries) {
    var m = Math.max(MIN_BITS, BITS_PER_KEY * entries.length), bits = [];
    for (var i = 0; i < m; i++) bits.push(0);
    entries.forEach(function (e) { positions(e.k, m).forEach(function (p) { bits[p] = 1; }); });
    return bits;
  }

  /* ---- messages ---- */
  function say(paras) { S.out = paras; }
  function drawOut() {
    elOut.textContent = "";
    S.out.forEach(function (item) {
      if (item.list) {
        var ol = el("ol");
        item.list.forEach(function (parts) { var li = el("li"); fill(li, parts); ol.appendChild(li); });
        elOut.appendChild(ol);
      } else { var p = el("p"); fill(p, item); elOut.appendChild(p); }
    });
  }
  function fill(node, parts) {
    parts.forEach(function (x) {
      if (typeof x === "string") node.appendChild(document.createTextNode(x));
      else node.appendChild(el(x[0] === "b" ? "strong" : "code", null, x[1]));
    });
  }

  /* ---- rendering ---- */
  function writeAmp() { return S.userB ? (S.walB + S.flushB + S.compB) / S.userB : 0; }

  function drawStats() {
    var wa = writeAmp(), total = S.walB + S.flushB + S.compB;
    var items = [
      ["User data written", S.userB + " B", "what the app asked to store"],
      ["Disk bytes written", total + " B", "WAL " + S.walB + " + flush " + S.flushB + " + compaction " + S.compB],
      ["Write amplification", S.userB ? wa.toFixed(2) + "×" : "–", "disk ÷ user bytes"],
      ["Files read, last get", S.last == null ? "–" : String(S.last), "read amplification"],
      ["Average per get", S.gets ? (S.filesRead / S.gets).toFixed(2) : "–", S.gets + " get" + (S.gets === 1 ? "" : "s") + " so far"]
    ];
    elStats.textContent = "";
    items.forEach(function (it) {
      var d = el("div", "lv-stat");
      d.appendChild(el("small", null, it[0]));
      d.appendChild(el("b", null, it[1]));
      d.appendChild(el("span", null, it[2]));
      elStats.appendChild(d);
    });
  }

  function drawMem() {
    elMem.textContent = "";
    var keys = Array.from(S.mem.keys()).sort();
    if (!keys.length) elMem.appendChild(el("span", "lv-note", "(empty)"));
    keys.forEach(function (k) {
      var e = S.mem.get(k);
      var c = el("span", "lv-chip" + (e.del ? " tomb" : "") + (S.trace && S.trace.memHit === k ? " hit" : ""), e.del ? k + " ✕" : k + "=" + e.v);
      elMem.appendChild(c);
    });
    elWal.textContent = "WAL on disk: " + S.walRecs + " record" + (S.walRecs === 1 ? "" : "s") + " (" + S.walCur + " B since the last flush)" +
      " · memtable " + S.mem.size + " / " + S.limit + " keys";
  }

  function drawRuns() {
    elRuns.textContent = "";
    if (!S.ssts.length) { elRuns.appendChild(el("p", "lv-note", "No SSTables yet. Put " + S.limit + " different keys and the memtable will flush to the first one.")); return; }
    S.ssts.forEach(function (sst) {
      var tr = S.trace && S.trace.per[sst.id];
      var cls = "lv-sst";
      if (S.trace) cls += tr ? " " + tr.state : " off";
      var card = el("div", cls);
      card.setAttribute("role", "group");
      card.setAttribute("aria-label", "SSTable " + sst.id);
      var head = el("div", "lv-sst-head");
      head.appendChild(el("span", null, "SSTable #" + sst.id));
      head.appendChild(el("span", "pill " + (sst.level === 0 ? "" : "green"), "L" + sst.level));
      head.appendChild(el("span", "pill", sst.entries.length + " keys"));
      head.appendChild(el("span", "pill", sst.size + " B"));
      card.appendChild(head);
      var chips = el("div", "lv-chips");
      sst.entries.forEach(function (e) {
        chips.appendChild(el("span", "lv-chip" + (e.del ? " tomb" : "") + (tr && tr.state === "hit" && tr.hitKey === e.k ? " hit" : ""), e.del ? e.k + " ✕" : e.k + "=" + e.v));
      });
      card.appendChild(chips);
      var bl = el("div", "lv-bloom");
      bl.appendChild(el("small", null, "Bloom"));
      bl.setAttribute("aria-hidden", "true");
      sst.bloom.forEach(function (b, i) {
        var c = "lv-bit" + (b ? " on" : "");
        if (tr && tr.probes && tr.probes.indexOf(i) >= 0) c += b ? " p1" : " p0";
        bl.appendChild(el("span", c));
      });
      card.appendChild(bl);
      if (tr) {
        var v = el("div", "lv-verdict " + (tr.bloomNo ? "no" : "maybe"),
          tr.bloomNo ? "Bloom: definitely not here. Skipped, no read." :
          tr.state === "hit" ? "Bloom: maybe here. File read: found it." : "Bloom: maybe here. File read: not there (false positive).");
        card.appendChild(v);
      }
      elRuns.appendChild(card);
    });
  }

  function render() { drawStats(); drawMem(); drawRuns(); drawOut(); }

  /* ---- engine ---- */
  function flush(events) {
    if (!S.mem.size) return;
    var entries = Array.from(S.mem.keys()).sort().map(function (k) { var e = S.mem.get(k); return { k: k, v: e.v, del: !!e.del }; });
    var size = entries.reduce(function (n, e) { return n + entryBytes(e.k, e); }, 0);
    var sst = { id: S.nextId++, level: 0, entries: entries, size: size, bloom: makeBloom(entries) };
    S.ssts.unshift(sst);                 // newest first
    S.flushB += size;
    S.mem = new Map(); S.walRecs = 0; S.walCur = 0;   // WAL file is discarded; bytes already written stay counted in walB
    if (events) events.push("flushed the memtable to SSTable #" + sst.id + " (" + entries.length + " sorted keys, " + size + " B)");
  }

  function put(k, v, del, events) {
    var e = { v: v, del: !!del };
    var b = entryBytes(k, e);
    S.userB += b; S.walB += b; S.walCur += b; S.walRecs++;
    S.mem.set(k, e);
    if (S.mem.size >= S.limit) flush(events);
  }

  function doPut(k, v) {
    if (!k) { say([["Type a key first."]]); return; }
    S.trace = null;
    var ev = [];
    put(k, v, false, ev);
    var m = [[["c", "put " + k + "=" + v], " went into the WAL (sequential append) and the sorted memtable."]];
    if (ev.length) m.push(["The memtable was full, so it " + ev.join("; ") + ". The WAL for it was discarded."]);
    say(m);
  }

  function doDel(k) {
    if (!k) { say([["Type a key first."]]); return; }
    S.trace = null;
    var ev = [];
    put(k, "", true, ev);
    var m = [[["c", "delete " + k], " wrote a tombstone, not an erase. The old values in older files are still there, hidden by it."]];
    if (ev.length) m.push(["The memtable was full, so it " + ev.join("; ") + "."]);
    say(m);
  }

  function doRand() {
    S.trace = null;
    var ev = [], keys = [];
    for (var i = 0; i < 5; i++) {
      S.rng = (Math.imul(S.rng, 1103515245) + 12345) & 0x7fffffff;
      var k = POOL[(S.rng >>> 16) % POOL.length];
      S.ctr++;
      put(k, "v" + S.ctr, false, ev);
      keys.push(k + "=v" + S.ctr);
    }
    var m = [["Inserted five random keys: ", ["c", keys.join("  ")]]];
    if (ev.length) m.push(["Along the way it " + ev.join("; and ") + "."]);
    m.push(["Keys come from a fixed pool of 12 animal names, so a repeat means an overwrite."]);
    say(m);
  }

  function doFlush() {
    S.trace = null;
    if (!S.mem.size) { say([["The memtable is empty, nothing to flush."]]); return; }
    var ev = [];
    flush(ev);
    say([["Forced a flush: it " + ev[0] + "."]]);
  }

  function lookup(sst, k) {
    for (var i = 0; i < sst.entries.length; i++) if (sst.entries[i].k === k) return sst.entries[i];
    return null;
  }

  function doGet(k) {
    if (!k) { say([["Type a key first."]]); S.trace = null; return; }
    var list = [], per = {}, reads = 0, result = null, memHit = null, done = false;
    if (S.mem.has(k)) {
      var me = S.mem.get(k);
      memHit = k; done = true;
      list.push([["b", "Memtable: "], me.del ? "found a tombstone, so the key is deleted. Stop." : "found " + me.v + ". Stop. No file was touched."]);
      result = me.del ? "deleted" : me.v;
    } else {
      list.push([["b", "Memtable: "], "not there."]);
    }
    S.ssts.forEach(function (sst) {
      if (done) return;
      var pos = positions(k, sst.bloom.length);
      var maybe = pos.every(function (p) { return sst.bloom[p] === 1; });
      var name = "SSTable #" + sst.id;
      if (!maybe) {
        per[sst.id] = { state: "skip", bloomNo: true, probes: pos };
        list.push([["b", name + ": "], "Bloom filter says definitely not here. Skipped, no disk read."]);
        return;
      }
      reads++;
      var e = lookup(sst, k);
      if (e) {
        per[sst.id] = { state: "hit", bloomNo: false, probes: pos, hitKey: k };
        list.push([["b", name + ": "], "Bloom says maybe, so read the file (read " + reads + "): " + (e.del ? "found a tombstone, the key is deleted. Stop." : "found " + e.v + ". Stop.")]);
        result = e.del ? "deleted" : e.v; done = true;
      } else {
        per[sst.id] = { state: "fp", bloomNo: false, probes: pos };
        list.push([["b", name + ": "], "Bloom says maybe, so read the file (read " + reads + "): not there. A false positive, one wasted read."]);
      }
    });
    if (!done) list.push([["b", "Result: "], "not found anywhere."]);
    S.trace = { per: per, memHit: memHit };
    S.gets++; S.filesRead += reads; S.last = reads;
    var head = [["c", "get " + k], " → ", ["b", result === null ? "not found" : result === "deleted" ? "deleted (tombstone)" : result], ". Files read from disk: ", ["b", String(reads)], "."];
    say([head, { list: list }]);
  }

  function doCompact() {
    S.trace = null;
    if (S.ssts.length < 2) { say([["Nothing to merge: compaction needs at least two SSTables. Fill the memtable a few more times."]]); return; }
    var total = 0, merged = new Map();
    for (var i = S.ssts.length - 1; i >= 0; i--) {       // oldest first, newer overwrite
      S.ssts[i].entries.forEach(function (e) { total++; merged.set(e.k, e); });
    }
    var uniq = merged.size, out = [];
    Array.from(merged.keys()).sort().forEach(function (k) { var e = merged.get(k); if (!e.del) out.push(e); });
    var overwritten = total - uniq, tombs = uniq - out.length;
    var runs = S.ssts.length;
    var size = out.reduce(function (n, e) { return n + entryBytes(e.k, e); }, 0);
    S.compB += size;
    if (out.length) S.ssts = [{ id: S.nextId++, level: 1, entries: out, size: size, bloom: makeBloom(out) }];
    else S.ssts = [];
    say([
      [["b", "Compacted "], runs + " SSTables (" + total + " entries) into " + (out.length ? "one L1 run (" + out.length + " keys, " + size + " B)" : "nothing") + "."],
      ["It was a merge of sorted lists: for each key the newest version won. Dropped " + overwritten + " overwritten value" + (overwritten === 1 ? "" : "s") + " and " + tombs + " tombstone" + (tombs === 1 ? "" : "s") + ". The " + size + " B rewrite counts toward write amplification, even though no user wrote anything."],
      ["Fewer files means fewer places for a get to look. Tombstones in the memtable (if any) still hide older data until they are flushed and merged."]
    ]);
  }

  function doReset() {
    S = fresh(parseInt(limitSel.value, 10) || 4);
    say([["Empty tree. Press ", ["c", "Random 5"], " a few times, then try a Get."]]);
  }

  root.addEventListener("click", function (ev) {
    var b = ev.target.closest ? ev.target.closest("button[data-act]") : null;
    if (!b) return;
    var act = b.getAttribute("data-act");
    if (act === "get") doGet(clean(keyIn.value));
    else if (act === "del") doDel(clean(keyIn.value));
    else if (act === "rand") doRand();
    else if (act === "flush") doFlush();
    else if (act === "compact") doCompact();
    else if (act === "reset") doReset();
    render();
  });
  q("form").addEventListener("submit", function (ev) {
    ev.preventDefault();
    doPut(clean(keyIn.value), valIn.value);
    render();
  });
  limitSel.addEventListener("change", function () { S.limit = parseInt(limitSel.value, 10) || 4; });

  doReset();
  render();
})();
