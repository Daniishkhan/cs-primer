/* Raft commitment subtlety, Figure 8 of the Raft paper (distributed chapter 10).

   Five servers S1..S5. Each log entry is shown as the TERM in which it was created; the
   column is its index. The story is a fixed script of frames:
     common frames 0-3 (the same for both branches)
     then branch D ("S1 crashes now") or branch E ("S1 first replicates a term-4 entry").
   The reader picks which COMMIT RULE the leader uses:
     raft  - an entry may be counted as committed by replica-counting only if it belongs to the
             leader's current term (older entries are committed indirectly, as a prefix);
     naive - any entry stored on a majority counts as committed.
   Each frame stores, for each rule, the list of entry terms the leader has declared committed
   (index 1 first); a cell is outlined when it matches that claim. Each frame also has a verdict sentence for each rule.
   The data below is hand-written from the paper's scenario, not computed by a Raft engine. */
(function () {
  "use strict";
  var root = document.getElementById("raft-commit");
  if (!root) return;

  var rule = "raft", branch = "D", idx = 0;

  var COMMON = [
    {
      cap: "Start. S1 is leader of term 2 and every server holds index 1 (term 1), which is committed.",
      logs: [[1], [1], [1], [1], [1]], leader: 1, term: 2, down: [], c: { raft: [1], naive: [1] },
      v: { raft: ["Nothing unusual yet.", ""], naive: ["Nothing unusual yet.", ""] }
    },
    {
      cap: "A client sends S1 a command. S1 appends it at index 2 (term 2) and replicates it to S2 only. Then S1 crashes.",
      logs: [[1, 2], [1, 2], [1], [1], [1]], leader: 0, term: 2, down: [1], c: { raft: [1], naive: [1] },
      v: { raft: ["Index 2 is on two of five servers: not a majority, not committed.", ""], naive: ["Index 2 is on two of five servers: not a majority, not committed.", ""] }
    },
    {
      cap: "S5 wins term 3 with votes from S3, S4 and itself (all of their logs end at term 1, so S5 is up to date enough). It appends its own entry at index 2 (term 3), then crashes before replicating it.",
      logs: [[1, 2], [1, 2], [1], [1], [1, 3]], leader: 0, term: 3, down: [1, 5], c: { raft: [1], naive: [1] },
      v: { raft: ["Two different entries now exist for index 2: (term 2) on S1, S2 and (term 3) on S5.", ""], naive: ["Two different entries now exist for index 2: (term 2) on S1, S2 and (term 3) on S5.", ""] }
    },
    {
      cap: "S1 restarts and wins term 4 (its log [1,2] is at least as up to date as the votes it needs from S2 and S3). It carries on replicating its old term-2 entry, and S3 now stores it. Index 2 is on S1, S2 and S3: a majority.",
      logs: [[1, 2], [1, 2], [1, 2], [1], [1, 3]], leader: 1, term: 4, down: [5], c: { raft: [1], naive: [1, 2] },
      v: {
        raft: ["Raft's rule: this entry is from term 2 but the leader's term is 4, so S1 does NOT count replicas for it. Not committed yet.", "ok"],
        naive: ["Naive rule: a majority stores index 2, so S1 calls it committed and may tell the client 'done'.", "warn"]
      }
    }
  ];

  var BRANCH = {
    D: [
      {
        cap: "Branch D. S1 crashes again before replicating anything new.",
        logs: [[1, 2], [1, 2], [1, 2], [1], [1, 3]], leader: 0, term: 4, down: [1], c: { raft: [1], naive: [1, 2] },
        v: {
          raft: ["Under Raft's rule index 2 is not committed, and the client has not been told anything.", "ok"],
          naive: ["Naive rule: the client was told index 2 is committed. Everything now depends on that being true.", "warn"]
        }
      },
      {
        cap: "S5 restarts and wins term 5. Its last entry has term 3, newer than the term-2 entries on S2 and S3, so S2, S3 and S4 all vote for it. S5 now overwrites index 2 on S2, S3 and S4 with its term-3 entry.",
        logs: [[1, 2], [1, 3], [1, 3], [1, 3], [1, 3]], leader: 5, term: 5, down: [1], c: { raft: [1], naive: [1, 2] },
        v: {
          raft: ["Safe. The term-2 entry was never committed and no client was told it succeeded, so replacing it is allowed.", "ok"],
          naive: ["VIOLATION. An entry that the leader called committed, and a client was told about, has been overwritten on a majority. Committed entries must never be lost.", "bad"]
        }
      }
    ],
    E: [
      {
        cap: "Branch E. Before crashing, S1 appends a new entry of its own term (a no-op, or any client command) at index 3 and replicates it to S2 and S3.",
        logs: [[1, 2, 4], [1, 2, 4], [1, 2, 4], [1], [1, 3]], leader: 1, term: 4, down: [5], c: { raft: [1, 2, 4], naive: [1, 2, 4] },
        v: {
          raft: ["Index 3 belongs to the current term (4) and is on a majority, so it is committed. Index 2 comes with it, because logs match as a prefix.", "ok"],
          naive: ["A majority stores index 3, so both rules agree: index 3 and everything before it is committed.", "ok"]
        }
      },
      {
        cap: "S1 crashes. S5 tries term 5: S4 would vote for it, but S2 and S3 refuse, because their last entry (term 4) is newer than S5's (term 3). S5 gets 2 votes of 5 and cannot win. Every possible winner holds indexes 2 and 3.",
        logs: [[1, 2, 4], [1, 2, 4], [1, 2, 4], [1], [1, 3]], leader: 0, term: 5, down: [1], c: { raft: [1, 2, 4], naive: [1, 2, 4] },
        v: {
          raft: ["Safe. The voting rule keeps S5 out, so the committed entries survive.", "ok"],
          naive: ["Safe, but only because a term-4 entry reached a majority first.", "ok"]
        }
      }
    ]
  };

  function frames() { return COMMON.concat(BRANCH[branch]); }

  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function btn(label, cls, fn) { var b = el("button", "btn " + (cls || ""), label); b.type = "button"; b.addEventListener("click", fn); return b; }

  root.textContent = "";
  var head = el("div", "widget-head");
  head.appendChild(el("span", "widget-tag", "Step through"));
  head.appendChild(el("h4", "widget-title", "Figure 8: why old-term entries are not counted"));
  root.appendChild(head);
  root.appendChild(el("p", "widget-help", "Each cell is one log entry, labelled with the term it was created in; the column is its index. A green outline means the leader considers that entry committed under the chosen rule. Step to the end under each rule and each branch, and watch what the naive rule gets wrong."));

  var opts = el("div", "rc-opts");
  function radioGroup(title, name, items, get, set) {
    var g = el("fieldset", "rc-group");
    g.appendChild(el("legend", null, title));
    items.forEach(function (it) {
      var l = el("label", "rc-radio");
      var r = el("input"); r.type = "radio"; r.name = "rc-" + name;
      r.addEventListener("change", function () { set(it[0]); render(); });
      r.checked = get() === it[0];
      l.appendChild(r); l.appendChild(el("span", null, it[1]));
      g.appendChild(l);
    });
    return g;
  }
  opts.appendChild(radioGroup("Commit rule", "rule", [["raft", "Raft: count replicas only for current-term entries"], ["naive", "Naive: any entry on a majority counts"]], function () { return rule; }, function (v) { rule = v; }));
  opts.appendChild(radioGroup("After step 4", "branch", [["D", "D: S1 crashes right away"], ["E", "E: S1 first replicates a term-4 entry"]], function () { return branch; }, function (v) { branch = v; if (idx > 3) idx = 3; }));
  root.appendChild(opts);

  var stage = el("div", "rc-stage");
  stage.setAttribute("role", "group");
  stage.setAttribute("aria-label", "Logs of the five servers");
  root.appendChild(stage);
  var cap = el("div", "rc-cap"); cap.setAttribute("aria-live", "polite");
  root.appendChild(cap);
  var ver = el("div", "rc-ver"); ver.setAttribute("role", "status");
  root.appendChild(ver);

  var ctl = el("div", "rc-ctl");
  var bBack = btn("Back", "", function () { if (idx > 0) { idx--; render(); } });
  var bNext = btn("Next", "primary", function () { if (idx < frames().length - 1) { idx++; render(); } });
  var bReset = btn("Reset", "", function () { idx = 0; render(); });
  var count = el("span", "rc-count");
  [bBack, bNext, bReset, count].forEach(function (x) { ctl.appendChild(x); });
  root.appendChild(ctl);

  function render() {
    var fs = frames(), f = fs[idx], i, j;
    stage.textContent = "";
    var claim = f.c[rule], commit = claim.length;
    for (i = 0; i < 5; i++) {
      var s = i + 1, isDown = f.down.indexOf(s) >= 0, isLead = f.leader === s;
      var row = el("div", "rc-row" + (isDown ? " down" : "") + (isLead ? " lead" : ""));
      var lab = el("div", "rc-lab");
      lab.appendChild(el("span", "rc-name", "S" + s));
      lab.appendChild(el("span", "rc-role", isDown ? "down" : isLead ? "leader, term " + f.term : "up"));
      row.appendChild(lab);
      var cells = el("div", "rc-cells");
      for (j = 1; j <= 3; j++) {
        var t = f.logs[i][j - 1];
        var c = el("span", "rc-cell" + (t ? " rc-t" + t : " empty") + (t && claim[j - 1] === t ? " cm" : ""), t ? String(t) : "·");
        c.setAttribute("aria-label", "index " + j + (t ? ", term " + t : ", empty") + (c.className.indexOf("cm") >= 0 ? ", counted as committed" : ""));
        cells.appendChild(c);
      }
      row.appendChild(cells);
      stage.appendChild(row);
    }
    var idxRow = el("div", "rc-idx");
    idxRow.appendChild(el("span", "rc-name", ""));
    var ic = el("div", "rc-cells");
    for (j = 1; j <= 3; j++) ic.appendChild(el("span", "rc-ixl", "idx " + j));
    idxRow.appendChild(ic);
    stage.appendChild(idxRow);

    cap.textContent = "Step " + (idx + 1) + " of " + fs.length + ". " + f.cap;
    var v = f.v[rule];
    ver.className = "rc-ver " + (v[1] || "");
    ver.textContent = v[0] + (commit ? "  (Leader's commit index under this rule: " + commit + ".)" : "");
    bBack.disabled = idx === 0;
    bNext.disabled = idx === fs.length - 1;
    count.textContent = (idx + 1) + " / " + fs.length;
  }

  render();
})();
