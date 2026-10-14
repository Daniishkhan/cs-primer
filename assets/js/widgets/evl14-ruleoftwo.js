/* Rule of Two checker (A6 chapter 14).
   Three properties (A untrusted input, B sensitive data or systems, C ability to change state or communicate
   externally) and an optional human gate. Counts how many are active and explains what an injection can reach. */
(function () {
  "use strict";
  var root = document.getElementById("evl14-ruleoftwo");
  if (!root) return;

  function q(n) { return root.querySelector("[data-act=" + n + "]"); }
  var boxes = { A: q("A"), B: q("B"), C: q("C") }, gate = q("gate"), preset = q("preset"), out = root.querySelector(".evl14-out");

  var PRESETS = {
    custom: null,
    summariser: { A: 1, B: 1, C: 0, gate: 0 },
    researcher: { A: 1, B: 0, C: 1, gate: 0 },
    coder: { A: 0, B: 1, C: 1, gate: 0 },
    inbox: { A: 1, B: 1, C: 1, gate: 0 },
    inboxgated: { A: 1, B: 1, C: 1, gate: 1 }
  };

  var LEG_NAME = { A: "untrusted input", B: "sensitive data or systems", C: "ability to act or communicate" };

  function explain(a, b, c) {
    if (a && b && c) return "An injected instruction can read private data and send it out or act on it. This is the combination behind the worst indirect-injection incidents.";
    if (a && b) return "An injection can read private data, but nothing can leave except through the model's reply to the user. Check that the reply itself cannot carry the data out (rendered images, links, auto-fetched URLs): that would be a hidden C.";
    if (a && c) return "An injection can make the agent act, but it holds no secrets to steal. The blast radius is whatever its actions can do, so the sandbox and the action list set the limit.";
    if (b && c) return "Inputs are trusted, so an injection has no route in. The remaining risk is a compromised or mistaken source, a mistake by the model, or an insider. Normal least privilege applies.";
    if (a) return "An injection can change what the model says, which still matters for accuracy and reputation, but cannot reach data or take actions.";
    if (b) return "Nothing untrusted reaches the model and nothing can leave. Low injection risk; ordinary data protection applies.";
    if (c) return "The agent can act, but on trusted input only and with no secrets. Check what its actions can reach.";
    return "No capability, no exposure. Nothing here to attack.";
  }

  function update() {
    var a = boxes.A.checked ? 1 : 0, b = boxes.B.checked ? 1 : 0, c = boxes.C.checked ? 1 : 0, g = gate.checked ? 1 : 0;
    var effC = (c && g) ? 0 : c;   // a human approving every consequential action gates the C leg
    var n = a + b + effC, k, cls, verdict, tips = [];
    ["A", "B", "C"].forEach(function (k2) { boxes[k2].parentNode.className = "evl14-leg" + (boxes[k2].checked ? " on" : ""); });
    if (n === 3) {
      cls = "bad"; verdict = "All three: do not run this autonomously";
      tips.push("Remove " + LEG_NAME.A + ": accept input only from trusted senders, or process it in an isolated step with no tools.");
      tips.push("Remove " + LEG_NAME.B + ": give the agent no access to private data in this session.");
      tips.push("Remove " + LEG_NAME.C + ": no send, write or network tools, or require a person to approve each action.");
    } else if (n === 2) {
      cls = "warn"; verdict = "Two of three: within the rule";
      tips.push("Within the rule is not safe. Apply least privilege to the two legs you have, and test with adaptive attacks (chapters 13 and 16).");
    } else {
      cls = "ok"; verdict = n + " of 3: well inside the rule";
    }
    if (c && g && n < 3) tips.unshift("The human gate counts only if the person sees exactly what will happen. A vague prompt or dozens of approvals a day turns it into a rubber stamp.");
    if (a && b && c && g) { cls = "warn"; verdict = "All three, with a human gate on actions: allowed by the rule, only as strong as the gate"; tips = ["Show the person the exact recipient, content and data before approval, and log every decision.", "Watch the approval rate: if people approve nearly everything, the gate is not working."]; }
    var html = "<p class=\"evl14-verdict " + cls + "\">" + verdict + "</p><p>" + explain(a, b, effC) + "</p>";
    if (tips.length) { html += "<ul>"; for (k = 0; k < tips.length; k++) html += "<li>" + tips[k] + "</li>"; html += "</ul>"; }
    out.innerHTML = html;
  }

  preset.addEventListener("change", function () {
    var p = PRESETS[preset.value];
    if (!p) return;
    boxes.A.checked = !!p.A; boxes.B.checked = !!p.B; boxes.C.checked = !!p.C; gate.checked = !!p.gate;
    update();
  });
  function manual() { preset.value = "custom"; update(); }
  boxes.A.addEventListener("change", manual); boxes.B.addEventListener("change", manual); boxes.C.addEventListener("change", manual); gate.addEventListener("change", manual);
  update();
})();
