/* "Where does encryption help?" explorer (security chapter 17).
   Pick a protection layer (full-disk, database TDE, application-level field encryption, none) and a threat;
   the widget says whether that layer helps and why. Verdicts are the qualitative ones argued in the chapter:
   they depend on where the key lives and who can call the decrypt path, and real products vary in detail.
   No storage, no network. */
(function () {
  "use strict";
  var root = document.getElementById("data-layers");
  if (!root) return;
  function h(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }

  var LAYERS = [
    { id: "disk", name: "Full-disk / volume", desc: "The block device is encrypted below the filesystem. The running machine sees plaintext." },
    { id: "tde",  name: "Database TDE",       desc: "The database engine encrypts its data files (and usually its backups) but decrypts for every authorised SQL session." },
    { id: "app",  name: "Application-level",  desc: "The application encrypts chosen fields with per-tenant or per-user keys (envelope encryption) before they reach the database." },
    { id: "none", name: "No encryption",      desc: "Plaintext at rest. Everything rests on access control alone." }
  ];
  var THREATS = [
    { id: "disk",   name: "Stolen or decommissioned drive" },
    { id: "backup", name: "Stolen database backup file" },
    { id: "dba",    name: "Administrator with SQL access" },
    { id: "sqli",   name: "SQL injection through the app" },
    { id: "app",    name: "Compromised application server" },
    { id: "wire",   name: "Eavesdropper between app and database" }
  ];
  /* [verdict, reason]; verdict: yes | part | no */
  var V = {
    disk: {
      disk: ["yes", "The drive is ciphertext without the volume key, which is held elsewhere (a TPM or the cloud provider's key service)."],
      tde:  ["yes", "Data files on the drive are ciphertext; this is the case TDE was built for."],
      app:  ["yes", "Fields are ciphertext on disk, and the keys are not on that disk."],
      none: ["no", "Whoever holds the drive reads everything."]
    },
    backup: {
      disk: ["part", "Only if the backup lands on an encrypted volume and stays there. Copied off, a backup file is plain."],
      tde:  ["yes", "Most engines write backups encrypted with the TDE key; check yours, since this is configuration."],
      app:  ["yes", "Encrypted fields stay encrypted inside the backup, whatever tool made it."],
      none: ["no", "A backup is a full copy of the data, usually less guarded than the live database."]
    },
    dba: {
      disk: ["no", "The administrator queries the running database, which sees decrypted blocks."],
      tde:  ["no", "TDE decrypts transparently for any authorised SQL session, so it does nothing against someone with that access."],
      app:  ["yes", "The administrator sees ciphertext unless they can also call the key service. Separation of duties, not magic."],
      none: ["no", "They read the tables."]
    },
    sqli: {
      disk: ["no", "The injected query runs inside the app's own database session; storage encryption is invisible to it."],
      tde:  ["no", "Same reason: the engine decrypts for the session the injection is running in."],
      app:  ["part", "Rows come back as ciphertext unless the injected path flows through the app's decrypt code. Fix the injection regardless."],
      none: ["no", "The injected query returns plaintext."]
    },
    app: {
      disk: ["no", "The attacker is on the running machine, which has the disk unlocked."],
      tde:  ["no", "The app is an authorised client; the database decrypts for it."],
      app:  ["part", "The attacker can use the app's decrypt path while they hold it. Per-tenant keys, KMS policy, rate limits and audit bound and reveal the damage."],
      none: ["no", "Everything the app can read, the attacker can read."]
    },
    wire: {
      disk: ["no", "At-rest encryption says nothing about the connection. You need TLS."],
      tde:  ["no", "Same: data is decrypted before it is sent. You need TLS."],
      app:  ["part", "The encrypted fields stay encrypted on the wire, but everything else on that link (other columns, queries, credentials) is exposed. Use TLS."],
      none: ["no", "Plain on the wire unless TLS is on."]
    }
  };
  var LABEL = { yes: "PROTECTS", part: "PARTLY", no: "DOES NOT HELP" };
  var PILL = { yes: "green", part: "yellow", no: "red" };
  var CLS = { yes: "dl-yes", part: "dl-part", no: "dl-no" };

  var st = { layer: "tde", threat: "dba" };

  var head = h("div", "widget-head");
  head.appendChild(h("span", "widget-tag", "Explore"));
  head.appendChild(h("h4", "widget-title", "Which encryption layer stops which threat?"));
  root.appendChild(head);

  var lrow = h("div", "widget-row dl-row"); lrow.setAttribute("role", "group"); lrow.setAttribute("aria-label", "Protection layer");
  var lbtns = {};
  LAYERS.forEach(function (l) {
    var b = h("button", "btn small", l.name); b.type = "button";
    b.addEventListener("click", function () { st.layer = l.id; render(); });
    lbtns[l.id] = b; lrow.appendChild(b);
  });
  root.appendChild(lrow);

  var ctl = h("div", "widget-row dl-row");
  var lab = h("label", "dl-ctl"); lab.appendChild(h("span", "dl-l", "Threat"));
  var sel = h("select");
  THREATS.forEach(function (t) { var o = h("option", null, t.name); o.value = t.id; sel.appendChild(o); });
  sel.value = st.threat; sel.addEventListener("change", function () { st.threat = sel.value; render(); });
  lab.appendChild(sel); ctl.appendChild(lab); root.appendChild(ctl);

  var desc = h("p", "dl-desc"); root.appendChild(desc);
  var out = h("div", "widget-out dl-out"); out.setAttribute("aria-live", "polite"); root.appendChild(out);
  var tbl = h("div", "dl-cmp"); root.appendChild(tbl);
  root.appendChild(h("p", "widget-help", "Verdicts are qualitative and assume the key is not stored next to the data. The table shows the chosen layer against every threat."));

  function render() {
    var layer = LAYERS.filter(function (x) { return x.id === st.layer; })[0];
    LAYERS.forEach(function (x) { lbtns[x.id].className = "btn small" + (x.id === st.layer ? " primary" : ""); lbtns[x.id].setAttribute("aria-pressed", x.id === st.layer ? "true" : "false"); });
    desc.textContent = layer.desc;
    var v = V[st.threat][st.layer];
    out.textContent = "";
    var p = h("p");
    p.appendChild(h("span", "pill " + PILL[v[0]], LABEL[v[0]]));
    p.appendChild(document.createTextNode(" " + v[1]));
    out.appendChild(p);
    tbl.textContent = "";
    var t = h("table", "dl-table");
    var hr = h("tr"); ["Threat", "Verdict", "Why"].forEach(function (x) { hr.appendChild(h("th", null, x)); }); t.appendChild(hr);
    THREATS.forEach(function (th) {
      var vv = V[th.id][st.layer];
      var tr = h("tr", th.id === st.threat ? "dl-sel" : "");
      tr.appendChild(h("td", null, th.name));
      tr.appendChild(h("td", CLS[vv[0]], LABEL[vv[0]].toLowerCase()));
      tr.appendChild(h("td", null, vv[1]));
      t.appendChild(tr);
    });
    tbl.appendChild(t);
  }
  render();
})();
