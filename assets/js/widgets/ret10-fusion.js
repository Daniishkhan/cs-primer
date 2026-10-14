/* Fusion explorer (retrieval chapter 10).
   Two ranked lists (BM25 and a stand-in dense retriever) for one of 12 constructed queries.
   Fuse them with reciprocal rank fusion or a normalised weighted sum and see where the
   judged-relevant documents land. Data were produced by the chapter's own listings. */
(function () {
  "use strict";
  var root = document.getElementById("ret10-fusion");
  if (!root) return;
  var DATA = {"docs":{"r2":"To get your money back for a faulty item, open an order and choose Return. Refunds take 5 to 10 working days.","r1":"Refund policy: we reimburse the full purchase price within 30 days. Reimbursement goes back to the original card.","t1":"To move money from savings to checking, open Transfers, choose Savings as the source and Checking as the destination.","t2":"To move money from checking to savings, open Transfers, choose Checking as the source and Savings as the destination.","d5":"Order cancellations: an order can be cancelled free of charge until it has been dispatched.","d3":"International orders may be charged import duty and taxes by the carrier on delivery.","r3":"Subscription refunds: cancel within 14 days of renewal and the charge is refunded in full.","d1":"Delivery takes 3 to 5 working days. Tracking information is emailed once the parcel has been dispatched.","r5":"If a refund has not arrived after 10 working days, contact your bank first, then our billing team.","d2":"If a parcel arrives damaged, photograph the packaging and the item and report it within 7 days.","e4":"Error E4021-B appears only in the legacy checkout, and means the same as E4021 in the new checkout.","e1":"Error E4021: the payment gateway rejected the card because the billing address did not match. Re-enter the address exactly as your bank holds it.","d4":"We cannot deliver to PO boxes. Please give a street address with a postcode.","e2":"Error E4107: the request timed out while contacting the payment gateway. Retry after a minute; no charge was made.","r4":"Gift cards are not refundable and cannot be exchanged for cash.","b3":"Payment methods accepted: credit card, bank transfer and direct debit.","c4":"New patients must bring photo identification and their insurance card to the first appointment.","e3":"Error E5002: your session expired. Sign in again and repeat the action.","b2":"To dispute an invoice, contact billing within 30 days and include the invoice number.","s1":"Forgot your password? Choose Reset password on the sign-in page and we will email a reset link that expires in one hour.","p2":"Standard plan: email support with a one business day response target; no phone support.","p1":"Premium plan: phone and chat support, a named account manager and a 99.9 percent uptime commitment.","s3":"If you lose your authenticator device, use one of your recovery codes to sign in and register a new device.","t4":"Daily transfer limits: 5,000 for standard accounts and 25,000 for premium accounts.","t3":"Transfers between your own accounts are instant. Transfers to other banks take one business day.","s6":"Security incident reports: email the security team and include the time, your account and what you observed.","s5":"Locked out after five failed sign-in attempts? The account unlocks automatically after 15 minutes.","c1":"Clinic appointments can be booked online or by phone. Cancel at least 24 hours ahead to avoid a missed-appointment fee.","s2":"Enable two-factor authentication in Settings, Security. You can use an authenticator app or a hardware key.","b1":"Late payment fees apply when an invoice is paid after the due date. The late fee is 2 percent per month.","b4":"Overdue accounts are reviewed weekly. After 60 days an overdue invoice is passed to collections.","b5":"Annual report. The company reported growth, new products, hiring, office moves and partnerships. Late in the year a payment platform was launched. Further detail on payment, tax and risk follows in the notes to this summary section.","b6":"Tax invoices must show the supplier tax number, the date and the total tax charged.","p3":"Plans can be changed at any time; the new price applies from the next billing date.","g2":"The supplier shall not be liable for indirect loss. Total liability is capped at the fees paid in the previous 12 months.","g1":"Either party may terminate this agreement with 30 days' written notice. Fees already paid are not returned.","g4":"Disputes under this agreement are settled by arbitration in the supplier's home jurisdiction.","h3":"Parental leave: eligible employees may take up to 26 weeks of paid time off after the birth or adoption of a child.","h2":"Sick leave: tell your manager before your shift starts. A doctor's note is needed after three days off.","h5":"Holiday calendar: offices are closed on public holidays. Staff on call are paid at double rate.","h1":"Annual leave: full-time staff receive 25 days a year. Request leave through the HR portal at least two weeks ahead.","c2":"Prescription renewals take two working days. Request them through the patient portal.","g3":"Personal data is processed only to provide the service and is deleted within 90 days of termination.","s4":"API keys are shown once at creation. Rotate a key every 90 days; revoked keys stop working immediately.","c3":"Test results are posted to the patient portal within five working days; urgent results are phoned to you.","h4":"Expense claims must be submitted within 30 days with receipts attached."},"queries":[{"id":"q1","text":"how do I get my money back","qrels":{"r1":2,"r2":2,"r3":1,"r5":1},"bm25":[["r2",8.2443],["r1",2.7794],["t1",2.717],["t2",2.717]],"dense":[["r2",0.9512],["t1",0.8458],["t2",0.8458],["d5",0.6004],["r1",0.5997],["d3",0.565],["r3",0.5585],["d1",0.5155],["r5",0.486],["d2",0.4852]]},{"id":"q2","text":"E4021","qrels":{"e1":2,"e4":1},"bm25":[["e4",3.0689],["e1",2.5399]],"dense":[["d4",0.9958],["e1",0.9928],["e4",0.9791],["e2",0.8734],["r4",0.8716],["b3",0.8532],["c4",0.7073],["e3",0.664],["r5",0.5625],["b2",0.4286]]},{"id":"q3","text":"forgot my password","qrels":{"s1":2,"s5":1},"bm25":[["s1",7.8256]],"dense":[["s1",0.9972],["p2",0.9639],["p1",0.8817],["s3",0.834],["t4",0.8335],["t3",0.8243],["s6",0.7536],["s5",0.6922],["c1",0.6647],["e3",0.6321]]},{"id":"q4","text":"lost my phone with the authenticator","qrels":{"s3":2,"s2":1},"bm25":[["s2",3.1793],["s3",2.966],["p2",2.6258],["c1",2.5406],["p1",2.5406]],"dense":[["p2",0.9809],["s1",0.9483],["p1",0.9389],["s3",0.8528],["s6",0.8441],["t4",0.8326],["s5",0.8187],["t3",0.7809],["c1",0.7799],["e3",0.6409]]},{"id":"q5","text":"charge for paying an invoice late","qrels":{"b1":2,"b4":1},"bm25":[["b1",6.0371],["b2",3.7716],["d5",2.8147],["r3",2.8147],["b4",2.717],["e2",2.3151],["b5",2.018]],"dense":[["b1",0.9269],["b6",0.9072],["p3",0.8332],["g2",0.7741],["b2",0.736],["g1",0.727],["b4",0.7176],["g4",0.7111],["b5",0.5055],["s6",0.4921]]},{"id":"q6","text":"move money from savings to checking","qrels":{"t1":2,"t3":1},"bm25":[["t1",13.7538],["t2",13.7538],["r2",2.3857],["b5",1.7866]],"dense":[["t1",0.997],["t2",0.997],["r2",0.6436],["t3",0.3513],["b3",0.3487],["t4",0.2686],["d3",0.1476],["b5",0.1192],["r1",0.1118],["d5",0.0918]]},{"id":"q7","text":"time off after having a baby","qrels":{"h3":2},"bm25":[["h3",6.5659],["h2",4.3804],["p3",2.8147],["s6",2.717],["s5",2.4852],["b4",1.9197],["r5",1.6857],["b1",1.6358],["e2",1.6358]],"dense":[["h3",0.9613],["h2",0.9321],["h5",0.8627],["b4",0.7284],["h1",0.7276],["c1",0.6699],["c2",0.6101],["s5",0.6067],["g4",0.5912],["g1",0.5461]]},{"id":"q8","text":"cancel my appointment","qrels":{"c1":2},"bm25":[["c1",5.7393],["r3",3.1793],["c4",3.0689]],"dense":[["c1",0.9292],["s5",0.8873],["t4",0.8305],["p2",0.7372],["p1",0.7222],["s6",0.7023],["t3",0.6891],["b4",0.6439],["h2",0.6426],["s1",0.6259]]},{"id":"q9","text":"my parcel came broken","qrels":{"d2":2},"bm25":[["d2",3.0689],["d1",2.7794]],"dense":[["d1",0.9853],["d5",0.9538],["g3",0.9452],["s4",0.9409],["d2",0.9265],["s2",0.8645],["r3",0.823],["c3",0.7976],["h4",0.774],["r1",0.7589]]},{"id":"q10","text":"which plan has phone support","qrels":{"p1":2,"p2":1},"bm25":[["p2",9.3159],["p1",7.9508],["d5",2.8147],["p3",2.8147],["c1",2.5406],["d1",2.4607],["r5",2.3857]],"dense":[["p2",0.9815],["p1",0.9514],["s1",0.931],["s5",0.8837],["t4",0.8686],["s6",0.8456],["t3",0.8373],["s3",0.8339],["c1",0.7857],["e3",0.6724]]},{"id":"q11","text":"can the supplier end the contract","qrels":{"g1":2},"bm25":[["g4",2.9197],["b6",2.717],["g2",2.4607]],"dense":[["g2",0.991],["g4",0.9406],["b1",0.9234],["g1",0.8987],["b6",0.8734],["h5",0.5953],["b4",0.5877],["b2",0.5813],["d3",0.5666],["p3",0.4996]]},{"id":"q12","text":"payment gateway rejected my card","qrels":{"e1":2,"e2":1},"bm25":[["e1",9.2365],["b3",4.8232],["e2",4.5272],["r4",2.6061],["b5",2.2484],["c4",2.2442],["r1",2.0325],["b1",1.9122]],"dense":[["e1",0.9808],["e4",0.9659],["d4",0.9498],["e2",0.9242],["b3",0.9112],["r4",0.8784],["c4",0.7822],["e3",0.6527],["r5",0.6],["p3",0.5466]]}]};

  var qSel = root.querySelector("[data-act=query]");
  var mSel = root.querySelector("[data-act=method]");
  var kIn = root.querySelector("[data-act=k]");
  var kOut = root.querySelector("[data-act=k-out]");
  var aIn = root.querySelector("[data-act=alpha]");
  var aOut = root.querySelector("[data-act=alpha-out]");
  var oIn = root.querySelector("[data-act=outlier]");
  var kBox = root.querySelector("[data-box=k]");
  var aBox = root.querySelector("[data-box=alpha]");
  var cols = root.querySelector(".fu-cols");
  var sum = root.querySelector(".fu-summary");

  var i;
  for (i = 0; i < DATA.queries.length; i++) {
    var o = document.createElement("option");
    o.value = String(i);
    o.textContent = DATA.queries[i].id + ": " + DATA.queries[i].text;
    qSel.appendChild(o);
  }

  function byScore(map) {
    var ids = Object.keys(map);
    ids.sort(function (a, b) { return map[b] - map[a] || (a < b ? -1 : 1); });
    return ids;
  }
  function toMap(pairs, boost) {
    var m = {}, j;
    for (j = 0; j < pairs.length; j++) m[pairs[j][0]] = pairs[j][1] * (j === 0 && boost ? boost : 1);
    return m;
  }
  function minMax(m) {
    var v = Object.keys(m).map(function (d) { return m[d]; });
    var lo = Math.min.apply(null, v), hi = Math.max.apply(null, v), out = {};
    Object.keys(m).forEach(function (d) { out[d] = hi > lo ? (m[d] - lo) / (hi - lo) : 0; });
    return out;
  }
  function zScore(m) {
    var ks = Object.keys(m), n = ks.length, mean = 0, v = 0, out = {};
    ks.forEach(function (d) { mean += m[d] / n; });
    ks.forEach(function (d) { v += Math.pow(m[d] - mean, 2) / n; });
    var sd = Math.sqrt(v);
    ks.forEach(function (d) { out[d] = sd ? (m[d] - mean) / sd : 0; });
    return out;
  }
  function rrf(lists, k) {
    var out = {};
    lists.forEach(function (ids) {
      ids.forEach(function (d, r) { out[d] = (out[d] || 0) + 1 / (k + r + 1); });
    });
    return out;
  }
  function convex(a, b, alpha, norm) {
    var na = norm(a), nb = norm(b), out = {};
    Object.keys(a).concat(Object.keys(b)).forEach(function (d) {
      out[d] = alpha * (na[d] || 0) + (1 - alpha) * (nb[d] || 0);
    });
    return out;
  }
  function ndcg(ranking, qrels) {
    var dcg = 0, j, ideal = [];
    for (j = 0; j < Math.min(10, ranking.length); j++) {
      dcg += (Math.pow(2, qrels[ranking[j]] || 0) - 1) / (Math.log(j + 2) / Math.LN2);
    }
    Object.keys(qrels).forEach(function (d) { ideal.push(qrels[d]); });
    ideal.sort(function (x, y) { return y - x; });
    var idcg = 0;
    for (j = 0; j < Math.min(10, ideal.length); j++) idcg += (Math.pow(2, ideal[j]) - 1) / (Math.log(j + 2) / Math.LN2);
    return idcg ? dcg / idcg : 0;
  }

  function column(title, ids, scores, qrels, note) {
    var div = document.createElement("div");
    div.className = "fu-col";
    var h = document.createElement("h5");
    h.textContent = title;
    div.appendChild(h);
    var ol = document.createElement("ol");
    ids.slice(0, 8).forEach(function (d) {
      var li = document.createElement("li");
      li.className = "fu-g" + (qrels[d] || 0);
      var b = document.createElement("b"); b.textContent = d;
      var s = document.createElement("span"); s.className = "fu-score"; s.textContent = scores[d].toFixed(3);
      var t = document.createElement("span"); t.className = "fu-text"; t.textContent = DATA.docs[d].slice(0, 46) + (DATA.docs[d].length > 46 ? "..." : "");
      li.appendChild(b); li.appendChild(s); li.appendChild(t);
      ol.appendChild(li);
    });
    div.appendChild(ol);
    var p = document.createElement("p");
    p.className = "fu-note";
    p.textContent = note;
    div.appendChild(p);
    return div;
  }

  function run() {
    var q = DATA.queries[parseInt(qSel.value, 10)];
    var method = mSel.value;
    var k = parseInt(kIn.value, 10), alpha = parseInt(aIn.value, 10) / 10;
    kOut.textContent = String(k);
    aOut.textContent = alpha.toFixed(1);
    kBox.style.display = method === "rrf" ? "" : "none";
    aBox.style.display = method === "rrf" ? "none" : "";
    var lex = toMap(q.bm25, oIn.checked ? 3 : 0), den = toMap(q.dense, 0);
    var lexIds = byScore(lex), denIds = byScore(den);
    var fused;
    if (method === "rrf") fused = rrf([lexIds, denIds], k);
    else fused = convex(lex, den, alpha, method === "minmax" ? minMax : zScore);
    var fusedIds = byScore(fused);
    var nL = ndcg(lexIds, q.qrels), nD = ndcg(denIds, q.qrels), nF = ndcg(fusedIds, q.qrels);
    cols.textContent = "";
    cols.appendChild(column("BM25", lexIds, lex, q.qrels, "nDCG@10 " + nL.toFixed(2)));
    cols.appendChild(column("Dense (stand-in)", denIds, den, q.qrels, "nDCG@10 " + nD.toFixed(2)));
    cols.appendChild(column("Fused", fusedIds, fused, q.qrels, "nDCG@10 " + nF.toFixed(2)));
    var verdict = nF > Math.max(nL, nD) + 0.005 ? "better than either list alone." :
                  nF < Math.min(nL, nD) - 0.005 ? "worse than both lists." :
                  nF >= Math.max(nL, nD) - 0.005 ? "as good as the better list." : "between the two lists.";
    sum.textContent = "Fused nDCG@10 is " + nF.toFixed(2) + ", " + verdict +
      (oIn.checked ? " BM25's top score is multiplied by 3 (order unchanged), as if one exact match were far stronger than the rest." : "");
  }

  [qSel, mSel, kIn, aIn, oIn].forEach(function (el) {
    el.addEventListener(el === oIn ? "change" : "input", run);
  });
  qSel.addEventListener("change", run);
  mSel.addEventListener("change", run);
  qSel.value = "0";
  run();
})();
