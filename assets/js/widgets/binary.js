/* Chapter 1: interactive byte (8 toggles -> decimal, hex, ASCII) and text -> binary viewer. */
(function () {
  "use strict";
  var root = document.getElementById("binary-widget");
  if (!root) return;

  var WEIGHTS = [128, 64, 32, 16, 8, 4, 2, 1];
  var bits = [0, 1, 0, 0, 1, 0, 0, 0]; // 72 = "H"
  var CONTROL = { 0: "NUL (null)", 7: "BEL (bell)", 8: "BS (backspace)", 9: "TAB", 10: "LF (new line)", 13: "CR (carriage return)", 27: "ESC (escape)", 32: "space", 127: "DEL (delete)" };

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function pad(str, len, ch) { while (str.length < len) str = ch + str; return str; }

  // ---- build UI ----
  var head = el("div", "widget-head");
  head.appendChild(el("span", "widget-tag", "Interactive"));
  head.appendChild(el("h4", "widget-title", "Flip the bits of one byte"));
  root.appendChild(head);
  root.appendChild(el("p", "widget-help", "Click a bit (or Tab to it and press Space) to flip it between 0 and 1. The number under each bit is its place value."));

  var row = el("div", "bitrow");
  var buttons = [];
  WEIGHTS.forEach(function (w, i) {
    var cell = el("div", "bitcell");
    var b = el("button", "bitbtn", "0");
    b.type = "button";
    b.setAttribute("aria-label", "Bit worth " + w);
    b.setAttribute("aria-pressed", "false");
    b.addEventListener("click", function () { bits[i] = bits[i] ? 0 : 1; render(); });
    buttons.push(b);
    cell.appendChild(b);
    cell.appendChild(el("span", "bitweight", String(w)));
    row.appendChild(cell);
  });
  root.appendChild(row);

  var stats = el("div", "nc-stats");
  function stat(name) {
    var s = el("div", "nc-stat");
    s.appendChild(el("span", "k", name));
    var v = el("span", "v", "");
    s.appendChild(v);
    stats.appendChild(s);
    return v;
  }
  var vDec = stat("Decimal"), vHex = stat("Hex"), vBin = stat("Binary"), vChr = stat("As ASCII text");
  root.appendChild(stats);

  var explain = el("div", "widget-out");
  root.appendChild(explain);

  var ctl = el("div", "widget-row");
  var bReset = el("button", "btn small", "Reset to 0");
  bReset.type = "button";
  bReset.addEventListener("click", function () { bits = [0, 0, 0, 0, 0, 0, 0, 0]; render(); });
  var bInc = el("button", "btn small", "+1");
  bInc.type = "button";
  bInc.addEventListener("click", function () { setValue((value() + 1) % 256); render(); });
  var bH = el("button", "btn small", "Set to \"H\"");
  bH.type = "button";
  bH.addEventListener("click", function () { setValue(72); render(); });
  ctl.appendChild(bReset); ctl.appendChild(bInc); ctl.appendChild(bH);
  root.appendChild(ctl);

  // ---- text section ----
  root.appendChild(el("h4", "widget-title", "Now type some text"));
  var trow = el("div", "widget-row");
  var lbl = el("label", null, "Text:");
  lbl.setAttribute("for", "binary-text");
  var inp = el("input", "mono");
  inp.type = "text"; inp.id = "binary-text"; inp.value = "Hi é€"; inp.maxLength = 12;
  inp.style.flex = "1"; inp.style.minWidth = "160px";
  trow.appendChild(lbl); trow.appendChild(inp);
  root.appendChild(trow);
  var cells = el("div", "charcells");
  cells.setAttribute("aria-live", "polite");
  root.appendChild(cells);
  var tsum = el("p", "widget-help");
  root.appendChild(tsum);

  function value() {
    var v = 0;
    for (var i = 0; i < 8; i++) v += bits[i] * WEIGHTS[i];
    return v;
  }
  function setValue(v) {
    for (var i = 0; i < 8; i++) { bits[i] = v >= WEIGHTS[i] ? 1 : 0; if (bits[i]) v -= WEIGHTS[i]; }
  }

  function render() {
    var v = value();
    buttons.forEach(function (b, i) {
      b.textContent = String(bits[i]);
      b.setAttribute("aria-pressed", bits[i] ? "true" : "false");
    });
    vDec.textContent = String(v);
    vHex.textContent = "0x" + pad(v.toString(16).toUpperCase(), 2, "0");
    vBin.textContent = bits.join("");
    var chr, note;
    if (v >= 33 && v <= 126) { chr = "“" + String.fromCharCode(v) + "”"; note = ""; }
    else if (CONTROL[v]) { chr = CONTROL[v]; note = ""; }
    else if (v < 128) { chr = "(control code)"; note = ""; }
    else { chr = "(not ASCII)"; note = " Values 128–255 are not ASCII; in UTF-8 they only appear as parts of multi-byte characters."; }
    vChr.textContent = chr;

    var terms = [];
    for (var i = 0; i < 8; i++) if (bits[i]) terms.push(String(WEIGHTS[i]));
    explain.textContent = (terms.length ? terms.join(" + ") : "0") + " = " + v + "." + note;
  }

  function utf8(cp) {
    var s = String.fromCodePoint(cp);
    return Array.prototype.slice.call(new TextEncoder().encode(s));
  }

  function renderText() {
    cells.textContent = "";
    var chars = Array.from(inp.value).slice(0, 12);
    var total = 0;
    chars.forEach(function (c) {
      var cp = c.codePointAt(0);
      var bytes = utf8(cp);
      total += bytes.length;
      var cell = el("div", "charcell");
      cell.appendChild(el("span", "ch", cp === 32 ? "␣" : c));
      cell.appendChild(el("span", "cp", "U+" + pad(cp.toString(16).toUpperCase(), 4, "0")));
      bytes.forEach(function (b) {
        cell.appendChild(el("span", "by", pad(b.toString(2), 8, "0") + "  " + pad(b.toString(16).toUpperCase(), 2, "0")));
      });
      cells.appendChild(cell);
    });
    tsum.textContent = chars.length
      ? chars.length + (chars.length === 1 ? " character" : " characters") + " → " + total + (total === 1 ? " byte" : " bytes") + " in UTF-8. Left: the byte in binary. Right: the same byte in hex."
      : "Type something above.";
  }

  inp.addEventListener("input", renderText);
  render();
  if (typeof TextEncoder === "undefined" || !String.fromCodePoint) {
    cells.textContent = "Your browser is too old to show this part.";
  } else renderText();
})();
