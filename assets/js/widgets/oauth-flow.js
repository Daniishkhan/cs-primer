/* OAuth 2.0 authorization code flow explorer (security chapter 7).

   Choose a scenario (the normal flow, or one of three attacks) and switch three defences on or off:
   PKCE, the state parameter, and exact redirect_uri matching. Step through the message flow and see
   where, if anywhere, the attack is stopped, and by which defence.
     Scenarios (all simulated in the page; nothing is sent anywhere):
       redirect  - the attacker gets a user to open an authorization link whose redirect_uri points at
                   a place the attacker controls. Stopped by exact redirect_uri matching only. PKCE does
                   NOT help here: the attacker wrote the authorization request, so they chose the
                   code_challenge and can redeem the code with their own verifier. (Authentication of
                   a confidential client would help; it is not modelled.)
       intercept - the code leaks in transit (a malicious app on the same device, a log, a Referer
                   header). The attacker redeems it. Stopped only by PKCE.
       csrf      - login CSRF on the callback: the attacker feeds the victim's browser a code from the
                   attacker's own flow. Stopped by state; PKCE also stops it, because the victim's
                   client holds a different code_verifier (RFC 9700 allows PKCE for this when the
                   authorization server supports it).
   Simplifications: one client, one authorization server, no consent screen detail, a public or
   confidential client treated alike. Real implementations have more checks (code is single use,
   short-lived, bound to the client). */
(function () {
  "use strict";
  var root = document.getElementById("oauth-flow");
  if (!root) return;
  var NS = "http://www.w3.org/2000/svg";
  function h(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function s(tag, attrs, cls) {
    var e = document.createElementNS(NS, tag);
    if (attrs) Object.keys(attrs).forEach(function (k) { e.setAttribute(k, attrs[k]); });
    if (cls) e.setAttribute("class", cls);
    return e;
  }

  var LANES = [
    { name: "Browser", sub: "user", cls: "s-green" },
    { name: "Client app", sub: "wants access", cls: "s-blue" },
    { name: "Auth server", sub: "issues tokens", cls: "s-purple" },
    { name: "API", sub: "resource server", cls: "s-blue" },
    { name: "Attacker", sub: "", cls: "s-red" }
  ];
  var X = [76, 228, 380, 532, 684];

  var SCEN = [
    { id: "normal",    name: "Normal login, no attacker" },
    { id: "redirect",  name: "Attack: tampered redirect_uri" },
    { id: "intercept", name: "Attack: authorization code intercepted" },
    { id: "csrf",      name: "Attack: forged callback (login CSRF)" }
  ];
  var st = { scen: "normal", pkce: true, state: true, exact: true, step: 1 };

  /* arrow: [from lane, to lane, label, kind] kind: "" blue, "bad" red, "ok" green, "tok" orange.
     note: [lane, text, kind]. Each step: { title, arrows, notes, text, end: null|"blocked"|"breach" } */
  function build() {
    var S = [], f = st;
    var A = function (a, b, l, k) { return [a, b, l, k || ""]; };
    var N = function (lane, t, k) { return [lane, t, k || ""]; };
    if (f.scen === "normal") {
      S.push({ title: "1. Client starts the flow", arrows: [A(1, 0, "302 to /authorize"), A(0, 2, "GET /authorize")], notes: [N(1, f.pkce ? "makes verifier, challenge, state" : "makes state")],
        text: "The client generates a random state" + (f.pkce ? ", a random code_verifier and its SHA-256 hash, the code_challenge," : "") + " keeps them in the user's session, and redirects the browser to the authorization endpoint with response_type=code, client_id, redirect_uri, scope, state" + (f.pkce ? ", code_challenge and code_challenge_method=S256" : "") + "." });
      S.push({ title: "2. User signs in and consents", arrows: [A(2, 0, "login + consent screen"), A(0, 2, "approve scopes")], notes: [],
        text: "The auth server authenticates the user itself (the client never sees the password) and shows what is being requested. It compares redirect_uri with the client's registered value" + (f.exact ? " by exact string match." : " using a loose match (prefix or wildcard) in this configuration.") });
      S.push({ title: "3. Code returns by redirect", arrows: [A(2, 0, "302 redirect_uri?code&state"), A(0, 1, "GET /cb?code&state")], notes: [],
        text: "The browser carries a short-lived, single-use authorization code back to the client. The code is not a token: on its own it grants nothing except the chance to redeem it." });
      S.push({ title: "4. Client checks state", arrows: [], notes: [N(1, f.state ? "state matches session: continue" : "state not checked", f.state ? "ok" : "bad")],
        text: f.state ? "The returned state equals the value stored in this user's session, so this callback answers a flow this browser started." : "State checking is off in this configuration, so the client cannot tell whether this callback belongs to a flow this browser started." });
      S.push({ title: "5. Client redeems the code", arrows: [A(1, 2, f.pkce ? "POST /token code + verifier" : "POST /token code")], notes: [],
        text: "A back-channel request, server to server, with the code, the redirect_uri, client authentication if the client is confidential" + (f.pkce ? ", and the code_verifier." : ".") });
      S.push({ title: "6. Tokens are issued", arrows: [A(2, 1, "access token (+ ID token)", "tok")], notes: [N(2, f.pkce ? "SHA-256(verifier) = challenge" : "code valid, client matches", "ok")],
        text: "The auth server checks the code is unused, unexpired and issued to this client and redirect_uri" + (f.pkce ? ", and that SHA-256(code_verifier) equals the code_challenge from step 1" : "") + ". It returns an access token, optionally a refresh token, and for OpenID Connect an ID token.", });
      S.push({ title: "7. Client calls the API", arrows: [A(1, 3, "Bearer access token", "tok")], notes: [N(3, "validate token, aud, scope", "ok")],
        text: "The API checks the token's signature or introspects it, its audience, expiry and scopes, then answers. The access token is for the API; the client should not try to read its contents.", end: "done" });
    } else if (f.scen === "redirect") {
      S.push({ title: "1. Attacker crafts a link", arrows: [A(4, 0, "link: redirect_uri=evil", "bad"), A(0, 2, "GET /authorize")], notes: [],
        text: "The attacker needs the victim to click a link to the real authorization endpoint, with the client_id of a real app but a redirect_uri the attacker controls. Nothing is hacked yet; the link is entirely legitimate looking." });
      if (f.exact) {
        S.push({ title: "2. Auth server rejects it", arrows: [A(2, 0, "error: invalid redirect_uri")], notes: [N(2, "not an exact match: refuse", "ok")],
          text: "The registered redirect_uri is compared as an exact string. The auth server must not redirect to an unregistered address, so it shows an error page instead. No code is issued.", end: "blocked", by: "exact redirect_uri matching" });
        return S;
      }
      S.push({ title: "2. Loose matching accepts it", arrows: [A(2, 0, "login + consent"), A(0, 2, "approve")], notes: [N(2, "prefix/wildcard match passes", "bad")],
        text: "With prefix or wildcard matching (or an open redirect on the registered domain) the evil address passes. The user logs in as normal." });
      S.push({ title: "3. Code goes to the attacker", arrows: [A(2, 0, "302 evil/cb?code"), A(0, 4, "GET evil/cb?code", "bad")], notes: [],
        text: "The browser follows the redirect and hands the authorization code to the attacker's server." });
      S.push({ title: "4. Attacker redeems the code", arrows: [A(4, 2, "POST /token code", "bad"), A(2, 4, "access token", "tok")], notes: [N(4, "holds the victim's access", "bad")],
        text: (f.pkce ? "PKCE does not save you here: the attacker wrote the authorization request themselves, so they chose the code_challenge and hold the matching code_verifier. " : "Nothing binds the code to the client that asked for it, so whoever holds it can redeem it. ") + "The attacker now has tokens for the victim's account. Only exact redirect_uri matching (or, for a confidential client, client authentication at the token endpoint) stops this; the fix belongs at step 2.", end: "breach" });
    } else if (f.scen === "intercept") {
      S.push({ title: "1. Normal start", arrows: [A(1, 0, "302 to /authorize"), A(0, 2, "GET /authorize")], notes: [N(1, f.pkce ? "stores verifier, sends challenge" : "no PKCE")],
        text: "The victim starts a legitimate login. The client " + (f.pkce ? "keeps the code_verifier and sends only its hash." : "sends no proof-of-possession value.") });
      S.push({ title: "2. User signs in", arrows: [A(2, 0, "login + consent"), A(0, 2, "approve")], notes: [], text: "The user approves the request." });
      S.push({ title: "3. The code leaks", arrows: [A(2, 0, "302 redirect_uri?code"), A(0, 1, "GET /cb?code"), A(0, 4, "code leaks", "bad")], notes: [],
        text: "The code is exposed somewhere on the way: another app on the device registered for the same custom URL scheme, a proxy or analytics log that records URLs, or a Referer header. This is why a code in a URL must be treated as sensitive but is not secret enough to be the only protection." });
      if (f.pkce) {
        S.push({ title: "4. Attacker tries to redeem", arrows: [A(4, 2, "POST /token code", "bad"), A(2, 4, "error: invalid_grant", "ok")], notes: [N(2, "attacker has no verifier", "ok")],
          text: "The token endpoint requires the code_verifier that hashes to the challenge. Only the legitimate client has it. The leaked code is useless.", end: "blocked", by: "PKCE" });
      } else {
        S.push({ title: "4. Attacker redeems it first", arrows: [A(4, 2, "POST /token code", "bad"), A(2, 4, "access token", "tok")], notes: [N(4, "holds the victim's access", "bad")],
          text: "Without PKCE the code is a bearer credential for one redemption. If the attacker redeems first, they hold the tokens, and the real client's attempt then fails. (A confidential client's secret would help here; public clients such as mobile and single-page apps have none.)", end: "breach" });
      }
    } else {
      S.push({ title: "1. Attacker starts their own flow", arrows: [A(4, 2, "logs in as attacker", "bad"), A(2, 4, "code for ATTACKER's account", "bad")], notes: [],
        text: "The attacker begins a login at the real auth server with their own account and stops before redeeming the code. They now hold a valid code that maps to the attacker's identity." });
      S.push({ title: "2. Victim opens a forged callback", arrows: [A(4, 0, "link: /cb?code=A&state=x", "bad"), A(0, 1, "GET /cb?code=A&state=x")], notes: [],
        text: "The attacker gets the victim's browser to request the client's callback with the attacker's code, for example through a link, an image tag or a hidden form. The victim has a session with the client; the attacker's flow never touched it." });
      if (f.state) {
        S.push({ title: "3. Client checks state", arrows: [], notes: [N(1, "state != session state: reject", "ok")],
          text: "The state value in the URL does not match the one the client stored in the victim's session when the victim started a flow (the victim started none). The client discards the request.", end: "blocked", by: "the state parameter" });
        return S;
      }
      S.push({ title: "3. Client skips the check", arrows: [], notes: [N(1, "state not checked", "bad")], text: "No state is checked, so the client accepts the callback as if it answered the victim's own request." });
      if (f.pkce) {
        S.push({ title: "4. Client redeems the code", arrows: [A(1, 2, "POST /token code + victim's verifier"), A(2, 1, "error: invalid_grant", "ok")], notes: [N(2, "verifier does not match", "ok")],
          text: "The client sends the code_verifier stored in the victim's session (or none at all), but the code was issued against the attacker's different challenge. The token endpoint rejects it. This is PKCE acting as CSRF protection, which RFC 9700 permits when the auth server supports PKCE.", end: "blocked", by: "PKCE" });
      } else {
        S.push({ title: "4. Client redeems the code", arrows: [A(1, 2, "POST /token code"), A(2, 1, "tokens for attacker's account", "tok")], notes: [N(1, "victim now logged in as attacker", "bad")],
          text: "The victim's session is now bound to the attacker's account. If the victim uploads documents or enters payment details, they land in the attacker's account. This is login CSRF.", end: "breach" });
      }
    }
    return S;
  }

  var head = h("div", "widget-head");
  head.appendChild(h("span", "widget-tag", "Step through"));
  head.appendChild(h("h4", "widget-title", "Authorization code flow: which check stops which attack?"));
  root.appendChild(head);

  var row = h("div", "widget-row of-row");
  var l = h("label", "of-ctl"); l.appendChild(h("span", "of-l", "Scenario"));
  var sc = h("select"); SCEN.forEach(function (o) { var op = h("option", null, o.name); op.value = o.id; sc.appendChild(op); });
  sc.addEventListener("change", function () { st.scen = sc.value; st.step = 1; render(); });
  l.appendChild(sc); row.appendChild(l);
  function tog(key, label) {
    var lb = h("label", "of-tog"); var cb = h("input"); cb.type = "checkbox"; cb.checked = st[key];
    cb.addEventListener("change", function () { st[key] = cb.checked; if (st.step > build().length) st.step = build().length; render(); });
    lb.appendChild(cb); lb.appendChild(document.createTextNode(" " + label)); row.appendChild(lb);
  }
  tog("pkce", "PKCE"); tog("state", "state check"); tog("exact", "exact redirect_uri");
  root.appendChild(row);

  var svg = s("svg", { viewBox: "0 0 760 100", role: "img", "aria-label": "Message flow between browser, client app, auth server, API and attacker for the selected scenario." }, "of-svg");
  root.appendChild(svg);
  var ctl = h("div", "widget-row");
  var back = h("button", "btn small", "Back"); back.type = "button";
  var next = h("button", "btn small primary", "Next step"); next.type = "button";
  var rst = h("button", "btn small", "Restart"); rst.type = "button";
  ctl.appendChild(back); ctl.appendChild(next); ctl.appendChild(rst);
  root.appendChild(ctl);
  var out = h("div", "widget-out"); out.setAttribute("aria-live", "polite"); root.appendChild(out);
  back.addEventListener("click", function () { if (st.step > 1) { st.step--; render(); } });
  next.addEventListener("click", function () { if (st.step < build().length) { st.step++; render(); } });
  rst.addEventListener("click", function () { st.step = 1; render(); });

  function render() {
    var steps = build();
    if (st.step > steps.length) st.step = steps.length;
    var attacker = st.scen !== "normal";
    var lanes = attacker ? [0, 1, 2, 3, 4] : [0, 1, 2, 3];
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    var defs = s("defs");
    [["", "arrowhead"], ["r", "arrowhead f-red"], ["g", "arrowhead f-green"], ["o", "arrowhead f-orange"]].forEach(function (m) {
      var mk = s("marker", { id: "ahS07w" + m[0], viewBox: "0 0 10 10", refX: "9", refY: "5", markerWidth: "7", markerHeight: "7", orient: "auto" });
      mk.appendChild(s("path", { d: "M0,0 L10,5 L0,10 z" }, m[1])); defs.appendChild(mk);
    });
    svg.appendChild(defs);
    var y = 56, rows = [];
    for (var i = 0; i < st.step; i++) {
      var step = steps[i], ys = y;
      step.arrows.forEach(function (a) { y += 34; rows.push({ type: "a", a: a, y: y, cur: i === st.step - 1 }); });
      step.notes.forEach(function (n) { y += 34; rows.push({ type: "n", n: n, y: y, cur: i === st.step - 1 }); });
      if (!step.arrows.length && !step.notes.length) y += 20;
      y += 10;
    }
    var H = Math.max(y + 18, 120);
    svg.setAttribute("viewBox", "0 0 760 " + H);
    lanes.forEach(function (li) {
      var L = LANES[li];
      svg.appendChild(s("line", { x1: X[li], y1: 44, x2: X[li], y2: H - 6 }, "line-thin"));
      var g = s("g");
      g.appendChild(s("rect", { x: X[li] - 62, y: 4, width: 124, height: 36, rx: 8 }, "box " + L.cls + " sw-2"));
      var t = s("text", { x: X[li], y: L.sub ? 20 : 27, "text-anchor": "middle" }, "t-sm t-bold"); t.textContent = L.name; g.appendChild(t);
      if (L.sub) { var t2 = s("text", { x: X[li], y: 34, "text-anchor": "middle" }, "t-xs t-muted"); t2.textContent = L.sub; g.appendChild(t2); }
      svg.appendChild(g);
    });
    /* trust boundary between client side and auth server */
    var bx = (X[1] + X[2]) / 2;
    svg.appendChild(s("line", { x1: bx, y1: 44, x2: bx, y2: H - 6 }, "line-dash s-yellow"));
    rows.forEach(function (r) {
      if (r.type === "a") {
        var a = r.a, x1 = X[a[0]], x2 = X[a[1]], dir = x2 > x1 ? 1 : -1;
        var mark = a[3] === "bad" ? "r" : a[3] === "ok" ? "g" : a[3] === "tok" ? "o" : "";
        var col = a[3] === "bad" ? "s-red" : a[3] === "ok" ? "s-green" : a[3] === "tok" ? "s-orange" : "s-blue";
        svg.appendChild(s("line", { x1: x1 + dir * 4, y1: r.y, x2: x2 - dir * 6, y2: r.y, "marker-end": "url(#ahS07w" + mark + ")" }, "line " + col + (r.cur ? "" : " of-old")));
        var tx = s("text", { x: (x1 + x2) / 2, y: r.y - 6, "text-anchor": "middle" }, "t-xs" + (r.cur ? " t-bold" : "")); tx.textContent = a[2]; svg.appendChild(tx);
      } else {
        var n = r.n, cx = X[n[0]], w = 200;
        var kc = n[2] === "bad" ? "fs-red s-red" : n[2] === "ok" ? "fs-green s-green" : "box";
        svg.appendChild(s("rect", { x: Math.max(4, Math.min(cx - w / 2, 756 - w)), y: r.y - 14, width: w, height: 26, rx: 6 }, kc + " sw-1"));
        var nt = s("text", { x: Math.max(4, Math.min(cx - w / 2, 756 - w)) + w / 2, y: r.y + 3, "text-anchor": "middle" }, "t-xs"); nt.textContent = n[1]; svg.appendChild(nt);
      }
    });
    var cur = steps[st.step - 1];
    out.textContent = "";
    var p = h("p", null); var b = h("strong", null, cur.title + ". "); p.appendChild(b); p.appendChild(document.createTextNode(cur.text)); out.appendChild(p);
    if (cur.end === "blocked") { var q = h("p"); q.appendChild(h("span", "pill green", "Attack stopped")); q.appendChild(document.createTextNode(" by " + cur.by + ".")); out.appendChild(q); }
    else if (cur.end === "breach") { var q2 = h("p"); q2.appendChild(h("span", "pill red", "Attack succeeds")); q2.appendChild(document.createTextNode(" with these settings. Switch a defence on and step through again.")); out.appendChild(q2); }
    else if (cur.end === "done") { var q3 = h("p"); q3.appendChild(h("span", "pill green", "Flow complete")); out.appendChild(q3); }
    back.disabled = st.step <= 1; next.disabled = st.step >= steps.length;
  }
  render();
})();
