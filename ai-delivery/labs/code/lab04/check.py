"""Self-check for Lab 4: A Take-Home, End to End.

    python3 check.py                  # checks your starter.py
    python3 check.py solution         # checks the reference solution
    python3 check.py solution 5       # only milestone 5
    python3 check.py solution 5 3     # milestone 5, replaying ONLY the random cases of seed 3

This file plays the reviewer. It loads hidden_tests.json (40 questions you have not been shown:
please do not open it before you finish, or the exercise measures nothing), runs your system on
them and checks the numbers. Everything is deterministic and offline; the "model" is the
extractive stand-in reader in your starter (built on llm.py). A failure prints its seed.
The whole check takes about a second.
Prints a tick, a cross, or "not implemented yet" for each milestone.
"""
import importlib
import json
import math
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True

args = sys.argv[1:]
target = args[0] if args and not args[0].isdigit() else "starter"
rest = [a for a in args if a.isdigit()]
ONLY = int(rest[0]) if rest else None
ONLY_SEED = int(rest[1]) if len(rest) > 1 else None
mod = importlib.import_module(target)
from llm import ScriptedModel  # noqa: E402
results = []


def seeds(default):
    return [ONLY_SEED] if ONLY_SEED is not None else list(default)


def check(number, name, fn):
    if ONLY is not None and ONLY != number:
        return
    try:
        note = fn()
        print(f"  ✔ {name}")
        for line in (note or "").splitlines():
            print(f"      {line}")
        results.append(True)
    except NotImplementedError as e:
        print(f"  … {name}: not implemented yet ({e})")
        results.append(False)
    except AssertionError as e:
        print(f"  ✘ {name}: {e}")
        results.append(False)
    except Exception as e:
        import traceback
        tb = traceback.extract_tb(e.__traceback__)
        where = next((f"{f.name}() line {f.lineno}" for f in reversed(tb) if f.filename.endswith(f"{target}.py")), "?")
        print(f"  ✘ {name}: {type(e).__name__}: {e}   [in {where}]")
        results.append(False)


def expect(cond, msg):
    assert cond, msg


def near(a, b, tol=1e-9):
    return abs(a - b) <= tol


CORPUS = mod.load_corpus()
CHUNKS = mod.chunks_of(CORPUS)
INDEX = mod.BM25Index(CHUNKS)
DEV = mod.load_dev()
with open(os.path.join(HERE, "hidden_tests.json"), encoding="utf-8") as f:
    HIDDEN = json.load(f)
_cache = {}


def run_system(questions, reader=None, name="sys"):
    """Run the full system and the baseline on a list of questions: (results, base_results, graded, base_graded)."""
    key = (name, id(questions))
    if key not in _cache:
        reader = reader or mod.ExtractiveReader()
        res = [mod.answer_or_abstain(reader, INDEX, q["question"]) for q in questions]
        base = [mod.baseline_answer(INDEX, q["question"]) for q in questions]
        gs = [mod.grade(q, r) for q, r in zip(questions, res)]
        bs = [mod.grade(q, r) for q, r in zip(questions, base)]
        _cache[key] = (res, base, gs, bs)
    return _cache[key]


# =============================================================================
# Milestone 1: the requirements restatement
# =============================================================================
GOOD = """# Requirements restatement

## Goal
An analyst asks questions about three annual reports and wants a short answer with the page it came from, or a clear refusal. A good answer can be checked by opening that page.

## Inputs
Three invented annual reports of six pages each as plain text, twelve example questions with answers and pages, and no tables or scans.

## Assumptions
- A question names its company.
- A page is the right unit to cite.
- A wrong answer is worse than no answer.

## Questions for the customer
- Who reads the answers, and do they open the cited page?
- Is a refusal acceptable when arithmetic across pages is needed?
- Which costs more: a wrong refusal or a wrong answer?

## Out of scope
Tables, scans, arithmetic across pages, a user interface and fine-tuning anything at all.

## Success measures
- At least 80% of 40 hidden questions correct, with a 95% interval.
"""


def m1():
    cr = mod.check_restatement
    got = cr(GOOD)
    expect(got == [], f"a complete restatement should have no problems; got {got}")
    t = GOOD.replace("## Out of scope", "## Scope")
    expect(cr(t) == ["missing heading: Out of scope"], f"heading missing; expected ['missing heading: Out of scope'], got {cr(t)}")
    t = GOOD.replace("## Goal", "## goal").replace("## Inputs", "##   INPUTS  ")
    expect(cr(t) == [], f"headings are matched ignoring case and surrounding spaces; got {cr(t)}")
    t = GOOD.replace("Three invented annual reports of six pages each as plain text, twelve example questions with answers and pages, and no tables or scans.", "Some reports.")
    expect(cr(t) == ["empty section: Inputs"], f"a body of fewer than 8 words is an empty section; got {cr(t)}")
    t = GOOD.replace("- A page is the right unit to cite.\n", "")
    expect(cr(t) == ["too few assumptions: 2"], f"three assumption bullets are required; got {cr(t)}")
    t = GOOD.replace("- Which costs more: a wrong refusal or a wrong answer?", "- Tell me which costs more, a wrong refusal or a wrong answer.")
    expect(cr(t) == ["question without ?: Tell me which costs more, a wrong refusal or a wrong answer."], f"every question must end with a question mark; got {cr(t)}")
    t = GOOD.replace("- Is a refusal acceptable when arithmetic across pages is needed?\n", "")
    expect(cr(t) == ["too few questions: 2"], f"three question bullets are required; got {cr(t)}")
    t = GOOD.replace("At least 80% of 40 hidden questions correct, with a 95% interval.", "Most of the hidden questions answered correctly and the numbers carefully checked.")
    expect(cr(t) == ["success measures need a number"], f"a success measure with no number is not measurable; got {cr(t)}")
    t = GOOD.replace("A good answer can be checked by opening that page.", "A good answer can be checked by opening that page. TODO refine this.")
    expect(cr(t) == ["placeholder left: TODO"], f"a leftover TODO is a problem; got {cr(t)}")
    t = GOOD + "\n" + "extra words here " * 130
    n = len(t.split())
    expect(cr(t) == [f"too long: {n} words"], f"more than 350 words is not one page; expected ['too long: {n} words'], got {cr(t)}")
    gone = cr(GOOD.replace("## Inputs", "## Input"))
    expect(gone == ["missing heading: Inputs"], f"'Input' is not 'Inputs'; got {gone}")
    both = cr(GOOD.replace("## Out of scope", "## Scope").replace("- A page is the right unit to cite.\n", ""))
    expect(both == ["too few assumptions: 2", "missing heading: Out of scope"], f"problems follow the order of REQUIRED_HEADINGS (Assumptions comes before Out of scope); got {both}")
    tpl = cr(mod.TEMPLATE)
    for want in ("too few assumptions: 1", "too few questions: 1", "success measures need a number", "placeholder left: TODO"):
        expect(want in tpl, f"the unfilled TEMPLATE should report {want!r}; got {tpl}")
    for s in seeds(range(1, 16)):
        rng = random.Random(s)
        h = rng.choice(mod.REQUIRED_HEADINGS)
        t = GOOD.replace(f"## {h}\n", "")
        expect(cr(t) == [f"missing heading: {h}"], f"seed {s}: deleting the '{h}' heading should give exactly ['missing heading: {h}']; got {cr(t)}")
    path = os.path.join(HERE, "restatement_solution.md" if target == "solution" else "restatement.md")
    expect(os.path.exists(path), f"write your own restatement for the lab's brief into {os.path.basename(path)} (start from mod.TEMPLATE) and make it pass")
    mine = cr(open(path, encoding="utf-8").read())
    expect(mine == [], f"{os.path.basename(path)} has problems: {mine}")
    return f"check_restatement spots every missing, empty, unmeasurable and unfinished part; {os.path.basename(path)} passes ({len(open(path).read().split())} words)"


# =============================================================================
# Milestone 2: a baseline you can beat
# =============================================================================
def m2():
    toy = [mod.Chunk("a", 1, "", "apple pie"), mod.Chunk("b", 1, "", "apple apple tart"), mod.Chunk("c", 1, "", "pie crust crust crust")]
    ix = mod.BM25Index(toy)
    expect(near(ix.idf("apple"), math.log(1 + (3 - 2 + 0.5) / (2 + 0.5))), f"idf('apple') with N=3, df=2 is ln(1 + 1.5/2.5) = 0.4700; got {ix.idf('apple')}")
    expect(near(ix.idf("zzz"), math.log(1 + 3.5 / 0.5)), f"a term in no page has df = 0: ln(1 + 3.5/0.5) = 2.0794; got {ix.idf('zzz')}")
    want = ix.idf("apple") * 1 * 2.2 / (1 + 1.2 * (1 - 0.75 + 0.75 * 2 / 3))
    expect(near(ix.score("apple", 0), want), f"page a (length 2, average length 3): idf x tf(k1+1)/(tf + k1(1-b+b dl/avgdl)) = {want:.4f}; got {ix.score('apple', 0)}")
    want = ix.idf("apple") * 2 * 2.2 / (2 + 1.2 * (1 - 0.75 + 0.75 * 3 / 3))
    expect(near(ix.score("apple", 1), want), f"page b has tf 2 and an average length: {want:.4f}; got {ix.score('apple', 1)}")
    expect(ix.score("tart", 0) == 0 and near(ix.score("apple apple", 0), ix.score("apple", 0)), "a missing term scores 0, and a repeated query term counts once")
    expect(near(ix.score("apple pie", 0), ix.score("apple", 0) + ix.score("pie", 0)), "scores add over distinct query terms")
    r = ix.search("apple", 5)
    expect([c.doc for _, c in r] == ["b", "a"], f"only pages with a positive score are returned, best first: expected ['b', 'a']; got {[c.doc for _, c in r]}")
    expect(len(ix.search("apple pie", 1)) == 1 and ix.search("zzz") == [] and ix.search("the of") == [], "k limits the list; no matching terms (or only stop words) gives []")
    tie = mod.BM25Index([mod.Chunk("z", 2, "", "same words"), mod.Chunk("a", 9, "", "same words"), mod.Chunk("a", 3, "", "same words")])
    expect([(c.doc, c.page) for _, c in tie.search("same words", 3)] == [("a", 3), ("a", 9), ("z", 2)], "ties are broken by (doc, page) ascending")
    for s in seeds(range(1, 11)):
        rng = random.Random(s)
        vocab = "red blue green gold iron silk wool oak elm ash fir pine".split()
        cs = [mod.Chunk("d", i, "", " ".join(rng.choice(vocab) for _ in range(rng.randint(3, 12)))) for i in range(8)]
        ix2 = mod.BM25Index(cs)
        q = " ".join(rng.sample(vocab, 3))
        got = ix2.search(q, 8)
        expect([sc for sc, _ in got] == sorted([sc for sc, _ in got], reverse=True), f"seed {s}: results must be best first")
        expect(all(near(sc, ix2.score(q, c.page)) for sc, c in got), f"seed {s}: search must return score() values")
    f1, n1 = mod.recall_at_k(DEV, INDEX, 1)
    f3, n3 = mod.recall_at_k(DEV, INDEX, 3)
    expect((n1, n3) == (9, 9), f"recall_at_k counts only answerable questions: dev has 9; got totals {n1} and {n3}")
    expect(f1 == 8 and f3 == 9, f"dev: the gold page is first for 8 of 9 answerable questions and in the top 3 for all 9; got {f1} and {f3}")
    h1, hn = mod.recall_at_k(HIDDEN, INDEX, 1)
    h3, _ = mod.recall_at_k(HIDDEN, INDEX, 3)
    expect(hn == 30 and h1 == 29 and h3 == 30, f"hidden: recall@1 should be 29/30 and recall@3 30/30; got {h1}/{hn} and {h3}/{hn}")
    b = mod.baseline_answer(INDEX, "How many trucks are in the Harbourline fleet?")
    expect("1,215" in b["answer"] and b["cites"] == [("harbourline", 3)] and b["hits"] == [("harbourline", 3)] and b["abstained"] is False and b["reason"] is None and b["problems"] == [],
           f"the baseline answers with the best sentence of the top page and cites it; got {b}")
    b = mod.baseline_answer(INDEX, "zzz qqq")
    expect(b["abstained"] is True and b["reason"] == "no_hits" and b["answer"] is None and b["cites"] == [], f"nothing found: abstain with reason 'no_hits'; got {b}")
    res, base, gs, bs = run_system(HIDDEN)
    ans_ok = sum(g["correct"] for g, q in zip(bs, HIDDEN) if q["answerable"])
    expect(ans_ok == 29, f"hidden answerable questions the baseline gets right: expected 29 of 30; got {ans_ok}")
    return (f"BM25 recall on the 9 dev questions: top 1 {f1}/9, top 3 {f3}/9; on the 30 hidden answerable: top 1 {h1}/30, top 3 {h3}/30;\n"
            f"the baseline (best sentence of the top page, never abstains) is right on {ans_ok} of 30 answerable hidden questions and on none of the 10 unanswerable")


# =============================================================================
# Milestone 3: answers with citations
# =============================================================================
def m3():
    hits = [(2.0, mod.Chunk("fernwood", 1, "T", "Revenue was 689 million euros.")), (1.0, mod.Chunk("harbourline", 4, "T", "The Ports division reported revenue."))]
    want = ("Answer the question using only the context below. Cite the page you used as [doc p.N]. If the context does not contain the answer, reply NOT_FOUND.\n\n"
            "Context:\n[fernwood p.1] Revenue was 689 million euros.\n[harbourline p.4] The Ports division reported revenue.\n\nQuestion: What was revenue?")
    got = mod.build_prompt("What was revenue?", hits)
    expect(got == want, f"build_prompt must produce exactly:\n{want}\ngot:\n{got}")
    expect(mod.parse_reply("Revenue was 5. [fernwood p.1]") == ("Revenue was 5.", [("fernwood", 1)]), f"got {mod.parse_reply('Revenue was 5. [fernwood p.1]')}")
    expect(mod.parse_reply("NOT_FOUND") == (None, []) and mod.parse_reply("  NOT_FOUND \n") == (None, []), "NOT_FOUND (even with spaces) means no answer: (None, [])")
    expect(mod.parse_reply("A [a p.2] and B [b_c p.10]") == ("A  and B", [("a", 2), ("b_c", 10)]), f"several citations, page numbers as ints, removed from the text; got {mod.parse_reply('A [a p.2] and B [b_c p.10]')}")
    expect(mod.parse_reply("No citation here.") == ("No citation here.", []), "text without a citation keeps its text and has no cites")
    nums = mod.numbers_in
    expect(nums("5,420 GWh, up 14.5% from 4910") == ["5420", "14.5", "4910"], f"commas removed, decimals kept; got {nums('5,420 GWh, up 14.5% from 4910')}")
    expect(nums("It was 21. Then 3.75% and 12 June 2023, id h36.") == ["21", "3.75", "12", "2023"], f"a sentence-final full stop is not part of a number, and 'h36' holds none; got {nums('It was 21. Then 3.75% and 12 June 2023, id h36.')}")
    expect(nums("1,215 trucks, 2022, up") == ["1215", "2022"] and nums("no digits") == [], "trailing commas do not matter; no digits, empty list")
    pool = [mod.Chunk("fernwood", 1, "T", "Revenue was 689 million euros, up 14%."), mod.Chunk("harbourline", 4, "T", "Ports revenue was 188.4 million pounds.")]
    cp = mod.citation_problems
    expect(cp("Revenue was 689 million euros.", [("fernwood", 1)], pool) == [], "number on the cited page: no problem")
    expect(cp("Revenue was 689 million euros.", [], pool) == ["no_citation", "number_not_on_cited_page: 689"], f"no cites: 'no_citation', and no page to hold the number; got {cp('Revenue was 689 million euros.', [], pool)}")
    expect(cp("Revenue was 999 million.", [("fernwood", 1)], pool) == ["number_not_on_cited_page: 999"], f"a figure that is on no cited page is flagged; got {cp('Revenue was 999 million.', [('fernwood', 1)], pool)}")
    expect(cp("Revenue was 689 million.", [("fernwood", 6)], pool) == ["cite_not_in_context: fernwood p.6", "number_not_on_cited_page: 689"],
           f"a citation to a page that was not in the prompt is flagged, and does not count as a page that holds the number; got {cp('Revenue was 689 million.', [('fernwood', 6)], pool)}")
    expect(cp("188.4 and 188.4 and 7", [("fernwood", 1), ("harbourline", 4)], pool) == ["number_not_on_cited_page: 7"], "all cited pages count together; each missing number is reported once")
    expect(cp("The answer is Leeds.", [("fernwood", 1)], pool) == [], "no numbers, nothing to tie")
    # the pipeline, with scripted replies
    q = "What was Fernwood Energy's installed capacity?"
    m = ScriptedModel(["Installed capacity reached 2,150 megawatts. [fernwood p.1]"])
    r = mod.answer_question(m, INDEX, q, k=3)
    call = m.calls[0]
    top = INDEX.search(q, 3)
    expect(call["messages"][-1]["content"] == mod.build_prompt(q, top) and call["system"] == mod.SYSTEM, "answer_question sends build_prompt(question, hits) as the user message, with SYSTEM as the system prompt")
    expect(r["answer"] == "Installed capacity reached 2,150 megawatts." and r["cites"] == [("fernwood", 1)] and r["abstained"] is False and r["reason"] is None and r["problems"] == [],
           f"answer, cites, no abstention, no problems; got {r}")
    expect(r["hits"] == [(c.doc, c.page) for _, c in top] and r["raw"] == "Installed capacity reached 2,150 megawatts. [fernwood p.1]" and r["question"] == q, "hits are the (doc, page) of all k results; raw is the reply text")
    r = mod.answer_question(ScriptedModel(["Installed capacity reached 9,999 megawatts. [fernwood p.1]"]), INDEX, q)
    expect(r["abstained"] is False and r["problems"] == ["number_not_on_cited_page: 9999"], f"a made-up figure is reported in problems (answer_question does not hide it); got {r['problems']}")
    r = mod.answer_question(ScriptedModel(["NOT_FOUND"]), INDEX, q)
    expect(r["abstained"] is True and r["answer"] is None and r["cites"] == [] and r["reason"] == "model_not_found" and r["problems"] == [], f"NOT_FOUND is an abstention with reason model_not_found; got {r}")
    r = mod.answer_question(ScriptedModel(["Capacity is large."]), INDEX, q)
    expect(r["problems"] == ["no_citation"], f"an answer with no citation is a problem; got {r['problems']}")
    # the stand-in reader on real questions
    answered = bad = 0
    for qq in DEV + HIDDEN:
        if not qq["answerable"]:
            continue
        rr = mod.answer_question(mod.ExtractiveReader(), INDEX, qq["question"])
        if rr["abstained"]:
            continue
        answered += 1
        expect(rr["problems"] == [], f"{qq['id']}: the stand-in reader quotes a real sentence and cites its page, so nothing should be flagged; got {rr['problems']} for {rr['raw']!r}")
        expect(set(rr["cites"]) <= set(rr["hits"]), f"{qq['id']}: cites must be among the hits")
        bad += 0
    expect(answered >= 33, f"the reader should answer at least 33 of the 39 answerable questions (dev and hidden); it answered {answered}")
    d = mod.answer_question(mod.ExtractiveReader(), INDEX, DEV[2]["question"])
    expect("1,215" in d["answer"] and d["cites"] == [("harbourline", 3)], f"dev question 3 ({DEV[2]['question']}): the reader quotes the sentence with 1,215 and cites harbourline p.3; got {d['answer']!r} {d['cites']}")
    return f"prompt format exact; citations parsed; numbers tie to the cited page (a made-up figure and a page outside the prompt are caught); the reader answered {answered} of 39 answerable dev and hidden questions with every figure tied"


# =============================================================================
# Milestone 4: abstention
# =============================================================================
def m4():
    rt = mod.required_terms
    expect(rt("What was Calder & Moss's net cash in 2024?") == ["calder", "moss", "2024"], f"got {rt('What was Calder & Moss' + chr(39) + 's net cash in 2024?')}")
    expect(rt("How many people did Harbourline employ?") == ["harbourline"], f"the first word (How) and ordinary lower-case words are not required; got {rt('How many people did Harbourline employ?')}")
    expect(rt("Who is the chair of Harbourline Freight?") == ["harbourline", "freight"], f"capitalised stop words (Who) are not required; got {rt('Who is the chair of Harbourline Freight?')}")
    expect(rt("What did Fernwood's Brightwater farm earn in 2023 and 2023?") == ["fernwood", "brightwater", "2023"], f"possessives are stripped and duplicates dropped; got {rt('What did Fernwood' + chr(39) + 's Brightwater farm earn in 2023 and 2023?')}")
    expect(rt("what is revenue?") == [] and rt("") == [], "nothing to require")
    expect(rt("How much did 12345 cost in 1999?") == ["1999"], "only four-digit numbers count")
    mt = mod.missing_terms
    c1, c2 = mod.Chunk("h", 1, "Harbourline Freight plc, Annual Report 2023", "Revenue rose."), mod.Chunk("f", 1, "Fernwood Energy Ltd", "Brightwater opened in May 2023.")
    expect(mt("What was Harbourline revenue in 2023?", [c1]) == [], "the company name is in the title, 2023 in the title: nothing missing")
    expect(mt("What was Harbourline revenue in 2024 in Scotland?", [c1]) == ["2024", "scotland"], f"missing terms keep question order; got {mt('What was Harbourline revenue in 2024 in Scotland?', [c1])}")
    expect(mt("What did Brightwater cost Harbourline?", [c1, c2]) == [], "terms may be found on any of the chunks")
    expect(mt("What did Harbourline pay?", [mod.Chunk("h", 1, "T", "Harbourlines pay.")]) == ["harbourline"], "a term must match a whole word: 'Harbourlines' is not 'Harbourline'")
    # the gate, with scripted replies
    R = mod.answer_or_abstain
    q = "What was Fernwood Energy's installed capacity?"
    r = R(ScriptedModel(["Installed capacity reached 2,150 megawatts. [fernwood p.1]"]), INDEX, q)
    expect(r["abstained"] is False and r["answer"] and r["cites"] == [("fernwood", 1)] and r["draft"] is None and r["reason"] is None, f"a grounded answer whose terms are on the cited page passes; got {r}")
    q = "What was Fernwood Energy's revenue in 2025?"
    r = R(ScriptedModel(["Revenue was 689 million euros, an increase of 14%. [fernwood p.1]"]), INDEX, q)
    expect(r["abstained"] is True and r["reason"] == "missing:2025" and r["answer"] is None and r["cites"] == [] and r["draft"] == "Revenue was 689 million euros, an increase of 14%.",
           f"the cited page never mentions 2025: abstain, reason 'missing:2025', keep the withheld answer as draft; got {r}")
    r = R(ScriptedModel(["Revenue was 999 million euros. [fernwood p.1]"]), INDEX, "What was Fernwood Energy's revenue?")
    expect(r["abstained"] is True and r["reason"] == "ungrounded" and r["draft"] == "Revenue was 999 million euros." and r["problems"] == ["number_not_on_cited_page: 999"], f"a figure that is not on the cited page: abstain as ungrounded; got {r}")
    r = R(ScriptedModel(["NOT_FOUND"]), INDEX, q)
    expect(r["abstained"] is True and r["reason"] == "model_not_found" and r["draft"] is None, f"the reader's own refusal is kept (draft None); got {r}")
    r = R(ScriptedModel(["Installed capacity reached 2,150 megawatts. [fernwood p.1]"]), INDEX, "What is the installed capacity of Calder & Moss Retail?")
    expect(r["abstained"] is True and r["reason"] == "missing:calder,moss,retail", f"an answer about the wrong company: all three words of the name are missing from the cited page's title and text; got {r['reason']}")
    # the gate against an over-eager reader: it must be your rules, not the reader, that catch these
    eager = mod.ExtractiveReader(min_overlap=1)
    caught = {}
    for qq in DEV + HIDDEN:
        if not qq["answerable"]:
            rr = R(eager, INDEX, qq["question"])
            if rr["abstained"] and rr["reason"].startswith("missing:"):
                caught[qq["id"]] = rr["reason"]
    want = {"d10": "missing:2024", "h31": "missing:2025", "h32": "missing:scotland", "h33": "missing:2021", "h37": "missing:calder,moss"}
    expect(caught == want, f"with a reader that almost always answers, your rule must catch exactly these unanswerable questions by missing terms:\n  expected {want}\n  got      {caught}")
    # and the whole system on the sets
    res, base, gs, bs = run_system(DEV, name="dev")
    unans = [g for g, q in zip(gs, DEV) if not q["answerable"]]
    expect(all(g["abstained"] for g in unans), f"all 3 unanswerable dev questions should be refused; got {[g['id'] for g in unans if not g['abstained']]}")
    res, base, gs, bs = run_system(HIDDEN)
    ua = [(g, q) for g, q in zip(gs, HIDDEN) if not q["answerable"]]
    right = sum(g["abstained"] for g, q in ua)
    fa = sum(g["abstained"] for g, q in zip(gs, HIDDEN) if q["answerable"])
    expect(right == 9, f"hidden: the system should refuse 9 of the 10 unanswerable questions (the 10th, 'dividend in 2022', is answered from the wrong year); got {right}")
    expect(fa == 5, f"hidden: the system should refuse 5 answerable questions (the stand-in reader needs two shared content words); got {fa}")
    return (f"your rules catch the 5 unanswerable questions with a missing year, place or company even when the reader would answer;\n"
            f"on the hidden set the system refuses {right} of 10 unanswerable questions and wrongly refuses {fa} of 30 answerable ones")


# =============================================================================
# Milestone 5: evaluation with intervals
# =============================================================================
def boot_oracle(values, reps, seed):
    rng = random.Random(seed)
    n = len(values)
    out = []
    for _ in range(reps):
        idx = [rng.randrange(n) for _ in range(n)]
        out.append(sum(values[i] for i in idx) / n)
    out.sort()
    return out[int(0.025 * reps)], out[int(0.975 * reps)]


def pboot_oracle(a, b, reps, seed):
    rng = random.Random(seed)
    n = len(a)
    out = []
    for _ in range(reps):
        idx = [rng.randrange(n) for _ in range(n)]
        out.append(sum(a[i] - b[i] for i in idx) / n)
    out.sort()
    return out[int(0.025 * reps)], out[int(0.975 * reps)]


def m5():
    nt = mod.normalise_text
    expect(nt("  Revenue of 6,840   and 1,234,567.5 ") == "revenue of 6840 and 1234567.5", f"lower case, number commas out, spaces collapsed; got {nt('  Revenue of 6,840   and 1,234,567.5 ')!r}")
    expect(nt("a, b") == "a, b", "commas between words stay")
    qa = {"id": "x", "question": "q", "answerable": True, "answer": "6,840", "pages": [["harbourline", 2]]}
    qu = {"id": "y", "question": "q", "answerable": False, "answer": None, "pages": []}

    def R(answer, cites, abstained=False):
        return {"answer": answer, "cites": cites, "abstained": abstained}
    g = mod.grade(qa, R("Headcount at year end was 6840, up.", [("harbourline", 2)]))
    expect(g == {"id": "x", "answerable": True, "abstained": False, "answer_ok": True, "cite_ok": True, "correct": True}, f"right figure, right page: correct; got {g}")
    g = mod.grade(qa, R("Headcount was 6,840.", [("harbourline", 1)]))
    expect(g["answer_ok"] is True and g["cite_ok"] is False and g["correct"] is False, f"right figure but the wrong page is NOT correct; got {g}")
    g = mod.grade(qa, R("Revenue was 412.6.", [("harbourline", 2)]))
    expect(g["answer_ok"] is False and g["cite_ok"] is True and g["correct"] is False, f"right page, wrong figure; got {g}")
    g = mod.grade(qa, R(None, [], True))
    expect(g["abstained"] is True and g["answer_ok"] is False and g["cite_ok"] is False and g["correct"] is False, f"refusing an answerable question is wrong; got {g}")
    g = mod.grade(qu, R(None, [], True))
    expect(g["correct"] is True and g["answerable"] is False, f"refusing an unanswerable question is right; got {g}")
    g = mod.grade(qu, R("Something, 1.", [("a", 1)]))
    expect(g["correct"] is False and g["answer_ok"] is False, f"answering an unanswerable question is wrong; got {g}")
    expect(mod.grade(qa, R("6840", [("fernwood", 1), ("harbourline", 2)]))["cite_ok"] is True, "one right page among the cites is enough")
    for s in seeds(range(1, 11)):
        rng = random.Random(s)
        vals = [rng.choice([0, 1]) for _ in range(rng.randint(5, 40))]
        reps = rng.choice([200, 500, 1000])
        got = mod.bootstrap_ci(vals, reps, s)
        expect(got == boot_oracle(vals, reps, s), f"seed {s}: bootstrap_ci({vals}, {reps}, {s}) should be {boot_oracle(vals, reps, s)} (one rng.randrange(n) per draw, n draws per repetition, percentile index int(p x reps)); got {got}")
        a = [rng.choice([0, 1]) for _ in vals]
        d, lo, hi = mod.paired_bootstrap(vals, a, reps, s)
        olo, ohi = pboot_oracle(vals, a, reps, s)
        expect(near(d, (sum(vals) - sum(a)) / len(vals)) and near(lo, olo) and near(hi, ohi), f"seed {s}: paired_bootstrap expected ({(sum(vals) - sum(a)) / len(vals)}, {olo}, {ohi}); got ({d}, {lo}, {hi})")
    lo, hi = mod.bootstrap_ci([1] * 20)
    expect((lo, hi) == (1.0, 1.0) and mod.bootstrap_ci([0, 0, 0]) == (0.0, 0.0), "no variation, no spread")
    for bad in ([], ):
        try:
            mod.bootstrap_ci(bad)
        except ValueError:
            pass
        else:
            raise AssertionError("an empty list should raise ValueError")
    for a, b in (([], []), ([1], [1, 0])):
        try:
            mod.paired_bootstrap(a, b)
        except ValueError:
            pass
        else:
            raise AssertionError(f"paired_bootstrap({a}, {b}) should raise ValueError")
    expect(mod.paired_bootstrap([1, 0, 1], [1, 0, 1])[0] == 0.0 and mod.paired_bootstrap([1, 1, 1, 1], [0, 0, 0, 0])[1:] == (1.0, 1.0), "identical lists differ by 0; always-better lists by 1")
    # a hand-built report
    mk = lambda i, ans, ok: {"id": f"q{i}", "answerable": ans, "abstained": False, "answer_ok": ok, "cite_ok": ok, "correct": ok}
    sys_g = [mk(0, True, True), mk(1, True, True), mk(2, True, False), mk(3, False, True), mk(4, False, False)]
    sys_g[3]["abstained"] = True
    sys_g[2]["abstained"] = True
    base_g = [mk(0, True, True), mk(1, True, False), mk(2, True, True), mk(3, False, False), mk(4, False, False)]
    rep = mod.make_report(sys_g, base_g)
    want = dict(n=5, correct=3, answerable_n=3, answerable_correct=2, unanswerable_n=2, abstained_right=1, false_abstain=1, baseline_correct=2)
    for k, v in want.items():
        expect(rep[k] == v, f"hand-built report: {k} should be {v}; got {rep[k]}")
    expect(near(rep["accuracy"], 0.6) and near(rep["baseline_accuracy"], 0.4), "accuracy 3/5 and baseline 2/5")
    expect(all(near(a, b) for a, b in zip(rep["wilson"], mod.wilson(3, 5))), f"wilson is wilson(correct, n); got {rep['wilson']}")
    sv, bv = [1, 1, 0, 1, 0], [1, 0, 1, 0, 0]
    expect(rep["boot"] == boot_oracle(sv, 2000, 7), f"boot is bootstrap_ci of the 0/1 correct values with default settings; expected {boot_oracle(sv, 2000, 7)}, got {rep['boot']}")
    exp = (sum(sv) / 5 - sum(bv) / 5,) + pboot_oracle(sv, bv, 2000, 7)
    expect((rep["diff"], rep["diff_lo"], rep["diff_hi"]) == exp, f"diff, diff_lo, diff_hi from paired_bootstrap (system minus baseline); expected {exp}")
    res, base, gs, bs = run_system(HIDDEN)
    rep = mod.make_report(gs, bs)
    expect(rep["n"] == 40 and rep["correct"] == 34 and rep["baseline_correct"] == 29,
           f"on the hidden set the reference system is right on 34 of 40 and the baseline on 29; you got {rep['correct']} and {rep['baseline_correct']}. If these differ, an earlier milestone differs from the reference: run milestones 2 to 4 first")
    expect(rep["answerable_correct"] == 25 and rep["abstained_right"] == 9 and rep["false_abstain"] == 5, f"25 of 30 answerable correct, 9 of 10 refusals right, 5 false refusals; got {rep['answerable_correct']}, {rep['abstained_right']}, {rep['false_abstain']}")
    w = rep["wilson"]
    return (f"system {rep['correct']}/{rep['n']} = {rep['accuracy']:.1%}  Wilson {w[0]:.1%} to {w[1]:.1%}  bootstrap {rep['boot'][0]:.1%} to {rep['boot'][1]:.1%}\n"
            f"baseline {rep['baseline_correct']}/{rep['n']} = {rep['baseline_accuracy']:.1%};  paired difference {rep['diff']:+.1%} (95% bootstrap {rep['diff_lo']:+.1%} to {rep['diff_hi']:+.1%})")


# =============================================================================
# Milestone 6: error analysis and the memo
# =============================================================================
def m6():
    ff = mod.first_failure
    qa = {"answerable": True, "pages": [["harbourline", 2]]}
    qu = {"answerable": False, "pages": []}

    def G(**kw):
        d = {"correct": False, "abstained": False, "answer_ok": False, "cite_ok": False}
        d.update(kw)
        return d
    hit = [("harbourline", 2)]
    miss = [("harbourline", 1), ("fernwood", 1)]
    cases = [
        (qa, G(correct=True, answer_ok=True, cite_ok=True), {"hits": hit}, None),
        (qa, G(abstained=True), {"hits": hit}, "false_abstain"),
        (qa, G(abstained=True), {"hits": miss}, "false_abstain"),
        (qa, G(), {"hits": miss}, "retrieval_miss"),
        (qa, G(cite_ok=True), {"hits": hit}, "wrong_sentence_same_page"),
        (qa, G(), {"hits": hit}, "wrong_page_cited"),
        (qa, G(answer_ok=True), {"hits": hit}, "citation_mismatch"),
        (qu, G(abstained=True, correct=True), {"hits": hit}, None),
        (qu, G(), {"hits": hit}, "should_have_abstained"),
    ]
    for i, (q, g, r, want) in enumerate(cases):
        got = ff(q, g, r)
        expect(got == want, f"first_failure case {i}: {q['answerable'] and 'answerable' or 'unanswerable'}, graded {g}, hits {r['hits']}: expected {want!r}; got {got!r}")
    et = mod.error_table
    expect(et(["b", None, "a", "b", "c", "a", None]) == [("a", 2), ("b", 2), ("c", 1)], f"count, ignore None, sort by count descending then name; got {et(['b', None, 'a', 'b', 'c', 'a', None])}")
    expect(et([]) == [] and et([None]) == [], "no failures, no rows")
    res, base, gs, bs = run_system(HIDDEN)
    cats = [ff(q, g, r) for q, g, r in zip(HIDDEN, gs, res)]
    errors = et(cats)
    expect(errors == [("false_abstain", 5), ("should_have_abstained", 1)], f"hidden failures by first cause should be [('false_abstain', 5), ('should_have_abstained', 1)]; got {errors}")
    rep = mod.make_report(gs, bs)
    bad_q = next(q for q, c in zip(HIDDEN, cats) if c == "should_have_abstained")
    bad_r = next(r for r, c in zip(res, cats) if c == "should_have_abstained")
    example = (bad_q["id"], bad_r["hits"][0], "should_have_abstained")
    memo = mod.render_memo(rep, errors, example)
    for head in ("# Take-home memo", "## Result", "## Baseline", "## Error analysis", "## Limitations", "## Next steps"):
        expect(head in memo, f"the memo must contain a '{head}' heading")
    expect("34 of 40" in memo and "85.0%" in memo and "29 of 40" in memo and "false_abstain 5" in memo and "should_have_abstained 1" in memo, f"memo content: the headline numbers are missing:\n{memo}")
    problems = mod.check_memo(memo, rep, errors, CORPUS)
    expect(problems == [], f"your render_memo output should pass your check_memo; problems: {problems}\n{memo}")
    cm = lambda m, r=rep, e=errors: mod.check_memo(m, r, e, CORPUS)
    t = memo.replace("34 of 40", "37 of 40")
    expect(cm(t) == ["untied number: 37"], f"a headline count that is not in the report must be flagged; got {cm(t)}")
    t = memo.replace("## Limitations", "## Caveats")
    got = cm(t)
    expect(got[0] == "missing section: Limitations", f"a missing section is reported first; got {got}")
    t = memo.replace("false_abstain 5", "false_abstain 4")
    expect(cm(t) == ["missing error row: false_abstain 5", "untied number: 4"], f"a wrong error count: the right row is missing and the 4 ties to nothing; got {cm(t)}")
    t = memo.replace("## Limitations", "Harbourline reported revenue of 412.6 million pounds [harbourline p.1].\n\n## Limitations")
    expect(cm(t) == [], f"a line with a citation is checked against the cited page only; 412.6 is on harbourline p.1; got {cm(t)}")
    t = memo.replace("## Limitations", "Harbourline reported revenue of 412.6 million pounds [harbourline p.2].\n\n## Limitations")
    expect(cm(t) == ["number not on cited page: 412.6 [harbourline p.2]"], f"412.6 is not on page 2; got {cm(t)}")
    t = memo.replace("## Limitations", "Harbourline reported revenue of 412.6 million pounds [harbourline p.9].\n\n## Limitations")
    expect(cm(t) == ["unknown page: harbourline p.9"], f"there is no page 9; got {cm(t)}")
    start = memo.index("## Limitations")
    end = memo.index("## Next steps")
    t = memo[:start] + "## Limitations\nSmall set.\n\n" + memo[end:]
    expect(cm(t) == ["limitations too thin"], f"fewer than 25 words of limitations; got {cm(t)}")
    short = [("false_abstain", 5)]
    memo2 = mod.render_memo(rep, short, example)
    expect(mod.check_memo(memo2, rep, short, CORPUS) == ["error counts sum to 5, report has 6 failures"], f"the failure table must account for every failure; got {mod.check_memo(memo2, rep, short, CORPUS)}")
    expect(mod.check_memo("# Memo\n\n## Result\nFine.", rep, errors, CORPUS)[:4] == ["missing section: Baseline", "missing section: Error analysis", "missing section: Limitations", "missing section: Next steps"], "missing sections are listed in MEMO_SECTIONS order")
    for s in seeds(range(1, 11)):
        rng = random.Random(s)
        n = rng.randint(8, 60)
        mkg = lambda: [{"id": f"q{i}", "answerable": i % 4 != 0, "abstained": False, "answer_ok": False, "cite_ok": False, "correct": rng.random() < 0.7} for i in range(n)]
        g1, g2 = mkg(), mkg()
        for g in g1 + g2:
            g["abstained"] = (not g["answerable"]) == g["correct"]
        r = mod.make_report(g1, g2)
        cats = [rng.choice(["false_abstain", "retrieval_miss", "wrong_page_cited"]) for g in g1 if not g["correct"]]
        e = et(cats)
        m = mod.render_memo(r, e, ("q1", ("fernwood", 3), "retrieval_miss"))
        p = mod.check_memo(m, r, e, CORPUS)
        expect(p == [], f"seed {s}: a memo rendered from a report must pass the checker; problems {p}\n{m}")
    return (f"first failures on the hidden set: {', '.join(f'{c} {k}' for c, k in errors)};\n"
            f"the rendered memo ties every number to the report or to a page ({len(memo.split())} words), and each planted error (wrong count, wrong page, missing section) is caught")


MILESTONES = [
    (1, "Milestone 1: the requirements restatement, checked mechanically", m1),
    (2, "Milestone 2: a baseline you can beat (BM25 over pages)", m2),
    (3, "Milestone 3: answers with page citations that tie out", m3),
    (4, "Milestone 4: knowing when not to answer", m4),
    (5, "Milestone 5: evaluation with intervals", m5),
    (6, "Milestone 6: first failures and a memo whose numbers tie", m6),
]

if __name__ == "__main__":
    t0 = time.time()
    print(f"Lab 4 checks against {target}.py\n")
    for n, name, fn in MILESTONES:
        check(n, name, fn)
    print(f"\n{sum(results)}/{len(results)} milestones passing  ({time.time() - t0:.1f} s)")
    sys.exit(0 if all(results) else 1)
