/* Byte-pair encoding trainer (A2 chapter 13).
   Works on characters (the chapter's code works on bytes; the idea is identical). Words keep their leading
   space, so a merge never crosses a word boundary. Each merge joins the most frequent adjacent pair,
   ties broken by the pair seen first. Training is re-run from scratch whenever a control changes. */
(function () {
  "use strict";
  var root = document.getElementById("dl13-bpe");
  if (!root) return;
  var q = function (sel) { return root.querySelector(sel); };
  var textIn = q("[data-act=text]"), nIn = q("[data-act=n]"), nOut = q("[data-act=n-out]"),
      newIn = q("[data-act=new]"), prev = q(".dl13-merges"), corpusOut = q(".dl13-corpus"),
      newOut = q(".dl13-newout"), stats = q(".dl13-stats");

  function split(text) { return text.match(/ ?[^\s]+|\s+/g) || []; }

  function train(text, nMerges) {
    var words = split(text), counts = {}, order = [], i;
    for (i = 0; i < words.length; i++) {
      if (!(words[i] in counts)) { counts[words[i]] = 0; order.push(words[i]); }
      counts[words[i]]++;
    }
    var seqs = {};
    order.forEach(function (w) { seqs[w] = w.split(""); });
    var merges = [], k;
    for (k = 0; k < nMerges; k++) {
      var pc = {}, pairOrder = [];
      order.forEach(function (w) {
        var s = seqs[w], j;
        for (j = 0; j + 1 < s.length; j++) {
          var key = s[j] + "\u0001" + s[j + 1];
          if (!(key in pc)) { pc[key] = 0; pairOrder.push(key); }
          pc[key] += counts[w];
        }
      });
      var best = null;
      pairOrder.forEach(function (key) { if (best === null || pc[key] > pc[best]) best = key; });
      if (best === null || pc[best] < 2) break;
      var parts = best.split("\u0001");
      merges.push({ a: parts[0], b: parts[1], n: pc[best] });
      order.forEach(function (w) { seqs[w] = applyMerge(seqs[w], parts[0], parts[1]); });
    }
    return { merges: merges, words: words, seqs: seqs };
  }
  function applyMerge(s, a, b) {
    var out = [], j = 0;
    while (j < s.length) {
      if (j + 1 < s.length && s[j] === a && s[j + 1] === b) { out.push(a + b); j += 2; } else { out.push(s[j]); j++; }
    }
    return out;
  }
  function encodeWord(w, merges) {
    var s = w.split(""), k;
    for (k = 0; k < merges.length; k++) s = applyMerge(s, merges[k].a, merges[k].b);
    return s;
  }
  function vis(t) { return t.replace(/ /g, "␣").replace(/\n/g, "↵"); }
  function chips(tokens, target) {
    tokens.forEach(function (t, i) {
      var c = document.createElement("span");
      c.className = "dl13-tok dl13-tok" + (i % 2);
      c.textContent = vis(t);
      target.appendChild(c);
    });
  }

  function update() {
    var text = textIn.value, n = parseInt(nIn.value, 10);
    nOut.textContent = String(n);
    var m = train(text, n), all = [], uniq = {}, i;
    m.words.forEach(function (w) { all = all.concat(m.seqs[w]); });
    for (i = 0; i < text.length; i++) uniq[text.charAt(i)] = 1;
    var base = Object.keys(uniq).length;
    while (corpusOut.firstChild) corpusOut.removeChild(corpusOut.firstChild);
    chips(all, corpusOut);
    prev.textContent = m.merges.length ? m.merges.map(function (g, k) {
      return ("0" + (k + 1)).slice(-2) + "  " + vis(g.a) + " + " + vis(g.b) + " → " + vis(g.a + g.b) + "   (seen " + g.n + " times)";
    }).join("\n") : "No merges yet: every character is its own token.";
    stats.textContent = "Vocabulary: " + base + " characters + " + m.merges.length + " merges = " + (base + m.merges.length) +
      " tokens.  The text has " + text.length + " characters and is now " + all.length + " tokens (" + (text.length / Math.max(1, all.length)).toFixed(2) + " characters per token)." +
      (m.merges.length < n ? "  Stopped early: no pair occurs twice any more." : "");
    var s = newIn.value;
    while (newOut.firstChild) newOut.removeChild(newOut.firstChild);
    var toks = [];
    split(s).forEach(function (w) { toks = toks.concat(encodeWord(w, m.merges)); });
    chips(toks, newOut);
  }
  [textIn, newIn].forEach(function (c) { c.addEventListener("input", update); });
  nIn.addEventListener("input", update);
  q("[data-act=step]").addEventListener("click", function () {
    nIn.value = String(Math.min(parseInt(nIn.max, 10), parseInt(nIn.value, 10) + 1)); update();
  });
  q("[data-act=reset]").addEventListener("click", function () { nIn.value = "0"; update(); });
  update();
})();
