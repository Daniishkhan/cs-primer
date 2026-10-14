/* Broadcasting explorer (A0 chapter 02).
   Type two array shapes; the widget aligns them from the right, applies the
   broadcasting rule axis by axis and reports the result shape or the first
   axis that does not fit. No data is allocated: the rule only needs shapes. */
(function () {
  "use strict";
  var root = document.getElementById("mlf02-broadcast");
  if (!root) return;

  var inA = root.querySelector("[data-act=a]");
  var inB = root.querySelector("[data-act=b]");
  var preset = root.querySelector("[data-act=preset]");
  var grid = root.querySelector(".bc-wrap");
  var verdict = root.querySelector(".bc-verdict");
  var notes = root.querySelector(".bc-notes");

  var PRESETS = [
    ["(4, 1) and (1, 3): an outer sum", "4,1", "1,3"],
    ["(3, 4) and (4,): add a row to each row", "3,4", "4"],
    ["(3, 4) and (3,): the classic mistake", "3,4", "3"],
    ["(3, 4) and (3, 1): add a column", "3,4", "3,1"],
    ["(8, 5, 16) and (16,): bias over a batch", "8,5,16", "16"],
    ["(8, 5, 16) and (8, 5, 1): per-token mean", "8,5,16", "8,5,1"],
    ["(5, 1, 4) and (3, 1): two stretches", "5,1,4", "3,1"],
    ["(4,) and (): a scalar", "4", ""],
    ["(2, 3) and (3, 2): no way to match", "2,3", "3,2"],
    ["(4, 1) and (4,): silent (4, 4)", "4,1", "4"]
  ];

  function parse(text) {
    var t = text.replace(/[()\s\[\]]/g, "");
    if (t === "") return [];
    var parts = t.split(",").filter(function (p) { return p !== ""; });
    var out = [];
    for (var i = 0; i < parts.length; i++) {
      if (!/^\d+$/.test(parts[i])) return null;
      var v = parseInt(parts[i], 10);
      if (v < 1 || v > 999) return null;
      out.push(v);
    }
    return out.length <= 6 ? out : null;
  }

  function fmt(shape) {
    if (shape.length === 0) return "()";
    if (shape.length === 1) return "(" + shape[0] + ",)";
    return "(" + shape.join(", ") + ")";
  }

  function cell(text, cls) {
    var td = document.createElement("td");
    td.textContent = text;
    if (cls) td.className = cls;
    return td;
  }

  function head(text) {
    var th = document.createElement("th");
    th.className = "bc-lab";
    th.scope = "row";
    th.textContent = text;
    return th;
  }

  function run() {
    var a = parse(inA.value), b = parse(inB.value);
    grid.textContent = "";
    notes.textContent = "";
    if (a === null || b === null) {
      verdict.textContent = "Enter shapes as comma-separated positive integers, for example 4,1 or 8,5,16. Leave empty for a scalar.";
      return;
    }
    var n = Math.max(a.length, b.length);
    var pa = [], pb = [], res = [], status = [], bad = -1, k, i;
    for (i = 0; i < n; i++) {
      var ai = i - (n - a.length), bi = i - (n - b.length);
      var da = ai >= 0 ? a[ai] : null, db = bi >= 0 ? b[bi] : null;
      pa.push(da); pb.push(db);
      var x = da === null ? 1 : da, y = db === null ? 1 : db;
      if (x === y) { res.push(x); status.push("ok"); }
      else if (x === 1) { res.push(y); status.push("stretch-a"); }
      else if (y === 1) { res.push(x); status.push("stretch-b"); }
      else { res.push("?"); status.push("bad"); if (bad < 0) bad = i; }
    }

    var table = document.createElement("table");
    table.className = "bc-grid";
    var thead = document.createElement("thead");
    var hr = document.createElement("tr");
    var corner = document.createElement("th"); corner.textContent = "axis"; corner.className = "bc-lab"; hr.appendChild(corner);
    for (i = 0; i < n; i++) { var th = document.createElement("th"); th.textContent = String(i - n); th.className = "bc-lab"; th.style.textAlign = "center"; hr.appendChild(th); }
    thead.appendChild(hr); table.appendChild(thead);
    var tb = document.createElement("tbody");
    var rowA = document.createElement("tr"), rowB = document.createElement("tr"), rowR = document.createElement("tr");
    rowA.appendChild(head("A " + fmt(a)));
    rowB.appendChild(head("B " + fmt(b)));
    rowR.appendChild(head("result"));
    for (i = 0; i < n; i++) {
      rowA.appendChild(pa[i] === null ? cell("1 (added)", "bc-pad") : cell(String(pa[i]), status[i] === "stretch-a" ? "bc-stretch" : status[i] === "bad" ? "bc-bad" : ""));
      rowB.appendChild(pb[i] === null ? cell("1 (added)", "bc-pad") : cell(String(pb[i]), status[i] === "stretch-b" ? "bc-stretch" : status[i] === "bad" ? "bc-bad" : ""));
      rowR.appendChild(cell(String(res[i]), status[i] === "bad" ? "bc-bad" : "bc-ok"));
    }
    tb.appendChild(rowA); tb.appendChild(rowB); tb.appendChild(rowR);
    table.appendChild(tb); grid.appendChild(table);

    var li;
    if (bad >= 0) {
      verdict.innerHTML = "";
      var f = document.createElement("span"); f.className = "bc-fail"; f.textContent = "Error: ";
      verdict.appendChild(f);
      verdict.appendChild(document.createTextNode("axis " + (bad - n) + " has sizes " + (pa[bad] === null ? 1 : pa[bad]) + " and " + (pb[bad] === null ? 1 : pb[bad]) + ". They differ and neither is 1, so NumPy raises a ValueError."));
    } else {
      var size = 1; for (i = 0; i < res.length; i++) size *= res[i];
      verdict.innerHTML = "";
      var g = document.createElement("span"); g.className = "bc-good"; g.textContent = "Works: ";
      verdict.appendChild(g);
      verdict.appendChild(document.createTextNode("the result has shape " + fmt(res) + " and " + size + " element" + (size === 1 ? "" : "s") + "."));
      var alen = a.length, blen = b.length;
      if (alen !== blen && alen > 0 && blen > 0) {
        li = document.createElement("li");
        li.textContent = "The shorter shape gets size-1 axes added on the left: " + (alen < blen ? "A" : "B") + " is treated as " + fmt(alen < blen ? pa.map(function (v) { return v === null ? 1 : v; }) : pb.map(function (v) { return v === null ? 1 : v; })) + ".";
        notes.appendChild(li);
      }
      var stretched = 0;
      for (k = 0; k < n; k++) if (status[k] === "stretch-a" || status[k] === "stretch-b") stretched++;
      if (stretched) {
        li = document.createElement("li");
        li.textContent = stretched + (stretched === 1 ? " axis is" : " axes are") + " stretched (shaded): the size-1 side is repeated along that axis without copying (its stride becomes 0).";
        notes.appendChild(li);
      }
      if (a.length === 2 && b.length === 1 && a[1] === 1 && a[0] === b[0] && a[0] > 1) {
        li = document.createElement("li");
        li.textContent = "Warning: a column (n, 1) combined with a flat (n,) array broadcasts to (n, n). This is the silent bug from the chapter.";
        notes.appendChild(li);
      }
    }
  }

  PRESETS.forEach(function (p, idx) {
    var o = document.createElement("option");
    o.value = String(idx); o.textContent = p[0];
    preset.appendChild(o);
  });
  preset.addEventListener("change", function () {
    var p = PRESETS[parseInt(preset.value, 10)];
    inA.value = p[1]; inB.value = p[2]; run();
  });
  inA.addEventListener("input", run);
  inB.addEventListener("input", run);
  inA.value = PRESETS[0][1]; inB.value = PRESETS[0][2];
  run();
})();
