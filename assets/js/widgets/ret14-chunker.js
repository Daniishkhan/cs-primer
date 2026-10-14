/* Chunk boundary explorer (retrieval chapter 14).
   A short passage is split three ways: fixed windows of N words with overlap, sentence-aware packing
   up to N words, or one chunk per paragraph. Chunk boundaries are drawn on the text. The widget
   reports the number of chunks, the mean size, the storage cost of overlap, how many sentences are
   cut in two, and whether a chosen fact sentence survives whole inside one chunk. */
(function () {
  "use strict";
  var root = document.getElementById("ret14-chunker");
  if (!root) return;

  var PARAS = [
    ["Revenue grew 9.8% compared with the previous year.", "The operating margin was 29%.", "Hospital budgets were released earlier than expected."],
    ["Revenue grew 7.4% compared with the previous year.", "The operating margin was 31%.", "Service contracts made up 40% of sales in the period."],
    ["Revenue grew 6.1% compared with the previous year.", "The operating margin was 30%.", "Two systems were withdrawn for a software update and returned within three weeks."]
  ];
  var FACTS = [PARAS[1][0], PARAS[1][2], PARAS[2][2]];

  function q(n) { return root.querySelector("[data-act=" + n + "]"); }
  var selS = q("strategy"), inN = q("size"), inO = q("overlap"), selF = q("fact");
  var outN = q("size-out"), outO = q("overlap-out");
  var text = root.querySelector(".r14-text"), stats = root.querySelector(".r14-stats"), note = root.querySelector(".r14-note");

  // Words, with the sentence and paragraph each belongs to.
  var W = [], S = [], P = [], sid = 0, pi, si, k, ws;
  for (pi = 0; pi < PARAS.length; pi++) {
    for (si = 0; si < PARAS[pi].length; si++) {
      ws = PARAS[pi][si].split(" ");
      for (k = 0; k < ws.length; k++) { W.push(ws[k]); S.push(sid); P.push(pi); }
      sid++;
    }
  }
  var N = W.length;

  function factRange(f) {
    var fw = FACTS[f].split(" "), i, j;
    for (i = 0; i + fw.length <= N; i++) {
      for (j = 0; j < fw.length; j++) if (W[i + j] !== fw[j]) break;
      if (j === fw.length) return [i, i + fw.length];
    }
    return [0, 0];
  }

  function chunksFor(strategy, size, overlap) {
    var out = [], i, start, end;
    if (strategy === "fixed") {
      var step = Math.max(1, size - overlap);
      for (i = 0; i < N; i += step) { out.push([i, Math.min(N, i + size)]); if (i + size >= N) break; }
    } else if (strategy === "sentence") {
      start = 0;
      while (start < N) {
        end = start;
        while (end < N) {
          var e = end; while (e < N && S[e] === S[end]) e++;
          if (end > start && e - start > size) break;
          end = e;
        }
        out.push([start, end]); start = end;
      }
    } else {
      start = 0;
      for (i = 1; i <= N; i++) if (i === N || P[i] !== P[start]) { out.push([start, i]); start = i; }
    }
    return out;
  }

  function update() {
    var strategy = selS.value, size = parseInt(inN.value, 10), overlap = Math.min(parseInt(inO.value, 10), size - 1);
    outN.textContent = size + " words";
    outO.textContent = strategy === "fixed" ? overlap + " words" : "not used";
    inO.disabled = strategy !== "fixed";
    inN.disabled = strategy === "paragraph";
    var ch = chunksFor(strategy, size, overlap), i, j, covered = [], html = "", total = 0;
    for (i = 0; i < N; i++) covered.push(0);
    for (i = 0; i < ch.length; i++) { total += ch[i][1] - ch[i][0]; for (j = ch[i][0]; j < ch[i][1]; j++) covered[j]++; }
    var first = {}, owner = [];
    for (i = 0; i < N; i++) owner.push(0);
    for (i = ch.length - 1; i >= 0; i--) for (j = ch[i][0]; j < ch[i][1]; j++) owner[j] = i;
    for (i = 0; i < ch.length; i++) first[ch[i][0]] = i;
    for (i = 0; i < N; i++) {
      var cls = "r14-w r14-c" + (owner[i] % 4);
      if (covered[i] > 1) cls += " r14-ov";
      if (first.hasOwnProperty(i)) html += '<span class="r14-bound" title="chunk ' + (first[i] + 1) + ' starts">|' + (first[i] + 1) + '</span>';
      html += '<span class="' + cls + '">' + W[i] + '</span> ';
    }
    text.innerHTML = html;

    var cut = 0;
    for (i = 1; i < N; i++) if (S[i] === S[i - 1]) {
      var boundary = false;
      for (j = 0; j < ch.length; j++) if (ch[j][0] === i) boundary = true;
      if (boundary) cut++;
    }
    var f = factRange(parseInt(selF.value, 10)), whole = false;
    for (j = 0; j < ch.length; j++) if (ch[j][0] <= f[0] && ch[j][1] >= f[1]) whole = true;
    stats.innerHTML =
      row("Chunks", ch.length) +
      row("Mean words per chunk", (total / ch.length).toFixed(1)) +
      row("Stored words / document words", (total / N).toFixed(2) + "x") +
      row("Sentences cut in two", cut) +
      row("Chosen fact inside one chunk", whole ? "yes" : "NO: split across chunks");
    note.textContent = whole
      ? "Underlined words are stored in more than one chunk (overlap). Drag the size down until the fact breaks, then raise the overlap to see whether it is rescued."
      : "A retriever can only return a chunk that contains the whole fact. Here no chunk does, so the question is unanswerable from this index however good the embedder is.";
  }
  function row(a, b) { return '<div class="r14-row"><span>' + a + '</span><b>' + b + '</b></div>'; }
  [selS, inN, inO, selF].forEach(function (el) { el.addEventListener("input", update); el.addEventListener("change", update); });
  update();
})();
