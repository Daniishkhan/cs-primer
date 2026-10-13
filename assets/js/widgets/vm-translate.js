/* Virtual-address translation toy (systems chapter 6).

   TOY SIZES (clearly not real hardware):
     16-bit virtual addresses, 4 KiB pages  -> 4-bit page number + 12-bit offset (16 virtual pages)
     8 physical frames of 4 KiB             -> 15-bit physical addresses
     4-entry TLB, first-in-first-out replacement
     one flat page table per process (real CPUs use multi-level tables)

   Page states:
     m  mapped: present in RAM (has a frame)
     n  never touched: valid, but the kernel hasn't given it a frame yet (minor fault, no disk)
     d  on disk: swapped out or a file not read yet (major fault, disk read)
     u  unmapped: not part of the address space at all (segmentation fault)

   Everything the user types is shown with textContent. No libraries, no storage. */
(function () {
  "use strict";
  var root = document.getElementById("vm-translate");
  if (!root) return;

  var NPAGES = 16, NFRAMES = 8, TLB_SIZE = 4, PAGE = 4096;

  var PROCS = [
    { name: "Process A", pid: 101, spec: "0:m2,1:m5,2:m0,3:n,4:d,5:n,12:d,14:m3,15:m6" },
    { name: "Process B", pid: 202, spec: "0:m4,1:m1,2:d,3:m6,4:n,8:m3,14:d,15:m2" },
    { name: "Process C", pid: 303, spec: "0:m7,1:m0,2:m1,10:d,11:n,14:m5,15:m4" }
  ];

  var STATE_LABEL = { m: "in RAM", n: "untouched", d: "on disk", u: "unmapped" };
  var KIND_LABEL = {
    hit: "TLB hit", walk: "TLB miss, table hit", minor: "minor fault",
    major: "major fault", segv: "segfault"
  };

  var state = { pi: 0, pt: [], tlb: [], loadQ: [], last: null, hist: [], lastVpn: 0 };
  var c = { total: 0, hit: 0, miss: 0, minor: 0, major: 0, segv: 0 };

  /* ---------- tiny helpers ---------- */
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function hex(n, w) { var s = n.toString(16).toUpperCase(); while (s.length < w) s = "0" + s; return s; }
  function bin(n, w) { var s = n.toString(2); while (s.length < w) s = "0" + s; return s; }
  function group4(s) { return s.replace(/(.{4})(?=.)/g, "$1 "); }
  function pct(a, b) { return b ? Math.round(100 * a / b) + "%" : "n/a"; }

  function parseSpec(spec) {
    var pt = [], i;
    for (i = 0; i < NPAGES; i++) pt.push({ s: "u", f: -1 });
    spec.split(",").forEach(function (part) {
      var m = /^(\d+):([mdn])(\d*)$/.exec(part.trim());
      if (m) pt[+m[1]] = { s: m[2], f: m[3] === "" ? -1 : +m[3] };
    });
    return pt;
  }

  function loadProc(i) {
    state.pi = i;
    state.pt = parseSpec(PROCS[i].spec);
    state.tlb = [];
    state.loadQ = [];
    state.last = null;
    for (var v = 0; v < NPAGES; v++) if (state.pt[v].s === "m") state.loadQ.push(v);
  }

  function findTlb(vpn) {
    for (var i = 0; i < state.tlb.length; i++) if (state.tlb[i].vpn === vpn) return i;
    return -1;
  }
  function dropTlb(vpn) {
    var i = findTlb(vpn);
    if (i >= 0) state.tlb.splice(i, 1);
  }
  function fillTlb(vpn, pfn) {
    dropTlb(vpn);
    var evicted = -1;
    if (state.tlb.length >= TLB_SIZE) evicted = state.tlb.shift().vpn;
    state.tlb.push({ vpn: vpn, pfn: pfn });
    return evicted;
  }

  function usedFrames() {
    var used = {};
    state.pt.forEach(function (e) { if (e.s === "m") used[e.f] = true; });
    return used;
  }
  /* Returns {f, victim} where victim is the page that lost its frame (or -1). */
  function allocFrame() {
    var used = usedFrames(), f;
    for (f = 0; f < NFRAMES; f++) if (!used[f]) return { f: f, victim: -1 };
    var victim = state.loadQ.shift();
    f = state.pt[victim].f;
    state.pt[victim] = { s: "d", f: -1 };
    dropTlb(victim);
    return { f: f, victim: victim };
  }

  /* ---------- the translation itself ---------- */
  function translate(va) {
    var vpn = va >> 12, off = va & 0xFFF;
    var steps = [], kind, pfn = -1, evictedPage = -1;
    c.total++;
    state.lastVpn = vpn;

    steps.push({ h: "1. Split the address", split: va,
      t: "The top 4 bits are the virtual page number (" + vpn + "); the low 12 bits are the offset inside the 4 KiB page (0x" + hex(off, 3) + ")." });

    var ti = findTlb(vpn);
    if (ti >= 0) {
      c.hit++;
      kind = "hit";
      pfn = state.tlb[ti].pfn;
      steps.push({ h: "2. Look in the TLB", t: "Hit! The TLB already remembers page " + vpn + " lives in frame " + pfn + ". No page-table access is needed.", cls: "ok" });
    } else {
      c.miss++;
      steps.push({ h: "2. Look in the TLB", t: "Miss. None of the " + TLB_SIZE + " TLB entries covers page " + vpn + ". The hardware must read the page table in RAM.", cls: "warn" });
      var e = state.pt[vpn];
      if (e.s === "m") {
        kind = "walk";
        pfn = e.f;
        steps.push({ h: "3. Read the page table", t: "Entry for page " + vpn + " says: present, frame " + e.f + ". One extra memory access, no kernel involved.", cls: "ok" });
        var ev1 = fillTlb(vpn, pfn);
        steps.push({ h: "4. Remember it in the TLB", t: "The translation is cached" + (ev1 >= 0 ? " (the oldest entry, page " + ev1 + ", was pushed out)." : ".") + " The next access to this page will hit." });
      } else if (e.s === "u") {
        kind = "segv";
        c.segv++;
        steps.push({ h: "3. Read the page table", t: "Entry for page " + vpn + " is not valid: this address isn't part of the process's address space at all.", cls: "bad" });
        steps.push({ h: "4. Exception", t: "The CPU raises a fault, the kernel finds no mapping to fix, and sends the process SIGSEGV: \"Segmentation fault\". Nothing is loaded.", cls: "bad" });
      } else {
        var minor = e.s === "n";
        kind = minor ? "minor" : "major";
        if (minor) c.minor++; else c.major++;
        steps.push({ h: "3. Read the page table", t: "Entry for page " + vpn + " is valid but not present in RAM (" + (minor ? "never touched yet" : "its contents are on disk") + "). The CPU raises a page fault.", cls: "warn" });
        var a = allocFrame();
        evictedPage = a.victim;
        var fh = "4. Kernel handles the page fault";
        var ft = a.victim >= 0
          ? "No free frame, so the kernel evicts page " + a.victim + " (the oldest loaded) from frame " + a.f + " and, if it had been modified, writes it back to disk. Its TLB entry is invalidated. "
          : "A free frame is available: frame " + a.f + ". ";
        ft += minor
          ? "It fills the frame with zeros (or maps a page already in the page cache). No disk read, so this is a minor fault, typically microseconds."
          : "It reads the page from disk into the frame. This is a major fault: the process sleeps while the disk works, which takes far longer than anything in memory.";
        steps.push({ h: fh, t: ft, cls: minor ? "warn" : "bad" });
        state.pt[vpn] = { s: "m", f: a.f };
        state.loadQ.push(vpn);
        pfn = a.f;
        var ev2 = fillTlb(vpn, pfn);
        steps.push({ h: "5. Retry the instruction", t: "The faulting instruction restarts. The TLB still misses, but now the page table has a valid entry (frame " + a.f + "), so the translation succeeds and is cached" + (ev2 >= 0 ? " (page " + ev2 + " pushed out of the TLB)." : "."), cls: "ok" });
      }
    }

    var pa = -1;
    if (pfn >= 0) {
      pa = (pfn << 12) | off;
      steps.push({ h: "Result", phys: { pfn: pfn, off: off, pa: pa }, t: "Physical address = frame " + pfn + " followed by the same offset.", cls: "ok" });
    } else {
      steps.push({ h: "Result", t: "No physical address: the access failed.", cls: "bad" });
    }

    var res = { kind: kind, va: va, vpn: vpn, off: off, pfn: pfn, pa: pa, steps: steps, evicted: evictedPage };
    state.last = res;
    state.hist.push({ va: va, kind: kind });
    if (state.hist.length > 10) state.hist.shift();
    return res;
  }

  function summary(r) {
    var v = "0x" + hex(r.va, 4);
    var p = r.pa >= 0 ? "0x" + hex(r.pa, 4) : "";
    switch (r.kind) {
      case "hit": return "TLB hit: " + v + " maps to " + p + " with no page-table access.";
      case "walk": return "TLB miss, but the page table had it: " + v + " maps to " + p + ".";
      case "minor": return "Minor page fault (no disk read): " + v + " now maps to " + p + ".";
      case "major": return "Major page fault (read from disk): " + v + " now maps to " + p + ".";
      default: return "Segmentation fault: " + v + " is not mapped in this process.";
    }
  }

  /* ---------- building the widget ---------- */
  var ui = {};

  function build() {
    var ctl = el("div", "widget-row vm-controls");
    var lab = el("label", "vm-label", "Virtual address (hex, 0000 to FFFF)");
    lab.setAttribute("for", "vm-addr-input");
    var inp = el("input", "mono vm-input");
    inp.type = "text"; inp.id = "vm-addr-input"; inp.value = "0x0123";
    inp.maxLength = 8; inp.autocomplete = "off"; inp.spellcheck = false;
    inp.setAttribute("aria-describedby", "vm-status");
    ui.input = inp;
    var go = el("button", "btn primary", "Translate"); go.type = "button";
    ui.sample = el("select", "mono vm-sample");
    ui.sample.setAttribute("aria-label", "Pick a sample address");
    var rnd = el("button", "btn small", "Random page"); rnd.type = "button";
    var run = el("button", "btn small", "Run 10 accesses"); run.type = "button";
    var np = el("button", "btn small", "New process"); np.type = "button";
    var rc = el("button", "btn small", "Reset counters"); rc.type = "button";

    var r1 = el("div", "vm-field"); r1.appendChild(lab); r1.appendChild(inp);
    ctl.appendChild(r1); ctl.appendChild(go);
    var r2 = el("div", "widget-row"); r2.appendChild(ui.sample); r2.appendChild(rnd); r2.appendChild(run);
    var r3 = el("div", "widget-row"); r3.appendChild(np); r3.appendChild(rc);

    ui.proc = el("p", "vm-proc");
    ui.status = el("p", "vm-status widget-out", "Pick an address and press Translate.");
    ui.status.id = "vm-status";
    ui.status.setAttribute("role", "status");
    ui.status.setAttribute("aria-live", "polite");
    ui.steps = el("ol", "vm-steps");
    ui.counters = el("div", "vm-counters");

    ui.tlb = el("div", "vm-tlb");
    ui.ram = el("div", "vm-ram");
    var panels = el("div", "vm-panels");
    var p1 = el("div", "vm-panel"); p1.appendChild(el("h5", "vm-h", "TLB (4 entries, oldest replaced first)")); p1.appendChild(ui.tlb);
    var p2 = el("div", "vm-panel"); p2.appendChild(el("h5", "vm-h", "RAM: 8 physical frames")); p2.appendChild(ui.ram);
    panels.appendChild(p1); panels.appendChild(p2);

    ui.pt = el("div", "vm-pt");
    var legend = el("p", "vm-legend");
    ["m", "n", "d", "u"].forEach(function (k) {
      var s = el("span", "vm-key vm-" + k, STATE_LABEL[k]);
      legend.appendChild(s);
    });
    ui.hist = el("div", "vm-hist");

    var ptWrap = el("div", "vm-panel");
    ptWrap.appendChild(el("h5", "vm-h", "Page table (click a page to aim at it)"));
    ptWrap.appendChild(legend);
    ptWrap.appendChild(ui.pt);
    var hWrap = el("div", "vm-panel");
    hWrap.appendChild(el("h5", "vm-h", "Last accesses"));
    hWrap.appendChild(ui.hist);

    [ctl, r2, r3, ui.proc, ui.status, ui.steps, ui.counters, panels, ptWrap, hWrap].forEach(function (n) { root.appendChild(n); });

    go.addEventListener("click", doTranslate);
    inp.addEventListener("keydown", function (ev) { if (ev.key === "Enter") { ev.preventDefault(); doTranslate(); } });
    ui.sample.addEventListener("change", function () {
      if (ui.sample.value) { inp.value = ui.sample.value; doTranslate(); }
    });
    rnd.addEventListener("click", function () {
      var cands = [], v;
      for (v = 0; v < NPAGES; v++) if (state.pt[v].s !== "u") cands.push(v);
      var vpn = (Math.random() < 0.1 || !cands.length) ? Math.floor(Math.random() * NPAGES) : cands[Math.floor(Math.random() * cands.length)];
      inp.value = "0x" + hex((vpn << 12) | Math.floor(Math.random() * PAGE), 4);
      doTranslate();
    });
    run.addEventListener("click", function () {
      var pages = [], v, last = null, i;
      for (v = 0; v < NPAGES; v++) if (state.pt[v].s !== "u") pages.push(v);
      for (i = 0; i < 10; i++) {
        var vpn = (i > 0 && Math.random() < 0.7) ? state.lastVpn : pages[Math.floor(Math.random() * pages.length)];
        last = translate((vpn << 12) | Math.floor(Math.random() * PAGE));
      }
      if (last) { inp.value = "0x" + hex(last.va, 4); }
      render("Ran 10 accesses with some locality (70% repeat the previous page). Last one: " + summary(last));
    });
    np.addEventListener("click", function () {
      loadProc((state.pi + 1) % PROCS.length);
      state.hist = [];
      inp.value = "0x0123";
      render("Switched to " + PROCS[state.pi].name + ". It has a different page table, and the TLB was flushed. Now translate 0x0123 and compare the physical address with the other processes.");
    });
    rc.addEventListener("click", function () {
      c.total = c.hit = c.miss = c.minor = c.major = c.segv = 0;
      state.hist = [];
      render("Counters reset.");
    });
  }

  function parseInput() {
    var s = ui.input.value.trim().replace(/^0x/i, "");
    if (!/^[0-9a-fA-F]{1,4}$/.test(s)) return -1;
    return parseInt(s, 16);
  }

  function doTranslate() {
    var va = parseInput();
    if (va < 0) {
      ui.status.textContent = "Please type 1 to 4 hex digits (0 to F), for example 0x3A7C. This toy only has 16-bit addresses.";
      ui.status.className = "vm-status widget-out vm-s-bad";
      ui.input.focus();
      return;
    }
    var r = translate(va);
    render(summary(r));
  }

  /* ---------- rendering ---------- */
  function addBits(parent, va) {
    var b = el("div", "vm-bits");
    var v = el("span", "vm-vpn", bin(va >> 12, 4));
    var o = el("span", "vm-off", group4(bin(va & 0xFFF, 12)));
    b.appendChild(v); b.appendChild(el("span", "vm-sep", " | ")); b.appendChild(o);
    parent.appendChild(b);
    var lab = el("div", "vm-bitlabel");
    lab.appendChild(el("span", "vm-vpn", "page " + (va >> 12)));
    lab.appendChild(document.createTextNode("  "));
    lab.appendChild(el("span", "vm-off", "offset 0x" + hex(va & 0xFFF, 3)));
    parent.appendChild(lab);
  }

  function renderSteps() {
    ui.steps.textContent = "";
    var r = state.last;
    if (!r) return;
    r.steps.forEach(function (st) {
      var li = el("li", "vm-step" + (st.cls ? " vm-" + st.cls : ""));
      li.appendChild(el("strong", "", st.h + ": "));
      li.appendChild(document.createTextNode(st.t));
      if (st.split !== undefined) addBits(li, st.split);
      if (st.phys) {
        var b = el("div", "vm-bits");
        b.appendChild(el("span", "vm-frame", bin(st.phys.pfn, 3)));
        b.appendChild(el("span", "vm-sep", " | "));
        b.appendChild(el("span", "vm-off", group4(bin(st.phys.off, 12))));
        li.appendChild(b);
        var lab = el("div", "vm-bitlabel", "physical address 0x" + hex(st.phys.pa, 4) + " (15 bits: 3-bit frame number + 12-bit offset)");
        li.appendChild(lab);
      }
      ui.steps.appendChild(li);
    });
  }

  function renderCounters() {
    ui.counters.textContent = "";
    var items = [
      ["translations", c.total, ""],
      ["TLB hits", c.hit, "green"],
      ["TLB misses", c.miss, "blue"],
      ["minor faults", c.minor, "yellow"],
      ["major faults", c.major, "purple"],
      ["segfaults", c.segv, "red"],
      ["TLB hit rate", pct(c.hit, c.total), ""]
    ];
    items.forEach(function (it) {
      var p = el("span", "pill " + it[2]);
      p.appendChild(document.createTextNode(it[0] + ": "));
      p.appendChild(el("strong", "", String(it[1])));
      ui.counters.appendChild(p);
    });
  }

  function renderTlb() {
    ui.tlb.textContent = "";
    var last = state.last;
    for (var i = 0; i < TLB_SIZE; i++) {
      var e = state.tlb[i];
      var row = el("div", "vm-trow" + (e && last && e.vpn === last.vpn ? " vm-hot" : ""));
      if (e) {
        row.appendChild(el("span", "", "page " + e.vpn));
        row.appendChild(el("span", "vm-arrow", "→"));
        row.appendChild(el("span", "", "frame " + e.pfn));
      } else {
        row.appendChild(el("span", "vm-empty", "(empty)"));
      }
      ui.tlb.appendChild(row);
    }
  }

  function renderRam() {
    ui.ram.textContent = "";
    var owner = {};
    state.pt.forEach(function (e, v) { if (e.s === "m") owner[e.f] = v; });
    var last = state.last;
    for (var f = 0; f < NFRAMES; f++) {
      var used = owner[f] !== undefined;
      var b = el("div", "vm-frame-box" + (used ? " vm-m" : " vm-free") + (last && last.pfn === f ? " vm-hot" : ""));
      b.appendChild(el("span", "vm-fn", "F" + f));
      b.appendChild(el("span", "vm-fo", used ? "page " + owner[f] : "free"));
      ui.ram.appendChild(b);
    }
  }

  function renderPt() {
    ui.pt.textContent = "";
    var last = state.last;
    state.pt.forEach(function (e, v) {
      var b = el("button", "vm-cell vm-" + e.s + (last && last.vpn === v ? " vm-hot" : ""));
      b.type = "button";
      b.appendChild(el("span", "vm-cn", "page " + v));
      b.appendChild(el("span", "vm-cs", e.s === "m" ? "→ F" + e.f : STATE_LABEL[e.s]));
      b.setAttribute("aria-label", "Page " + v + ": " + (e.s === "m" ? "in frame " + e.f : STATE_LABEL[e.s]) + ". Press to aim at this page.");
      b.addEventListener("click", function () {
        var off = parseInput();
        off = off < 0 ? 0x123 : (off & 0xFFF);
        ui.input.value = "0x" + hex((v << 12) | off, 4);
        ui.input.focus();
        ui.status.textContent = "Address set to " + ui.input.value + " (page " + v + "). Press Translate.";
        ui.status.className = "vm-status widget-out";
      });
      ui.pt.appendChild(b);
    });
  }

  function renderHist() {
    ui.hist.textContent = "";
    if (!state.hist.length) { ui.hist.appendChild(el("span", "vm-empty", "nothing yet")); return; }
    state.hist.forEach(function (h) {
      var s = el("span", "vm-chip vm-k-" + h.kind);
      s.textContent = "0x" + hex(h.va, 4) + " " + KIND_LABEL[h.kind];
      ui.hist.appendChild(s);
    });
  }

  function refreshSamples() {
    var sel = ui.sample;
    sel.textContent = "";
    var o0 = el("option", "", "Pick a sample address...");
    o0.value = ""; sel.appendChild(o0);
    var firstOf = {};
    state.pt.forEach(function (e, v) { if (firstOf[e.s] === undefined) firstOf[e.s] = v; });
    var desc = { m: "page in RAM", n: "untouched page", d: "page on disk", u: "unmapped page" };
    ["m", "n", "d", "u"].forEach(function (k) {
      if (firstOf[k] === undefined) return;
      var v = firstOf[k], a = (v << 12) | 0xA30;
      var o = el("option", "", "0x" + hex(a, 4) + "  (" + desc[k] + ")");
      o.value = "0x" + hex(a, 4);
      sel.appendChild(o);
    });
    var o = el("option", "", "0x0123  (same address in every process)");
    o.value = "0x0123"; sel.appendChild(o);
    sel.value = "";
  }

  function render(msg) {
    var p = PROCS[state.pi];
    ui.proc.textContent = p.name + " (PID " + p.pid + "). Its page table is below. The TLB belongs to the CPU, so this toy flushes it whenever we switch process. For simplicity the RAM panel shows only this process's pages, as if it had all 8 frames to itself.";
    ui.status.textContent = msg;
    var kind = state.last && msg === summary(state.last) ? state.last.kind : "";
    ui.status.className = "vm-status widget-out" + (kind === "segv" ? " vm-s-bad" : kind === "hit" ? " vm-s-ok" : "");
    renderSteps(); renderCounters(); renderTlb(); renderRam(); renderPt(); renderHist(); refreshSamples();
  }

  build();
  loadProc(0);
  render("Pick an address and press Translate. Try 0x0123 first, then again, then use New process and repeat.");
})();
