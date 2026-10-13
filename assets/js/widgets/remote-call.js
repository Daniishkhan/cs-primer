/* "The uncertainty of a remote call" (chapter 15).
   The user picks where a failure happens. The sequence diagram changes,
   the "what really happened" panel changes, but the client's view never does. */
(function () {
  "use strict";
  var root = document.getElementById("remote-call");
  if (!root) return;

  var NS = "http://www.w3.org/2000/svg";
  var SCEN = [
    { id: "a", label: "Request lost", truth: "The request vanished in the network. The server never saw it.", done: false, effect: "The payment was NOT taken." },
    { id: "b", label: "Server crashed first", truth: "The request arrived, but the server crashed before doing anything.", done: false, effect: "The payment was NOT taken." },
    { id: "c", label: "Crash after the work", truth: "The server took the payment and saved it, then crashed before it could reply.", done: true, effect: "The payment WAS taken." },
    { id: "d", label: "Reply lost", truth: "The server took the payment and replied, but the reply was lost on the way back.", done: true, effect: "The payment WAS taken." },
    { id: "e", label: "Just slow", truth: "The server took the payment and replied, but everything was slow. The reply arrives after the client gave up.", done: true, effect: "The payment WAS taken." }
  ];

  var svg = root.querySelector(".rc-svg");
  var btnBox = root.querySelector(".rc-scn");
  var truthEl = root.querySelector(".rc-truth");
  var effectEl = root.querySelector(".rc-effect");
  var progress = root.querySelector(".rc-progress");
  var seen = {}, current = null, buttons = [];

  function s(tag, attrs, text) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function arrow(x1, y1, x2, y2, cls, dashed) {
    svg.appendChild(s("line", { x1: x1, y1: y1, x2: x2, y2: y2, "class": (dashed ? "line-dash " : "line ") + cls, "marker-end": "url(#ah15rc)" }));
  }
  function mark(x, y, txt, cls) { svg.appendChild(s("text", { x: x, y: y, "text-anchor": "middle", "class": "t-lg " + (cls || "") }, txt)); }
  function label(x, y, txt, cls, anchor) { svg.appendChild(s("text", { x: x, y: y, "text-anchor": anchor || "middle", "class": "t-sm " + (cls || "t-muted") }, txt)); }

  function draw(id) {
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    var defs = s("defs", {});
    var mk = s("marker", { id: "ah15rc", viewBox: "0 0 10 10", refX: "9", refY: "5", markerWidth: "7", markerHeight: "7", orient: "auto" });
    mk.appendChild(s("path", { d: "M0,0 L10,5 L0,10 z", "class": "arrowhead" }));
    defs.appendChild(mk); svg.appendChild(defs);

    var CX = 110, SX = 590;
    svg.appendChild(s("rect", { x: CX - 70, y: 6, width: 140, height: 30, rx: 8, "class": "fs-yellow s-yellow sw-2" }));
    label(CX, 26, "Client", "t-bold", "middle");
    svg.appendChild(s("rect", { x: SX - 70, y: 6, width: 140, height: 30, rx: 8, "class": "fs-purple s-purple sw-2" }));
    label(SX, 26, "Server (takes payment)", "t-bold", "middle");
    svg.appendChild(s("line", { x1: CX, y1: 38, x2: CX, y2: 290, "class": "line-thin" }));
    svg.appendChild(s("line", { x1: SX, y1: 38, x2: SX, y2: 290, "class": "line-thin" }));

    // client always sends
    arrow(CX + 2, 60, id === "a" ? 340 : SX - 2, id === "a" ? 90 : 90, "s-blue");
    label(CX + 6, 54, "\"charge £10\"", "tc-blue", "start");
    if (id === "a") mark(344, 98, "✕", "tc-red");

    if (id === "b") { svg.appendChild(s("circle", { cx: SX, cy: 112, r: 12, "class": "fs-red s-red sw-2" })); mark(SX, 118, "✕", "tc-red"); label(SX - 20, 138, "crashed", "tc-red", "end"); }
    if (id === "c") {
      label(SX - 20, 112, "payment saved", "tc-green t-bold", "end");
      svg.appendChild(s("circle", { cx: SX, cy: 134, r: 12, "class": "fs-red s-red sw-2" })); mark(SX, 140, "✕", "tc-red");
      label(SX - 20, 160, "crashed before replying", "tc-red", "end");
    }
    if (id === "d") {
      label(SX - 20, 112, "payment saved", "tc-green t-bold", "end");
      arrow(SX - 2, 130, 360, 170, "s-green");
      mark(356, 178, "✕", "tc-red");
      label(SX - 20, 164, "\"done\"", "tc-green", "end");
    }
    if (id === "e") {
      label(SX - 20, 112, "payment saved (slowly)", "tc-green t-bold", "end");
      arrow(SX - 2, 214, CX + 26, 252, "s-green", true);
      label(430, 252, "reply arrives too late", "tc-green", "middle");
    }

    // client side: waiting and timeout, identical for every scenario
    svg.appendChild(s("line", { x1: CX - 40, y1: 200, x2: CX + 40, y2: 200, "class": "line-dash s-yellow" }));
    label(CX - 46, 204, "timeout", "tc-yellow t-bold", "end");
    svg.appendChild(s("rect", { x: CX + 10, y: 120, width: 190, height: 22, rx: 6, "class": "fs-yellow" }));
    label(CX + 105, 135, "⏳ waiting, nothing arrives…", "tc-yellow", "middle");
    svg.appendChild(s("rect", { x: CX + 10, y: 206, width: 190, height: 22, rx: 6, "class": "fs-yellow s-yellow" }));
    label(CX + 105, 221, "❓ \"What happened?\"", "tc-yellow t-bold", "middle");
  }

  function show(i) {
    var sc = SCEN[i];
    current = i; seen[sc.id] = true;
    draw(sc.id);
    truthEl.textContent = sc.truth;
    effectEl.textContent = sc.effect;
    buttons.forEach(function (b, j) {
      b.setAttribute("aria-pressed", j === i ? "true" : "false");
      if (seen[SCEN[j].id]) b.classList.add("seen");
    });
    var n = Object.keys(seen).length;
    progress.textContent = n < SCEN.length
      ? "Scenarios explored: " + n + " of " + SCEN.length + ". Watch the left-hand panel."
      : "All five explored. The client's information was identical every time. Only the truth (and the money) differed.";
  }

  SCEN.forEach(function (sc, i) {
    var b = document.createElement("button");
    b.type = "button"; b.className = "btn small"; b.textContent = sc.label;
    b.setAttribute("aria-pressed", "false");
    b.addEventListener("click", function () { show(i); });
    btnBox.appendChild(b); buttons.push(b);
  });
  show(0);
})();
