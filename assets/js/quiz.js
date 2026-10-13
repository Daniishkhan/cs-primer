/* Declarative multiple-choice quizzes.

   <section class="quiz">
     <h2>Check your understanding</h2>
     <div class="q" data-answer="1">              ← 0-based index of the right option
       <p class="q-text">Question?</p>
       <ol class="q-options"><li>A</li><li>B</li></ol>
       <div class="q-explain">Why B is right (and why A is tempting).</div>
     </div>
   </section>
*/
(function () {
  "use strict";
  var LETTERS = "ABCDEFGH";

  function setup(quiz) {
    var qs = Array.prototype.slice.call(quiz.querySelectorAll(".q"));
    var score = document.createElement("div");
    score.className = "quiz-score";
    quiz.appendChild(score);

    function refresh() {
      var answered = qs.filter(function (q) { return q.classList.contains("answered"); });
      var right = qs.filter(function (q) { return q.dataset.result === "ok"; }).length;
      score.innerHTML = "";
      if (!answered.length) { score.textContent = "Pick an answer for each question. You'll get an explanation either way."; return; }
      var msg = document.createElement("span");
      msg.textContent = "Score: " + right + " / " + qs.length +
        (answered.length === qs.length ? (right === qs.length ? "  🎉 Perfect!" : "  Read the explanations, then try again.") : "");
      score.appendChild(msg);
      if (answered.length === qs.length) {
        var again = document.createElement("button");
        again.type = "button"; again.className = "btn small"; again.textContent = "↺ Retry quiz";
        again.addEventListener("click", function () { qs.forEach(reset); refresh(); });
        score.appendChild(again);
      }
    }

    function reset(q) {
      q.classList.remove("answered"); delete q.dataset.result;
      q.querySelectorAll(".q-opt").forEach(function (b) { b.disabled = false; b.classList.remove("correct", "wrong"); });
      var v = q.querySelector(".q-verdict"); if (v) v.remove();
    }

    qs.forEach(function (q, i) {
      var answer = parseInt(q.dataset.answer, 10);
      var text = q.querySelector(".q-text");
      if (text) text.dataset.n = String(i + 1);
      var opts = q.querySelectorAll(".q-options > li");
      opts.forEach(function (li, j) {
        var b = document.createElement("button");
        b.type = "button"; b.className = "q-opt";
        var letter = document.createElement("span");
        letter.className = "letter"; letter.textContent = LETTERS[j];
        var label = document.createElement("span");
        while (li.firstChild) label.appendChild(li.firstChild);
        b.appendChild(letter); b.appendChild(label);
        li.appendChild(b);
        b.addEventListener("click", function () {
          if (q.classList.contains("answered")) return;
          q.classList.add("answered");
          var ok = j === answer;
          q.dataset.result = ok ? "ok" : "no";
          q.querySelectorAll(".q-opt").forEach(function (o, k) {
            o.disabled = true;
            if (k === answer) o.classList.add("correct");
          });
          if (!ok) b.classList.add("wrong");
          var exp = q.querySelector(".q-explain");
          if (exp) {
            var v = document.createElement("span");
            v.className = "q-verdict " + (ok ? "ok" : "no");
            v.textContent = ok ? "Correct!" : "Not quite.";
            exp.insertBefore(v, exp.firstChild);
          }
          refresh();
        });
      });
    });
    refresh();
  }

  function init() { document.querySelectorAll(".quiz").forEach(setup); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
