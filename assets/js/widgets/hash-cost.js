/* Hash cost explorer (security chapter 5).

   Pick a password strength (in bits of entropy) and an attacker, and see the expected time to
   find the password by guessing, for each way of storing it. The model is deliberately simple:

     guesses/second for function F  =  attacker's fast-hash rate  x  (time of one SHA-256 / time of one F)

   Times per hash are editable. The defaults for SHA-256, PBKDF2 and scrypt were measured with
   Python's hashlib on the author's laptop (see the chapter's code); bcrypt and Argon2id are not in
   the Python standard library, so their defaults are labelled assumptions. The attacker presets
   other than "one CPU core of this kind" are order-of-magnitude ASSUMPTIONS, not measurements.
   "Measure PBKDF2 here" times crypto.subtle in your own browser, when available.
   Simplifications: the cost ratio treats all hardware as equally good at every function. In
   practice GPUs are relatively worse at memory-hard functions (scrypt, Argon2id), so for those the
   estimate errs on the attacker's side (the true time is longer). The expected time to find a
   password is half the search space. Human-chosen passwords are not uniformly random; the
   "breached list" row is a reminder that guessing order matters more than entropy formulas. */
(function () {
  "use strict";
  var root = document.getElementById("hash-cost");
  if (!root) return;
  function h(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }

  /* ms per hash. src: "measured" or "assumed" */
  var FUNCS = [
    { id: "sha",   name: "Salted SHA-256 (one fast hash)",        ms: 0.0002, src: "measured" },
    { id: "pbk",   name: "PBKDF2-HMAC-SHA256, 600,000 iterations", ms: 43.2,   src: "measured" },
    { id: "bc",    name: "bcrypt, cost 10",                        ms: 60,     src: "assumed" },
    { id: "s14",   name: "scrypt N=2^14, r=8, p=1 (16 MiB)",       ms: 22.9,   src: "measured" },
    { id: "s17",   name: "scrypt N=2^17, r=8, p=1 (128 MiB)",      ms: 183.8,  src: "measured" },
    { id: "argon", name: "Argon2id, m=19 MiB, t=2, p=1",           ms: 30,     src: "assumed" }
  ];
  var PASSWORDS = [
    { name: "In a breached-password list (found in the first ~1,000,000 guesses)", bits: Math.log2(2e6) },
    { name: "6 random digits", bits: 6 * Math.log2(10) },
    { name: "8 random lowercase letters", bits: 8 * Math.log2(26) },
    { name: "8 random printable ASCII characters", bits: 8 * Math.log2(94) },
    { name: "4 random words from a 7,776-word list", bits: 4 * Math.log2(7776) },
    { name: "6 random words from a 7,776-word list", bits: 6 * Math.log2(7776) },
    { name: "16 random printable ASCII characters", bits: 16 * Math.log2(94) }
  ];
  var ATTACKERS = [
    { name: "One CPU core like the one measured (a measurement)", rate: null },
    { name: "One GPU, about 10^10 fast hashes/s (assumption)", rate: 1e10 },
    { name: "A rented farm of 100 GPUs, about 10^12 fast hashes/s (assumption)", rate: 1e12 }
  ];
  var st = { pw: 2, att: 1, ms: FUNCS.map(function (f) { return f.ms; }) };

  function fmtTime(sec) {
    if (!isFinite(sec)) return "never";
    if (sec < 1e-3) return "under a millisecond";
    if (sec < 1) return Math.round(sec * 1000) + " ms";
    var units = [["second", "seconds", 1], ["minute", "minutes", 60], ["hour", "hours", 3600], ["day", "days", 86400], ["year", "years", 31557600], ["thousand years", "thousand years", 31557600e3], ["million years", "million years", 31557600e6], ["billion years", "billion years", 31557600e9]];
    if (sec > 31557600e9 * 1e6) return "more than a million billion years";
    var u = units[0];
    for (var i = 0; i < units.length; i++) if (sec >= units[i][2]) u = units[i];
    var v = sec / u[2];
    var txt = v >= 100 ? Math.round(v).toLocaleString() : v >= 10 ? v.toFixed(0) : v.toFixed(1);
    return txt + " " + (v < 1.95 ? u[0] : u[1]);
  }
  function fmtRate(r) {
    if (r >= 1e9) return (r / 1e9).toPrecision(3) + " G/s";
    if (r >= 1e6) return (r / 1e6).toPrecision(3) + " M/s";
    if (r >= 1e3) return (r / 1e3).toPrecision(3) + " k/s";
    return r.toPrecision(3) + " /s";
  }

  var head = h("div", "widget-head");
  head.appendChild(h("span", "widget-tag", "Explore"));
  head.appendChild(h("h4", "widget-title", "How long to guess a stolen password hash?"));
  root.appendChild(head);

  var row = h("div", "widget-row hc-row");
  function sel(label, opts, key) {
    var l = h("label", "hc-ctl"); l.appendChild(h("span", "hc-l", label));
    var s = h("select");
    opts.forEach(function (o, i) { var op = h("option", null, o.name); op.value = String(i); s.appendChild(op); });
    s.value = String(st[key]);
    s.addEventListener("change", function () { st[key] = parseInt(s.value, 10); render(); });
    l.appendChild(s); row.appendChild(l);
  }
  sel("Password", PASSWORDS, "pw");
  sel("Attacker", ATTACKERS, "att");
  root.appendChild(row);

  var info = h("p", "widget-help hc-info"); info.setAttribute("aria-live", "polite"); root.appendChild(info);
  var wrap = h("div", "hc-wrap"); root.appendChild(wrap);
  var btnrow = h("div", "widget-row");
  var measure = h("button", "btn small", "Measure PBKDF2 here");
  measure.type = "button";
  var reset = h("button", "btn small", "Reset times");
  reset.type = "button";
  var status = h("span", "widget-help hc-status", "");
  btnrow.appendChild(measure); btnrow.appendChild(reset); btnrow.appendChild(status);
  root.appendChild(btnrow);
  root.appendChild(h("p", "widget-help", "Edit any time per hash (milliseconds) to model your own hardware or settings. Measured rows came from Python's hashlib on one laptop; assumed rows are placeholders. Only password hashes you are authorised to test belong anywhere near a cracking tool."));

  reset.addEventListener("click", function () { st.ms = FUNCS.map(function (f) { return f.ms; }); status.textContent = ""; render(); });
  measure.addEventListener("click", function () {
    var c = window.crypto, sub = c && c.subtle;
    if (!sub) { status.textContent = "crypto.subtle is not available on this page."; return; }
    status.textContent = "Measuring...";
    var enc = new TextEncoder();
    sub.importKey("raw", enc.encode("correct horse battery staple"), "PBKDF2", false, ["deriveBits"]).then(function (k) {
      var t0 = performance.now();
      return sub.deriveBits({ name: "PBKDF2", hash: "SHA-256", salt: enc.encode("0123456789abcdef"), iterations: 600000 }, k, 256).then(function () {
        var ms = performance.now() - t0;
        st.ms[1] = Math.max(ms, 0.01);
        status.textContent = "This browser: " + ms.toFixed(1) + " ms for 600,000 iterations (includes one-off setup).";
        render();
      });
    }).catch(function () { status.textContent = "Measurement failed in this browser."; });
  });

  function render() {
    var pw = PASSWORDS[st.pw], att = ATTACKERS[st.att];
    var shaSec = st.ms[0] / 1000;
    var base = att.rate == null ? 1 / shaSec : att.rate;
    info.textContent = "Search space about 2^" + pw.bits.toFixed(1) + " guesses; the attacker needs half of that on average. Fast-hash baseline: " + fmtRate(base) + ".";
    wrap.textContent = "";
    var tb = h("table", "hc-table");
    var hr = h("tr");
    ["Storage", "ms per hash", "Guesses per second", "Expected time to find it"].forEach(function (t) { hr.appendChild(h("th", null, t)); });
    tb.appendChild(hr);
    FUNCS.forEach(function (f, i) {
      var tr = h("tr");
      var nameTd = h("td", "hc-name"); nameTd.appendChild(document.createTextNode(f.name + " "));
      nameTd.appendChild(h("span", "pill " + (f.src === "measured" ? "green" : "yellow"), f.src));
      tr.appendChild(nameTd);
      var inTd = h("td"); var inp = h("input"); inp.type = "number"; inp.min = "0.00001"; inp.step = "any"; inp.value = String(st.ms[i]);
      inp.setAttribute("aria-label", "milliseconds per hash for " + f.name);
      inp.addEventListener("change", function () { var v = parseFloat(inp.value); if (v > 0) { st.ms[i] = v; render(); } });
      inTd.appendChild(inp); tr.appendChild(inTd);
      var rate = base * (shaSec / (st.ms[i] / 1000));
      tr.appendChild(h("td", null, fmtRate(rate)));
      var secs = Math.pow(2, pw.bits - 1) / rate;
      var cls = secs < 3600 ? "red" : secs < 31557600 ? "yellow" : "green";
      var td = h("td"); td.appendChild(h("span", "pill " + cls, fmtTime(secs)));
      tr.appendChild(td);
      tb.appendChild(tr);
    });
    wrap.appendChild(tb);
  }
  render();
})();
