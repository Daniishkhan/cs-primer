/* Origin, site and request explorer (security chapter 10).

   Type (or pick a preset for) two URLs: the PAGE the user is looking at, and the TARGET it talks to.
   The widget splits each into scheme / host / port, then reports:
     - same-origin?  (scheme + host + port all equal)
     - same-site?    (same scheme and same registrable domain, "eTLD+1")
   and, for a chosen cookie SameSite value and a chosen server CORS policy, whether
     - the TARGET's cookie is attached to: a fetch(), a link click (top-level GET), a form POST,
     - the page's JavaScript may READ the response of a fetch().
   Simplifications: a tiny built-in public-suffix list (the real one is publicsuffix.org/list);
   default ports 80/443 only; "simple request" semantics (no preflight unless the toggle is on);
   the SameSite=Lax "2-minute POST" grace some browsers apply to cookies with no explicit SameSite is ignored.
   All user text is written with textContent. */
(function () {
  "use strict";
  var root = document.getElementById("origin-sim");
  if (!root) return;
  function h(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }

  var SUFFIXES = { "com": 1, "org": 1, "net": 1, "uk": 1, "co.uk": 1, "github.io": 1, "herokuapp.com": 1, "appspot.com": 1 };
  var DEF = { "http:": "80", "https:": "443" };

  function parse(text) {
    var u;
    try { u = new URL(text); } catch (e) { return null; }
    if (!DEF[u.protocol]) return null;
    return { scheme: u.protocol.replace(":", ""), host: u.hostname, port: u.port || DEF[u.protocol] };
  }
  function etld1(host) {
    if (host.indexOf(":") >= 0 || /^[0-9.]+$/.test(host)) return host; /* IP literals have no registrable domain */
    var labels = host.split(".");
    for (var i = 0; i < labels.length; i++) {
      if (SUFFIXES[labels.slice(i).join(".")]) return labels.slice(Math.max(i - 1, 0)).join(".");
    }
    /* No listed suffix: the Public Suffix List's default rule treats the last label as the suffix. */
    return labels.slice(-2).join(".");
  }
  function origin(p) { return p.scheme + "://" + p.host + ":" + p.port; }

  var PRESETS = [
    { name: "Same origin",           a: "https://shop.example.com/cart",  b: "https://shop.example.com/api/items" },
    { name: "Sibling subdomain",     a: "https://shop.example.com/cart",  b: "https://api.example.com/items" },
    { name: "Different port",        a: "https://shop.example.com/cart",  b: "https://shop.example.com:8443/items" },
    { name: "http vs https",         a: "https://example.com/",           b: "http://example.com/" },
    { name: "Unrelated site",        a: "https://shop.example.com/cart",  b: "https://evil.test/" },
    { name: "Two github.io users",   a: "https://alice.github.io/",       b: "https://bob.github.io/" }
  ];

  var st = { a: PRESETS[1].a, b: PRESETS[1].b, ss: "Lax", cors: "none", creds: false, pre: false };

  var head = h("div", "widget-head");
  head.appendChild(h("span", "widget-tag", "Explore"));
  head.appendChild(h("h4", "widget-title", "Same-origin, same-site and what flows"));
  root.appendChild(head);

  var pr = h("div", "widget-row os-presets");
  PRESETS.forEach(function (p) {
    var b = h("button", "btn small", p.name); b.type = "button";
    b.addEventListener("click", function () { st.a = p.a; st.b = p.b; ia.value = p.a; ib.value = p.b; render(); });
    pr.appendChild(b);
  });
  root.appendChild(pr);

  function field(label, value, key) {
    var l = h("label", "os-ctl"); l.appendChild(h("span", "os-l", label));
    var i = h("input"); i.type = "text"; i.value = value; i.setAttribute("spellcheck", "false");
    i.addEventListener("input", function () { st[key] = i.value; render(); });
    l.appendChild(i); return { l: l, i: i };
  }
  var fa = field("Page the user is on", st.a, "a"), fb = field("Target the page talks to", st.b, "b");
  var ia = fa.i, ib = fb.i;
  var urls = h("div", "widget-row os-urls"); urls.appendChild(fa.l); urls.appendChild(fb.l); root.appendChild(urls);

  function select(label, opts, key) {
    var l = h("label", "os-ctl"); l.appendChild(h("span", "os-l", label));
    var s = h("select");
    opts.forEach(function (o) { var op = h("option", null, o[1]); op.value = o[0]; s.appendChild(op); });
    s.value = st[key];
    s.addEventListener("change", function () { st[key] = s.value; render(); });
    l.appendChild(s); return l;
  }
  function check(label, key) {
    var l = h("label", "os-chk"); var c = h("input"); c.type = "checkbox"; c.checked = st[key];
    c.addEventListener("change", function () { st[key] = c.checked; render(); });
    l.appendChild(c); l.appendChild(document.createTextNode(" " + label)); return l;
  }
  var opts = h("div", "widget-row os-opts");
  opts.appendChild(select("Target's cookie SameSite", [["Strict", "Strict"], ["Lax", "Lax (browser default)"], ["None", "None; Secure"]], "ss"));
  opts.appendChild(select("Target's CORS policy", [
    ["none", "No CORS headers"],
    ["star", "Allow-Origin: *"],
    ["exact", "Allow-Origin: the page's origin, + Allow-Credentials"],
    ["reflect", "Reflects ANY Origin, + Allow-Credentials (bug)"]], "cors"));
  root.appendChild(opts);
  var o2 = h("div", "widget-row os-opts");
  o2.appendChild(check("fetch() uses credentials: \"include\"", "creds"));
  o2.appendChild(check("request needs a preflight (e.g. custom header or JSON content type)", "pre"));
  root.appendChild(o2);

  var out = h("div", "widget-out os-out"); out.setAttribute("aria-live", "polite"); root.appendChild(out);

  function row(tbody, label, verdict, cls, why) {
    var tr = h("tr"); tr.appendChild(h("th", null, label));
    var td = h("td"); td.appendChild(h("span", "pill " + cls, verdict)); tr.appendChild(td);
    tr.appendChild(h("td", "os-why", why)); tbody.appendChild(tr);
  }

  function render() {
    out.textContent = "";
    var A = parse(st.a), B = parse(st.b);
    if (!A || !B) { out.appendChild(h("p", null, "Enter two complete http:// or https:// URLs.")); return; }
    var so = origin(A) === origin(B);
    var ss = A.scheme === B.scheme && etld1(A.host) === etld1(B.host);

    var info = h("div", "os-info");
    [["Page", A], ["Target", B]].forEach(function (x) {
      var p = h("p", "os-split");
      p.appendChild(h("strong", null, x[0] + ": "));
      p.appendChild(document.createTextNode("scheme " + x[1].scheme + " | host " + x[1].host + " | port " + x[1].port + " | site (eTLD+1) " + etld1(x[1].host)));
      info.appendChild(p);
    });
    var sum = h("p", "os-sum");
    sum.appendChild(h("span", "pill " + (so ? "green" : "red"), so ? "same-origin" : "cross-origin"));
    sum.appendChild(document.createTextNode(" "));
    sum.appendChild(h("span", "pill " + (ss ? "green" : "red"), ss ? "same-site" : "cross-site"));
    info.appendChild(sum);
    out.appendChild(info);

    var tb = h("tbody");
    /* cookies: whether the TARGET's cookie is attached */
    function cookie(kind) {
      if (ss) return [true, "Same-site request, so SameSite does not restrict it."];
      if (st.ss === "None") return [true, "SameSite=None sends it on cross-site requests too (and needs Secure)."];
      if (st.ss === "Lax" && kind === "nav") return [true, "Lax allows cookies on top-level navigations that use a safe method (GET)."];
      if (st.ss === "Lax") return [false, "Lax withholds the cookie from cross-site subrequests and cross-site POST navigations."];
      return [false, "Strict never sends the cookie on cross-site requests, even link clicks."];
    }
    var c1 = cookie("sub"), c2 = cookie("nav"), c3 = cookie(kindPost());
    function kindPost() { return "post"; }
    var credsOn = st.creds || so; /* same-origin fetch sends cookies by default */
    var c1v = c1[0] && credsOn;
    row(tb, "Cookie on fetch()", c1v ? "attached" : "not attached", c1v ? "yellow" : "green",
      !credsOn ? "Cross-origin fetch() omits cookies unless credentials: \"include\" is set." : c1[1]);
    row(tb, "Cookie on link click (GET)", c2[0] ? "attached" : "not attached", c2[0] ? "yellow" : "green", c2[1]);
    row(tb, "Cookie on form POST", c3[0] ? "attached" : "not attached", c3[0] ? "yellow" : "green",
      c3[0] ? c3[1] : c3[1] + " This is the CSRF case: a cross-site form POST carries no cookie.");

    /* CORS */
    var cors = st.cors, readable, why, cls, sent = true;
    var needsPre = st.pre && !so;
    if (so) { readable = true; why = "Same-origin: the SOP lets the page read the response; CORS is not involved."; cls = "green"; }
    else if (cors === "none") { readable = false; why = "No Access-Control-Allow-Origin header, so the browser hides the response from JavaScript."; cls = "red"; }
    else if (cors === "star") {
      if (st.creds) { readable = false; why = "A wildcard is not allowed for credentialed requests; the browser blocks the read."; cls = "red"; }
      else { readable = true; why = "Allow-Origin: * lets any origin read a response that was fetched without credentials."; cls = "yellow"; }
    }
    else if (cors === "exact") {
      readable = true; cls = "green";
      why = "The server named exactly this origin" + (st.creds ? " and allowed credentials" : "") + ". That is a deliberate relaxation of the SOP; keep the allowlist exact. (Pretend this page's origin is on it.)";
    }
    else { readable = true; cls = "red"; why = "The server echoes whatever Origin it is sent and allows credentials, so ANY site can read this user's authenticated responses" + (st.creds ? "" : " (tick credentials: \"include\" to send the cookie; without it this particular fetch is unauthenticated)") + ". This is the classic misconfiguration."; }
    if (needsPre && (cors === "none")) sent = false;
    if (needsPre && cors === "star" && st.creds) sent = false;

    var sentTxt = so ? "sent" : (needsPre ? (sent ? "sent after an approved preflight" : "NOT sent (preflight refused)") : "sent");
    row(tb, "Request reaches the server", sentTxt, sent ? "yellow" : "green",
      so ? "Same-origin requests are ordinary." : (needsPre ? "Preflighted requests ask permission first with an OPTIONS request." : "A simple request is sent regardless of CORS; CORS only controls whether the page may read the reply, so state-changing endpoints still need CSRF defences."));
    row(tb, "Page's JS can read the reply", readable ? "yes" : "no", readable ? (cls === "red" ? "red" : cls) : "green", why);

    var t = h("table", "os-table"); var th = h("thead"); var tr = h("tr");
    ["Question", "Answer", "Why"].forEach(function (x) { tr.appendChild(h("th", null, x)); });
    th.appendChild(tr); t.appendChild(th); t.appendChild(tb);
    var wrap = h("div", "os-wrap"); wrap.appendChild(t); out.appendChild(wrap);
  }
  render();
})();
