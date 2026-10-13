/* Crash simulator (systems chapter 9).

   A deliberately simplified model of one config file and its directory.
   - "disk" is what survives a power cut.
   - "queue" is the list of dirty changes sitting in the kernel's page cache,
     oldest first. The cache view is the disk with every queued change applied.
   - write()/rename() only append to the queue. fsync() applies the matching
     changes to the disk. Background writeback applies some of them.
   - Pulling the plug: any subset of the queued changes may have reached the
     disk (the kernel is free to write back in any order), except that a name
     or data can't land on disk before the inode it refers to exists. We
     enumerate every such subset, classify what config.json would hold, and
     show one random timing plus a summary of all of them.
   Files have two blocks. Not modelled: file-system-specific extra guarantees,
   drive write caches, I/O errors. */
(function () {
  "use strict";
  var root = document.getElementById("crash-sim");
  if (!root) return;

  var ACTIONS = [
    { id: "write",    text: "write new contents into config.json" },
    { id: "fsynccfg", text: "fsync(config.json)" },
    { id: "tmpwrite", text: "write new contents to config.tmp" },
    { id: "fsynctmp", text: "fsync(config.tmp)" },
    { id: "rename",   text: "rename(config.tmp, config.json)" },
    { id: "fsyncdir", text: "fsync(directory)" }
  ];
  var PRESETS = [
    { id: "naive", label: "Naive overwrite", plan: ["write"],
      desc: "The simplest code: open config.json for writing (which empties it), write the new bytes, close. No fsync. Run the step, then pull the plug a few times with “Re-roll”." },
    { id: "fsync", label: "Overwrite + fsync", plan: ["write", "fsynccfg"],
      desc: "Same, plus fsync. Pull the plug after step 1, then again after step 2. Once fsync returns, the file is durable. Before that, overwriting in place is not atomic." },
    { id: "rename", label: "Temp + rename, no fsync", plan: ["tmpwrite", "rename"],
      desc: "Write config.tmp, then rename it over config.json, but never fsync. The rename swaps the name in one step, but nothing made the contents reach the disk first." },
    { id: "safe", label: "The full safe pattern", plan: ["tmpwrite", "fsynctmp", "rename", "fsyncdir"],
      desc: "Write temp, fsync temp, rename, fsync the directory. Pull the plug after any step: you get the old file or the new one, never a broken one. After the last step it is certainly the new one." }
  ];
  var BLK = { o1: ["o", "old 1"], o2: ["o", "old 2"], n1: ["n", "new 1"], n2: ["n", "new 2"] };
  var KIND_ORDER = ["old", "new", "missing", "empty", "torn"];

  var S, plan = [], planPos = 0, presetId = null;

  function fresh(first) {
    var disk = first ? { dir: {}, ino: {} } : { dir: { "config.json": "A" }, ino: { A: { len: 2, s: ["o1", "o2"] } } };
    return { first: first, disk: disk, queue: [], seq: 0, createId: {}, procDead: false, fds: {}, used: {}, log: [], crash: null };
  }
  function clone(v) { return JSON.parse(JSON.stringify(v)); }
  function applyOp(v, op) {
    var f = v.ino[op.ino];
    if (op.t === "create") v.ino[op.ino] = { len: 0, s: [null, null] };
    else if (op.t === "trunc" && f) { f.len = 0; f.s = [null, null]; }
    else if (op.t === "blk" && f) { f.s[op.i] = op.v; f.len = Math.max(f.len, op.i + 1); }
    else if (op.t === "link") v.dir[op.name] = op.ino;
    else if (op.t === "rename") { v.dir[op.to] = op.ino; delete v.dir[op.from]; }
  }
  function view(disk, queue) { var v = clone(disk); queue.forEach(function (op) { applyOp(v, op); }); return v; }
  function inQueue(id) { return S.queue.some(function (o) { return o.id === id; }); }
  function push(op, dep) { op.id = ++S.seq; if (dep) op.dep = dep; S.queue.push(op); return op.id; }

  function flush(pred) {
    var chosen = {}, changed = true;
    S.queue.forEach(function (op) { if (pred(op)) chosen[op.id] = true; });
    while (changed) {
      changed = false;
      S.queue.forEach(function (op) {
        if (chosen[op.id] && op.dep && !chosen[op.dep] && inQueue(op.dep)) { chosen[op.dep] = true; changed = true; }
      });
    }
    var n = 0, rest = [];
    S.queue.forEach(function (op) { if (chosen[op.id]) { applyOp(S.disk, op); n++; } else rest.push(op); });
    S.queue = rest;
    return n;
  }

  function describeOp(op) {
    if (op.t === "trunc") return "emptying the file (truncate)";
    if (op.t === "blk") return "block " + (op.i + 1) + " of a file’s data";
    if (op.t === "create") return "creating a file’s inode";
    if (op.t === "link") return "the directory entry “" + op.name + "”";
    return "the rename to “" + op.to + "”";
  }
  function log(text, bad) { S.log.push({ text: text, bad: !!bad }); }

  function doAction(id) {
    if (S.crash || S.procDead) return;
    if (plan[planPos] === id) planPos++;
    var cv = view(S.disk, S.queue), ino, n, cid;
    if (id === "write") {
      if (S.used.write) return;
      S.used.write = true;
      ino = cv.dir["config.json"];
      if (ino) {
        S.fds.cfg = ino;
        push({ t: "trunc", ino: ino });
        push({ t: "blk", ino: ino, i: 0, v: "n1" });
        push({ t: "blk", ino: ino, i: 1, v: "n2" });
        log("write(config.json): returned OK at once. The kernel emptied the file and copied the new bytes into the page cache, marked dirty. Nothing new is on the disk yet.");
      } else {
        ino = "N"; S.fds.cfg = ino;
        cid = push({ t: "create", ino: ino });
        S.createId[ino] = cid;
        push({ t: "blk", ino: ino, i: 0, v: "n1" }, cid);
        push({ t: "blk", ino: ino, i: 1, v: "n2" }, cid);
        push({ t: "link", name: "config.json", ino: ino }, cid);
        log("write(config.json): returned OK. The kernel created the file and cached its bytes and its name, all dirty. Nothing is on the disk yet.");
      }
    } else if (id === "tmpwrite") {
      if (S.used.tmpwrite) return;
      S.used.tmpwrite = true;
      S.fds.tmp = "T";
      cid = push({ t: "create", ino: "T" });
      S.createId.T = cid;
      push({ t: "blk", ino: "T", i: 0, v: "n1" }, cid);
      push({ t: "blk", ino: "T", i: 1, v: "n2" }, cid);
      push({ t: "link", name: "config.tmp", ino: "T" }, cid);
      log("write(config.tmp): returned OK. A new file exists in the page cache with the new bytes and its name, all dirty.");
    } else if (id === "fsynccfg" || id === "fsynctmp") {
      var key = id === "fsynccfg" ? "cfg" : "tmp";
      var nm = id === "fsynccfg" ? "config.json" : "config.tmp";
      ino = S.fds[key];
      if (!ino) { log("fsync(" + nm + ") failed: no file is open yet. Do the matching write first.", true); render(); return; }
      n = flush(function (op) { return op.ino === ino && (op.t === "create" || op.t === "trunc" || op.t === "blk"); });
      log(n ? "fsync(" + nm + ") returned after the kernel wrote " + n + " dirty item" + (n > 1 ? "s" : "") + " of this file to the disk. The file’s data is now durable. (It does not cover the directory entry.)"
            : "fsync(" + nm + ") returned at once: nothing about this file was dirty.");
    } else if (id === "rename") {
      if (S.used.rename) return;
      if (!cv.dir["config.tmp"]) { log("rename failed: there is no config.tmp yet. Write it first.", true); render(); return; }
      S.used.rename = true;
      push({ t: "rename", from: "config.tmp", to: "config.json", ino: cv.dir["config.tmp"] }, S.createId[cv.dir["config.tmp"]]);
      log("rename(config.tmp, config.json): returned OK. In the cache, config.json now means the new file. The swap of the name is atomic, but so far only in memory.");
    } else if (id === "fsyncdir") {
      n = flush(function (op) { return op.t === "link" || op.t === "rename"; });
      log(n ? "fsync(directory) returned after the kernel wrote " + n + " dirty directory change" + (n > 1 ? "s" : "") + " to the disk. The names are durable."
            : "fsync(directory) returned at once: no directory change was dirty.");
    }
    render();
  }

  function writebackOne() {
    if (S.crash || !S.queue.length) return;
    var first = S.queue[0];
    flush(function (op) { return op === first; });
    log("Kernel writeback wrote one dirty item to the disk: " + describeOp(first) + ". (Real kernels choose the order freely; this toy takes the oldest first.)");
    render();
  }
  function writebackAll() {
    if (S.crash) return;
    var n = flush(function () { return true; });
    log(n ? "Time passed. The kernel’s background writeback wrote all " + n + " dirty item" + (n > 1 ? "s" : "") + " to the disk." : "Time passed. Nothing was dirty.");
    render();
  }
  function killProc() {
    if (S.crash || S.procDead) return;
    S.procDead = true;
    log("kill -9: the process is gone and so is its memory. The page cache belongs to the kernel, so every write() that had already returned is still there, and the kernel will still write it back.");
    render();
  }

  function classify(v) {
    var ino = v.dir["config.json"], f = ino && v.ino[ino];
    if (!f) return "missing";
    if (f.len === 0) return "empty";
    var c = f.s.slice(0, f.len).join(",");
    if (c === "o1,o2") return "old";
    if (c === "n1,n2") return "new";
    return "torn";
  }
  function pullPlug() {
    if (S.crash) return;
    var q = S.queue, n = q.length, masks = [], counts = {}, m, i;
    for (m = 0; m < (1 << n); m++) {
      var ok = true, v = clone(S.disk);
      for (i = 0; i < n && ok; i++) {
        if (m & (1 << i)) {
          var d = q[i].dep;
          if (d && inQueue(d)) {
            var di = -1, j;
            for (j = 0; j < n; j++) if (q[j].id === d) di = j;
            if (!(m & (1 << di))) ok = false;
          }
          if (ok) applyOp(v, q[i]);
        }
      }
      if (!ok) continue;
      var kind = classify(v);
      counts[kind] = (counts[kind] || 0) + 1;
      masks.push({ v: v, kind: kind });
    }
    S.crash = { masks: masks, counts: counts, total: masks.length, pick: Math.floor(Math.random() * masks.length), dirOnly: n > 0 && q.every(function (o) { return o.t === "link" || o.t === "rename"; }) };
    log("⚡ Power cut. RAM is wiped: the application’s memory and the page cache are gone. Only the disk remains.", true);
    render();
  }
  function reroll() {
    if (!S.crash) return;
    S.crash.pick = Math.floor(Math.random() * S.crash.total);
    render();
  }

  /* ---------- rendering ---------- */
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function chip(code) {
    if (code === null) return el("span", "cs-blk z", "zeros");
    var b = BLK[code];
    return el("span", "cs-blk " + b[0], b[1]);
  }
  function drawFiles(host, v, dirtyNames, dirtyInos) {
    var named = {}, names = Object.keys(v.dir).sort();
    names.forEach(function (name) {
      var ino = v.dir[name]; named[ino] = true;
      host.appendChild(fileBox(name, v.ino[ino], dirtyNames[name] || (dirtyInos && dirtyInos[ino])));
    });
    Object.keys(v.ino).sort().forEach(function (ino) {
      if (!named[ino]) host.appendChild(fileBox("(a file with no name)", v.ino[ino], dirtyInos && dirtyInos[ino]));
    });
    if (!host.childNodes.length) host.appendChild(el("p", "cs-note", "(no files)"));
  }
  function fileBox(name, f, dirty) {
    var box = el("div", "cs-file" + (dirty ? " dirty" : ""));
    var nm = el("div", "nm", name);
    if (dirty) nm.appendChild(el("span", "pill yellow", "dirty"));
    box.appendChild(nm);
    var chips = el("div", "cs-chips");
    if (!f) chips.appendChild(el("span", "cs-blk e", "no inode"));
    else if (f.len === 0) chips.appendChild(el("span", "cs-blk e", "empty (0 bytes)"));
    else for (var i = 0; i < f.len; i++) chips.appendChild(chip(f.s[i]));
    box.appendChild(chips);
    return box;
  }
  function pane(cls, title) {
    var p = el("div", "cs-pane " + cls);
    p.appendChild(el("h5", "", title));
    return p;
  }

  var ui = {};
  function build() {
    root.textContent = "";
    root.className = "widget";
    root.innerHTML =
      '<div class="widget-head"><span class="widget-tag">Interactive</span><h4 class="widget-title">Crash simulator: what survives?</h4></div>' +
      '<p class="widget-help">A simplified model: one config file of two blocks, its directory, the kernel’s page cache and the disk. It treats fsync as reaching stable storage (see the drive-cache section for why that is not always true) and ignores file-system-specific extras. Pick a scenario, step through it, and pull the plug at any moment.</p>' +
      '<div><div class="cs-label">1. Pick a scenario</div>' +
      '<div class="widget-row" data-role="presets" role="group" aria-label="Scenarios"></div>' +
      '<label class="cs-check"><input type="checkbox" data-role="first"> First save: config.json does not exist yet</label>' +
      '<p class="cs-desc" data-role="desc">Choose a scenario above, or just click the actions below in any order you like.</p>' +
      '<ol class="cs-plan" data-role="plan" hidden></ol>' +
      '<div class="widget-row" data-role="planbtns" hidden><button type="button" class="btn small primary" data-act="next">Next step ▶</button><button type="button" class="btn small" data-act="runall">Run all steps ▶▶</button></div></div>' +
      '<div><div class="cs-label">2. Your program’s actions</div><div class="cs-actions" data-role="actions"></div></div>' +
      '<div><div class="cs-label">3. The operating system and the world</div><div class="widget-row" data-role="world">' +
      '<button type="button" class="btn small" data-act="wb1">Kernel writes back 1 dirty item</button>' +
      '<button type="button" class="btn small" data-act="wball">Let time pass (write back everything)</button>' +
      '<button type="button" class="btn small" data-act="kill">💥 kill -9 the process</button>' +
      '<button type="button" class="btn small danger" data-act="plug">⚡ Pull the plug</button>' +
      '<button type="button" class="btn small" data-act="reroll" hidden>Re-roll the timing</button>' +
      '<button type="button" class="btn small" data-act="reset">Reset</button></div></div>' +
      '<div class="cs-panes" data-role="panes"></div>' +
      '<div><div class="cs-label">What happened</div><ol class="cs-log" data-role="log" role="log"></ol></div>' +
      '<div class="widget-out cs-result" data-role="result" aria-live="polite"></div>';
    ["presets", "first", "desc", "plan", "planbtns", "actions", "panes", "log", "result"].forEach(function (r) {
      ui[r] = root.querySelector('[data-role="' + r + '"]');
    });
    PRESETS.forEach(function (p) {
      var b = el("button", "btn small", p.label);
      b.type = "button"; b.setAttribute("data-preset", p.id); b.setAttribute("aria-pressed", "false");
      ui.presets.appendChild(b);
    });
    ACTIONS.forEach(function (a, i) {
      var b = el("button", "btn small", (i + 1) + ". " + a.text);
      b.type = "button"; b.setAttribute("data-do", a.id);
      ui.actions.appendChild(b);
    });
    root.addEventListener("click", function (e) {
      var t = e.target;
      while (t && t !== root && t.tagName !== "BUTTON") t = t.parentNode;
      if (!t || t === root || t.tagName !== "BUTTON") return;
      var act = t.getAttribute("data-act"), d = t.getAttribute("data-do"), p = t.getAttribute("data-preset");
      if (d) doAction(d);
      else if (p) loadPreset(p);
      else if (act === "next") { if (planPos < plan.length) doAction(plan[planPos]); }
      else if (act === "runall") { while (planPos < plan.length && !S.crash && !S.procDead) { var before = planPos; doAction(plan[planPos]); if (planPos === before) planPos++; } render(); }
      else if (act === "wb1") writebackOne();
      else if (act === "wball") writebackAll();
      else if (act === "kill") killProc();
      else if (act === "plug") pullPlug();
      else if (act === "reroll") reroll();
      else if (act === "reset") { reset(); }
    });
    ui.first.addEventListener("change", function () { reset(); });
  }

  function reset() {
    S = fresh(ui.first.checked);
    planPos = 0;
    render();
  }
  function loadPreset(id) {
    var p = PRESETS.filter(function (x) { return x.id === id; })[0];
    presetId = id; plan = p.plan.slice();
    S = fresh(ui.first.checked); planPos = 0;
    ui.desc.textContent = p.desc;
    render();
  }

  function render() {
    var i, cv = view(S.disk, S.queue), crashed = !!S.crash;

    // presets and plan
    Array.prototype.forEach.call(ui.presets.children, function (b) { b.setAttribute("aria-pressed", String(b.getAttribute("data-preset") === presetId)); });
    ui.plan.textContent = "";
    plan.forEach(function (id, k) {
      var a = ACTIONS.filter(function (x) { return x.id === id; })[0];
      var li = el("li", k < planPos ? "done" : (k === planPos ? "cur" : ""), a.text + (k < planPos ? " ✓" : ""));
      ui.plan.appendChild(li);
    });
    var hasPlan = plan.length > 0;
    ui.plan.hidden = !hasPlan; ui.planbtns.hidden = !hasPlan;
    var nextBtn = root.querySelector('[data-act="next"]'), allBtn = root.querySelector('[data-act="runall"]');
    nextBtn.disabled = allBtn.disabled = crashed || S.procDead || planPos >= plan.length;

    // action buttons
    Array.prototype.forEach.call(ui.actions.children, function (b) {
      var id = b.getAttribute("data-do");
      b.disabled = crashed || S.procDead || !!S.used[id];
    });
    root.querySelector('[data-act="wb1"]').disabled = crashed || !S.queue.length;
    root.querySelector('[data-act="wball"]').disabled = crashed || !S.queue.length;
    root.querySelector('[data-act="kill"]').disabled = crashed || S.procDead;
    root.querySelector('[data-act="plug"]').disabled = crashed;
    root.querySelector('[data-act="reroll"]').hidden = !crashed || S.crash.total < 2;

    // panes
    ui.panes.textContent = "";
    var mem = pane("mem", "🧠 Application memory");
    var cache = pane("cache", "🗂️ Kernel page cache (RAM)");
    var disk = pane("disk", crashed ? "💾 Disk after reboot" : "💾 Disk");
    if (crashed) {
      mem.appendChild(el("p", "cs-note", "Gone. The process died with the machine."));
      cache.appendChild(el("p", "cs-note", "Gone. RAM does not survive a power cut. Anything dirty that had not reached the disk is lost."));
    } else {
      mem.appendChild(el("p", "cs-note", S.procDead ? "Process killed: its memory is gone." : "The program is running. In a variable it holds the new config:"));
      if (!S.procDead) {
        var chips = el("div", "cs-chips"); chips.appendChild(chip("n1")); chips.appendChild(chip("n2"));
        mem.appendChild(chips);
        var fdl = [];
        if (S.fds.cfg) fdl.push("config.json");
        if (S.fds.tmp) fdl.push("config.tmp");
        mem.appendChild(el("p", "cs-note", "Open files: " + (fdl.length ? fdl.join(", ") : "none")));
      }
      var dn = {}, di = {};
      S.queue.forEach(function (op) {
        if (op.t === "link") dn[op.name] = true;
        else if (op.t === "rename") dn[op.to] = true;
        else di[op.ino] = true;
      });
      drawFiles(cache, cv, dn, di);
      cache.appendChild(el("p", "cs-note", S.queue.length ? S.queue.length + " dirty item" + (S.queue.length > 1 ? "s" : "") + " waiting to be written back." : "Nothing dirty: cache and disk agree."));
    }
    drawFiles(disk, crashed ? S.crash.masks[S.crash.pick].v : S.disk, {}, null);
    ui.panes.appendChild(mem); ui.panes.appendChild(cache); ui.panes.appendChild(disk);

    // log
    ui.log.textContent = "";
    S.log.forEach(function (l) { ui.log.appendChild(el("li", l.bad ? "bad" : "", l.text)); });
    ui.log.scrollTop = ui.log.scrollHeight;

    // result
    ui.result.textContent = "";
    if (crashed) renderCrash();
    else if (S.procDead) ui.result.appendChild(el("p", "", "Process killed, power still on. Look at the page cache pane: the dirty data is still there. A process crash does not lose data that write() already handed to the kernel. Now try “Pull the plug” to see what a power cut does instead."));
    else ui.result.appendChild(el("p", "", "Nothing has been lost yet. Do some steps, then pull the plug (or kill the process, and compare)."));
  }

  var KIND_TEXT = {
    old: "The old config.json, whole. The update was lost, but nothing is broken.",
    "new": "The new config.json, whole.",
    missing: "There is no config.json at all.",
    empty: "config.json exists but is empty (0 bytes). A program that loads it at startup will probably fail.",
    torn: "config.json holds a mix: some new blocks, some old ones, or blocks of zeros. It is neither version, and the program reading it may crash or misbehave."
  };
  function renderCrash() {
    var c = S.crash, mk = c.masks[c.pick], first = S.first, out = ui.result;
    var head = el("p", "");
    head.appendChild(document.createTextNode("This time, after reboot: "));
    var good = first ? (mk.kind === "missing" || mk.kind === "new") : (mk.kind === "old" || mk.kind === "new");
    head.appendChild(el("strong", good ? "cs-ok" : "cs-badk", KIND_TEXT[mk.kind] && (mk.kind === "missing" && first ? "no config.json yet (the update was lost, nothing is broken)." : KIND_TEXT[mk.kind])));
    out.appendChild(head);
    out.appendChild(el("p", "", c.total === 1 ? "Nothing was left dirty, so there is only one possible outcome:" : "Which one you get depends on which dirty items the kernel had written back by that instant. Across all " + c.total + " possible timings:"));
    var ul = el("ul", "");
    var allGood = true;
    KIND_ORDER.forEach(function (k) {
      if (!c.counts[k]) return;
      var ok = first ? (k === "missing" || k === "new") : (k === "old" || k === "new");
      if (!ok) allGood = false;
      var li = el("li", "");
      li.appendChild(el("span", ok ? "cs-ok" : "cs-badk", (ok ? "✓ " : "✗ ") + c.counts[k] + " of " + c.total + ": "));
      li.appendChild(document.createTextNode(k === "missing" && first ? "no config.json (nothing saved yet)." : KIND_TEXT[k]));
      ul.appendChild(li);
    });
    out.appendChild(ul);
    var hasNew = !!c.counts["new"], hasBefore = !!c.counts[first ? "missing" : "old"], v;
    if (!allGood) v = "Verdict: unsafe. At some timings the disk holds a broken file.";
    else if (hasNew && !hasBefore) v = "Verdict: durable. At every timing the new file is on the disk.";
    else if (hasNew) v = "Verdict: safe but not yet durable. You get " + (first ? "no file" : "the old file") + " or the new file, never a broken one, but the update itself may be lost.";
    else v = "Verdict: nothing was saved yet, but nothing is broken either.";
    out.appendChild(el("p", "", v));
    if (c.dirOnly && mk.kind !== "new") out.appendChild(el("p", "", "Note: the file’s contents are already on the disk. What is missing is the directory change that gives them their name. That is why the directory needs its own fsync."));
  }

  build();
  S = fresh(false);
  render();
})();
