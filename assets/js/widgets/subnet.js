/* Chapter 4: subnet calculator + "is this IP in the subnet?" checker. */
(function () {
  "use strict";
  var root = document.getElementById("subnet-widget");
  if (!root) return;

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  // Returns an unsigned 32-bit integer, or null if s is not a clean dotted quad.
  function parseIP(s) {
    var parts = String(s).trim().split(".");
    if (parts.length !== 4) return null;
    var n = 0;
    for (var i = 0; i < 4; i++) {
      if (!/^\d{1,3}$/.test(parts[i])) return null;
      if (parts[i].length > 1 && parts[i][0] === "0") return null; // avoid ambiguous octal-looking input
      var v = parseInt(parts[i], 10);
      if (v > 255) return null;
      n = n * 256 + v;
    }
    return n;
  }
  function dotted(n) { return [n >>> 24, (n >>> 16) & 255, (n >>> 8) & 255, n & 255].join("."); }
  function maskOf(p) { return p === 0 ? 0 : (0xFFFFFFFF << (32 - p)) >>> 0; }
  function bin32(n) {
    var s = (n >>> 0).toString(2);
    while (s.length < 32) s = "0" + s;
    return s;
  }
  function fmtInt(n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ","); }

  // Append a 32-bit binary string as dotted octets, colouring the first `p` bits as network bits.
  function addBits(parent, n, p) {
    var s = bin32(n);
    for (var i = 0; i < 32; i++) {
      if (i > 0 && i % 8 === 0) parent.appendChild(el("span", "dot", "."));
      parent.appendChild(el("span", i < p ? "nb" : "hb", s[i]));
    }
  }

  // ---- UI ----
  var head = el("div", "widget-head");
  head.appendChild(el("span", "widget-tag", "Interactive"));
  head.appendChild(el("h4", "widget-title", "Subnet calculator"));
  root.appendChild(head);
  root.appendChild(el("p", "widget-help", "Type an address with a prefix like 192.168.1.20/24, or drag the slider to change the prefix length."));

  var row = el("div", "widget-row");
  var lab = el("label", null, "Address / prefix:");
  lab.setAttribute("for", "subnet-input");
  var inp = el("input", "mono sn-ip");
  inp.type = "text"; inp.id = "subnet-input"; inp.value = "192.168.1.20/24";
  inp.setAttribute("autocomplete", "off"); inp.setAttribute("spellcheck", "false"); inp.maxLength = 18;
  row.appendChild(lab); row.appendChild(inp);
  root.appendChild(row);

  var srow = el("div", "widget-row");
  var slab = el("label", null, "Prefix length: ");
  slab.setAttribute("for", "subnet-slider");
  var sval = el("output", "mono", "/24");
  sval.setAttribute("for", "subnet-slider");
  slab.appendChild(sval);
  var slider = el("input");
  slider.type = "range"; slider.id = "subnet-slider"; slider.min = "0"; slider.max = "32"; slider.step = "1"; slider.value = "24";
  slider.style.flex = "1"; slider.style.minWidth = "160px";
  srow.appendChild(slab); srow.appendChild(slider);
  root.appendChild(srow);

  var err = el("p", "sn-err");
  err.setAttribute("aria-live", "polite");
  root.appendChild(err);

  var bitsBox = el("div", "widget-out sn-bits");
  root.appendChild(bitsBox);
  var legend = el("p", "sn-legend");
  var l1 = el("span", "nb", "Blue = network bits (fixed)");
  var l2 = el("span", "hb", "Orange = host bits (free to vary)");
  legend.appendChild(l1); legend.appendChild(document.createTextNode("   ·   ")); legend.appendChild(l2);
  root.appendChild(legend);

  var stats = el("div", "nc-stats");
  var S = {};
  [["mask", "Subnet mask"], ["net", "Network address"], ["bcast", "Broadcast address"], ["first", "First usable host"], ["last", "Last usable host"], ["total", "Total addresses"], ["hosts", "Usable hosts"]].forEach(function (k) {
    var s = el("div", "nc-stat");
    s.appendChild(el("span", "k", k[1]));
    S[k[0]] = el("span", "v");
    s.appendChild(S[k[0]]);
    stats.appendChild(s);
  });
  root.appendChild(stats);

  root.appendChild(el("h4", "widget-title", "Is another address in this subnet?"));
  var crow = el("div", "widget-row");
  var clab = el("label", null, "Other IP:");
  clab.setAttribute("for", "subnet-other");
  var other = el("input", "mono sn-ip");
  other.type = "text"; other.id = "subnet-other"; other.value = "192.168.1.77";
  other.setAttribute("autocomplete", "off"); other.setAttribute("spellcheck", "false"); other.maxLength = 15;
  crow.appendChild(clab); crow.appendChild(other);
  root.appendChild(crow);
  var verdict = el("div", "widget-out");
  verdict.setAttribute("aria-live", "polite");
  root.appendChild(verdict);

  var cur = null; // {ip, p, mask, net, bcast}

  function parseMain() {
    var raw = inp.value.trim();
    var slash = raw.indexOf("/");
    var ipPart = slash >= 0 ? raw.slice(0, slash) : raw;
    var p = Number(slider.value);
    if (slash >= 0) {
      var ps = raw.slice(slash + 1).trim();
      if (!/^\d{1,2}$/.test(ps) || parseInt(ps, 10) > 32) return { error: "The prefix after the / must be a whole number from 0 to 32." };
      p = parseInt(ps, 10);
    }
    var ip = parseIP(ipPart);
    if (ip === null) return { error: "That doesn't look like an IPv4 address. Use four numbers from 0 to 255 separated by dots, like 192.168.1.20 (no leading zeros)." };
    return { ip: ip, p: p };
  }

  function update(fromSlider) {
    if (fromSlider) {
      var t = inp.value.trim();
      var i = t.indexOf("/");
      inp.value = (i >= 0 ? t.slice(0, i) : t) + "/" + slider.value;
    }
    var r = parseMain();
    err.textContent = "";
    if (r.error) {
      err.textContent = r.error;
      cur = null;
      bitsBox.textContent = "";
      Object.keys(S).forEach(function (k) { S[k].textContent = "–"; });
      verdict.textContent = "";
      return;
    }
    var p = r.p;
    slider.value = String(p);
    sval.textContent = "/" + p;
    var mask = maskOf(p);
    var net = (r.ip & mask) >>> 0;
    var bcast = (net | (~mask >>> 0)) >>> 0;
    var total = Math.pow(2, 32 - p);
    cur = { ip: r.ip, p: p, mask: mask, net: net, bcast: bcast };

    bitsBox.textContent = "";
    [["Address", r.ip], ["Subnet mask", mask], ["Network address (address AND mask)", net]].forEach(function (x) {
      bitsBox.appendChild(el("span", "lbl", x[0]));
      var line = el("div");
      addBits(line, x[1], p);
      bitsBox.appendChild(line);
    });

    S.mask.textContent = dotted(mask) + "  (/" + p + ")";
    S.net.textContent = dotted(net);
    S.total.textContent = fmtInt(total);
    if (p <= 30) {
      S.bcast.textContent = dotted(bcast);
      S.first.textContent = dotted(net + 1);
      S.last.textContent = dotted(bcast - 1);
      S.hosts.textContent = fmtInt(total - 2);
    } else if (p === 31) {
      S.bcast.textContent = "none (point-to-point link)";
      S.first.textContent = dotted(net);
      S.last.textContent = dotted(bcast);
      S.hosts.textContent = "2";
    } else {
      S.bcast.textContent = "none (single address)";
      S.first.textContent = dotted(net);
      S.last.textContent = dotted(net);
      S.hosts.textContent = "1";
    }
    check();
  }

  function check() {
    verdict.textContent = "";
    if (!cur) return;
    var o = parseIP(other.value);
    if (o === null) {
      var m = el("span", "sn-err", "Enter the other address as four numbers from 0 to 255, like 192.168.1.77.");
      verdict.appendChild(m);
      return;
    }
    var and = (o & cur.mask) >>> 0;
    var inside = and === cur.net;
    var line1 = el("div");
    line1.appendChild(document.createTextNode(dotted(o) + " AND " + dotted(cur.mask) + " = " + dotted(and)));
    var line2 = el("div");
    line2.appendChild(document.createTextNode("This network address is " + dotted(cur.net) + ". "));
    line2.appendChild(el("strong", inside ? "sn-ok" : "sn-bad", inside ? "Same? Yes: " + dotted(o) + " is inside this subnet (a direct delivery, no router needed)." : "Same? No: " + dotted(o) + " is outside this subnet (traffic would go via the router)."));
    verdict.appendChild(line1); verdict.appendChild(line2);
  }

  inp.addEventListener("input", function () { update(false); });
  slider.addEventListener("input", function () { update(true); });
  other.addEventListener("input", check);
  update(false);
})();
