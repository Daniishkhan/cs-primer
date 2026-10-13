/* Choreography vs orchestration (architecture chapter 14).

   The same order flow, Order -> Payment -> Inventory -> Shipping -> Notification,
   shown twice, side by side:
     choreography  - services react to each other's events on a bus; nobody owns the flow;
     orchestration - an orchestrator sends commands and waits for replies; it owns the flow.
   One shared step counter drives both panes. Four scenarios:
     normal   the happy path
     fraud    "add a fraud check between order and payment": the nodes that must change
              are marked "edit" (existing code) or "new"; the subscription lines change
     down     "payment service is down": what each style does
     where    "where is order 42?": choreography asks every service, orchestration asks one
   Every pane is generated from small script tables below, so the widget is fully
   deterministic: no timers, no randomness. Structure is built once and updated in place
   so keyboard focus is never lost.

   Simplifications: the bus is assumed to be a durable broker; the orchestrator's own
   state is assumed durable (chapter 15 shows how). */
(function () {
  "use strict";
  var root = document.getElementById("choreo-orch");
  if (!root) return;

  var NODE_NAMES = { hub: "", order: "Order", fraud: "Fraud", payment: "Payment", inventory: "Inventory", shipping: "Shipping", notify: "Notification" };
  var ORDER = ["hub", "order", "fraud", "payment", "inventory", "shipping", "notify"];

  var SCEN = [
    { id: "normal", label: "Happy path" },
    { id: "fraud", label: "Add a fraud check between order and payment" },
    { id: "down", label: "Payment service is down" },
    { id: "where", label: "Where is order 42?" }
  ];

  /* ---------- scripts ---------- */
  function st(from, to, msg, kind, text, active, extra) {
    var s = { from: from, to: to, msg: msg, kind: kind, text: text, active: active };
    if (extra) for (var k in extra) s[k] = extra[k];
    return s;
  }

  function choreo(sc) {
    var steps = [], e = "event";
    if (sc === "where") {
      steps.push(st("you", "Order", "Where is order 42?", "query", "Order service: \"I published OrderPlaced. After that I know nothing.\"", ["order"]));
      steps.push(st("you", "Payment", "Where is order 42?", "query", "Payment: \"I took the money and published PaymentTaken.\"", ["payment"]));
      steps.push(st("you", "Inventory", "Where is order 42?", "query", "Inventory: \"Stock reserved, StockReserved published.\"", ["inventory"]));
      steps.push(st("you", "Shipping", "Where is order 42?", "query", "Shipping: \"I saw StockReserved, but I have not booked a courier yet.\"", ["shipping"]));
      steps.push(st("you", "Notification", "Where is order 42?", "query", "Notification: \"I have sent nothing for order 42.\"", ["notify"]));
      steps.push(st("you", "you", "(stitch the answers together)", "note", "You assemble the story: payment done, stock reserved, waiting at Shipping. Five questions, and you had to know which five services to ask and in what order. A tracking service that listens to every event would help, but then you have built a small orchestrator's memory anyway.", []));
      return { steps: steps, take: "Choreography: the answer is spread over every service. Finding one order means asking them all." };
    }
    if (sc === "down") {
      steps.push(st("Order", "bus", "OrderPlaced", e, "Order records the order and publishes OrderPlaced. From its point of view the job is done.", ["order", "hub"]));
      steps.push(st("bus", "Payment", "OrderPlaced", "fault", "Payment is down. A durable broker keeps OrderPlaced waiting in Payment's queue, so nothing is lost, but nothing moves either. Inventory, Shipping and Notification just sit idle: nobody told them anything.", ["payment"], { down: ["payment"] }));
      steps.push(st("customer", "customer", "(sees \"order received\")", "note", "Nobody is in charge of noticing the order is stuck. Spotting it needs a separate monitor that knows the expected sequence (a workflow definition you never wrote down), or a customer complaint.", []));
      return { steps: steps, take: "Choreography: failure is contained and nothing is lost, but nobody decides what to do about it. The stall is silent." };
    }
    var fraud = sc === "fraud";
    steps.push(st("Order", "bus", "OrderPlaced", e, "Order records the order and publishes OrderPlaced. It does not know who is listening.", ["order", "hub"]));
    if (fraud) steps.push(st("bus", "Fraud", "OrderPlaced", e, "The new Fraud service listens for OrderPlaced, screens the order and publishes OrderCleared.", ["fraud", "hub"]));
    steps.push(st("bus", "Payment", fraud ? "OrderCleared" : "OrderPlaced", e, fraud ? "Payment used to listen for OrderPlaced. To put fraud in front of it, its subscription had to be changed to OrderCleared. It charges the card and publishes PaymentTaken." : "Payment reacts to OrderPlaced, charges the card and publishes PaymentTaken.", ["payment", "hub"]));
    steps.push(st("bus", "Inventory", "PaymentTaken", e, "Inventory reacts to PaymentTaken, reserves stock and publishes StockReserved.", ["inventory", "hub"]));
    steps.push(st("bus", "Shipping", "StockReserved", e, "Shipping reacts to StockReserved, books a courier and publishes ShipmentBooked.", ["shipping", "hub"]));
    steps.push(st("bus", "Notification", "ShipmentBooked", e, "Notification reacts to ShipmentBooked and emails the customer. The flow ends. " + (fraud ? "If Fraud ever rejects an order and publishes OrderRejected, Notification must also learn to react to that, or the customer hears nothing." : "No single place ever held the whole flow: it exists only as the sum of five subscriptions."), ["notify", "hub"]));
    return { steps: steps, take: fraud
      ? "Choreography: 1 new service, 2 existing services edited (Payment's trigger, Notification's handlers), and the only record of the flow is spread over their subscriptions."
      : "Choreography: each service knows only its own trigger. Low coupling, but the flow is implicit." };
  }

  function orch(sc) {
    var steps = [], c = "command", r = "reply";
    if (sc === "where") {
      steps.push(st("you", "Orchestrator", "GetStatus(order 42)", "query", "One question, to the one component that owns the flow.", ["hub"]));
      steps.push(st("Orchestrator", "you", "AWAITING_SHIPMENT", "answer", "Answer from its saga state: PaymentTaken yes, StockReserved yes, BookShipment sent, no reply yet. Done in two messages.", ["hub"]));
      return { steps: steps, take: "Orchestration: the flow's state is in one place, so \"where is it?\" is one lookup. The price: that component must keep its state durable and correct." };
    }
    if (sc === "down") {
      steps.push(st("Order", "Orchestrator", "PlaceOrder", c, "Order asks the orchestrator to run the order workflow. The orchestrator creates a record for order 42.", ["order", "hub"]));
      steps.push(st("Orchestrator", "Payment", "TakePayment", "fault", "The orchestrator sends TakePayment. Payment is down, so no reply arrives.", ["hub", "payment"], { down: ["payment"] }));
      steps.push(st("Orchestrator", "Payment", "TakePayment (retry)", "fault", "Its timeout fires and the policy says retry with a delay. Still no reply. Inventory and Shipping have not been touched.", ["hub"]));
      steps.push(st("Orchestrator", "Order", "OrderOnHold", c, "Retries exhausted: the orchestrator sets the order to PAYMENT_UNAVAILABLE, tells Order to show \"we'll retry\" and schedules a later attempt. The decision lives in one place and the stuck order is visible.", ["hub", "order"]));
      return { steps: steps, take: "Orchestration: one component notices, retries and decides. The cost is that this component is now a critical dependency." };
    }
    var fraud = sc === "fraud";
    steps.push(st("Order", "Orchestrator", "PlaceOrder", c, "Order asks the orchestrator to run the order workflow. The orchestrator creates a record for order 42.", ["order", "hub"]));
    if (fraud) {
      steps.push(st("Orchestrator", "Fraud", "ScreenOrder", c, "The new step: the orchestrator tells the Fraud service to screen the order.", ["hub", "fraud"]));
      steps.push(st("Fraud", "Orchestrator", "Cleared", r, "Fraud replies Cleared (a rejection would end the workflow right here, with the refusal handled in the orchestrator).", ["fraud", "hub"]));
    }
    var seq = [["Payment", "payment", "TakePayment", "PaymentTaken"], ["Inventory", "inventory", "ReserveStock", "StockReserved"],
               ["Shipping", "shipping", "BookShipment", "ShipmentBooked"], ["Notification", "notify", "SendReceipt", "ReceiptSent"]];
    seq.forEach(function (s, i) {
      steps.push(st("Orchestrator", s[0], s[2], c, "The orchestrator tells " + s[0] + " what to do: " + s[2] + "." + (i === 0 && fraud ? " Payment's code is untouched: it still just obeys TakePayment." : ""), ["hub", s[1]]));
      steps.push(st(s[0], "Orchestrator", s[3], r, s[0] + " replies " + s[3] + (i === 3 ? ". The workflow is complete." : "."), [s[1], "hub"]));
    });
    return { steps: steps, take: fraud
      ? "Orchestration: 1 new service and 1 edited component, the orchestrator, where the new step is one added line. Payment and Notification are unchanged."
      : "Orchestration: the flow is one readable sequence. The services are simple, but they depend on the orchestrator." };
  }

  /* ---------- per-scenario node details ---------- */
  function nodeInfo(style, sc) {
    var fraud = sc === "fraud", d = {};
    if (style === "choreo") {
      d.hub = { name: "Event bus", sub: "delivers events to subscribers" };
      d.order = { sub: "publishes OrderPlaced" };
      d.fraud = { sub: "OrderPlaced → OrderCleared", mark: "new" };
      d.payment = { sub: (fraud ? "OrderCleared" : "OrderPlaced") + " → PaymentTaken", mark: fraud ? "edit" : "" };
      d.inventory = { sub: "PaymentTaken → StockReserved" };
      d.shipping = { sub: "StockReserved → ShipmentBooked" };
      d.notify = { sub: "ShipmentBooked → email" + (fraud ? "; OrderRejected → email" : ""), mark: fraud ? "edit" : "" };
    } else {
      d.hub = { name: "Orchestrator", sub: "owns the flow and its state", mark: fraud ? "edit" : "" };
      d.order = { sub: "asks to start the workflow" };
      d.fraud = { sub: "obeys ScreenOrder", mark: "new" };
      d.payment = { sub: "obeys TakePayment" };
      d.inventory = { sub: "obeys ReserveStock" };
      d.shipping = { sub: "obeys BookShipment" };
      d.notify = { sub: "obeys SendReceipt" };
    }
    return d;
  }

  /* ---------- state ---------- */
  var scen = "normal", idx = -1;
  var panes = {};

  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function btn(label, cls, fn) { var b = el("button", "btn " + (cls || ""), label); b.type = "button"; b.addEventListener("click", fn); return b; }

  /* ---------- build ---------- */
  var head = el("div", "widget-head");
  head.appendChild(el("span", "widget-tag", "Simulator"));
  head.appendChild(el("span", "widget-title", "Choreography vs orchestration"));
  root.appendChild(head);
  root.appendChild(el("p", "widget-help", "The same order flow, wired two ways. Use Step to advance both panes together, then try each scenario button to see how the two styles cope with change, failure and a simple question."));

  root.appendChild(el("p", "co-label", "Scenario"));
  var scrow = el("div", "co-btns"); scrow.setAttribute("role", "group"); scrow.setAttribute("aria-label", "Scenario");
  var scbtns = {};
  SCEN.forEach(function (s) {
    var b = btn(s.label, "", function () { scen = s.id; idx = -1; render(); });
    scbtns[s.id] = b; scrow.appendChild(b);
  });
  root.appendChild(scrow);

  var ctl = el("div", "co-btns co-ctl");
  var bBack = btn("← Back", "small", function () { if (idx > -1) { idx--; render(); } });
  var bStep = btn("Step →", "primary small", function () { if (idx < maxLen() - 1) { idx++; render(); } });
  var bReset = btn("Reset", "small", function () { idx = -1; render(); });
  var count = el("span", "co-count");
  ctl.appendChild(bBack); ctl.appendChild(bStep); ctl.appendChild(bReset); ctl.appendChild(count);
  root.appendChild(ctl);

  var cols = el("div", "co-cols");
  [["choreo", "Choreography", "services react to events"], ["orch", "Orchestration", "a coordinator sends commands"]].forEach(function (p) {
    var pane = el("div", "co-pane " + p[0]);
    var h = el("h5", null, p[1]); h.appendChild(el("span", "co-h-sub", " " + p[2])); pane.appendChild(h);
    var nodes = el("div", "co-nodes"), map = {};
    ORDER.forEach(function (id) {
      var n = el("div", "co-node");
      var t = el("div", "co-node-top");
      var nm = el("span", "co-node-name"); var mk = el("span", "co-mark");
      t.appendChild(nm); t.appendChild(mk); n.appendChild(t);
      var sub = el("div", "co-node-sub"); n.appendChild(sub);
      nodes.appendChild(n); map[id] = { box: n, name: nm, mark: mk, sub: sub };
    });
    pane.appendChild(nodes);
    var now = el("p", "co-now"); now.setAttribute("aria-live", "polite"); pane.appendChild(now);
    var log = el("ol", "co-log"); pane.appendChild(log);
    var take = el("p", "co-take"); pane.appendChild(take);
    cols.appendChild(pane);
    panes[p[0]] = { nodes: map, now: now, log: log, take: take, pane: pane };
  });
  root.appendChild(cols);

  function maxLen() { return Math.max(choreo(scen).steps.length, orch(scen).steps.length); }

  /* ---------- render ---------- */
  function renderPane(style) {
    var P = panes[style], sc = style === "choreo" ? choreo(scen) : orch(scen), info = nodeInfo(style, scen);
    var steps = sc.steps, last = Math.min(idx, steps.length - 1);
    var touched = {}, down = {}, i;
    for (i = 0; i <= last; i++) {
      var s = steps[i];
      if (i < last) s.active.forEach(function (a) { touched[a] = true; });
      (s.down || []).forEach(function (d) { down[d] = true; });
    }
    var cur = last >= 0 ? steps[last] : null;
    ORDER.forEach(function (id) {
      var n = P.nodes[id], d = info[id];
      var hidden = id === "fraud" && scen !== "fraud";
      n.box.hidden = hidden;
      if (hidden) return;
      var mark = scen === "fraud" ? d.mark || "" : "";
      var isNow = cur && cur.active.indexOf(id) >= 0;
      var cls = "co-node";
      if (down[id]) cls += " down"; else if (isNow) cls += " now"; else if (touched[id]) cls += " done";
      if (mark === "edit") cls += " edit"; else if (mark === "new") cls += " new";
      n.box.className = cls;
      n.name.textContent = d.name || NODE_NAMES[id];
      n.mark.textContent = mark === "edit" ? "must change" : mark === "new" ? "new" : (down[id] ? "down" : "");
      n.sub.textContent = d.sub;
    });
    if (!cur) {
      P.now.textContent = scen === "fraud"
        ? "Highlighted boxes show what must change when the fraud check is added. Press Step to run the new flow."
        : "Press Step to begin.";
    } else if (idx >= steps.length) {
      P.now.textContent = "Finished: this style needed only " + steps.length + " steps here.";
    } else {
      P.now.textContent = cur.text;
    }
    P.log.textContent = "";
    for (i = 0; i <= last; i++) {
      var li = el("li", "co-" + steps[i].kind + (i === last && idx < steps.length ? " cur" : ""));
      var m = el("strong", null, steps[i].msg);
      li.appendChild(m);
      li.appendChild(document.createTextNode("  " + steps[i].from + " → " + steps[i].to));
      P.log.appendChild(li);
    }
    P.take.textContent = (scen === "fraud" || idx >= steps.length - 1 && idx >= 0) ? sc.take : "";
    P.take.hidden = !P.take.textContent;
    P.pane.classList.toggle("co-finished", idx >= steps.length - 1 && idx >= 0);
  }

  function render() {
    SCEN.forEach(function (s) { scbtns[s.id].setAttribute("aria-pressed", String(s.id === scen)); });
    var n = maxLen();
    bBack.disabled = idx < 0;
    bStep.disabled = idx >= n - 1;
    count.textContent = idx < 0 ? "Step 0 of " + n : "Step " + (idx + 1) + " of " + n;
    renderPane("choreo");
    renderPane("orch");
  }
  render();
})();
