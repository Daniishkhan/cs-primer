/* Discovery interview practice (A8 chapter 01).
   A short branching conversation with a claims analyst who has asked for a chatbot.
   Each turn offers three questions; only one asks about a specific past event or
   a concrete next step. Weak questions return fluff and you try again, so the
   transcript shows how much you learnt per question asked. No randomness. */
(function () {
  "use strict";
  var root = document.getElementById("aid01-interview");
  if (!root) return;

  var TURNS = [
    { said: "We need a chatbot over our policy documents.",
      opts: [
        { q: "Would a chatbot help your team?", good: false, said: "Oh yes, definitely. That would be great.",
          why: "A hypothetical plus a compliment. It feels like a yes and tells you nothing you can act on." },
        { q: "What features should the chatbot have?", good: false, said: "Search, maybe a dashboard, a nice interface. Voice?",
          why: "You asked for a wish list, so you got one, invented on the spot. This is solution talk, not evidence." },
        { q: "Tell me about the last time you needed something from those documents.", good: true,
          said: "Tuesday. A client asked if flood damage to a detached garage is covered. I spent about 40 minutes across three PDFs.",
          fact: "Last Tuesday: 40 minutes across three PDFs for one coverage question." }
      ] },
    { said: "It was a pain, honestly.",
      opts: [
        { q: "How often does that happen?", good: false, said: "Oh, all the time.",
          why: "A generic count. \"All the time\" cannot be priced. Ask about specific recent occasions first, then count them." },
        { q: "Do you think better search would fix it?", good: false, said: "Probably? I suppose so.",
          why: "A leading question about your own idea. People agree politely." },
        { q: "What happened next?", good: true,
          said: "Two of the PDFs disagreed. The 2023 update was never merged into the older one. In the end I asked Priya.",
          fact: "Two documents contradict each other: a 2023 update was never merged." }
      ] },
    { said: "Priya is our senior adjuster.",
      opts: [
        { q: "Would it save time if a chatbot answered instead of Priya?", good: false, said: "Sure, I'd think so.",
          why: "Another hypothetical. \"I'd think so\" is a guess about a product that does not exist." },
        { q: "Which matters more to you, accuracy or speed?", good: false, said: "Both, obviously.",
          why: "A forced choice with no context gets a platitude. Trade-offs are found in stories, not in abstract rankings." },
        { q: "How did asking Priya go?", good: true,
          said: "She answered from memory in two minutes. She gets interrupted about eight times a day like that.",
          fact: "The senior expert answers from memory, about eight interruptions a day." }
      ] },
    { said: "She knows the answers.",
      opts: [
        { q: "How much would your team pay for a tool that fixed this?", good: false, said: "I'm not the one who pays. Ask my manager.",
          why: "A price question to someone without a budget, about a hypothetical. Ask about money spent today, to the person who spends it." },
        { q: "Would you recommend a tool like that to colleagues?", good: false, said: "Sure.",
          why: "Politeness again. Nothing in the answer could change your plan." },
        { q: "Is any of what Priya knows written down anywhere?", good: true,
          said: "She keeps a spreadsheet of her rulings. About 120 rows. Nobody else uses it.",
          fact: "A private spreadsheet of about 120 expert rulings already exists." }
      ] },
    { said: "That spreadsheet is the real answer book, to be honest.",
      opts: [
        { q: "Great, so shall we go ahead and build the chatbot?", good: false, said: "Er... if you think that's best.",
          why: "Closing too early. The customer defers to you, and you have just turned evidence into a commitment to a solution." },
        { q: "Thanks, that is everything I need.", good: false, said: "Okay. Good luck with it.",
          why: "No next step. A conversation that ends with no commitment, such as data, time or an introduction, has not advanced anything." },
        { q: "Could I see the spreadsheet, and talk to Priya on Thursday?", good: true,
          said: "I'll ask her. She'll probably agree if you promise this is not about replacing her.",
          fact: "Next step secured: spreadsheet and expert access, and a concern to address." }
      ] }
  ];

  var turn = 0, asked = 0, facts = [];
  var logEl = root.querySelector(".aid01-log");
  var optsEl = root.querySelector(".aid01-opts");
  var scoreEl = root.querySelector(".aid01-score");
  var resetBtn = root.querySelector("[data-act=reset]");

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function line(who, text, cls) {
    var p = el("p", "aid01-line " + (cls || ""));
    p.appendChild(el("strong", "", who + ": "));
    p.appendChild(document.createTextNode(text));
    logEl.appendChild(p);
    logEl.scrollTop = logEl.scrollHeight;
  }
  function note(text, cls) { logEl.appendChild(el("p", "aid01-note " + cls, text)); }

  function score() {
    scoreEl.textContent = "Facts uncovered: " + facts.length + " of " + TURNS.length +
      "   |   Questions asked: " + asked +
      (asked ? "   |   Facts per question: " + (facts.length / asked).toFixed(2) : "");
  }

  function showTurn() {
    optsEl.textContent = "";
    if (turn >= TURNS.length) { finish(); return; }
    var t = TURNS[turn];
    t.opts.forEach(function (o) {
      var b = el("button", "btn aid01-opt", o.q);
      b.type = "button";
      b.addEventListener("click", function () { choose(o, b); });
      optsEl.appendChild(b);
    });
  }

  function choose(o, btn) {
    asked++;
    line("You", o.q, "you");
    line("Marco", o.said, "them");
    if (o.good) {
      facts.push(o.fact);
      note("Evidence: " + o.fact, "good");
      turn++;
      if (turn < TURNS.length) line("Marco", TURNS[turn].said, "them");
      showTurn();
    } else {
      note("Nothing learnt. " + o.why, "bad");
      btn.disabled = true;
    }
    score();
  }

  function finish() {
    var box = el("div", "aid01-final");
    box.appendChild(el("p", "", "Interview over. You asked " + asked + " questions and collected " + facts.length + " facts."));
    var wasted = asked - facts.length;
    box.appendChild(el("p", "",
      wasted === 0 ? "No wasted questions. " : wasted + " question" + (wasted === 1 ? "" : "s") + " returned only opinion or politeness. ") );
    box.appendChild(el("p", "",
      "Read the facts together: the documents contradict each other, the real answers live in one expert's head and a private spreadsheet, " +
      "and she is interrupted constantly. The requested feature was a chatbot. The problem is out-of-date documents and unwritten expert rulings, " +
      "which is where you start."));
    optsEl.appendChild(box);
  }

  function reset() {
    turn = 0; asked = 0; facts = [];
    logEl.textContent = "";
    line("Marco", TURNS[0].said, "them");
    showTurn(); score();
  }

  resetBtn.addEventListener("click", reset);
  reset();
})();
