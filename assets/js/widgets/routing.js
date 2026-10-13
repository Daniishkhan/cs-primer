/* Routing explorer (chapter 5).
   Six routers, a laptop and a few destination networks. Routing tables are
   computed from the live links (shortest path by hop count; ties broken by
   router number), so cutting a link really changes the tables.
   Root: <div class="widget" id="routing-widget"> ... </div> (JS fills it in). */
(function () {
  "use strict";
  var root = document.getElementById("routing-widget");
  if (!root) return;
  var NS = "http://www.w3.org/2000/svg";

  var ROUTERS = ["R1", "R2", "R3", "R4", "R5", "R6"];
  var POS = {
    L: { x: 38, y: 150 }, R1: { x: 130, y: 150 }, R2: { x: 230, y: 60 }, R3: { x: 230, y: 240 },
    R5: { x: 370, y: 60 }, R4: { x: 370, y: 240 }, R6: { x: 480, y: 150 }
  };
  var LINKS = [["R1", "R2"], ["R1", "R3"], ["R2", "R5"], ["R2", "R4"], ["R3", "R4"], ["R5", "R6"], ["R4", "R6"]];
  /* Networks that exist "out there", and which router they hang off. */
  var PREFIXES = [
    { cidr: "203.0.113.0/24", origin: "R6" },
    { cidr: "198.51.100.0/24", origin: "R6" },
    { cidr: "198.51.100.128/25", origin: "R5" },
    { cidr: "192.0.2.0/24", origin: "R4" }
  ];
  var HOSTS = {
    A: { ip: "203.0.113.10", name: "Server A", router: "R6", x: 530, y: 96 },
    B: { ip: "198.51.100.7", name: "Server B", router: "R6", x: 530, y: 180 },
    C: { ip: "192.0.2.50", name: "Server C", router: "R4", x: 335, y: 274 },
    D: { ip: "198.51.100.200", name: "Server D", router: "R5", x: 335, y: 4 }
  };
  var DESTS = [
    { id: "A", label: "Server A  203.0.113.10" },
    { id: "B", label: "Server B  198.51.100.7" },
    { id: "D", label: "Server D  198.51.100.200" },
    { id: "C", label: "Server C  192.0.2.50" },
    { id: "P", label: "Printer  192.168.1.50 (same LAN)" },
    { id: "X", label: "172.16.5.5 (private, not routable)" }
  ];

  var cut = {};
  var T = {};
  var steps = [];
  var cur = 0;
  var timer = null;
  var dest = "A";
  var ttl0 = 64;
  var inspect = "follow";

  /* ---------- tiny helpers ---------- */
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function sv(tag, attrs, cls) {
    var e = document.createElementNS(NS, tag);
    Object.keys(attrs || {}).forEach(function (k) { e.setAttribute(k, attrs[k]); });
    if (cls) e.setAttribute("class", cls);
    return e;
  }
  function ip2n(s) { var p = s.split("."); return (((+p[0]) << 24) | ((+p[1]) << 16) | ((+p[2]) << 8) | (+p[3])) >>> 0; }
  function plen(cidr) { return parseInt(cidr.split("/")[1], 10); }
  function inNet(ipn, cidr) {
    var a = cidr.split("/"), len = +a[1];
    var mask = len === 0 ? 0 : (0xFFFFFFFF << (32 - len)) >>> 0;
    return ((ipn & mask) >>> 0) === ((ip2n(a[0]) & mask) >>> 0);
  }
  function lid(a, b) { return a + "-" + b; }
  function isLive(a, b) { return !cut[lid(a, b)] && !cut[lid(b, a)]; }
  function nb(u) {
    var out = [];
    LINKS.forEach(function (l) {
      if (!isLive(l[0], l[1])) return;
      if (l[0] === u) out.push(l[1]);
      else if (l[1] === u) out.push(l[0]);
    });
    return out.sort();
  }
  /* hop counts from `origin` across live links, never transiting the home router R1 */
  function dist(origin) {
    var d = {}; d[origin] = 0;
    var q = [origin];
    while (q.length) {
      var u = q.shift();
      nb(u).forEach(function (v) {
        if (v === "R1" || d[v] !== undefined) return;
        d[v] = d[u] + 1; q.push(v);
      });
    }
    return d;
  }

  function buildTables() {
    T = {};
    ROUTERS.forEach(function (r) {
      var rows = [];
      if (r === "R1") {
        rows.push({ cidr: "192.168.1.0/24", connected: true });
        var gw = ["R2", "R3"].filter(function (g) { return isLive("R1", g); })[0];
        if (gw) rows.push({ cidr: "0.0.0.0/0", next: gw, def: true });
      } else {
        PREFIXES.forEach(function (p) {
          if (p.origin === r) { rows.push({ cidr: p.cidr, connected: true }); return; }
          var d = dist(p.origin), best = null;
          nb(r).forEach(function (n) {
            if (d[n] !== undefined && (best === null || d[n] < d[best])) best = n;
          });
          if (best) rows.push({ cidr: p.cidr, next: best });
        });
      }
      rows.sort(function (a, b) { return plen(b.cidr) - plen(a.cidr); });
      T[r] = rows;
    });
  }

  function lookup(r, ip) {
    var n = ip2n(ip), matches = [];
    T[r].forEach(function (row, i) { if (inNet(n, row.cidr)) matches.push(i); });
    return { matches: matches, chosen: matches.length ? matches[0] : -1 };
  }

  function destInfo() {
    if (dest === "P") return { ip: "192.168.1.50", name: "the printer" };
    if (dest === "X") return { ip: "172.16.5.5", name: "172.16.5.5" };
    return HOSTS[dest];
  }

  /* ---------- simulation ---------- */
  function simulate() {
    buildTables();
    steps = [];
    var d = destInfo();
    if (dest === "P") {
      steps.push({ node: "L", ttl: ttl0, head: "Laptop · 192.168.1.20", end: "ok",
        text: "I want to reach 192.168.1.50. Is that inside my own subnet, 192.168.1.0/24? Yes! No router is needed: ARP for its MAC address (chapter 6) and send the Ethernet frame straight to it. Delivered, TTL never touched." });
      return;
    }
    steps.push({ node: "L", ttl: ttl0, head: "Laptop · 192.168.1.20",
      text: "I want to reach " + d.ip + ". Is that inside my own subnet, 192.168.1.0/24? No. I can't deliver it myself, so I hand the packet to my default gateway, R1." });
    var node = "R1", ttl = ttl0, guard = 0;
    while (guard++ < 14) {
      ttl -= 1;
      if (ttl <= 0) {
        steps.push({ node: node, ttl: 0, head: node + " · TTL " + (ttl + 1) + " → 0", end: "drop", rows: node,
          text: "TTL reached 0, so " + node + " discards the packet and sends an ICMP \"time exceeded\" message back to 192.168.1.20. This is exactly what traceroute listens for." });
        return;
      }
      var m = lookup(node, d.ip);
      var head = node + " · TTL " + (ttl + 1) + " → " + ttl;
      if (m.chosen < 0) {
        steps.push({ node: node, ttl: ttl, head: head, end: "drop", rows: node, matches: [],
          text: "No row in " + node + "'s table matches " + d.ip + ", and there is no default route. The router can't know where to send it, so it drops the packet and sends back ICMP \"destination unreachable\". (Private addresses like 172.16.x.x aren't routed on the public Internet.)" });
        return;
      }
      var row = T[node][m.chosen];
      var matchTxt = m.matches.map(function (i) { return T[node][i].cidr; }).join(", ");
      var why;
      if (m.matches.length === 1) {
        why = row.def ? "Only the default route 0.0.0.0/0 matches (prefix length 0, so it matches everything but loses to anything more specific)." : "One row matches: " + row.cidr + ".";
      } else {
        why = "Matching rows: " + matchTxt + ". The longest prefix wins: " + row.cidr + " (" + plen(row.cidr) + " bits).";
      }
      if (row.connected) {
        var ok = d.router === node;
        steps.push({ node: node, ttl: ttl, head: head, end: ok ? "ok" : "drop", rows: node, matches: m.matches, chosen: m.chosen,
          text: why + " That network is directly attached to " + node + ", so it delivers on the local network (ARP for the host, then an Ethernet frame). " +
            (ok ? "Delivered to " + d.name + "!" : "But nobody answers at " + d.ip + " (the ARP request gets no reply), so " + node + " sends back ICMP \"host unreachable\".") });
        return;
      }
      steps.push({ node: node, ttl: ttl, head: head, rows: node, matches: m.matches, chosen: m.chosen, next: row.next,
        text: why + " Next hop: " + row.next + ". " + node + " only decides the next step; it has no idea what happens after " + row.next + "." });
      node = row.next;
    }
  }

  /* ---------- DOM ---------- */
  var ui = {};
  function build() {
    var head = root.querySelector(".widget-head");
    Array.prototype.slice.call(root.children).forEach(function (c) { if (c !== head) root.removeChild(c); });

    root.appendChild(el("p", "widget-help", "Pick a destination and a starting TTL, then step through. Each router looks at the destination address, finds the longest matching row in its own table, and forwards. Cut a link to watch the tables (and the path) change."));

    var r1 = el("div", "widget-row");
    function labelled(text, id, sel) { var l = el("label", null, text); l.htmlFor = id; r1.appendChild(l); sel.id = id; r1.appendChild(sel); }
    ui.dest = el("select");
    DESTS.forEach(function (d) { var o = el("option", null, d.label); o.value = d.id; ui.dest.appendChild(o); });
    labelled("Send to:", "rt-dest", ui.dest);
    ui.ttl = el("select");
    [64, 5, 3, 2].forEach(function (t) { var o = el("option", null, String(t)); o.value = t; ui.ttl.appendChild(o); });
    labelled("Starting TTL:", "rt-ttl", ui.ttl);
    root.appendChild(r1);

    var svg = sv("svg", { viewBox: "0 0 600 300", role: "img", "aria-label": "Network of six routers R1 to R6 with a laptop on the left and servers on the right; the packet's current position and path are highlighted" });
    ui.svg = svg;
    ui.linkEls = {};
    LINKS.forEach(function (l) {
      var a = POS[l[0]], b = POS[l[1]], id = lid(l[0], l[1]);
      var ln = sv("line", { x1: a.x, y1: a.y, x2: b.x, y2: b.y }, "line");
      var hit = sv("line", { x1: a.x, y1: a.y, x2: b.x, y2: b.y, "stroke-width": 16, stroke: "transparent" }, "rt-hit");
      hit.addEventListener("click", function () { toggleCut(id); });
      svg.appendChild(ln); svg.appendChild(hit);
      ui.linkEls[id] = ln;
    });
    ui.lanLink = sv("line", { x1: POS.L.x + 32, y1: 150, x2: POS.R1.x, y2: 150 }, "line");
    svg.appendChild(ui.lanLink);
    ui.cutMarks = {};
    LINKS.forEach(function (l) {
      var a = POS[l[0]], b = POS[l[1]], id = lid(l[0], l[1]);
      var g = sv("text", { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 + 5, "text-anchor": "middle" }, "t-bold tc-red");
      g.setAttribute("style", "font-size:16px");
      g.textContent = "✕"; g.style.display = "none"; svg.appendChild(g); ui.cutMarks[id] = g;
    });
    /* hosts */
    ui.hostEls = {};
    Object.keys(HOSTS).forEach(function (k) {
      var h = HOSTS[k], r = POS[h.router];
      var cx = h.x + 33, cy = h.y + 12;
      var ln = sv("line", { x1: r.x, y1: r.y, x2: cx, y2: cy }, "line-thin");
      svg.appendChild(ln);
      var rect = sv("rect", { x: h.x, y: h.y, width: 66, height: 24, rx: 5 }, "box");
      var t = sv("text", { x: cx, y: cy + 4, "text-anchor": "middle" }, "t-xs");
      t.textContent = h.name;
      svg.appendChild(rect); svg.appendChild(t);
      ui.hostEls[k] = rect;
    });
    /* laptop */
    ui.laptop = sv("rect", { x: 6, y: 125, width: 64, height: 50, rx: 8 }, "box");
    svg.appendChild(ui.laptop);
    var lt = sv("text", { x: 38, y: 147, "text-anchor": "middle" }, "t-sm t-bold"); lt.textContent = "Laptop"; svg.appendChild(lt);
    var lt2 = sv("text", { x: 38, y: 163, "text-anchor": "middle" }, "t-xs t-muted"); lt2.textContent = "192.168.1.20"; svg.appendChild(lt2);
    /* routers */
    ui.nodeEls = {};
    ROUTERS.forEach(function (r) {
      var p = POS[r];
      var c = sv("circle", { cx: p.x, cy: p.y, r: 22 }, "box2");
      var t = sv("text", { x: p.x, y: p.y + 5, "text-anchor": "middle" }, "t-sm t-bold"); t.textContent = r;
      svg.appendChild(c); svg.appendChild(t);
      ui.nodeEls[r] = c;
    });
    var fig = el("div"); fig.appendChild(svg); root.appendChild(fig);

    ui.linkRow = el("div", "widget-row");
    ui.linkRow.appendChild(el("span", "widget-help", "Cut a link:"));
    ui.linkBtns = {};
    LINKS.forEach(function (l) {
      var id = lid(l[0], l[1]);
      var b = el("button", "btn small rt-link-btn", l[0] + "–" + l[1]);
      b.type = "button"; b.setAttribute("aria-pressed", "false");
      b.addEventListener("click", function () { toggleCut(id); });
      ui.linkRow.appendChild(b); ui.linkBtns[id] = b;
    });
    root.appendChild(ui.linkRow);

    ui.caption = el("div", "widget-out rt-caption");
    ui.caption.setAttribute("aria-live", "polite");
    ui.capHead = el("div", "rt-caphead");
    ui.capText = el("div", "rt-captext");
    ui.capState = el("span", "pill");
    ui.caption.appendChild(ui.capHead); ui.caption.appendChild(ui.capText);
    root.appendChild(ui.caption);

    var r3 = el("div", "widget-row");
    ui.inspect = el("select");
    var o0 = el("option", null, "the router the packet is at"); o0.value = "follow"; ui.inspect.appendChild(o0);
    ROUTERS.forEach(function (r) { var o = el("option", null, r); o.value = r; ui.inspect.appendChild(o); });
    var il = el("label", null, "Show routing table of:"); il.htmlFor = "rt-inspect"; ui.inspect.id = "rt-inspect";
    r3.appendChild(il); r3.appendChild(ui.inspect);
    root.appendChild(r3);

    ui.tableBox = el("div", "table-wrap rt-tablebox");
    root.appendChild(ui.tableBox);

    var r4 = el("div", "widget-row");
    ui.first = el("button", "btn small", "⏮"); ui.first.setAttribute("aria-label", "Back to the start");
    ui.prev = el("button", "btn small", "← Back");
    ui.next = el("button", "btn small primary", "Next →");
    ui.play = el("button", "btn small", "▶ Play");
    ui.count = el("span", "rt-count");
    [ui.first, ui.prev, ui.next, ui.play].forEach(function (b) { b.type = "button"; r4.appendChild(b); });
    r4.appendChild(ui.count);
    root.appendChild(r4);

    ui.dest.addEventListener("change", function () { dest = ui.dest.value; restart(); });
    ui.ttl.addEventListener("change", function () { ttl0 = parseInt(ui.ttl.value, 10); restart(); });
    ui.inspect.addEventListener("change", function () { inspect = ui.inspect.value; render(); });
    ui.first.addEventListener("click", function () { stop(); cur = 0; render(); });
    ui.prev.addEventListener("click", function () { stop(); cur = Math.max(0, cur - 1); render(); });
    ui.next.addEventListener("click", function () { stop(); cur = Math.min(steps.length - 1, cur + 1); render(); });
    ui.play.addEventListener("click", function () { if (timer) stop(); else start(); });
  }

  function stop() { if (timer) { clearInterval(timer); timer = null; } ui.play.textContent = "▶ Play"; }
  function start() {
    if (cur >= steps.length - 1) cur = 0;
    render();
    ui.play.textContent = "⏸ Pause";
    timer = setInterval(function () {
      if (cur >= steps.length - 1) { stop(); render(); return; }
      cur += 1; render();
    }, 1700);
  }
  function restart() { stop(); cur = 0; simulate(); render(); }
  function toggleCut(id) { cut[id] = !cut[id]; restart(); }

  function setCls(node, cls) { node.setAttribute("class", cls); }

  function render() {
    var s = steps[cur];
    var d = destInfo();
    /* links */
    Object.keys(ui.linkEls).forEach(function (id) {
      var isCut = !!cut[id];
      setCls(ui.linkEls[id], isCut ? "line-dash s-red" : "line");
      ui.cutMarks[id].style.display = isCut ? "" : "none";
      ui.linkBtns[id].setAttribute("aria-pressed", isCut ? "true" : "false");
    });
    var used = {};
    var prevNode = null;
    for (var i = 0; i <= cur && i < steps.length; i++) {
      if (prevNode && prevNode !== "L") used[lid(prevNode, steps[i].node)] = true;
      prevNode = steps[i].node;
    }
    Object.keys(used).forEach(function (id) {
      var e = ui.linkEls[id] || ui.linkEls[id.split("-").reverse().join("-")];
      if (e) setCls(e, "line s-green sw-3");
    });
    setCls(ui.lanLink, (cur >= 1 || dest === "P") ? "line s-green sw-3" : "line");
    /* nodes */
    ROUTERS.forEach(function (r) {
      var cls = "box2";
      if (s.node === r) cls += s.end === "drop" ? " s-red sw-3" : " s-yellow sw-3";
      setCls(ui.nodeEls[r], cls);
    });
    setCls(ui.laptop, "box" + (s.node === "L" ? " s-yellow sw-3" : ""));
    Object.keys(ui.hostEls).forEach(function (k) {
      var on = dest === k;
      var cls = "box" + (on ? " s-blue sw-2" : "");
      if (on && s.end === "ok") cls = "fs-green s-green sw-3";
      setCls(ui.hostEls[k], cls);
    });
    /* caption */
    ui.capHead.textContent = "";
    var strong = el("strong", null, "Step " + (cur + 1) + " of " + steps.length + " · " + s.head);
    ui.capHead.appendChild(strong);
    if (s.end) {
      var pill = el("span", "pill " + (s.end === "ok" ? "green" : "red"), s.end === "ok" ? "delivered" : "dropped");
      pill.style.marginLeft = "10px";
      ui.capHead.appendChild(pill);
    }
    ui.capText.textContent = s.text;
    /* table */
    var rname = inspect === "follow" ? (s.rows || (s.node !== "L" ? s.node : "R1")) : inspect;
    var onlyHere = inspect === "follow" && s.node === "L";
    var m = lookup(rname, d.ip);
    ui.tableBox.textContent = "";
    var title = el("div", "rt-tabletitle", "Routing table of " + rname + (onlyHere ? " (next stop; the laptop's own table is just \"default → R1\")" : "") + " · looking up " + d.ip);
    ui.tableBox.appendChild(title);
    var tbl = el("table", "rt-table");
    var thead = el("thead"); var hr = el("tr");
    ["Destination prefix", "Next hop", "For this packet"].forEach(function (h) { hr.appendChild(el("th", null, h)); });
    thead.appendChild(hr); tbl.appendChild(thead);
    var tb = el("tbody");
    if (!T[rname].length) { var er = el("tr"); var ec = el("td", null, "(empty)"); ec.colSpan = 3; er.appendChild(ec); tb.appendChild(er); }
    T[rname].forEach(function (row, idx) {
      var tr = el("tr");
      var isMatch = m.matches.indexOf(idx) >= 0, isChosen = m.chosen === idx;
      if (isChosen) tr.className = "chosen"; else if (isMatch) tr.className = "match";
      tr.appendChild(el("td", "mono", row.cidr + (row.def ? " (default)" : "")));
      tr.appendChild(el("td", "mono", row.connected ? "directly connected" : row.next));
      tr.appendChild(el("td", null, isChosen ? (m.matches.length > 1 ? "matches, longest prefix: used" : "matches: used") : isMatch ? "matches, but shorter" : "no match"));
      tb.appendChild(tr);
    });
    tbl.appendChild(tb); ui.tableBox.appendChild(tbl);
    /* buttons */
    ui.first.disabled = ui.prev.disabled = cur === 0;
    ui.next.disabled = cur >= steps.length - 1;
    ui.count.textContent = (cur + 1) + " / " + steps.length;
    if (s.ttl !== undefined) ui.count.textContent += " · TTL " + s.ttl;
  }

  build();
  restart();
})();
