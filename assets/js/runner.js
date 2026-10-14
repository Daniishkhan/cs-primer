/* Runnable code cells. Loaded by main.js (loadRunner) on pages with *.py blocks.

   Each <pre data-title="*.py"> becomes a cell: a header (filename, Copy, Edit,
   Run), the code, and an output area that holds the page's printed output (the
   <pre data-title="output"> right after it) plus the reader's own run.

   Nothing is fetched until the reader asks: CodeMirror (vendored) loads on the
   first Edit, Python (Pyodide, from jsDelivr, ~10 MB, cached by the browser)
   on the first Run. Python runs in a Web Worker so a slow or endless script can
   be stopped; if the browser refuses the worker it runs on the page instead.
*/
(function () {
  "use strict";

  var NZ = window.NZ || {};
  var ASSETS = NZ.assets || "";
  var PYODIDE = "https://cdn.jsdelivr.net/pyodide/v0.26.4/full/";
  var SLOW_S = 10;           // after this, remind the reader that Stop exists
  var LIMIT_S = 180;         // safety net for a script that never ends
  var BOOT_S = 90;           // give up on a download that has stalled
  var RUN_DIR = "/home/pyodide/run";

  // Scripts that need a real operating system (processes, threads, sockets,
  // signals, system files) or what browser Python lacks (asyncio.run inside
  // the page's event loop, OpenSSL-only hashlib functions) offer Copy only.
  function osOnly(modules) {
    return new RegExp([
      "^[ \\t]*(?:import|from)[ \\t][^\\n]*\\b(?:" + modules.join("|") + ")\\b"
    ].concat(OS_CALLS).join("|"), "m");
  }
  var OS_MODULES = ["socket", "subprocess", "threading", "multiprocessing", "signal", "select",
                    "selectors", "mmap", "fcntl", "resource", "ctypes", "concurrent\\.futures"];
  var OS_CALLS = [
    /\bos\.(?:fork|fsync|fdatasync|kill|pipe|getpid|getppid|wait|_exit)\b/.source,
    /\basyncio\.run\(/.source,
    /\bhashlib\.(?:pbkdf2_hmac|scrypt)\b/.source,
    /\bopen\(\s*["']\/(?:etc|proc|sys|dev)\//.source,
    /\binput\(/.source
  ];
  var OS_ONLY = osOnly(OS_MODULES);
  // Lab checkers import signal only for an alarm-based timeout guarded by
  // hasattr(signal, "SIGALRM"), which browser Python skips; allow it there.
  var OS_ONLY_LAB = osOnly(OS_MODULES.filter(function (m) { return m !== "signal"; }));

  // A script's title starts with its filename ("demo1.py (uses lin.py, below)");
  // titles like "python3 x.py" are terminal transcripts, not code.
  var SCRIPT_TITLE = /^([\w.-]+\.py)(?:\s|$)/;

  /* ---------- small helpers ---------- */

  function el(tag, attrs, children) {
    var n = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (k === "text") n.textContent = attrs[k];
      else if (attrs[k] !== false && attrs[k] != null) n.setAttribute(k, attrs[k]);
    });
    (children || []).forEach(function (c) { if (c) n.appendChild(c); });
    return n;
  }
  function load(key) { try { return localStorage.getItem(key); } catch (e) { return null; } }
  function save(key, v) {
    try {
      if (v == null) localStorage.removeItem(key);
      else localStorage.setItem(key, v);
    } catch (e) { /* storage unavailable: edits just don't persist */ }
  }
  function loadScript(src) {
    return new Promise(function (ok, fail) {
      var s = el("script", { src: src });
      s.onload = ok;
      s.onerror = function () { fail(new Error("could not load " + src)); };
      document.head.appendChild(s);
    });
  }
  function loadCss(href) {
    if (document.querySelector('link[href="' + href + '"]')) return;
    document.head.appendChild(el("link", { rel: "stylesheet", href: href }));
  }
  function highlight(pre, src) {
    var code = pre.querySelector("code") || pre;
    if (NZ.highlightPython) code.innerHTML = NZ.highlightPython(src);
    else code.textContent = src;
  }
  function norm(s) { return s.replace(/[ \t]+$/gm, "").replace(/\s+$/, ""); }
  function button(cls, icon, label, title) {
    return el("button", { type: "button", class: "cell-btn " + cls, title: title, "aria-label": label }, [
      el("span", { class: "cell-btn-icon", "aria-hidden": "true", text: icon }),
      el("span", { class: "cell-btn-label", text: label })
    ]);
  }

  // Shell-like split: spaces separate, quotes group ("a b" 'c d').
  function splitArgs(s) {
    var out = [];
    s.replace(/"([^"]*)"|'([^']*)'|(\S+)/g, function (_, a, b, c) { out.push(a != null ? a : b != null ? b : c); });
    return out;
  }

  // The first "python3 name.py args" in the page's code (not its prose) with
  // literal arguments: "python3 smr_nondet.py naive" gives "naive".
  function exampleArgs(name) {
    var re = new RegExp("python3?\\s+" + name.replace(/\./g, "\\.") + "[ \\t]+([^\\n$<>|;&,#]+)");
    var code = document.querySelectorAll("article pre, article code");
    for (var i = 0; i < code.length; i++) {
      var m = re.exec(code[i].textContent);
      if (m) return m[1].trim();
    }
    return "";
  }

  /* ---------- the Python engine (one per page, shared by all cells) ---------- */

  // Runs inside Pyodide: a fresh __main__ per run, sibling blocks importable,
  // and tracebacks trimmed to the reader's own files.
  var PY_RUN = [
    "import os, sys, runpy, traceback",
    "FAILED = ''",
    "os.chdir(RUN_DIR)",
    "sys.argv = list(ARGV)",
    "if RUN_DIR not in sys.path: sys.path.insert(0, RUN_DIR)",
    "for _n in list(sys.modules):",
    "    if _n in MODULES: del sys.modules[_n]",
    "try:",
    "    runpy.run_path(TARGET, run_name='__main__')",
    "except SystemExit as e:",
    "    if e.code not in (None, 0): print(f'exit status {e.code}', file=sys.stderr)",
    "except BaseException as e:",
    "    frames = [f for f in traceback.extract_tb(e.__traceback__) if f.filename.startswith(RUN_DIR)]",
    "    listing = ''.join(traceback.format_list(frames)).replace(RUN_DIR + '/', '')",
    "    FAILED = 'Traceback (most recent call last):\\n' + listing + ''.join(traceback.format_exception_only(type(e), e))",
    "finally:",
    "    sys.stdout.flush(); sys.stderr.flush()"
  ].join("\n");

  // Shared by the worker and the on-page fallback: given a loaded pyodide and a
  // job, write the files, load any packages they import, run, report via emit.
  function runJob(py, job, emit) {
    var dec = { out: new TextDecoder(), err: new TextDecoder() };
    function stream(kind) {
      return { write: function (buf) { emit(kind, dec[kind].decode(buf, { stream: true })); return buf.length; } };
    }
    py.setStdout(stream("out"));
    py.setStderr(stream("err"));
    try { py.FS.mkdirTree(job.dir); } catch (e) { /* exists */ }
    job.files.forEach(function (f) {
      var path = job.dir + "/" + f.name;
      var slash = path.lastIndexOf("/");
      try { py.FS.mkdirTree(path.slice(0, slash)); } catch (e) { /* exists */ }
      py.FS.writeFile(path, f.src);
    });
    var all = job.files.map(function (f) { return f.src; }).join("\n");
    // zoneinfo needs the time-zone database, which is a separate package.
    var extra = /\bzoneinfo\b/.test(all) ? py.loadPackage("tzdata") : Promise.resolve();
    return extra
      .then(function () { return py.loadPackagesFromImports(all); })
      .then(function () {
        var g = py.globals;
        g.set("RUN_DIR", job.dir);
        g.set("TARGET", job.dir + "/" + job.name);
        g.set("ARGV", py.toPy(job.argv || [job.name]));
        g.set("MODULES", py.toPy(job.files.filter(function (f) { return /^[\w-]+\.py$/.test(f.name); })
          .map(function (f) { return f.name.replace(/\.py$/, ""); })));
        return py.runPythonAsync(job.code);
      })
      .then(function () {
        // An uncaught exception is reported separately from ordinary stderr
        // (unittest, warnings), so only real failures are shown as errors.
        emit("exc", py.globals.get("FAILED"));
      });
  }

  var WORKER_SRC = [
    'importScripts("' + PYODIDE + 'pyodide.js");',
    'var ready = loadPyodide({ indexURL: "' + PYODIDE + '" });',
    "var runJob = " + runJob.toString() + ";",
    "ready.then(function () { postMessage({ kind: 'ready' }); },",
    "           function (e) { postMessage({ kind: 'fail', text: String(e && e.message || e) }); });",
    "self.onmessage = function (m) {",
    "  var job = m.data;",
    "  function emit(kind, text) { if (text) postMessage({ id: job.id, kind: kind, text: text }); }",
    "  ready.then(function (py) { return runJob(py, job, emit); })",
    "    .then(function () { postMessage({ id: job.id, kind: 'done' }); },",
    "          function (e) { postMessage({ id: job.id, kind: 'exc', text: String(e && e.message || e) + '\\n' });",
    "                         postMessage({ id: job.id, kind: 'done' }); });",
    "};"
  ].join("\n");

  var engine = {
    worker: null,
    pending: null,        // a worker still downloading Python
    page: null,           // pyodide on the main thread (fallback)
    mode: null,           // "worker" | "page"
    booting: null,        // promise until Python is ready
    current: null,        // the running job's handlers
    nextId: 1,

    start: function () {
      if (this.booting) return this.booting;
      var self = this;
      var boot = this.startWorker().catch(function () { return self.startPage(); });
      var stalled = new Promise(function (_, fail) {
        setTimeout(function () { fail(new Error("the download stalled")); }, BOOT_S * 1000);
      });
      this.booting = Promise.race([boot, stalled]).catch(function (e) {
        // Forget the failed attempt so the next Run starts over.
        if (self.pending) self.pending.terminate();
        if (self.worker) self.worker.terminate();
        self.pending = null;
        self.worker = null;
        self.mode = null;
        self.booting = null;
        throw e;
      });
      return this.booting;
    },

    startWorker: function () {
      var self = this;
      return new Promise(function (ok, fail) {
        var w;
        try {
          var url = URL.createObjectURL(new Blob([WORKER_SRC], { type: "text/javascript" }));
          w = new Worker(url);
        } catch (e) { fail(e); return; }
        self.pending = w;
        w.onerror = function (e) {
          if (self.mode !== "worker") { w.terminate(); fail(e); return; }
          // The worker died mid-run: report it and let the next Run boot a new one.
          if (self.current) self.current.emit("exc", "Python stopped unexpectedly.\n");
          self.stop();
        };
        w.onmessage = function (m) {
          var d = m.data;
          if (d.kind === "ready") { self.worker = w; self.pending = null; self.mode = "worker"; ok(); return; }
          if (d.kind === "fail") { w.terminate(); fail(new Error(d.text)); return; }
          var job = self.current;
          if (!job || d.id !== job.id) return;
          if (d.kind === "done") self.finish();
          else job.emit(d.kind, d.text);
        };
      });
    },

    startPage: function () {
      var self = this;
      return loadScript(PYODIDE + "pyodide.js")
        .then(function () { return window.loadPyodide({ indexURL: PYODIDE }); })
        .then(function (py) { self.page = py; self.mode = "page"; });
    },

    run: function (job, emit) {
      var self = this;
      job.id = this.nextId++;
      job.code = PY_RUN;
      return new Promise(function (ok) {
        self.current = { id: job.id, emit: emit, done: ok };
        if (self.mode === "worker") { self.worker.postMessage(job); return; }
        // Fallback: on the page, so no Stop; yield a frame first so "running" paints.
        setTimeout(function () {
          runJob(self.page, job, emit)
            .catch(function (e) { emit("exc", String(e && e.message || e) + "\n"); })
            .then(function () { self.finish(); });
        }, 30);
      });
    },

    finish: function () {
      var job = this.current;
      this.current = null;
      if (job) job.done();
    },

    canStop: function () { return this.mode === "worker"; },

    // Killing the worker is the only reliable way to stop running Python; the
    // next Run boots a fresh one (fast: the files are in the browser cache).
    stop: function () {
      if (this.mode !== "worker") return;
      this.worker.terminate();
      this.worker = null;
      this.mode = null;
      this.booting = null;
      this.finish();
    }
  };

  /* ---------- CodeMirror (vendored, loaded on first Edit) ---------- */

  var cmReady = null;
  function loadEditor() {
    if (cmReady) return cmReady;
    var base = ASSETS + "vendor/codemirror/";
    loadCss(base + "codemirror.min.css");
    cmReady = loadScript(base + "codemirror.min.js").then(function () {
      return Promise.all([
        loadScript(base + "python.min.js"),
        loadScript(base + "matchbrackets.min.js"),
        loadScript(base + "closebrackets.min.js")
      ]);
    });
    return cmReady;
  }

  /* ---------- cells ---------- */

  var pageFiles = [];       // every *.py block on the page, in order: {name, cell}

  // opts (lab workspaces): run  - the file Run executes instead of this one
  //                         extra - hidden files written alongside, {name, src}
  //                         label - the Run button's label
  //                         local - a reason this cell cannot run in the page
  function Cell(pre, index, opts) {
    opts = opts || {};
    this.pre = pre;
    this.title = pre.getAttribute("data-title");
    this.name = SCRIPT_TITLE.exec(this.title)[1];
    this.target = opts.run || this.name;
    this.extra = opts.extra || [];
    this.runLabel = opts.label || "Run";
    this.original = (pre.querySelector("code") || pre).textContent;
    // Saved edits are keyed by file name (and which copy of it on the page),
    // so adding or reordering other blocks does not lose them.
    var copy = pageFiles.filter(function (f) { return f.cell.title === this.title; }, this).length;
    this.key = "nz-code:" + location.pathname + ":" + this.title + (copy ? ":" + copy : "");
    var legacy = "nz-code:" + location.pathname + ":" + index + ":" + this.title;
    if (load(this.key) == null && load(legacy) != null) {
      save(this.key, load(legacy));
      save(legacy, null);
    }
    this.cm = null;
    this.running = false;
    this.runnable = pre.getAttribute("data-run") !== "off" && !opts.local && !OS_ONLY.test(this.original);
    this.localReason = opts.local;
    this.build();
    var saved = load(this.key);
    if (saved != null && saved !== this.original) this.setCode(saved);
    this.refreshEdited();
  }

  Cell.prototype.code = function () {
    if (this.cm) return this.cm.getValue();
    return this.current != null ? this.current : this.original;
  };

  Cell.prototype.setCode = function (src) {
    this.current = src;
    if (this.cm) this.cm.setValue(src);
    else highlight(this.pre, src);
  };

  Cell.prototype.build = function () {
    var pre = this.pre;
    var next = pre.nextElementSibling;
    var printed = next && next.tagName === "PRE" && /output/i.test(next.getAttribute("data-title") || "") ? next : null;

    this.copyBtn = button("", "⧉", "Copy", "Copy the code");
    this.resetBtn = button("", "↺", "Reset", "Undo your edits");
    this.editBtn = button("", "✎", "Edit", "Edit the code (changes stay in this browser)");
    this.runBtn = button("run", "▶", this.runLabel, this.target === this.name
      ? "Run in your browser (Ctrl/⌘ + Enter while editing)"
      : "Run " + this.target + " against this file, in your browser (Ctrl/⌘ + Enter while editing)");
    this.editedPill = el("span", { class: "cell-edited", text: "edited" });

    var actions = [this.copyBtn];
    var argvSrc = this.target === this.name ? this.original
      : (this.extra.filter(function (f) { return f.name === this.target; }, this)[0] || {}).src || "";
    if (this.runnable && /\bsys\.argv\b/.test(argvSrc)) {
      // The script reads command-line arguments: offer a field, prefilled
      // from the page's own "python3 name.py ..." example when there is one.
      this.argsInput = el("input", {
        type: "text", class: "cell-args-input", spellcheck: "false",
        "aria-label": "Command-line arguments", placeholder: "arguments",
        value: this.target === this.name ? exampleArgs(this.name) : ""
      });
      actions.push(el("label", { class: "cell-args", title: "Command-line arguments (sys.argv)" }, [
        el("span", { class: "cell-args-label", text: "args" }), this.argsInput
      ]));
      var cell = this;
      this.argsInput.addEventListener("keydown", function (e) {
        if (e.key === "Enter" && !cell.running) cell.run();
      });
    }
    if (this.runnable) actions.push(this.resetBtn, this.editBtn, this.runBtn);
    else actions.push(el("span", {
      class: "cell-local", text: "run locally",
      title: this.localReason || "Uses operating-system features (processes, threads, sockets, files) that a browser cannot provide. Copy it and run it with python3."
    }));

    // The result of a run, next to the button that started it; click to jump
    // to the output (which can be far below a long script).
    this.chip = el("button", { type: "button", class: "cell-chip", hidden: "", title: "Show the output" });
    if (this.runnable) actions.unshift(this.chip);

    this.head = el("div", { class: "cell-head" }, [
      el("span", { class: "cell-dots", "aria-hidden": "true" }),
      el("span", { class: "cell-title", text: this.title }),
      this.editedPill,
      el("span", { class: "cell-actions" }, actions)
    ]);

    this.cell = el("div", { class: "code-cell" + (this.runnable ? "" : " is-local") });
    pre.parentNode.insertBefore(this.cell, pre);
    this.cell.appendChild(this.head);
    this.cell.appendChild(pre);
    pre.classList.add("cell-code");

    // Output: the printed output (if the page has one) and the reader's run.
    this.tabPrinted = el("button", { type: "button", role: "tab", class: "cell-tab", "aria-selected": "true", text: "Printed" });
    this.tabLive = el("button", { type: "button", role: "tab", class: "cell-tab", "aria-selected": "false", text: "Your run" });
    this.status = el("span", { class: "cell-status", "aria-live": "polite" });
    this.live = el("pre", { class: "cell-live", hidden: "" }, [el("code")]);
    this.printed = printed;
    this.out = el("div", { class: "cell-out", hidden: printed ? false : "" }, [
      el("div", { class: "cell-out-head" }, [
        el("span", { class: "cell-out-label", text: "Output" }),
        this.tabs = el("span", { class: "cell-tabs", role: "tablist", hidden: "" }, [printed ? this.tabPrinted : null, this.tabLive]),
        this.status
      ]),
      printed,
      this.live
    ]);
    this.tabLive.hidden = true;
    if (printed) printed.classList.add("cell-printed");
    this.cell.appendChild(this.out);

    var self = this;
    this.copyBtn.addEventListener("click", function () { self.copy(); });
    this.resetBtn.addEventListener("click", function () { self.reset(); });
    this.editBtn.addEventListener("click", function () { self.toggleEdit(); });
    this.runBtn.addEventListener("click", function () { self.running ? engine.stop() : self.run({ reveal: true }); });
    this.chip.addEventListener("click", function () { self.revealOutput(true); });
    this.tabPrinted.addEventListener("click", function () { self.show("printed"); });
    this.tabLive.addEventListener("click", function () { self.show("live"); });
  };

  Cell.prototype.show = function (which) {
    var live = which === "live";
    if (this.printed) this.printed.hidden = live;
    this.live.hidden = !live;
    this.tabPrinted.setAttribute("aria-selected", String(!live));
    this.tabLive.setAttribute("aria-selected", String(live));
  };

  Cell.prototype.refreshEdited = function () {
    var edited = norm(this.code()) !== norm(this.original);
    this.editedPill.hidden = !edited;
    this.resetBtn.hidden = !edited;
    this.cell.classList.toggle("is-edited", edited);
    return edited;
  };

  Cell.prototype.copy = function () {
    var text = this.code();
    var btn = this.copyBtn;
    function done() {
      btn.querySelector(".cell-btn-label").textContent = "Copied";
      setTimeout(function () { btn.querySelector(".cell-btn-label").textContent = "Copy"; }, 1400);
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done, fallback);
    } else fallback();
    function fallback() {
      var ta = el("textarea", { class: "cell-clip" });
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand("copy"); done(); } catch (e) { /* nothing more to try */ }
      ta.remove();
    }
  };

  Cell.prototype.reset = function () {
    save(this.key, null);
    this.setCode(this.original);
    this.current = null;
    this.refreshEdited();
    if (this.printed) this.show("printed");
  };

  Cell.prototype.toggleEdit = function () {
    var self = this;
    if (this.cm) {            // Done: back to the highlighted view of the current code
      var src = this.cm.getValue();
      this.cm.getWrapperElement().remove();
      this.cm = null;
      this.pre.hidden = false;
      this.setCode(src);
      this.setEditLabel("Edit");
      return;
    }
    this.setEditLabel("Loading…");
    loadEditor().then(function () {
      self.pre.hidden = true;
      var host = el("div", { class: "cell-editor" });
      self.pre.parentNode.insertBefore(host, self.pre);
      var run = function () { if (!self.running) self.run(); };
      self.cm = window.CodeMirror(host, {
        value: self.code(),
        mode: "python",
        theme: "site",
        lineNumbers: true,
        indentUnit: 4,
        tabSize: 4,
        indentWithTabs: false,
        matchBrackets: true,
        autoCloseBrackets: true,
        viewportMargin: Infinity,       // grow with the code instead of scrolling inside
        extraKeys: {
          "Ctrl-Enter": run, "Cmd-Enter": run, "Shift-Enter": run,
          Tab: function (cm) { cm.execCommand(cm.somethingSelected() ? "indentMore" : "insertSoftTab"); },
          Esc: function () { self.toggleEdit(); }
        }
      });
      // "# ── 1. Step ──" banners keep their highlighted look while editing.
      self.cm.addOverlay({
        token: function (stream) {
          if (stream.sol() && stream.match(/^\s*#\s*──.*$/)) return "section";
          stream.skipToEnd();
          return null;
        }
      });
      // The wrapper replaces the host so the editor sits directly in the cell.
      host.replaceWith(self.cm.getWrapperElement());
      self.cm.refresh();
      self.cm.on("change", function () {
        save(self.key, self.refreshEdited() ? self.cm.getValue() : null);
      });
      self.cm.focus();
      self.setEditLabel("Done");
    }, function () {
      self.setEditLabel("Edit");
      self.setStatus("err", "Could not load the editor.");
    });
  };

  Cell.prototype.setEditLabel = function (label) {
    this.editBtn.querySelector(".cell-btn-label").textContent = label;
    this.editBtn.querySelector(".cell-btn-icon").textContent = label === "Done" ? "✓" : "✎";
    this.editBtn.setAttribute("aria-pressed", String(label === "Done"));
  };

  var CHIP = { busy: "Running…", ok: "✓ Done", warn: "Stopped", err: "✕ Error" };

  Cell.prototype.setStatus = function (kind, text, chip) {
    this.status.className = "cell-status" + (kind ? " is-" + kind : "");
    this.status.textContent = text || "";
    this.chip.className = "cell-chip" + (kind ? " is-" + kind : "");
    this.chip.textContent = chip || CHIP[kind] || "";
    this.chip.hidden = !kind;
  };

  // Bring the output into view if it is off-screen (below a long script).
  Cell.prototype.revealOutput = function (always) {
    var r = this.out.getBoundingClientRect();
    var visible = r.top < window.innerHeight - 60 && r.bottom > 80;
    if (visible && !always) return;
    var still = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    this.out.scrollIntoView({ behavior: still ? "auto" : "smooth", block: "start" });
  };

  Cell.prototype.setRunning = function (on) {
    this.running = on;
    this.cell.classList.toggle("is-running", on);
    var stop = on && engine.canStop();
    this.runBtn.querySelector(".cell-btn-icon").textContent = stop ? "■" : "▶";
    this.runBtn.querySelector(".cell-btn-label").textContent = stop ? "Stop" : this.runLabel;
    this.runBtn.disabled = on && !stop;
    pageFiles.forEach(function (f) { if (f.cell !== this && f.cell.runBtn) f.cell.runBtn.disabled = on; }, this);
  };

  Cell.prototype.run = function (opts) {
    var self = this;
    var reveal = opts && opts.reveal;
    var src = this.code();
    var code = this.live.querySelector("code");
    code.textContent = "";
    this.out.hidden = false;
    this.tabLive.hidden = false;
    this.tabs.hidden = !this.printed;     // a lone "Your run" tab says nothing
    this.show("live");
    this.setRunning(true);
    this.live.classList.remove("is-fresh");
    if (reveal) this.revealOutput(false);

    // Every script on the page is written alongside, so one can import another
    // (toolkit.py above, lin.py "listed below"), exactly as in a folder.
    var name = this.name;
    // A lab workspace runs its own folder only; snippets elsewhere on the
    // page (often titled solution.py) must not overwrite the real files.
    var files = this.extra.length
      ? this.extra.filter(function (f) { return f.name !== name; })
      : pageFiles
        .filter(function (f) { return f.name !== name && !f.cell.extra.length; })
        .map(function (f) { return { name: f.name, src: f.cell.code() }; });
    // A file shown in parts ("paxos_sim.py (part 2: ...)") runs as one file.
    var parts = pageFiles.filter(function (f) { return f.name === name; });
    if (parts.length > 1 && !this.extra.length) src = parts.map(function (f) { return f.cell.code(); }).join("\n\n");
    files.push({ name: name, src: src });
    var target = this.target;
    var argv = [target].concat(this.argsInput ? splitArgs(this.argsInput.value) : []);

    // Output arrives in many small pieces; paint at most once a frame.
    var pending = "";
    var painting = false;
    var stdout = "";
    var failed = false;
    function paint() {
      painting = false;
      code.insertAdjacentHTML("beforeend", pending);
      pending = "";
    }
    function emit(kind, text) {
      if (!text) return;
      var safe = text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
      if (kind === "out") stdout += text;
      else if (kind === "exc") { failed = true; safe = '<span class="cell-exc">' + safe + "</span>"; }
      else safe = '<span class="cell-stderr">' + safe + "</span>";
      pending += safe;
      if (!painting) { painting = true; requestAnimationFrame(paint); }
    }

    if (engine.mode) this.setStatus("busy", "Running…");
    else this.setStatus("busy", "Loading Python (about 10 MB, first run only)…", "Loading Python…");
    var slow = null;
    var limit = null;
    var started = 0;
    var hitLimit = false;
    engine.start().then(function () {
      self.setRunning(true);            // Stop is available now that we know the mode
      self.setStatus("busy", "Running…");
      started = performance.now();
      slow = setTimeout(function () {
        self.setStatus("busy", engine.canStop() ? "Still running… (slower than native Python; Stop to cancel)" : "Still running…", "Still running…");
      }, SLOW_S * 1000);
      limit = setTimeout(function () { hitLimit = true; engine.stop(); }, LIMIT_S * 1000);
      return engine.run({ dir: RUN_DIR, name: target, files: files, argv: argv }, emit);
    }).then(function () {
      clearTimeout(slow);
      clearTimeout(limit);
      paint();
      self.setRunning(false);
      // A brief highlight, so even a one-number change is noticed.
      void self.live.offsetWidth;
      self.live.classList.add("is-fresh");
      var ms = performance.now() - started;
      var took = ms < 1000 ? Math.max(1, Math.round(ms)) + " ms" : (ms / 1000).toFixed(1) + " s";
      if (hitLimit) self.setStatus("warn", "Stopped after " + LIMIT_S / 60 + " minutes.");
      else if (!engine.mode) self.setStatus("warn", "Stopped.");
      else if (failed) self.setStatus("err", "Error · " + took, "✕ Error · see output");
      else if (self.printed && !self.refreshEdited()) {
        var same = norm(stdout) === norm(self.printed.textContent);
        self.setStatus(same ? "ok" : "warn", (same ? "✓ Matches the printed output" : "Differs from the printed output") + " · " + took,
                       same ? "✓ Matches · " + took : "Differs · " + took);
      } else self.setStatus("ok", "Done · " + took, "✓ Done · " + took);
    }, function (e) {
      clearTimeout(slow);
      clearTimeout(limit);
      self.setRunning(false);
      self.setStatus("err", "Python could not start (" + (e && e.message || "offline?") + "). Try again online, or copy the code and run it with python3.", "✕ Python could not start");
    });
  };

  /* ---------- lab workspaces ----------

     <div class="lab-workspace" data-dir="code/lab01/" data-files="check.py llm.py solution.py"></div>

     Fetches the lab's files, shows starter.py as an editable cell whose
     button runs check.py (args: "solution", a milestone number). Fetching
     needs the site served over http(s); from a file:// page it says so. */

  function fetchText(url) {
    return fetch(url).then(function (r) {
      if (!r.ok) throw new Error(r.status + " " + url);
      return r.text();
    });
  }

  function workspace(box) {
    var dir = box.getAttribute("data-dir");
    var edit = box.getAttribute("data-edit") || "starter.py";
    var names = (box.getAttribute("data-files") || "").split(/\s+/).filter(Boolean);
    var note = el("p", { class: "lab-ws-note", text: "Loading the lab's files…" });
    box.appendChild(note);
    if (location.protocol === "file:") {
      note.textContent = "To run this lab in the page, open the site over http: the published site, or "
        + "python3 -m http.server in the site folder and http://localhost:8000. "
        + "Or download the files above and run python3 check.py.";
      return Promise.resolve();
    }
    return Promise.all([edit].concat(names).map(function (n) { return fetchText(dir + n); }))
      .then(function (srcs) {
        var extra = names.map(function (n, i) { return { name: n, src: srcs[i + 1] }; });
        var all = srcs.join("\n");
        var local = OS_ONLY_LAB.test(all)
          ? "This lab uses operating-system features (processes, threads, sockets) that browser Python lacks. Download the files and run python3 check.py."
          : null;
        var pre = el("pre", { class: "terminal", "data-title": edit }, [el("code", { text: srcs[0] })]);
        note.remove();
        box.appendChild(pre);
        highlight(pre, srcs[0]);
        var cell = new Cell(pre, index++, { run: "check.py", extra: extra, label: "Check", local: local });
        pageFiles.push({ name: cell.name, cell: cell });
        if (local) box.classList.add("is-local");
      })
      .catch(function (e) {
        note.textContent = "Could not load the lab's files (" + e.message + "). Download them above and run python3 check.py.";
      });
  }

  /* ---------- go ---------- */

  var index = 0;
  document.querySelectorAll("article pre[data-title]").forEach(function (pre) {
    if (!SCRIPT_TITLE.test(pre.getAttribute("data-title"))) return;
    if (pre.closest(".widget, .code-cell, .lab-workspace")) return;
    var cell = new Cell(pre, index++);
    pageFiles.push({ name: cell.name, cell: cell });
  });
  document.querySelectorAll(".lab-workspace").forEach(workspace);
})();
