/* Sketch mode: redraws the static diagrams (figure.diagram and .stepper SVGs)
   in a hand-drawn, Excalidraw-like style with Rough.js.

   For every shape it adds a rough "twin" right after the original:
   - the original keeps its fill and arrow markers; only its stroke is hidden
     (html.sketch [data-sk] in main.css), so layout and tints are unchanged;
   - the twin draws a wobbly outline, plus light hachure on soft-tinted areas.
   Labels switch to a handwriting font (Shantell Sans, the tldraw font) and are shrunk if they got wider.
   Colors are read from the current theme, so the layer is rebuilt when the
   theme changes. Custom widgets are left alone (they redraw themselves). */
(function () {
  "use strict";
  if (!window.rough) return;

  var html = document.documentElement;
  var SHAPES = "rect,circle,ellipse,line,polyline,polygon,path";
  var TARGETS = "figure.diagram svg, .stepper svg";
  var page = location.pathname.split("/").pop() || "index";
  var observers = [];

  function hash(s) {
    var h = 2166136261;
    for (var i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); }
    return (h >>> 0) % 2147483646 + 1;
  }
  function num(el, name) { return parseFloat(el.getAttribute(name)) || 0; }
  function alphaOf(c) {
    if (!c || c === "none" || c === "transparent") return 0;
    var slash = c.match(/\/\s*([\d.]+%?)\s*\)\s*$/);
    if (slash) return slash[1].slice(-1) === "%" ? parseFloat(slash[1]) / 100 : parseFloat(slash[1]);
    var rgba = c.match(/^rgba\(([^)]+)\)/);
    if (rgba) { var p = rgba[1].split(","); return p.length > 3 ? parseFloat(p[3]) : 1; }
    return 1;
  }
  function opaque(c) {
    // Same color without alpha, for hachure lines drawn from a soft tint.
    return c.replace(/\s*\/\s*[\d.]+%?\s*\)\s*$/, ")").replace(/^rgba\(([^,]+),([^,]+),([^,]+),[^)]+\)/, "rgb($1,$2,$3)");
  }
  function points(el) {
    var nums = (el.getAttribute("points") || "").trim().split(/[\s,]+/).map(parseFloat);
    var out = [];
    for (var i = 0; i + 1 < nums.length; i += 2) out.push([nums[i], nums[i + 1]]);
    return out;
  }
  function roundedRect(x, y, w, h, r) {
    r = Math.min(r, w / 2, h / 2);
    return "M" + (x + r) + "," + y + " H" + (x + w - r) + " Q" + (x + w) + "," + y + " " + (x + w) + "," + (y + r) +
      " V" + (y + h - r) + " Q" + (x + w) + "," + (y + h) + " " + (x + w - r) + "," + (y + h) +
      " H" + (x + r) + " Q" + x + "," + (y + h) + " " + x + "," + (y + h - r) + " V" + (y + r) +
      " Q" + x + "," + y + " " + (x + r) + "," + y + " Z";
  }

  // Draw one shape with the given options; returns an <g> or null.
  function draw(rc, el, opts) {
    switch (el.tagName.toLowerCase()) {
      case "rect": {
        var x = num(el, "x"), y = num(el, "y"), w = num(el, "width"), h = num(el, "height");
        var r = num(el, "rx") || num(el, "ry");
        if (w <= 0 || h <= 0) return null;
        return r > 0 ? rc.path(roundedRect(x, y, w, h, r), opts) : rc.rectangle(x, y, w, h, opts);
      }
      case "circle": return rc.circle(num(el, "cx"), num(el, "cy"), 2 * num(el, "r"), opts);
      case "ellipse": return rc.ellipse(num(el, "cx"), num(el, "cy"), 2 * num(el, "rx"), 2 * num(el, "ry"), opts);
      case "line": return rc.line(num(el, "x1"), num(el, "y1"), num(el, "x2"), num(el, "y2"), opts);
      case "polyline": return rc.linearPath(points(el), opts);
      case "polygon": return rc.polygon(points(el), opts);
      case "path": return el.getAttribute("d") ? rc.path(el.getAttribute("d"), opts) : null;
    }
    return null;
  }

  // Rough writes colors as presentation attributes; move them into style so
  // any CSS color syntax (color(), url(#gradient)) works.
  function styleize(g) {
    g.querySelectorAll("path").forEach(function (p) {
      ["stroke", "fill"].forEach(function (k) {
        var v = p.getAttribute(k);
        if (v !== null) { p.style[k] = v; p.removeAttribute(k); }
      });
    });
  }

  function sketchSvg(svg, svgIndex) {
    var rc = rough.svg(svg);
    var shapes = Array.prototype.slice.call(svg.querySelectorAll(SHAPES));
    shapes.forEach(function (el, i) {
      if (el.closest("defs, marker, .sk") || el.classList.contains("flow")) return;
      var cs = getComputedStyle(el);
      if (cs.display === "none" || cs.visibility === "hidden") return;
      var stroke = cs.stroke, fill = cs.fill;
      var sw = parseFloat(cs.strokeWidth) || 1;
      var hasStroke = sw > 0 && (stroke.indexOf("url(") === 0 || alphaOf(stroke) > 0);
      var fillA = fill.indexOf("url(") === 0 ? 1 : alphaOf(fill);
      var tag = el.tagName.toLowerCase();
      var isLine = tag === "line" || tag === "polyline" || (tag === "path" && fillA === 0);
      if (!hasStroke && fillA === 0) return;

      var seed = hash(page + ":" + svgIndex + ":" + i);
      var dash = cs.strokeDasharray && cs.strokeDasharray !== "none"
        ? cs.strokeDasharray.split(/[\s,]+/).map(parseFloat).filter(function (n) { return n > 0; }) : null;
      var base = { seed: seed, roughness: isLine ? 0.9 : 1.15, bowing: isLine ? 0.6 : 1, disableMultiStroke: false, preserveVertices: true };

      var twin = document.createElementNS("http://www.w3.org/2000/svg", "g");
      twin.setAttribute("class", "sk");
      twin.setAttribute("aria-hidden", "true");
      if (el.getAttribute("transform")) twin.setAttribute("transform", el.getAttribute("transform"));
      if (cs.opacity !== "1") twin.style.opacity = cs.opacity;

      // Light hachure on soft-tinted areas big enough to read.
      if (!isLine && fillA > 0 && fillA < 0.6) {
        var bb = el.getBBox();
        if (bb.width * bb.height > 1600) {
          var hatch = draw(rc, el, Object.assign({}, base, {
            stroke: "none", fill: opaque(fill), fillStyle: "hachure", hachureAngle: -41,
            hachureGap: 9, fillWeight: 1
          }));
          if (hatch) { hatch.style.opacity = "0.26"; twin.appendChild(hatch); }
        }
      }

      // Wobbly outline: the shape's stroke, or (for solid shapes without one) its own fill color.
      var outlineColor = hasStroke ? stroke : (fillA >= 0.6 ? fill : null);
      if (outlineColor) {
        var outline = draw(rc, el, Object.assign({}, base, {
          stroke: outlineColor, strokeWidth: hasStroke ? Math.max(1, sw) : 1.4, fill: undefined,
          strokeLineDash: dash || undefined
        }));
        if (outline) twin.appendChild(outline);
      }
      if (!twin.childNodes.length) return;
      styleize(twin);

      el.setAttribute("data-sk", hasStroke ? "stroke" : "fill");
      el.parentNode.insertBefore(twin, el.nextSibling);

      // Shapes that the stepper shows/hides directly: mirror its classes onto the twin.
      if (el.hasAttribute("data-steps") || el.hasAttribute("data-active")) {
        if (el.hasAttribute("data-steps")) twin.setAttribute("data-steps", el.getAttribute("data-steps"));
        var sync = function () {
          twin.classList.toggle("step-hidden", el.classList.contains("step-hidden"));
          twin.classList.toggle("step-active", el.classList.contains("step-active"));
        };
        sync();
        var mo = new MutationObserver(sync);
        mo.observe(el, { attributes: true, attributeFilter: ["class"] });
        observers.push(mo);
      }
    });
  }

  /* ---------- handwriting labels, shrunk to their clean width ---------- */

  function texts() { return document.querySelectorAll("figure.diagram svg text, .stepper svg text"); }

  function measureClean() {
    html.classList.add("sk-measure");
    texts().forEach(function (t) {
      if (!t.hasAttribute("data-w0")) {
        try { t.setAttribute("data-w0", String(t.getComputedTextLength())); } catch (e) { /* not rendered */ }
      }
    });
    html.classList.remove("sk-measure");
  }
  function fitText() {
    texts().forEach(function (t) {
      var w0 = parseFloat(t.getAttribute("data-w0"));
      if (!w0) return;
      var w1;
      try { w1 = t.getComputedTextLength(); } catch (e) { return; }
      if (w1 > w0 * 1.03) {
        var size = parseFloat(getComputedStyle(t).fontSize);
        t.style.fontSize = (size * w0 / w1).toFixed(2) + "px";
        t.setAttribute("data-skfit", "");
      }
    });
  }

  /* ---------- lifecycle ---------- */

  function teardown() {
    observers.forEach(function (o) { o.disconnect(); });
    observers = [];
    document.querySelectorAll(".sk").forEach(function (n) { n.remove(); });
    document.querySelectorAll("[data-sk]").forEach(function (n) { n.removeAttribute("data-sk"); });
    document.querySelectorAll("[data-skfit]").forEach(function (n) { n.style.fontSize = ""; n.removeAttribute("data-skfit"); });
  }

  function render() {
    teardown();
    if (!html.classList.contains("sketch")) return;
    measureClean();
    document.querySelectorAll(TARGETS).forEach(sketchSvg);
    fitText();
  }

  function fontsReady() {
    var timeout = new Promise(function (res) { setTimeout(res, 1500); });
    if (!document.fonts || !document.fonts.load) return timeout;
    return Promise.race([
      Promise.all([document.fonts.load("400 16px \"Shantell Sans\""), document.fonts.load("700 16px \"Shantell Sans\"")]),
      timeout
    ]);
  }

  var ready = fontsReady().then(function () { return document.fonts ? document.fonts.ready : null; });
  function rerender() { ready.then(render); }

  document.addEventListener("nz:sketchchange", rerender);
  document.addEventListener("nz:themechange", rerender);
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", rerender);
  else rerender();
})();
