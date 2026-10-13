/* Quorum explorer (chapter 18).

   Model (deliberately simple):
   - One key, "x". Each replica stores a (version, value) pair.
   - A write is acknowledged once it has reached W replicas that are up. The
     other replicas are "slow": they do not have it until you press Sync.
   - A read contacts R replicas that are up and returns the highest version
     among them. It is "stale" if that is older than the latest acknowledged write.
   - A write or read that cannot reach enough replicas fails and changes nothing.

   Markup contract (see chapters/18-replication.html): #quorum-widget with
   #qr-n #qr-w #qr-r (range inputs), #qr-wmode #qr-rmode (selects),
   .qr-reps, .qr-status, .qr-banner, .qr-log, and buttons with data-act.
*/
(function () {
  "use strict";
  var root = document.getElementById("quorum-widget");
  if (!root) return;

  var $ = function (s) { return root.querySelector(s); };
  var nIn = $("#qr-n"), wIn = $("#qr-w"), rIn = $("#qr-r");
  var nOut = $("#qr-n-out"), wOut = $("#qr-w-out"), rOut = $("#qr-r-out");
  var wMode = $("#qr-wmode"), rMode = $("#qr-rmode");
  var repsBox = $(".qr-reps"), statusBox = $(".qr-status"), banner = $(".qr-banner"), logBox = $(".qr-log");
  if (!nIn || !wIn || !rIn || !repsBox || !statusBox || !banner || !logBox) return;

  var COLORS = ["red", "orange", "yellow", "green", "blue", "indigo", "violet", "pink", "teal", "gray"];
  var n, w, r, reps, latest, wSet, rSet, log;

  function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }

  function fresh() {
    reps = [];
    for (var i = 0; i < n; i++) reps.push({ up: true, ver: 0, val: "(none)" });
    latest = { ver: 0, val: "(none)" };
    wSet = []; rSet = []; log = [];
    setBanner("", "");
  }

  function readSliders(resetData) {
    n = clamp(+nIn.value, 1, 7);
    wIn.max = String(n); rIn.max = String(n);
    w = clamp(+wIn.value, 1, n); r = clamp(+rIn.value, 1, n);
    wIn.value = String(w); rIn.value = String(r);
    nOut.textContent = n; wOut.textContent = w; rOut.textContent = r;
    if (resetData) fresh();
    render();
  }

  function upList() {
    var u = [];
    for (var i = 0; i < reps.length; i++) if (reps[i].up) u.push(i);
    return u;
  }

  function pick(count, mode, pool) {
    var p = pool.slice();
    if (mode === "first") return p.slice(0, count);
    if (mode === "last") return p.slice(p.length - count);
    for (var i = p.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var t = p[i]; p[i] = p[j]; p[j] = t;
    }
    return p.slice(0, count).sort(function (a, b) { return a - b; });
  }

  function names(set) {
    return set.map(function (i) { return "R" + (i + 1); }).join(", ");
  }

  function addLog(text, cls) {
    log.unshift({ text: text, cls: cls || "" });
    if (log.length > 6) log.pop();
  }

  function setBanner(text, kind) {
    banner.textContent = text;
    banner.className = "qr-banner widget-out" + (kind ? " " + kind : "");
    banner.hidden = !text;
  }

  function doWrite() {
    var up = upList();
    wSet = []; rSet = [];
    if (up.length < w) {
      addLog("Write failed: only " + up.length + " replica(s) up, but W = " + w + " acknowledgements are needed. Nothing changed.", "bad");
      setBanner("Write rejected: not enough replicas are up (" + up.length + " up, W = " + w + ").", "bad");
      render(); return;
    }
    var targets = pick(w, wMode.value, up);
    var ver = latest.ver + 1, val = COLORS[(ver - 1) % COLORS.length];
    targets.forEach(function (i) { reps[i].ver = ver; reps[i].val = val; });
    latest = { ver: ver, val: val };
    wSet = targets;
    var late = up.length - targets.length;
    addLog("Wrote x = " + val + " (v" + ver + ") to " + names(targets) + ". Acknowledged by " + w + " replica(s)." + (late > 0 ? " The other " + late + " up replica(s) have not received it yet." : ""), "ok");
    setBanner("Write succeeded on " + names(targets) + ".", "ok");
    render();
  }

  function doRead() {
    var up = upList();
    wSet = []; rSet = [];
    if (up.length < r) {
      addLog("Read failed: only " + up.length + " replica(s) up, but R = " + r + " are needed.", "bad");
      setBanner("Read rejected: not enough replicas are up (" + up.length + " up, R = " + r + ").", "bad");
      render(); return;
    }
    var targets = pick(r, rMode.value, up);
    var best = reps[targets[0]];
    targets.forEach(function (i) { if (reps[i].ver > best.ver) best = reps[i]; });
    rSet = targets;
    var stale = best.ver < latest.ver;
    if (stale) {
      addLog("Read " + names(targets) + " and returned x = " + best.val + " (v" + best.ver + "). STALE: the latest write is x = " + latest.val + " (v" + latest.ver + ").", "bad");
      setBanner("Stale read! Returned v" + best.ver + " but the latest acknowledged write is v" + latest.ver + ". The read set and the write set did not overlap.", "bad");
    } else {
      addLog("Read " + names(targets) + " and returned x = " + best.val + " (v" + best.ver + "). Fresh.", "ok");
      setBanner("Fresh read: x = " + best.val + " (v" + best.ver + ").", "ok");
    }
    render();
  }

  function doSync() {
    var up = upList();
    wSet = []; rSet = [];
    if (!up.length) { addLog("Sync: no replicas are up.", "bad"); render(); return; }
    var best = reps[up[0]];
    up.forEach(function (i) { if (reps[i].ver > best.ver) best = reps[i]; });
    var best2 = { ver: best.ver, val: best.val };
    up.forEach(function (i) { reps[i].ver = best2.ver; reps[i].val = best2.val; });
    var note = best2.ver < latest.ver ? " (The newest write, v" + latest.ver + ", only lives on replicas that are down, so it cannot spread yet.)" : "";
    addLog("Sync: every replica that is up now holds v" + best2.ver + "." + note, "ok");
    setBanner("", "");
    render();
  }

  function toggleReplica(i) {
    reps[i].up = !reps[i].up;
    wSet = []; rSet = [];
    addLog("R" + (i + 1) + " is now " + (reps[i].up ? "back up" : "down") + ".", "");
    setBanner("", "");
    render();
  }

  function render() {
    // replicas
    repsBox.textContent = "";
    reps.forEach(function (rep, i) {
      var b = document.createElement("button");
      b.type = "button";
      var cls = "qr-rep " + (rep.up ? "up" : "down");
      if (rep.up && rep.ver === latest.ver && latest.ver > 0) cls += " latest";
      if (rep.up && rep.ver < latest.ver) cls += " behind";
      if (wSet.indexOf(i) !== -1) cls += " inW";
      if (rSet.indexOf(i) !== -1) cls += " inR";
      b.className = cls;
      b.setAttribute("aria-pressed", String(rep.up));
      b.setAttribute("aria-label", "Replica R" + (i + 1) + ", " + (rep.up ? "up" : "down") + ", holds x = " + rep.val + " version " + rep.ver + ". Press to take it " + (rep.up ? "down" : "up") + ".");
      var nm = document.createElement("span"); nm.className = "nm"; nm.textContent = "R" + (i + 1);
      var st = document.createElement("span"); st.className = "st"; st.textContent = rep.up ? "up" : "DOWN";
      var vl = document.createElement("span"); vl.className = "vl"; vl.textContent = "x = " + rep.val;
      var vv = document.createElement("span"); vv.className = "vv"; vv.textContent = "v" + rep.ver;
      var tags = document.createElement("span"); tags.className = "tg";
      tags.textContent = (wSet.indexOf(i) !== -1 ? "WROTE " : "") + (rSet.indexOf(i) !== -1 ? "READ" : "");
      b.appendChild(nm); b.appendChild(st); b.appendChild(vl); b.appendChild(vv); b.appendChild(tags);
      b.addEventListener("click", function () { toggleReplica(i); });
      repsBox.appendChild(b);
    });

    // status
    var up = upList().length;
    var sum = r + w;
    statusBox.textContent = "";
    function row(label, text, kind) {
      var d = document.createElement("div"); d.className = "qr-row";
      var l = document.createElement("span"); l.className = "lbl"; l.textContent = label;
      var p = document.createElement("span"); p.className = "pill " + kind; p.textContent = text;
      d.appendChild(l); d.appendChild(p);
      statusBox.appendChild(d);
    }
    row("Overlap rule", "R + W = " + r + " + " + w + " = " + sum + (sum > n ? " > " : " ≤ ") + "N = " + n + (sum > n ? "  → every read set overlaps every write set" : "  → read and write sets can miss each other"), sum > n ? "green" : "red");
    row("Fresh reads guaranteed?", sum > n ? "Yes, whenever a read succeeds" : "No: stale reads are possible", sum > n ? "green" : "red");
    row("Writes can succeed now?", up >= w ? "Yes (" + up + " up ≥ W = " + w + ")" : "No (" + up + " up < W = " + w + ")", up >= w ? "green" : "red");
    row("Reads can succeed now?", up >= r ? "Yes (" + up + " up ≥ R = " + r + ")" : "No (" + up + " up < R = " + r + ")", up >= r ? "green" : "red");
    row("Failures tolerated", "writes: " + (n - w) + " down · reads: " + (n - r) + " down", "blue");

    // log
    logBox.textContent = "";
    if (!log.length) {
      var li0 = document.createElement("li"); li0.textContent = "No operations yet. Write, then read."; logBox.appendChild(li0);
    }
    log.forEach(function (e) {
      var li = document.createElement("li");
      if (e.cls) li.className = e.cls;
      li.textContent = e.text;
      logBox.appendChild(li);
    });
  }

  function preset(nn, ww, rr) {
    nIn.value = String(nn); wIn.max = String(nn); rIn.max = String(nn);
    wIn.value = String(ww); rIn.value = String(rr);
    readSliders(true);
  }

  nIn.addEventListener("input", function () { readSliders(true); });
  wIn.addEventListener("input", function () { readSliders(false); });
  rIn.addEventListener("input", function () { readSliders(false); });

  root.addEventListener("click", function (ev) {
    var btn = ev.target.closest ? ev.target.closest("button[data-act]") : null;
    if (!btn || !root.contains(btn)) return;
    var act = btn.getAttribute("data-act");
    if (act === "write") doWrite();
    else if (act === "read") doRead();
    else if (act === "sync") doSync();
    else if (act === "reset") readSliders(true);
    else if (act === "preset") preset(+btn.getAttribute("data-n"), +btn.getAttribute("data-w"), +btn.getAttribute("data-r"));
  });

  preset(3, 2, 2);
})();
