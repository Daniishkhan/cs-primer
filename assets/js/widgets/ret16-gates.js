/* Citation gate checker (chapter 16).
   Runs the same three deterministic gates as the chapter's cite_check.py listing:
   1 pointer exists, 2 quote is verbatim (after normalisation), 3 the quote supports the claim.
   Gate 3 is a crude lexical stand-in for an entailment model: numbers must match, negation must
   agree, and at least 75% of the claim's content words must appear in the quote. */
(function () {
  "use strict";
  var root = document.getElementById("ret16-gates");
  if (!root) return;

  var DOCS = {
    returns: "Items may be returned within 30 days of delivery for a full refund. Items must be unused and in original packaging. Refunds are issued to the original payment method within 5 business days of receipt.",
    clearance: "Items bought in the clearance sale are final sale and cannot be returned, except where faulty.",
    shipping: "Standard delivery takes 3 to 5 business days. Express delivery takes 1 to 2 business days and costs 9.50.",
    warranty: "Tents carry a 2 year warranty against manufacturing defects. The warranty does not cover damage caused by misuse."
  };
  var PRESETS = [
    { name: "Faithful copy", doc: "returns", claim: "Refunds reach the original payment method within 5 business days of receipt.", quote: "Refunds are issued to the original payment method within 5 business days of receipt." },
    { name: "Altered number in the quote", doc: "warranty", claim: "Tents have a 3 year warranty.", quote: "Tents carry a 3 year warranty" },
    { name: "Real quote, claim goes beyond it", doc: "shipping", claim: "Express delivery is free.", quote: "Express delivery takes 1 to 2 business days" },
    { name: "Pointer to a missing document", doc: "giftcards", claim: "Gift cards never expire.", quote: "Gift cards do not expire" },
    { name: "Negation flipped", doc: "clearance", claim: "Clearance items can be returned.", quote: "Items bought in the clearance sale are final sale and cannot be returned, except where faulty." },
    { name: "One-word slip the check misses", doc: "returns", claim: "Items may be returned within 30 days of purchase.", quote: "Items may be returned within 30 days of delivery for a full refund." }
  ];
  var STOP = "a an the is are of to in on and or by for with be can may at as it its their".split(" ");
  var NEG = ["not", "no", "never", "cannot", "without"];

  function q(n) { return root.querySelector("[data-act=" + n + "]"); }
  var preset = q("preset"), doc = q("doc"), claim = q("claim"), quote = q("quote"), docText = q("doctext"), out = q("out");
  var i;
  for (i = 0; i < PRESETS.length; i++) {
    var o = document.createElement("option"); o.value = i; o.textContent = PRESETS[i].name; preset.appendChild(o);
  }
  var names = Object.keys(DOCS).concat(["giftcards"]);
  for (i = 0; i < names.length; i++) {
    var d = document.createElement("option"); d.value = names[i]; d.textContent = names[i] + (DOCS[names[i]] ? "" : " (not in the index)"); doc.appendChild(d);
  }

  function norm(s) {
    var t = s.normalize ? s.normalize("NFKC") : s;
    return t.toLowerCase().replace(/\s+/g, " ").replace(/^ | $/g, "");
  }
  function words(s) { return norm(s).match(/[a-z0-9.]+/g) || []; }
  function content(s) {
    var seen = {}, r = [];
    words(s).forEach(function (w) {
      w = w.replace(/\.+$/, "");
      if (!w || STOP.indexOf(w) >= 0) return;
      w = w.replace(/s$/, "");
      if (!seen[w]) { seen[w] = 1; r.push(w); }
    });
    return r;
  }
  function hasNeg(s) { return norm(s).split(" ").some(function (w) { return NEG.indexOf(w) >= 0; }); }
  function esc(s) { return s.replace(/&/g, "&amp;").replace(/</g, "&lt;"); }

  function gate(n, title, ok, why, skipped) {
    var cls = skipped ? "r16-skip" : (ok ? "r16-pass" : "r16-fail");
    var mark = skipped ? "-" : (ok ? "OK" : "X");
    return '<li class="' + cls + '"><span class="r16-mark">' + mark + '</span><div><b>Gate ' + n + ": " + title + '</b><span class="r16-why">' + why + "</span></div></li>";
  }

  function run() {
    var id = doc.value, text = DOCS[id];
    docText.textContent = text ? text : "(no document with this id exists in the index)";
    var html = "", verdict, good = false;
    var g1 = !!text;
    html += gate(1, "the pointer resolves", g1, g1 ? "Document &quot;" + esc(id) + "&quot; exists." : "No document &quot;" + esc(id) + "&quot; was retrieved or exists.", false);
    var g2 = g1 && norm(text).indexOf(norm(quote.value)) >= 0 && norm(quote.value).length > 0;
    html += gate(2, "the quote is verbatim", g2, !g1 ? "Skipped." : (g2 ? "The quote occurs in the document after whitespace and case normalisation." : "The quote does not occur in the document."), !g1);
    var g3 = false, why3 = "Skipped.";
    if (g2) {
      var cw = content(claim.value), qw = content(quote.value);
      var nums = cw.filter(function (w) { return /^[0-9]/.test(w); });
      var numsOk = nums.every(function (w) { return qw.indexOf(w) >= 0; });
      var negOk = hasNeg(claim.value) === hasNeg(quote.value);
      var hit = cw.filter(function (w) { return qw.indexOf(w) >= 0; }).length;
      var cover = cw.length ? hit / cw.length : 0;
      if (!numsOk) why3 = "A number in the claim is not in the quote.";
      else if (!negOk) why3 = "The claim and the quote disagree about negation.";
      else why3 = Math.round(cover * 100) + "% of the claim's content words appear in the quote (needs 75%).";
      g3 = numsOk && negOk && cover >= 0.75;
    }
    html += gate(3, "the quote supports the claim (stand-in)", g3, why3, !g2);
    if (!g1) verdict = "BAD_POINTER";
    else if (!g2) verdict = "FABRICATED_QUOTE";
    else if (!g3) verdict = "UNSUPPORTED";
    else { verdict = "SUPPORTED"; good = true; }
    out.innerHTML = '<ol class="r16-gates">' + html + '</ol><p class="r16-verdict ' + (good ? "ok" : "bad") + '">Verdict: ' + verdict + "</p>";
  }

  function load(n) {
    var p = PRESETS[n];
    doc.value = p.doc; claim.value = p.claim; quote.value = p.quote; run();
  }
  preset.addEventListener("change", function () { load(parseInt(preset.value, 10)); });
  [doc, claim, quote].forEach(function (el) { el.addEventListener("input", run); el.addEventListener("change", run); });
  load(0);
})();
