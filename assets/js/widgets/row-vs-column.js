/* Row layout vs column layout: bytes read for  SELECT avg(price) FROM sales
   Mount point: <div class="widget" id="row-vs-column"></div>
   Pure DOM, no libraries. The grid shows eight sample rows; the numbers use the chosen table size. */
(function () {
  "use strict";
  var root = document.getElementById("row-vs-column");
  if (!root) return;

  root.textContent = "";          // drop the no-JavaScript fallback text

  var NAMED = ["id", "date", "country", "qty", "price"];
  var PRICE = 4;
  var SAMPLE_ROWS = 8;
  var VALUE_BYTES = 8;            // simplification: every value takes 8 bytes
  var layout = "row";

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  function fmt(bytes) {
    var units = ["B", "KiB", "MiB", "GiB", "TiB"];
    var i = 0;
    while (bytes >= 1024 && i < units.length - 1) { bytes /= 1024; i++; }
    return (bytes >= 100 || i === 0 ? bytes.toFixed(0) : bytes.toFixed(1)) + " " + units[i];
  }

  // header
  var head = el("div", "widget-head");
  head.appendChild(el("span", "widget-tag", "Try it"));
  head.appendChild(el("h4", "widget-title", "What does SELECT avg(price) read?"));
  root.appendChild(head);
  root.appendChild(el("p", "widget-help", "Pick a layout and a table size. Highlighted cells are the bytes the query must read from storage."));

  // controls
  var row = el("div", "widget-row rvc-controls");
  var bRow = el("button", "btn small", "Row layout");
  var bCol = el("button", "btn small", "Column layout");
  bRow.type = bCol.type = "button";
  var lc = el("label", "rvc-label", "Columns in table ");
  var selC = document.createElement("select");
  [5, 20, 100].forEach(function (n) { var o = el("option", null, String(n)); o.value = n; selC.appendChild(o); });
  lc.appendChild(selC);
  var lr = el("label", "rvc-label", "Rows ");
  var selR = document.createElement("select");
  [["1 million", 1e6], ["100 million", 1e8]].forEach(function (p) { var o = el("option", null, p[0]); o.value = p[1]; selR.appendChild(o); });
  lr.appendChild(selR);
  [bRow, bCol, lc, lr].forEach(function (n) { row.appendChild(n); });
  root.appendChild(row);

  // grid
  var gridWrap = el("div", "rvc-grid-wrap");
  var grid = el("div", "rvc-grid");
  grid.setAttribute("role", "img");
  gridWrap.appendChild(grid);
  root.appendChild(gridWrap);
  var note = el("p", "rvc-note");
  root.appendChild(note);

  // results
  var out = el("div", "widget-out rvc-out");
  out.setAttribute("aria-live", "polite");
  root.appendChild(out);

  function render() {
    var cols = parseInt(selC.value, 10);
    var rows = parseFloat(selR.value);
    bRow.setAttribute("aria-pressed", layout === "row" ? "true" : "false");
    bCol.setAttribute("aria-pressed", layout === "column" ? "true" : "false");

    var shown = NAMED.length + (cols > NAMED.length ? 1 : 0);
    grid.style.gridTemplateColumns = "repeat(" + shown + ", minmax(0, 1fr))";
    grid.textContent = "";
    var i, r;
    for (i = 0; i < shown; i++) {
      var h = el("div", "rvc-cell rvc-h" + (i === PRICE ? " rvc-price" : ""),
        i < NAMED.length ? NAMED[i] : "+" + (cols - NAMED.length) + " more");
      grid.appendChild(h);
    }
    for (r = 0; r < SAMPLE_ROWS; r++) {
      for (i = 0; i < shown; i++) {
        var read = layout === "row" ? true : i === PRICE;
        var c = el("div", "rvc-cell" + (read ? " rvc-read" : " rvc-skip") + (i === PRICE ? " rvc-price" : ""),
          i < NAMED.length ? "·" : "…");
        grid.appendChild(c);
      }
    }
    grid.setAttribute("aria-label", layout === "row"
      ? "Row layout: every column of every row is read"
      : "Column layout: only the price column is read");

    var rowBytes = rows * cols * VALUE_BYTES;
    var colBytes = rows * VALUE_BYTES;
    note.textContent = layout === "row"
      ? "Row layout: each row is stored together, so to reach price the disk reads the whole row, all " + cols + " values."
      : "Column layout: each column is stored together, so the query reads only the price column and never touches the other " + (cols - 1) + ".";

    out.textContent = "";
    function bar(label, bytes, active, maxBytes) {
      var line = el("div", "rvc-line" + (active ? " active" : ""));
      line.appendChild(el("span", "rvc-lab", label));
      var track = el("span", "rvc-track");
      var fill = el("span", "rvc-fill");
      fill.style.width = Math.max(1.5, 100 * bytes / maxBytes) + "%";
      track.appendChild(fill);
      line.appendChild(track);
      line.appendChild(el("span", "rvc-val", fmt(bytes)));
      return line;
    }
    out.appendChild(bar("Row layout", rowBytes, layout === "row", rowBytes));
    out.appendChild(bar("Column layout", colBytes, layout === "column", rowBytes));
    out.appendChild(el("p", "rvc-ratio", "The column layout reads " + cols + "× fewer bytes here (" + cols + " columns, one needed). " +
      "Compression would shrink the column side further. Simplified: every value is taken as 8 bytes, and real row stores read whole pages, not exact bytes."));
  }

  bRow.addEventListener("click", function () { layout = "row"; render(); });
  bCol.addEventListener("click", function () { layout = "column"; render(); });
  selC.addEventListener("change", render);
  selR.addEventListener("change", render);
  render();
})();
