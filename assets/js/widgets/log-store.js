/* Log store (data chapter 4).

   A tiny Bitcask-style key-value store, drawn.
   - The log is a list of segments; each holds records in the order they were
     appended. A record is a set (key=value) or a tombstone (key, no value).
     When the active (last) segment reaches N records, it is sealed and a new
     one starts. Sealed segments are never modified.
   - The hash index maps key -> (segment, record number). A record is "live"
     when the index points at it; every other record is garbage.
   - get: look in the index (RAM), then one seek to the record.
   - Compact merges the sealed segments only (the active one is still being
     written): it copies the live records, drops stale ones and tombstones,
     and renumbers the segments.
   - Crash & recover: wipes the index and rebuilds it by scanning every
     segment from oldest to newest. Optionally the last record is torn by the
     crash; its checksum fails and it is discarded.
   Deterministic: no randomness. Counts are in records, not bytes. */
(function () {
  "use strict";
  var root = document.getElementById("log-store");
  if (!root) return;

  var reduce = !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  var MAX_RECORDS = 48;
  var PICKS = [
    { label: "set user:1 = Ada", op: "set", k: "user:1", v: "Ada" },
    { label: "set user:2 = Grace", op: "set", k: "user:2", v: "Grace" },
    { label: "set user:1 = Ada L.", op: "set", k: "user:1", v: "Ada L." },
    { label: "get user:1", op: "get", k: "user:1" },
    { label: "delete user:2", op: "del", k: "user:2" }
  ];
  var DEMO = [
    ["set", "user:1", "Ada"], ["set", "user:2", "Grace"], ["set", "user:1", "Ada L."], ["set", "user:3", "Alan"],
    ["set", "user:2", "Grace H."], ["del", "user:3"], ["set", "user:4", "Edsger"], ["set", "user:1", "Ada Lv."],
    ["set", "user:5", "Linus"], ["set", "user:4", "Ed"]
  ];

  var S, timers = [];

  function fresh(segMax) {
    return { segs: [], index: new Map(), nextId: 1, segMax: segMax || 4, busy: false, recovering: false,
             hl: null, scan: null, newKey: null, counters: null, out: [] };
  }
  S = fresh(4);

  root.className = "widget";
  root.innerHTML =
    '<div class="widget-head"><span class="widget-tag">Interactive</span><h4 class="widget-title">A log with a hash index</h4></div>' +
    '<p class="widget-help">Type a key and value, or use the quick picks. Watch records append to the log, the index point at the newest one, and old versions turn into garbage. Then compact, or crash the process and rebuild the index.</p>' +
    '<form class="lg-form" data-role="form" autocomplete="off">' +
    '<label class="lg-field"><span>Key</span><input type="text" class="mono" data-role="key" maxlength="12" value="user:1" spellcheck="false"></label>' +
    '<label class="lg-field"><span>Value</span><input type="text" class="mono" data-role="val" maxlength="14" value="Ada" spellcheck="false"></label>' +
    '<button type="submit" class="btn small primary" data-act="set">Set</button>' +
    '<button type="button" class="btn small" data-act="get">Get</button>' +
    '<button type="button" class="btn small" data-act="del">Delete</button></form>' +
    '<div><div class="lg-label">Quick picks</div><div class="lg-picks" data-role="picks" role="group" aria-label="Quick picks"></div></div>' +
    '<div class="lg-tools" role="group" aria-label="Maintenance">' +
    '<button type="button" class="btn small" data-act="demo">Load a demo log</button>' +
    '<button type="button" class="btn small" data-act="compact">Compact</button>' +
    '<button type="button" class="btn small danger" data-act="crash">Crash &amp; recover</button>' +
    '<button type="button" class="btn small" data-act="reset">Reset</button>' +
    '<label class="lg-size">Records per segment <select data-role="size" aria-label="Records per segment"><option>3</option><option selected>4</option><option>5</option><option>6</option></select></label></div>' +
    '<label class="lg-check"><input type="checkbox" data-role="tear"> The crash hits mid-append: the last record is torn</label>' +
    '<div class="lg-stats" data-role="stats"></div>' +
    '<div class="lg-panes"><div class="lg-pane disk"><h5>Log on disk (append-only segments)</h5><div data-role="segs"></div></div>' +
    '<div class="lg-pane idx"><h5>Hash index in RAM</h5><div data-role="index"></div></div></div>' +
    '<div class="widget-out lg-out" data-role="out" aria-live="polite"></div>';

  function q(role) { return root.querySelector('[data-role="' + role + '"]'); }
  var keyIn = q("key"), valIn = q("val"), tearBox = q("tear"), sizeSel = q("size");
  var elSegs = q("segs"), elIndex = q("index"), elStats = q("stats"), elOut = q("out"), elPicks = q("picks");

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function clearTimers() { timers.forEach(function (t) { clearTimeout(t); }); timers = []; }
  function later(fn, ms) { timers.push(setTimeout(fn, ms)); }

  /* messages: each paragraph is an array; a string is text, [kind, text] is <code> or <strong> */
  function say(paras) { S.out = paras; }
  function drawOut() {
    elOut.textContent = "";
    S.out.forEach(function (parts) {
      var p = el("p");
      parts.forEach(function (x) {
        if (typeof x === "string") p.appendChild(document.createTextNode(x));
        else p.appendChild(el(x[0] === "b" ? "strong" : "code", null, x[1]));
      });
      elOut.appendChild(p);
    });
  }

  function totalRecs() { return S.segs.reduce(function (n, s) { return n + s.recs.length; }, 0); }
  function isLive(seg, off, rec) {
    if (rec.del) return false;
    var e = S.index.get(rec.k);
    return !!e && e.seg === seg.id && e.off === off;
  }

  function drawStats() {
    var total = totalRecs(), live = 0;
    S.segs.forEach(function (s) { s.recs.forEach(function (r, i) { if (isLive(s, i, r)) live++; }); });
    var garbage = total ? Math.round(100 * (total - live) / total) : 0;
    var items = [["Segments", S.segs.length], ["Records on disk", total], ["Live keys", S.index.size],
                 ["Garbage", S.recovering ? "…" : garbage + "%"]];
    if (S.counters) {
      var c = S.counters;
      items = [["Scanned", c.scanned], ["Keys indexed", S.index.size], ["Overwrites seen", c.over], ["Tombstones", c.tomb], ["Torn dropped", c.torn]];
    }
    elStats.textContent = "";
    items.forEach(function (it) {
      var d = el("div", "lg-stat");
      d.appendChild(el("small", null, it[0]));
      d.appendChild(el("b", null, String(it[1])));
      elStats.appendChild(d);
    });
  }

  function drawSegs() {
    elSegs.textContent = "";
    if (!S.segs.length) { elSegs.appendChild(el("p", "lg-note", "The log is empty. Every write will be appended to the end of the newest segment.")); return; }
    S.segs.forEach(function (seg, si) {
      var last = si === S.segs.length - 1;
      var box = el("div", "lg-seg");
      box.setAttribute("role", "group");
      box.setAttribute("aria-label", "segment " + seg.id + (last ? ", active" : ", sealed"));
      var head = el("div", "lg-seg-head");
      head.appendChild(el("span", null, "seg-" + seg.id));
      head.appendChild(el("span", "pill" + (last ? " blue" : ""), last ? "active" : "sealed"));
      head.appendChild(el("span", "pill", seg.recs.length + "/" + S.segMax));
      box.appendChild(head);
      var wrap = el("div", "lg-recs");
      seg.recs.forEach(function (r, off) {
        var cls = "lg-rec";
        if (r.del) cls += " tomb";
        if (r.torn) cls += " torn";
        if (!S.recovering && !r.del && !isLive(seg, off, r)) cls += " stale";
        if (S.scan && S.scan.seg === seg.id && S.scan.off === off) cls += " scan";
        if (S.hl && S.hl.seg === seg.id && S.hl.off === off) cls += " hit";
        var c = el("span", cls);
        c.appendChild(el("small", null, "#" + off));
        c.appendChild(document.createTextNode(r.del ? r.k + " ✕" : r.k + "=" + r.v));
        if (r.torn) c.appendChild(document.createTextNode(" (bad checksum)"));
        wrap.appendChild(c);
      });
      if (!seg.recs.length) wrap.appendChild(el("span", "lg-note", "(empty)"));
      box.appendChild(wrap);
      elSegs.appendChild(box);
    });
    elSegs.appendChild(el("p", "lg-note", "Faded, struck-through records are garbage: the index points at a newer version, or the key was deleted. Red ✕ records are tombstones."));
  }

  function drawIndex() {
    elIndex.textContent = "";
    var keys = Array.from(S.index.keys()).sort();
    if (!keys.length) {
      elIndex.appendChild(el("p", "lg-note", S.recovering ? "Wiped by the crash. Rebuilding from the log…" : "Empty. Nothing is stored yet, or every key was deleted."));
      return;
    }
    var t = el("table", "lg-tbl");
    var hr = el("tr");
    ["key", "segment", "record"].forEach(function (h) { hr.appendChild(el("th", null, h)); });
    t.appendChild(hr);
    keys.forEach(function (k) {
      var e = S.index.get(k), tr = el("tr");
      if (S.hl && S.hl.key === k) tr.className = "hl";
      else if (S.newKey === k) tr.className = "new";
      tr.appendChild(el("td", null, k));
      tr.appendChild(el("td", null, "seg-" + e.seg));
      tr.appendChild(el("td", null, "#" + e.off));
      t.appendChild(tr);
    });
    elIndex.appendChild(t);
    elIndex.appendChild(el("p", "lg-note", "Each entry is a pointer: which file, and where in it. The values stay on disk, so RAM holds only the keys (plus a small pointer)."));
  }

  function render() {
    drawStats(); drawSegs(); drawIndex(); drawOut();
    var dis = S.busy;
    Array.prototype.forEach.call(root.querySelectorAll("button, select, input"), function (b) { b.disabled = dis; });
  }

  /* ---- operations ---- */
  function append(rec) {
    var act = S.segs[S.segs.length - 1], rolled = false;
    if (!act || act.recs.length >= S.segMax) {
      if (act) rolled = true;
      act = { id: S.nextId++, recs: [] };
      S.segs.push(act);
    }
    act.recs.push(rec);
    return { seg: act.id, off: act.recs.length - 1, rolled: rolled };
  }

  function cleanKey(k) { return (k || "").replace(/^\s+|\s+$/g, ""); }

  function doSet(k, v) {
    if (!k) { say([["Type a key first."]]); return; }
    if (totalRecs() >= MAX_RECORDS) { say([["The demo log is full (" + MAX_RECORDS + " records). Compact or reset to keep going."]]); return; }
    var old = S.index.get(k);
    var loc = append({ k: k, v: v });
    S.index.set(k, { seg: loc.seg, off: loc.off });
    S.hl = null; S.newKey = k; S.scan = null; S.counters = null;
    var p1 = [["c", "set " + k + "=" + v], " appended to the end of ", ["c", "seg-" + loc.seg], " as record ", ["c", "#" + loc.off],
              " (one sequential write, no seek). The index now points there."];
    var out = [p1];
    if (loc.rolled) out.push(["The previous segment reached " + S.segMax + " records, so it was sealed (never written again) and a new active segment started."]);
    if (old) out.push(["The older version of ", ["c", k], " in ", ["c", "seg-" + old.seg + " #" + old.off], " is now garbage. It stays on disk until compaction."]);
    say(out);
  }

  function doDel(k) {
    if (!k) { say([["Type a key first."]]); return; }
    if (!S.index.has(k)) { say([["Nothing to delete: ", ["c", k], " is not in the index."]]); return; }
    if (totalRecs() >= MAX_RECORDS) { say([["The demo log is full. Compact or reset to keep going."]]); return; }
    var loc = append({ k: k, del: true });
    S.index.delete(k);
    S.hl = null; S.newKey = null; S.scan = null; S.counters = null;
    var out = [[["c", "delete " + k], " appended a tombstone to ", ["c", "seg-" + loc.seg + " #" + loc.off], ". Nothing was erased: the old value is still in the file. The key is removed from the index, so reads now miss."]];
    if (loc.rolled) out.push(["The previous segment was sealed and a new one started."]);
    out.push(["The tombstone must survive until compaction, so that recovery (which replays the whole log) does not bring the key back."]);
    say(out);
  }

  function doGet(k) {
    clearTimers();
    S.counters = null; S.newKey = null; S.scan = null;
    if (!k) { say([["Type a key first."]]); S.hl = null; render(); return; }
    var e = S.index.get(k);
    if (!e) {
      S.hl = null;
      say([[["b", "1. Index lookup: "], ["c", k], " is not in the hash table. That is the whole answer: zero disk reads. (Either it was never written or it was deleted.)"]]);
      render(); return;
    }
    var rec = null;
    S.segs.forEach(function (s) { if (s.id === e.seg) rec = s.recs[e.off]; });
    var step1 = [["b", "1. Index lookup (RAM): "], ["c", k], " → ", ["c", "seg-" + e.seg + ", record #" + e.off], ". No disk access yet."];
    var step2 = [["b", "2. One seek + one read: "], "jump straight to ", ["c", "seg-" + e.seg + " #" + e.off], " and read that single record. Value: ", ["c", rec.v]];
    S.hl = { key: k };
    if (reduce) { S.hl = { key: k, seg: e.seg, off: e.off }; say([step1, step2]); render(); return; }
    say([step1]); render();
    later(function () { S.hl = { key: k, seg: e.seg, off: e.off }; say([step1, step2]); render(); }, 600);
  }

  function rebuild(segs) {
    var idx = new Map();
    segs.forEach(function (s) {
      s.recs.forEach(function (r, off) {
        if (r.del) idx.delete(r.k); else idx.set(r.k, { seg: s.id, off: off });
      });
    });
    return idx;
  }

  function doCompact() {
    clearTimers();
    S.hl = null; S.scan = null; S.counters = null; S.newKey = null;
    if (S.segs.length < 2) { say([["Nothing to compact yet: only the active segment exists, and the active segment is never compacted. Write more records until a segment is sealed."]]); return; }
    var sealed = S.segs.slice(0, -1), active = S.segs[S.segs.length - 1];
    var before = 0, tomb = 0, stale = 0, liveRecs = [];
    sealed.forEach(function (s) {
      s.recs.forEach(function (r, off) {
        before++;
        if (r.del) tomb++;
        else if (isLive(s, off, r)) liveRecs.push({ k: r.k, v: r.v });
        else stale++;
      });
    });
    var merged = [], id = 1;
    for (var i = 0; i < liveRecs.length; i += S.segMax) merged.push({ id: id++, recs: liveRecs.slice(i, i + S.segMax) });
    active.id = id;
    S.segs = merged.concat([active]);
    S.nextId = id + 1;
    S.index = rebuild(S.segs);
    say([
      [["b", "Compacted "], sealed.length + " sealed segments (" + before + " records) into " + merged.length + " (" + liveRecs.length + " records)."],
      ["Dropped " + stale + " overwritten value" + (stale === 1 ? "" : "s") + " and " + tomb + " tombstone" + (tomb === 1 ? "" : "s") + ". Only records the index pointed at were copied, then the old files were deleted and the index was updated."],
      ["The active segment was left alone because it is still being appended to. (The widget renumbers segments for tidiness; real stores keep their ids.)"]
    ]);
  }

  function doCrash() {
    clearTimers();
    if (!S.segs.length) { say([["There is nothing on disk to recover. Write a few records first."]]); render(); return; }
    var flat = [];
    S.segs.forEach(function (s) { s.recs.forEach(function (r, off) { flat.push({ seg: s, off: off, rec: r }); }); });
    var tear = tearBox.checked;
    S.hl = null; S.newKey = null;
    S.index = new Map();
    S.recovering = true;
    S.counters = { scanned: 0, over: 0, tomb: 0, torn: 0 };
    S.busy = true;
    say([[["b", "Crash! "], "The process died and RAM is gone, including the whole hash index. The log on disk is intact. Recovery scans every segment from oldest to newest and replays each record into a fresh index."]]);
    var pos = 0;

    function stepOne() {
      var f = flat[pos], c = S.counters;
      S.scan = { seg: f.seg.id, off: f.off };
      c.scanned++;
      if (tear && pos === flat.length - 1) {
        f.rec.torn = true;      // checksum mismatch: the record is not replayed
        c.torn++;
      } else if (f.rec.del) {
        c.tomb++;
        S.index.delete(f.rec.k);
      } else {
        if (S.index.has(f.rec.k)) c.over++;
        S.index.set(f.rec.k, { seg: f.seg.id, off: f.off });
      }
      pos++;
    }
    function finish() {
      var torn = null;
      if (tear) {
        var ls = S.segs[S.segs.length - 1];
        torn = ls.recs.pop();
      }
      S.recovering = false; S.scan = null; S.busy = false;
      var c = S.counters, nsegs = S.segs.length;
      var out = [[["b", "Recovered. "], "Scanned " + c.scanned + " records in " + nsegs + " segment" + (nsegs === 1 ? "" : "s") + ", and ended with " + S.index.size + " live key" + (S.index.size === 1 ? "" : "s") + " (" + c.over + " overwrites and " + c.tomb + " tombstones replayed along the way)."]];
      if (torn) out.push(["The last record's checksum did not match, so it was treated as the append that was in flight when the machine died and was cut off the end of the file. In a real store that write had not been acknowledged yet, so no promise is broken."]);
      out.push(["Cost: reading the entire log once. A hint file (a snapshot of keys and offsets saved at compaction time) lets a real store skip reading the values."]);
      say(out);
      render();
      var cb = root.querySelector('[data-act="crash"]');
      if (cb) cb.focus();
    }
    if (reduce) {
      while (pos < flat.length) stepOne();
      finish(); return;
    }
    render();
    (function tick() {
      if (pos >= flat.length) { finish(); return; }
      stepOne(); render();
      later(tick, 160);
    })();
  }

  function doDemo() {
    clearTimers();
    S = fresh(parseInt(sizeSel.value, 10) || 4);
    DEMO.forEach(function (d) {
      if (d[0] === "set") { var loc = append({ k: d[1], v: d[2] }); S.index.set(d[1], { seg: loc.seg, off: loc.off }); }
      else { append({ k: d[1], del: true }); S.index.delete(d[1]); }
    });
    say([[["b", "Demo loaded: "], DEMO.length + " operations. Notice how many records are garbage, and that ", ["c", "user:3"], " is deleted but its old value and its tombstone are still in the log. Now try Compact."]]);
  }

  function doReset() {
    clearTimers();
    S = fresh(parseInt(sizeSel.value, 10) || 4);
    say([["Empty store. Try ", ["c", "Set"], " a few keys, overwrite one, then ", ["c", "Get"], " it."]]);
  }

  function value(input) { return input.value; }
  function run(act, k, v) {
    if (S.busy) return;
    clearTimers();
    if (act === "set") doSet(k, v);
    else if (act === "del") doDel(k);
    else if (act === "get") { doGet(k); return; }
    render();
  }

  PICKS.forEach(function (p) {
    var b = el("button", "btn small", p.label);
    b.type = "button";
    b.addEventListener("click", function () {
      keyIn.value = p.k;
      if (p.v != null) valIn.value = p.v;
      run(p.op, p.k, p.v);
    });
    elPicks.appendChild(b);
  });

  root.addEventListener("click", function (ev) {
    var b = ev.target.closest ? ev.target.closest("button[data-act]") : null;
    if (!b || S.busy) return;
    var act = b.getAttribute("data-act");
    if (act === "get" || act === "del") { run(act, cleanKey(value(keyIn))); }
    else if (act === "compact") { doCompact(); render(); }
    else if (act === "crash") { doCrash(); }
    else if (act === "demo") { doDemo(); render(); }
    else if (act === "reset") { doReset(); render(); }
  });
  q("form").addEventListener("submit", function (ev) {
    ev.preventDefault();
    run("set", cleanKey(value(keyIn)), value(valIn));
  });
  sizeSel.addEventListener("change", function () { S.segMax = parseInt(sizeSel.value, 10) || 4; });

  doReset();
  render();
})();
