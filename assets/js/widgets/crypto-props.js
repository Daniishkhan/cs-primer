/* Crypto properties explorer (security chapter 3).

   Choose a primitive and an attacker goal; the widget says whether the primitive, used correctly
   with secrets kept secret, stops that goal, and why. The goals are phrased from the attacker's side:
     read       - learn the message contents from what is sent
     tamper     - change the message in transit without the receiver noticing
     forge      - create a message that the receiver accepts as coming from the sender
     repudiate  - (the SENDER's goal) later deny having sent a message the receiver holds
   Verdicts: "stops" (green), "does not stop" (red), "partly" (yellow, depends on a condition).
   The full matrix is shown below the explorer. Simplifications: algorithms are idealised (no
   implementation bugs, nonces not reused); "message" means the whole transmitted object. */
(function () {
  "use strict";
  var root = document.getElementById("crypto-props");
  if (!root) return;
  function h(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }

  var PRIMS = [
    { id: "hash",  name: "Hash (SHA-256)",                  desc: "No key. Anyone can compute it, including the attacker." },
    { id: "mac",   name: "MAC (HMAC-SHA-256)",              desc: "Sender and receiver share a secret key. The tag proves the key holder produced the message." },
    { id: "enc",   name: "Encryption only (unauthenticated)", desc: "A stream or CTR-mode cipher with a shared key, no tag." },
    { id: "aead",  name: "AEAD (AES-GCM, ChaCha20-Poly1305)", desc: "Shared key. Encrypts and attaches an authentication tag over ciphertext and associated data." },
    { id: "sig",   name: "Digital signature (Ed25519, ECDSA)", desc: "Signer holds a private key; anyone with the public key can verify. The message itself is sent in clear." },
    { id: "pke",   name: "Public-key encryption alone",      desc: "Anyone can encrypt to the receiver's public key; only the receiver can decrypt. No proof of who sent it." }
  ];
  var GOALS = [
    { id: "read",  name: "Read the message" },
    { id: "tamper", name: "Tamper undetected" },
    { id: "forge", name: "Forge a message from the sender" },
    { id: "rep",   name: "Sender denies sending it (repudiation)" }
  ];
  /* v: 0 does not stop, 1 stops, 2 partly */
  var M = {
    hash: {
      read:   [0, "The message is sent in the clear, and a hash conceals nothing the attacker needs: they already have the message."],
      tamper: [0, "The attacker changes the message and recomputes the hash. A hash has no secret, so it detects accidental corruption but not an adversary."],
      forge:  [0, "Anyone can hash a message of their own choosing, so a hash proves nothing about who wrote it."],
      rep:    [0, "There is no key tying the hash to the sender, so the sender can say anyone made it."]
    },
    mac: {
      read:   [0, "A MAC authenticates; it does not encrypt. The message travels in the clear unless you also encrypt it."],
      tamper: [1, "Changing any bit invalidates the tag, and the attacker cannot compute a new one without the key."],
      forge:  [1, "Producing a valid tag requires the shared key. (Replay of an old valid message is a separate problem: add a counter or timestamp.)"],
      rep:    [0, "Both parties hold the same key, so either could have produced the tag. A third party cannot tell which did. MACs give no non-repudiation."]
    },
    enc: {
      read:   [1, "Without the key the ciphertext hides the plaintext (assuming a sound cipher and a nonce that is never reused)."],
      tamper: [0, "Stream and CTR modes are malleable: flipping a ciphertext bit flips the same plaintext bit. The attacker can change a message in predictable ways without knowing the key."],
      forge:  [2, "Blind forgery of random-looking data is trivial; a targeted forgery is possible whenever the attacker knows part of the plaintext. Do not rely on it."],
      rep:    [0, "Shared key: either side could have produced the ciphertext."]
    },
    aead: {
      read:   [1, "The plaintext is encrypted under a key the attacker does not have. The nonce must be unique per key; repeating it breaks confidentiality (and for GCM, authenticity too)."],
      tamper: [1, "The tag covers the ciphertext and the associated data. Any change makes decryption fail before any plaintext is released."],
      forge:  [1, "Producing a valid ciphertext and tag needs the key (again, assuming nonces are never reused)."],
      rep:    [0, "Shared key, so the receiver could have created the message too. Use a signature if you need proof to a third party."]
    },
    sig: {
      read:   [0, "A signature does not hide the message. Pair it with encryption if confidentiality matters."],
      tamper: [1, "Verification fails if the message changes, and the attacker lacks the private key to re-sign."],
      forge:  [1, "Only the private key holder can sign; the public verification key reveals nothing useful for forging."],
      rep:    [2, "This is the one primitive that gives non-repudiation: only the signer holds the private key. It holds as long as the key was not stolen and the public key is reliably bound to the signer (certificates, PKI)."]
    },
    pke: {
      read:   [1, "Only the holder of the private key can decrypt."],
      tamper: [2, "Textbook RSA is malleable, and even modern schemes alone do not tell the receiver the data is unchanged or who sent it. Use authenticated hybrid encryption (e.g. HPKE) or sign as well."],
      forge:  [0, "The encryption key is public, so anyone can create a message that decrypts fine. It proves nothing about the sender."],
      rep:    [0, "Anyone could have sent it, so there is no evidence about the sender at all."]
    }
  };
  var LABEL = ["Does not stop it", "Stops it", "Partly / conditional"];
  var CLS = ["red", "green", "yellow"];

  var head = h("div", "widget-head");
  head.appendChild(h("span", "widget-tag", "Explore"));
  head.appendChild(h("h4", "widget-title", "Which primitive stops which attack?"));
  root.appendChild(head);

  var st = { p: "mac", g: "tamper" };
  var row = h("div", "widget-row cp-row");
  function sel(label, opts, key) {
    var l = h("label", "cp-ctl"); l.appendChild(h("span", "cp-l", label));
    var s = h("select");
    opts.forEach(function (o) { var op = h("option", null, o.name); op.value = o.id; s.appendChild(op); });
    s.value = st[key];
    s.addEventListener("change", function () { st[key] = s.value; render(); });
    l.appendChild(s); row.appendChild(l);
  }
  sel("Primitive", PRIMS, "p"); sel("Attacker goal", GOALS, "g");
  root.appendChild(row);
  var desc = h("p", "widget-help cp-desc"); root.appendChild(desc);
  var out = h("div", "widget-out"); out.setAttribute("aria-live", "polite"); root.appendChild(out);
  var wrap = h("div", "cp-table-wrap"); root.appendChild(wrap);

  function render() {
    var prim = PRIMS.filter(function (x) { return x.id === st.p; })[0];
    desc.textContent = prim.desc;
    var v = M[st.p][st.g];
    out.textContent = "";
    var pill = h("span", "pill " + CLS[v[0]], LABEL[v[0]]);
    out.appendChild(pill);
    out.appendChild(document.createTextNode(" "));
    out.appendChild(h("span", null, v[1]));
    wrap.textContent = "";
    var tb = h("table", "cp-table");
    var th = h("tr"); th.appendChild(h("th", null, ""));
    GOALS.forEach(function (g) { th.appendChild(h("th", null, g.name)); });
    tb.appendChild(th);
    PRIMS.forEach(function (p) {
      var tr = h("tr"); tr.appendChild(h("th", null, p.name));
      GOALS.forEach(function (g) {
        var cell = M[p.id][g.id][0];
        var td = h("td", "cp-" + CLS[cell] + (p.id === st.p && g.id === st.g ? " cp-sel" : ""));
        var b = h("button", "cp-cell", cell === 1 ? "yes" : cell === 2 ? "partly" : "no");
        b.type = "button"; b.setAttribute("aria-label", p.name + ", " + g.name + ": " + LABEL[cell]);
        b.addEventListener("click", function () { st.p = p.id; st.g = g.id; rebuildSel(); render(); });
        td.appendChild(b); tr.appendChild(td);
      });
      tb.appendChild(tr);
    });
    wrap.appendChild(tb);
    wrap.appendChild(h("p", "widget-help", "Table: does the primitive stop the attacker goal? Click a cell to select it. Real systems combine primitives: AEAD for the channel, signatures for evidence."));
  }
  function rebuildSel() {
    var ss = row.querySelectorAll("select");
    ss[0].value = st.p; ss[1].value = st.g;
  }
  render();
})();
