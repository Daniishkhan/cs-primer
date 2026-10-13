/* Chapter 1: delivery time calculator (propagation vs transmission delay). */
(function () {
  "use strict";
  var root = document.getElementById("delay-widget");
  if (!root) return;

  var SPEED_KM_PER_S = 200000; // light in fibre, roughly

  var RANGES = {
    km: { min: 1, max: 20000 },
    mbps: { min: 1, max: 100000 },
    bytes: { min: 100, max: 1e10 }
  };
  var state = { km: 5600, mbps: 1000, bytes: 1000 };

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }
  function fromPos(key, p) {
    var r = RANGES[key];
    var v = Math.exp(Math.log(r.min) + (p / 1000) * (Math.log(r.max) - Math.log(r.min)));
    return Number(v.toPrecision(2));
  }
  function toPos(key, v) {
    var r = RANGES[key];
    return Math.round(1000 * (Math.log(v) - Math.log(r.min)) / (Math.log(r.max) - Math.log(r.min)));
  }
  function num(v) {
    if (v >= 100) return String(Math.round(v));
    return String(Number(v.toPrecision(3)));
  }
  function fmtTime(s) {
    if (s < 1e-3) return num(s * 1e6) + " µs";
    if (s < 1) return num(s * 1e3) + " ms";
    if (s < 120) return num(s) + " s";
    if (s < 7200) return num(s / 60) + " min";
    return num(s / 3600) + " h";
  }
  function fmtBytes(b) {
    if (b < 1e3) return Math.round(b) + " B";
    if (b < 1e6) return num(b / 1e3) + " KB";
    if (b < 1e9) return num(b / 1e6) + " MB";
    return num(b / 1e9) + " GB";
  }
  function fmtBw(m) { return m >= 1000 ? num(m / 1000) + " Gbps" : num(m) + " Mbps"; }
  function fmtKm(k) { return num(k) + " km"; }

  var head = el("div", "widget-head");
  head.appendChild(el("span", "widget-tag", "Interactive"));
  head.appendChild(el("h4", "widget-title", "Delivery time calculator"));
  root.appendChild(head);
  root.appendChild(el("p", "widget-help", "Drag the sliders (or pick an example). The bar shows where the time goes for one message sent one way, ignoring queuing and processing."));

  var presets = el("div", "widget-row");
  var PRESETS = [
    { t: "1 KB, London–New York, 1 Gbps", v: { km: 5600, mbps: 1000, bytes: 1e3 } },
    { t: "1 GB, London–New York, 1 Gbps", v: { km: 5600, mbps: 1000, bytes: 1e9 } },
    { t: "1 KB, 100 km, 10 Mbps", v: { km: 100, mbps: 10, bytes: 1e3 } },
    { t: "1 GB, 100 km, 10 Mbps", v: { km: 100, mbps: 10, bytes: 1e9 } }
  ];
  PRESETS.forEach(function (p) {
    var b = el("button", "btn small", p.t);
    b.type = "button";
    b.addEventListener("click", function () {
      state.km = p.v.km; state.mbps = p.v.mbps; state.bytes = p.v.bytes;
      syncSliders(); render();
    });
    presets.appendChild(b);
  });
  root.appendChild(presets);

  var grid = el("div", "dc-grid");
  var sliders = {}, outputs = {};
  function ctl(key, label, id) {
    var box = el("div", "dc-ctl");
    var l = el("label", null, label + " ");
    l.setAttribute("for", id);
    var o = el("output");
    o.setAttribute("for", id);
    l.appendChild(o);
    var s = el("input");
    s.type = "range"; s.id = id; s.min = "0"; s.max = "1000"; s.step = "1";
    s.addEventListener("input", function () {
      state[key] = fromPos(key, Number(s.value));
      render();
    });
    box.appendChild(l); box.appendChild(s);
    grid.appendChild(box);
    sliders[key] = s; outputs[key] = o;
  }
  ctl("km", "Distance", "dc-km");
  ctl("mbps", "Bandwidth", "dc-bw");
  ctl("bytes", "Message size", "dc-size");
  root.appendChild(grid);

  var bar = el("div", "dc-bar");
  bar.setAttribute("role", "img");
  var segP = el("span", "dc-prop"), segT = el("span", "dc-trans");
  bar.appendChild(segP); bar.appendChild(segT);
  root.appendChild(bar);

  var legend = el("div", "dc-legend");
  var lp = el("span"), lt = el("span");
  var ip = el("i", "dc-prop"), it = el("i", "dc-trans");
  var tp = el("span"), tt = el("span");
  lp.appendChild(ip); lp.appendChild(tp);
  lt.appendChild(it); lt.appendChild(tt);
  legend.appendChild(lp); legend.appendChild(lt);
  root.appendChild(legend);

  var stats = el("div", "nc-stats");
  function stat(name) {
    var s = el("div", "nc-stat");
    s.appendChild(el("span", "k", name));
    var v = el("span", "v");
    s.appendChild(v); stats.appendChild(s);
    return v;
  }
  var sTotal = stat("Total, one way"), sRtt = stat("Min. round trip"), sThr = stat("Effective rate");
  root.appendChild(stats);

  var verdict = el("div", "widget-out");
  verdict.setAttribute("aria-live", "polite");
  root.appendChild(verdict);

  function syncSliders() {
    Object.keys(sliders).forEach(function (k) { sliders[k].value = String(toPos(k, state[k])); });
  }

  function render() {
    outputs.km.textContent = fmtKm(state.km);
    outputs.mbps.textContent = fmtBw(state.mbps);
    outputs.bytes.textContent = fmtBytes(state.bytes);

    var prop = state.km / SPEED_KM_PER_S;
    var trans = (state.bytes * 8) / (state.mbps * 1e6);
    var total = prop + trans;
    var pp = (prop / total) * 100, pt = 100 - pp;
    segP.style.width = pp + "%";
    segT.style.width = pt + "%";
    bar.setAttribute("aria-label", "Propagation " + fmtTime(prop) + ", transmission " + fmtTime(trans));
    tp.textContent = "Propagation (distance ÷ speed): " + fmtTime(prop);
    tt.textContent = "Transmission (size ÷ bandwidth): " + fmtTime(trans);
    sTotal.textContent = fmtTime(total);
    sRtt.textContent = fmtTime(prop * 2);
    var eff = (state.bytes * 8) / total / 1e6;
    sThr.textContent = (eff >= 1000 ? num(eff / 1000) + " Gbps" : eff >= 1 ? num(eff) + " Mbps" : num(eff * 1000) + " kbps");

    var msg;
    if (prop > 10 * trans) {
      msg = "Latency-bound. Propagation is " + num(prop / trans) + "× larger than transmission. The message is tiny compared with the pipe, so the wait is almost all distance. A faster link would barely help; only a shorter path would.";
    } else if (trans > 10 * prop) {
      msg = "Bandwidth-bound. Transmission is " + num(trans / prop) + "× larger than propagation. Squeezing all those bits through the link takes far longer than the trip itself, so a fatter pipe is what helps.";
    } else {
      msg = "Both matter. Propagation and transmission are within a factor of ten of each other, so improving either one noticeably changes the total.";
    }
    verdict.textContent = msg;
  }

  syncSliders();
  render();
})();
