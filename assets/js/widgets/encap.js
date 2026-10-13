/* Encapsulation explorer (chapter 3).
   Walks a message down the sender's layers, across a router, and up the
   receiver's layers, showing the nested headers and the byte overhead. */
(function () {
  "use strict";
  var root = document.getElementById("encap-widget");
  if (!root) return;

  var input = root.querySelector("#encap-msg");
  var stage = root.querySelector(".encap-stage");
  var track = root.querySelector(".encap-track");
  var caption = root.querySelector(".encap-caption");
  var stats = root.querySelector(".encap-stats");
  var prevBtn = root.querySelector("[data-act=prev]");
  var nextBtn = root.querySelector("[data-act=next]");
  var resetBtn = root.querySelector("[data-act=reset]");
  var count = root.querySelector(".encap-count");

  function eth(dst, src) {
    return { key: "eth", name: "Ethernet frame", layer: "Link layer", color: "orange", bytes: 14, trailer: 4,
      fields: [["dst MAC", dst], ["src MAC", src], ["type", "IPv4"]] };
  }
  function ip(ttl) {
    return { key: "ip", name: "IP packet", layer: "Network layer", color: "green", bytes: 20,
      fields: [["src IP", "192.168.1.20"], ["dst IP", "93.184.216.34"], ["TTL", String(ttl)]] };
  }
  var tcp = { key: "tcp", name: "TCP segment", layer: "Transport layer", color: "blue", bytes: 20,
    fields: [["src port", "51734"], ["dst port", "80"], ["seq #", "1"]] };

  var LAPTOP = "laptop a4:83:e7:1c:52:2f", ROUTER_IN = "router 0c:4a:9b:20:11:91",
      ROUTER_OUT = "router 0c:4a:9b:20:11:92", NEXT = "next-hop 3e:01:77:a0:5d:10",
      SRV_GW = "dc-switch 58:11:0a:42:9e:01", SERVER = "server 00:1b:21:3a:8f:c4";

  var steps = [
    { at: 0, layers: [], title: "Application layer: your browser writes a message",
      text: "The browser wants a picture, so it writes an HTTP request. To the application this is the whole story; it has no idea how the bytes will travel." },
    { at: 0, layers: [tcp], hl: ["tcp"], title: "Transport layer adds a TCP header (+20 bytes)",
      text: "The operating system wraps the data in a TCP header. The <b>ports</b> say which program should receive it (port 80 = web server) and the <b>sequence number</b> lets the receiver put pieces back in order." },
    { at: 0, layers: [ip(64), tcp], hl: ["ip"], title: "Network layer adds an IP header (+20 bytes)",
      text: "Now the IP header: the <b>source and destination IP addresses</b> of the two computers, plus a TTL counter that stops lost packets from circling forever. Notice the TCP segment is now just the <i>payload</i> of the IP packet." },
    { at: 0, layers: [eth(ROUTER_IN, LAPTOP), ip(64), tcp], hl: ["eth"], title: "Link layer adds an Ethernet header + trailer (+18 bytes)",
      text: "Finally the network card wraps everything in a frame for <b>this one hop</b> only: from the laptop's hardware (MAC) address to the router's. The trailer is a checksum to detect bits damaged on the wire." },
    { at: 0.5, bits: true, layers: [eth(ROUTER_IN, LAPTOP), ip(64), tcp], title: "Physical layer: it's all just bits now",
      text: "The physical layer doesn't care about headers; it turns the whole frame into a stream of 1s and 0s: voltages on copper, flashes of light, or radio waves." },
    { at: 1, layers: [ip(63), tcp], hl: ["TTL"], title: "Router: unwrap the frame, read the IP header",
      text: "The router receives the frame, checks it was addressed to its MAC, and throws the Ethernet wrapper away. It reads the <b>destination IP</b> to choose the next hop, and lowers the TTL by one (64 → 63). It never looks inside the TCP segment." },
    { at: 1, layers: [eth(NEXT, ROUTER_OUT), ip(63), tcp], hl: ["eth"], title: "Router: re-wrap in a brand-new frame",
      text: "For the next hop the router builds a <b>new</b> Ethernet frame with new MAC addresses. The IP addresses stay the same end to end; the MAC addresses change at every hop. (Home routers also rewrite the source IP. That's NAT, chapter 4.)" },
    { at: 2, layers: [eth(SERVER, SRV_GW), ip(52), tcp], title: "…many hops later, the server receives a frame",
      text: "After a dozen or so more routers (each one unwrapping and re-wrapping), a frame arrives at the server. TTL has dropped to 52. Now the server unwraps, layer by layer, in the reverse order." },
    { at: 2, layers: [ip(52), tcp], hl: ["ip"], title: "Server's link layer strips the frame",
      text: "The checksum is fine and the destination MAC is its own, so the network card removes the Ethernet header and trailer and passes the IP packet up." },
    { at: 2, layers: [tcp], hl: ["tcp"], title: "Server's network layer strips the IP header",
      text: "The destination IP matches this server, so the IP header is removed and the TCP segment is passed up to the transport layer." },
    { at: 2, layers: [], done: true, title: "Server's transport layer delivers to port 80",
      text: "TCP checks the sequence number, sends an acknowledgement, removes its header and hands the bytes to whichever program is listening on port 80: the web server. It reads exactly what the browser wrote. 🎉" }
  ];

  var i = 0;

  function message() { return (input.value || "GET /cat.jpg").slice(0, 60); }
  function byteLen(s) { return new TextEncoder().encode(s).length; }

  function node(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function renderLayer(layers, k, hl, msg, done) {
    if (k >= layers.length) {
      var d = node("div", "encap-data" + (done ? " done" : ""));
      d.appendChild(node("span", "encap-label", "data"));
      d.appendChild(node("code", null, msg));
      return d;
    }
    var L = layers[k];
    var box = node("div", "encap-layer c-" + L.color + (hl.indexOf(L.key) >= 0 ? " fresh" : ""));
    var head = node("div", "encap-head");
    head.appendChild(node("span", "encap-name", L.name));
    head.appendChild(node("span", "encap-sub", L.layer + " · " + L.bytes + " B header" + (L.trailer ? " + " + L.trailer + " B trailer" : "")));
    box.appendChild(head);
    var fields = node("div", "encap-fields");
    L.fields.forEach(function (f) {
      var p = node("span", "encap-field" + (hl.indexOf(f[0]) >= 0 ? " fresh" : ""));
      p.appendChild(node("small", null, f[0]));
      p.appendChild(document.createTextNode(f[1]));
      fields.appendChild(p);
    });
    box.appendChild(fields);
    box.appendChild(renderLayer(layers, k + 1, hl, msg, done));
    if (L.trailer) box.appendChild(node("div", "encap-trailer", "checksum (FCS)"));
    return box;
  }

  function bits(msg) {
    return Array.prototype.map.call(new TextEncoder().encode(msg), function (b) {
      return ("0000000" + b.toString(2)).slice(-8);
    }).join(" ");
  }

  function render() {
    var s = steps[i], msg = message();
    stage.innerHTML = "";
    if (s.bits) {
      var b = node("div", "encap-bits");
      b.appendChild(node("div", "encap-sub", "The bits of your message alone (headers become bits the same way):"));
      b.appendChild(node("code", null, bits(msg)));
      stage.appendChild(b);
    } else {
      stage.appendChild(renderLayer(s.layers, 0, s.hl || [], msg, s.done));
    }

    track.querySelectorAll("[data-at]").forEach(function (n) {
      n.classList.toggle("here", parseFloat(n.dataset.at) === s.at);
    });

    caption.innerHTML = "";
    caption.appendChild(node("strong", null, s.title));
    var p = node("p"); p.innerHTML = s.text; caption.appendChild(p);

    var payload = byteLen(msg);
    var header = s.layers.reduce(function (sum, L) { return sum + L.bytes + (L.trailer || 0); }, 0);
    var total = payload + header;
    stats.innerHTML = "";
    [["your data", payload + " B"], ["headers", header + " B"], ["total", total + " B"],
     ["overhead", total ? Math.round((header / total) * 100) + "%" : "0%"]].forEach(function (x) {
      var pill = node("span", "pill"); pill.textContent = x[0] + ": " + x[1]; stats.appendChild(pill);
    });

    count.textContent = (i + 1) + " / " + steps.length;
    prevBtn.disabled = i === 0;
    nextBtn.disabled = i === steps.length - 1;
  }

  prevBtn.addEventListener("click", function () { if (i > 0) { i--; render(); } });
  nextBtn.addEventListener("click", function () { if (i < steps.length - 1) { i++; render(); } });
  resetBtn.addEventListener("click", function () { i = 0; render(); });
  input.addEventListener("input", render);
  render();
})();
