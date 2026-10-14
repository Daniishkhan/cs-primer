"""Lab 4: a take-home, end to end.

The brief (a typical applied-AI take-home, with a 5-hour clock in real life): "Build a small
question-answering system over three annual reports. Every answer must say which page it came
from. Say 'I cannot tell from these reports' when the reports do not contain the answer. Tell
us how good it is, and what you would do next." The corpus is three short, invented reports
(corpus.json, 18 pages in all). Twelve questions with their answers and pages are given to
you (dev_questions.json). A reviewer holds forty more (hidden_tests.json), and check.py is
that reviewer.

What you build is what chapter 18 lists as the deliverables, in miniature: a requirements
restatement that passes a mechanical review, a baseline retrieval system, an answer with page
citations whose numbers tie to the cited page, an abstention rule, an evaluation with
intervals against the baseline, and an error analysis and memo whose every number you can
trace.

What is GIVEN: the corpus loader, text helpers, a stand-in reader (a deterministic 'model'),
the section parser and the restatement template. What YOU write is marked TODO:

    1  check_restatement
    2  BM25Index (idf, score, search), recall_at_k, baseline_answer
    3  build_prompt, parse_reply, numbers_in, citation_problems, answer_question
    4  required_terms, missing_terms, answer_or_abstain
    5  normalise_text, grade, bootstrap_ci, paired_bootstrap, make_report
    6  first_failure, error_table, render_memo, check_memo

`python3 check.py` runs the milestones; the lab page explains each one.
Every company, person and figure in the corpus is invented.
"""
import json
import math
import os
import random
import re
from collections import Counter, namedtuple

from llm import Model, Response, message_text, text as text_block, text_of

HERE = os.path.dirname(os.path.abspath(__file__))

# =============================================================================
# GIVEN: data, text helpers and the stand-in reader
# =============================================================================
Chunk = namedtuple("Chunk", "doc page title text")      # one page of one report

STOPWORDS = set("""a an the of in on at by for to and or is are was were be been did do does what which who whom whose when
where how many much that this with from as it its their his her per than into during about s""".split())

SYSTEM = "You answer questions about annual reports using only the context you are given."
MIN_OVERLAP = 2             # the stand-in reader says NOT_FOUND below this many shared content words

REQUIRED_HEADINGS = ["Goal", "Inputs", "Assumptions", "Questions for the customer", "Out of scope", "Success measures"]
MEMO_SECTIONS = ["Result", "Baseline", "Error analysis", "Limitations", "Next steps"]

TEMPLATE = """# Requirements restatement

## Goal
TODO: one or two sentences in your own words: who asks what, and what a good answer looks like.

## Inputs
TODO: what you were given and what you can see about it.

## Assumptions
- TODO: a decision you made because the brief was silent (at least three bullets)

## Questions for the customer
- TODO: a question you would ask if you could, ending with a question mark (at least three)

## Out of scope
TODO: what you will not build in the time, and why.

## Success measures
- TODO: how you will judge it, with numbers (for example a share of questions, and an interval)
"""


def load_corpus():
    """GIVEN. The reports: [{doc, title, pages: [{page, text}]}], three documents of six pages."""
    with open(os.path.join(HERE, "corpus.json"), encoding="utf-8") as f:
        return json.load(f)


def chunks_of(corpus):
    """GIVEN. One Chunk per page, in document order."""
    return [Chunk(d["doc"], p["page"], d["title"], p["text"]) for d in corpus for p in d["pages"]]


def context(chunk):
    """GIVEN. The text a search index sees for a page: the report's title, then the page."""
    return chunk.title + ". " + chunk.text


def load_dev():
    """GIVEN. The twelve visible questions: id, question, answerable, answer, pages [[doc, page]]."""
    with open(os.path.join(HERE, "dev_questions.json"), encoding="utf-8") as f:
        return json.load(f)


def stem(word):
    """GIVEN. A very light stemmer: drop 'ing', 'ed', 'es' or 's' from words longer than 4 letters."""
    if len(word) > 4 and not word[0].isdigit():
        for suffix in ("ing", "ed", "es", "s"):
            if word.endswith(suffix) and len(word) - len(suffix) >= 3:
                return word[:-len(suffix)]
    return word


def tokenize(text):
    """GIVEN. Lower-case, keep numbers such as 6,840 and 412.6 whole, drop stop words, stem.
    tokenize("How many trucks did Harbourline run?") -> ['truck', 'harbourline', 'run']"""
    words = re.findall(r"[a-z0-9]+(?:[.,][0-9]+)*", text.lower())
    return [stem(w) for w in words if w not in STOPWORDS]


def split_sentences(text):
    """GIVEN. Sentences of a page (a full stop followed by a space ends one; 412.6 does not)."""
    return re.split(r"(?<=[.!?])\s+", text.strip())


def entity_words():
    """GIVEN. The words of the report titles (company names and 'annual report'). A question names
    its company, but so does only the first page of each report, so these words are ignored when
    choosing a sentence: they say which report, not which fact."""
    return {t for d in load_corpus() for t in tokenize(d["title"])}


ENTITY_WORDS = entity_words()


def best_sentence(question, text):
    """GIVEN. (score, sentence) for the sentence of `text` sharing the most distinct content words
    with `question` (ENTITY_WORDS excluded); the first such sentence wins a tie; (0.0, "") if none
    share a word."""
    q = set(tokenize(question)) - ENTITY_WORDS
    best = (0.0, "")
    for sentence in split_sentences(text):
        score = float(len(q & set(tokenize(sentence))))
        if score > best[0]:
            best = (score, sentence)
    return best


def sections(text):
    """GIVEN. Split markdown into {heading (lower case): [non-blank body lines]} by '## ' headings.
    Text before the first '## ' heading is ignored; the first of two equal headings wins."""
    out, current = {}, None
    for line in text.split("\n"):
        m = re.match(r"^##\s+(.*?)\s*$", line)
        if m:
            current = m.group(1).casefold()
            out.setdefault(current, [])
        elif current is not None and line.strip():
            out[current].append(line.strip())
    return out


class ExtractiveReader(Model):
    """GIVEN. A deterministic stand-in for a language model that reads a prompt in the format
    produced by build_prompt (milestone 3): context lines '[doc p.N] page text', a blank line and
    'Question: ...'. It finds the context sentence sharing the most content words with the question
    and replies '<sentence> [doc p.N]'. If the best sentence shares fewer than min_overlap words (default
    MIN_OVERLAP) it replies NOT_FOUND. It never invents a number, but it can pick the wrong sentence, the wrong
    year or the wrong company, as a real model can."""
    name = "extractive-reader"

    def __init__(self, min_overlap=MIN_OVERLAP):
        self.min_overlap = min_overlap
        self.calls = []

    def complete(self, messages, *, system=None, tools=None, max_tokens=1024, temperature=0.0):
        prompt = message_text(messages[-1])
        self.calls.append({"messages": [dict(m) for m in messages], "system": system})
        q = re.search(r"^Question: (.*)$", prompt, re.M)
        question = q.group(1) if q else ""
        best = (0.0, "", "", 0)
        for doc, page, body in re.findall(r"^\[([a-z0-9_]+) p\.(\d+)\] (.*)$", prompt, re.M):
            score, sentence = best_sentence(question, body)
            if score > best[0]:
                best = (score, sentence, doc, int(page))
        reply = "NOT_FOUND" if best[0] < self.min_overlap else f"{best[1]} [{best[2]} p.{best[3]}]"
        return Response(content=[text_block(reply)], model=self.name,
                        usage={"input_tokens": len(prompt) // 4, "output_tokens": len(reply) // 4})


# =============================================================================
# Milestone 1: the requirements restatement, checked mechanically
# =============================================================================
def check_restatement(text):
    """Problems found in a requirements restatement (an empty list means it passes).

    `text` is markdown with '## ' headings (use sections()). For each heading in REQUIRED_HEADINGS,
    in that order (headings are matched ignoring case), report in this order and skip the rest of that
    heading's checks after the first problem marked (stop):
      'missing heading: <Heading>'                           (stop)
      'empty section: <Heading>'    fewer than 8 words in its body (bullet markers do not count)  (stop)
      Assumptions:                  'too few assumptions: <n>'   fewer than 3 bullet lines ('- ' or '* ')
      Questions for the customer:   'too few questions: <n>' for fewer than 3 bullets, then for each bullet
                                    that does not end with '?': 'question without ?: <the bullet text>'
      Success measures:             'success measures need a number' if no digit appears in the body
    After the headings, two whole-document checks: 'placeholder left: TODO' if the word TODO appears
    anywhere, and 'too long: <n> words' if the whole text has more than 350 words (one page).
    <Heading> is spelled as in REQUIRED_HEADINGS."""
    sec = sections(text)
    problems = []

    def words(lines):
        return [w for line in lines for w in re.sub(r"^[-*]\s+", "", line).split()]

    for h in REQUIRED_HEADINGS:
        body = sec.get(h.casefold())
        if body is None:
            problems.append(f"missing heading: {h}")
            continue
        if len(words(body)) < 8:
            problems.append(f"empty section: {h}")
            continue
        bullets = [re.sub(r"^[-*]\s+", "", ln) for ln in body if re.match(r"^[-*]\s+", ln)]
        if h == "Assumptions" and len(bullets) < 3:
            problems.append(f"too few assumptions: {len(bullets)}")
        if h == "Questions for the customer":
            if len(bullets) < 3:
                problems.append(f"too few questions: {len(bullets)}")
            problems += [f"question without ?: {b}" for b in bullets if not b.rstrip().endswith("?")]
        if h == "Success measures" and not re.search(r"\d", " ".join(body)):
            problems.append("success measures need a number")
    if "TODO" in text:
        problems.append("placeholder left: TODO")
    n = len(text.split())
    if n > 350:
        problems.append(f"too long: {n} words")
    return problems


# =============================================================================
# Milestone 2: a baseline you can beat
# =============================================================================
class BM25Index:
    """BM25 over page chunks, each represented by tokenize(context(chunk)).
    Parameters k1 = 1.2 and b = 0.75. For a query, each DISTINCT query term t scores
        idf(t) * tf * (k1 + 1) / (tf + k1 * (1 - b + b * dl / avgdl))
    where tf is the term's count in the page, dl the page's length in tokens and avgdl the mean
    length over all pages, and idf(t) = ln(1 + (N - df + 0.5) / (df + 0.5)) with N pages of which df
    contain t. A page's score is the sum over the query's distinct terms."""

    def __init__(self, chunks, k1=1.2, b=0.75):
        self.chunks, self.k1, self.b = list(chunks), k1, b
        self.tokens = [tokenize(context(c)) for c in self.chunks]
        self.tf = [Counter(t) for t in self.tokens]
        self.avgdl = sum(len(t) for t in self.tokens) / len(self.tokens)
        self.df = Counter(term for tf in self.tf for term in tf)

    def idf(self, term):
        """ln(1 + (N - df + 0.5) / (df + 0.5)); a term in no page has df = 0."""
        n, df = len(self.chunks), self.df.get(term, 0)
        return math.log(1 + (n - df + 0.5) / (df + 0.5))

    def score(self, query, i):
        """BM25 score of page number `i` (an index into self.chunks) for the query string."""
        tf, dl = self.tf[i], len(self.tokens[i])
        total = 0.0
        for term in set(tokenize(query)):
            f = tf.get(term, 0)
            if f:
                total += self.idf(term) * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
        return total

    def search(self, query, k=3):
        """The top `k` pages as [(score, Chunk)], best first, only pages with score > 0.
        Ties are broken by (doc, page) in ascending order."""
        scored = [(self.score(query, i), c) for i, c in enumerate(self.chunks)]
        scored = [(s, c) for s, c in scored if s > 0]
        scored.sort(key=lambda sc: (-sc[0], sc[1].doc, sc[1].page))
        return scored[:k]


def recall_at_k(questions, index, k):
    """(found, total): of the ANSWERABLE questions, how many have their gold page among the top k
    results of index.search(question['question'], k). A question's gold pages are [[doc, page]]."""
    found = total = 0
    for q in questions:
        if not q["answerable"]:
            continue
        total += 1
        got = {(c.doc, c.page) for _, c in index.search(q["question"], k)}
        found += any(tuple(p) in got for p in q["pages"])
    return found, total


def baseline_answer(index, question):
    """The baseline system: no model, no abstention. Take the top-ranked page (k = 1), answer with
    its best sentence (best_sentence) and cite that page. Returns the result dict used everywhere:
      {"question", "answer", "cites": [(doc, page)], "hits": [(doc, page)], "abstained": False,
       "reason": None, "problems": []}
    If the search finds nothing at all, answer None and abstain with reason "no_hits"."""
    hits = index.search(question, 1)
    if not hits:
        return {"question": question, "answer": None, "cites": [], "hits": [], "abstained": True, "reason": "no_hits", "problems": []}
    chunk = hits[0][1]
    _, sentence = best_sentence(question, chunk.text)
    return {"question": question, "answer": sentence, "cites": [(chunk.doc, chunk.page)], "hits": [(chunk.doc, chunk.page)],
            "abstained": False, "reason": None, "problems": []}


# =============================================================================
# Milestone 3: an answer that cites its page, and a check that the numbers tie
# =============================================================================
def build_prompt(question, hits):
    """The prompt for the reader. `hits` is the list of (score, Chunk) from search. Exactly:

    Answer the question using only the context below. Cite the page you used as [doc p.N]. If the context does not contain the answer, reply NOT_FOUND.<newline>
    <newline>
    Context:<newline>
    one line per hit, in rank order:  [doc p.N] page text<newline>
    <newline>
    Question: <question>

    (no trailing newline). Use chunk.text, not the title."""
    lines = [f"[{c.doc} p.{c.page}] {c.text}" for _, c in hits]
    return ("Answer the question using only the context below. Cite the page you used as [doc p.N]. "
            "If the context does not contain the answer, reply NOT_FOUND.\n\nContext:\n"
            + "\n".join(lines) + f"\n\nQuestion: {question}")


CITE_RE = re.compile(r"\[([a-z0-9_]+) p\.(\d+)\]")


def parse_reply(reply):
    """(answer, cites) from a reader's reply. Citations look like [doc p.N]; they are removed from
    the answer text, which is then stripped, and returned as [(doc, N)] with N an int, in order.
    A reply whose stripped text is exactly NOT_FOUND gives (None, []).
    parse_reply("Revenue was 5. [fernwood p.1]") -> ("Revenue was 5.", [("fernwood", 1)])"""
    if reply.strip() == "NOT_FOUND":
        return None, []
    cites = [(d, int(p)) for d, p in CITE_RE.findall(reply)]
    return CITE_RE.sub("", reply).strip(), cites


# --solution-only-begin
NUM_RE = re.compile(r"(?<![A-Za-z0-9])\d[\d,]*(?:\.\d+)?")


# --solution-only-end


def numbers_in(text):
    """Every number in `text`, as a string without thousands commas, in order of appearance.
    A number is digits with optional commas and an optional decimal part, not glued to a letter or
    another digit on the left (so 'h36' holds none). numbers_in("5,420 GWh, up 14.5% from 4910") -> ['5420', '14.5', '4910'];
    a full stop that ends a sentence is not part of the number: numbers_in("It was 21.") -> ['21']."""
    return [m.group().replace(",", "") for m in NUM_RE.finditer(text)]


def citation_problems(answer, cites, chunks):
    """Reasons an answer cannot be trusted, as a list of strings (empty means it ties out).
    `chunks` are the pages that were put in the prompt. In this order:
      'no_citation'                                  if cites is empty
      'cite_not_in_context: <doc> p.<N>'             for each cite that is not one of `chunks`
      'number_not_on_cited_page: <n>'                for each number of the answer (numbers_in) that appears
                                                     on none of the cited pages' text (only cites that ARE in context count)
    A number is checked once however often it appears in the answer."""
    problems = []
    if not cites:
        problems.append("no_citation")
    by_key = {(c.doc, c.page): c for c in chunks}
    for doc, page in cites:
        if (doc, page) not in by_key:
            problems.append(f"cite_not_in_context: {doc} p.{page}")
    on_pages = set()
    for key in cites:
        if key in by_key:
            on_pages.update(numbers_in(by_key[key].text))
    seen = set()
    for n in numbers_in(answer or ""):
        if n not in on_pages and n not in seen:
            problems.append(f"number_not_on_cited_page: {n}")
        seen.add(n)
    return problems


def answer_question(model, index, question, k=3):
    """Retrieve, ask the reader, parse, check. Steps: hits = index.search(question, k);
    reply = model.complete([{"role": "user", "content": build_prompt(question, hits)}], system=SYSTEM);
    (answer, cites) = parse_reply(text_of(reply)). Returns the result dict:
      {"question", "answer", "cites", "hits": [(doc, page)] of all hits, "abstained": answer is None,
       "reason": "model_not_found" if abstained else None,
       "problems": citation_problems(answer, cites, chunks of the hits) (an abstention has none),
       "raw": the reply text}"""
    hits = index.search(question, k)
    resp = model.complete([{"role": "user", "content": build_prompt(question, hits)}], system=SYSTEM)
    raw = text_of(resp)
    answer, cites = parse_reply(raw)
    problems = citation_problems(answer, cites, [c for _, c in hits]) if answer is not None else []
    return {"question": question, "answer": answer, "cites": cites, "hits": [(c.doc, c.page) for _, c in hits],
            "abstained": answer is None, "reason": "model_not_found" if answer is None else None,
            "problems": problems, "raw": raw}


# =============================================================================
# Milestone 4: knowing when not to answer
# =============================================================================
CAPS_STOP = {"What", "How", "Which", "Who", "When", "Where", "Why", "Does", "Did", "Is", "Are", "Was", "Were", "The", "In", "On", "By", "For", "Of", "A", "An"}


def required_terms(question):
    """The things a question names that the source must contain, lower-cased, without duplicates,
    in order of first appearance: every word beginning with a capital letter that is not the first
    word of the question and not in CAPS_STOP, and every four-digit number. Words are runs of
    letters (an apostrophe plus s, as in Harbourline's, is dropped); '&' is ignored.
    required_terms("What was Calder & Moss's net cash in 2024?") -> ['calder', 'moss', '2024']"""
    seen = []
    for i, m in enumerate(re.finditer(r"[A-Za-z]+(?:['’][A-Za-z]+)?|\b\d{4}\b", question)):
        w = re.sub(r"['’]s$", "", m.group())
        if w.isdigit():
            term = w
        elif i > 0 and w[0].isupper() and w not in CAPS_STOP:
            term = w.lower()
        else:
            continue
        if term not in seen:
            seen.append(term)
    return seen


def missing_terms(question, chunks):
    """The required_terms of `question` that occur in none of the `chunks` (use tokens of
    context(chunk), lower-cased, without stemming; a term must match a whole word). Same order."""
    have = set()
    for c in chunks:
        have.update(re.findall(r"[a-z0-9]+", context(c).lower()))
    return [t for t in required_terms(question) if t not in have]


def answer_or_abstain(model, index, question, k=3):
    """The full system. Start from answer_question. Then, if it did not already abstain:
      1. if it has problems -> abstain with reason "ungrounded";
      2. else take the chunks it cites; if missing_terms(question, those chunks) is non-empty ->
         abstain with reason "missing:" + the terms joined by ",".
    An abstention returns the same dict with "answer": None, "cites": [], "abstained": True, the
    reason set, and a new key "draft" holding the answer that was withheld (None if the reader had
    none). A non-abstention has "draft": None."""
    res = answer_question(model, index, question, k)
    res["draft"] = None
    if res["abstained"]:
        return res
    reason = None
    if res["problems"]:
        reason = "ungrounded"
    else:
        by_key = {(c.doc, c.page): c for c in index.chunks}
        miss = missing_terms(question, [by_key[key] for key in res["cites"]])
        if miss:
            reason = "missing:" + ",".join(miss)
    if reason:
        res.update(draft=res["answer"], answer=None, cites=[], abstained=True, reason=reason)
    return res


# =============================================================================
# Milestone 5: the evaluation, with intervals
# =============================================================================
def wilson(k, n, z=1.96):
    """GIVEN. Wilson 95% interval (lo, hi) for k of n (as in Lab 1)."""
    if n == 0:
        return 0.0, 1.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


def normalise_text(s):
    """Lower case, thousands commas inside numbers removed (6,840 -> 6840), runs of whitespace
    collapsed to one space, stripped."""
    s = re.sub(r"(?<=\d),(?=\d)", "", s.lower())
    return " ".join(s.split())


def grade(q, result):
    """Grade one result against its question. Returns a dict:
      {"id", "answerable", "abstained", "answer_ok", "cite_ok", "correct"}
    answer_ok: the gold answer (normalise_text) occurs inside the normalised answer text (False if
               there is no answer or the question is unanswerable).
    cite_ok:   at least one cited (doc, page) is one of the gold pages (False if none is cited).
    correct:   for an answerable question, not abstained and answer_ok and cite_ok;
               for an unanswerable question, abstained."""
    answerable = q["answerable"]
    abstained = bool(result["abstained"])
    answer_ok = bool(answerable and result["answer"] and normalise_text(q["answer"]) in normalise_text(result["answer"]))
    gold = {tuple(p) for p in q["pages"]}
    cite_ok = any(tuple(c) in gold for c in result["cites"])
    correct = (not abstained and answer_ok and cite_ok) if answerable else abstained
    return {"id": q["id"], "answerable": answerable, "abstained": abstained,
            "answer_ok": answer_ok, "cite_ok": cite_ok, "correct": correct}


def bootstrap_ci(values, reps=2000, seed=7):
    """95% percentile bootstrap interval (lo, hi) for the mean of `values` (numbers or booleans).
    rng = random.Random(seed); for each of `reps` repetitions draw n = len(values) indices with
    rng.randrange(n), one call per draw, and take the mean of those values. Sort the means; lo is
    means[int(0.025 * reps)] and hi is means[int(0.975 * reps)]. Empty input raises ValueError."""
    n = len(values)
    if n == 0:
        raise ValueError("no values")
    rng = random.Random(seed)
    means = []
    for _ in range(reps):
        means.append(sum(values[rng.randrange(n)] for _ in range(n)) / n)
    means.sort()
    return means[int(0.025 * reps)], means[int(0.975 * reps)]


def paired_bootstrap(a, b, reps=2000, seed=7):
    """(diff, lo, hi): the mean of a minus the mean of b on the full sample, and the 95% percentile
    bootstrap interval for that difference. a and b are parallel lists scored on the SAME items.
    rng = random.Random(seed); each repetition draws n indices with rng.randrange(n), one call per
    draw, and uses the SAME indices for both lists: the repetition's difference is
    sum(a[i] - b[i] for the drawn i) / n. Sort; lo = diffs[int(0.025 * reps)], hi = diffs[int(0.975 * reps)].
    Unequal lengths or empty lists raise ValueError."""
    n = len(a)
    if n == 0 or n != len(b):
        raise ValueError("a and b must be non-empty and the same length")
    rng = random.Random(seed)
    diffs = []
    for _ in range(reps):
        idx = [rng.randrange(n) for _ in range(n)]
        diffs.append(sum(a[i] - b[i] for i in idx) / n)
    diffs.sort()
    return sum(a) / n - sum(b) / n, diffs[int(0.025 * reps)], diffs[int(0.975 * reps)]


def make_report(graded, base_graded):
    """The numbers of the evaluation, from the graded items of the system and of the baseline
    (parallel lists from grade(), same questions in the same order). Returns:
      n, correct, accuracy                    over all questions
      wilson: (lo, hi)                        wilson(correct, n)
      boot: (lo, hi)                          bootstrap_ci of the 0/1 'correct' values (default reps and seed)
      answerable_n, answerable_correct        questions with a gold answer, and how many were correct
      unanswerable_n, abstained_right         questions with no answer, and how many were abstained on
      false_abstain                           answerable questions the system abstained on
      baseline_correct, baseline_accuracy
      diff, diff_lo, diff_hi                  paired_bootstrap(system, baseline) on the 0/1 'correct' values."""
    sys_ok = [int(g["correct"]) for g in graded]
    base_ok = [int(g["correct"]) for g in base_graded]
    n, correct = len(graded), sum(sys_ok)
    diff, dlo, dhi = paired_bootstrap(sys_ok, base_ok)
    return {
        "n": n, "correct": correct, "accuracy": correct / n,
        "wilson": wilson(correct, n), "boot": bootstrap_ci(sys_ok),
        "answerable_n": sum(g["answerable"] for g in graded),
        "answerable_correct": sum(g["correct"] for g in graded if g["answerable"]),
        "unanswerable_n": sum(not g["answerable"] for g in graded),
        "abstained_right": sum(g["correct"] for g in graded if not g["answerable"]),
        "false_abstain": sum(g["abstained"] for g in graded if g["answerable"]),
        "baseline_correct": sum(base_ok), "baseline_accuracy": sum(base_ok) / n,
        "diff": diff, "diff_lo": dlo, "diff_hi": dhi,
    }


# =============================================================================
# Milestone 6: the first failure, and a memo whose numbers tie
# =============================================================================
def first_failure(q, graded, result):
    """Name the FIRST thing that went wrong for one question, or None if it was correct. Check in
    this order (the pipeline's own order) and return the first that applies:
      answerable question:
        'false_abstain'              the system abstained
        'retrieval_miss'             no gold page among result['hits']
        'wrong_sentence_same_page'   cite_ok but not answer_ok
        'wrong_page_cited'           not answer_ok (and not cite_ok)
        'citation_mismatch'          answer_ok but not cite_ok
      unanswerable question:
        'should_have_abstained'      the system answered anyway"""
    if graded["correct"]:
        return None
    if not q["answerable"]:
        return "should_have_abstained"
    if graded["abstained"]:
        return "false_abstain"
    gold = {tuple(p) for p in q["pages"]}
    if not any(tuple(h) in gold for h in result["hits"]):
        return "retrieval_miss"
    if not graded["answer_ok"]:
        return "wrong_sentence_same_page" if graded["cite_ok"] else "wrong_page_cited"
    return "citation_mismatch"


def error_table(categories):
    """Count a list of failure categories (ignore None). Returns [(category, count)] sorted by
    count descending, then category name ascending."""
    c = Counter(x for x in categories if x)
    return sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))


def render_memo(rep, errors, example):
    """The memo, as markdown, from a make_report dict, an error_table list and one worked example
    (question id, (doc, page) of the page involved, category). Percentages have one decimal place. Exactly these
    sections in this order, each a '## ' heading:

    # Take-home memo: document QA over three annual reports
    ## Result            "The system was correct on C of N hidden questions (P%), 95% Wilson interval LO% to HI%,
                          95% bootstrap interval LO% to HI%." and a second line "It answered AC of AN answerable
                          questions correctly and abstained correctly on UC of UN unanswerable ones."
    ## Baseline          "The retrieval-only baseline was correct on BC of N (BP%). The paired difference is
                          +D.D points (95% bootstrap interval +L.L to +H.H)." (signed with a sign, one decimal; points = 100 x)
    ## Error analysis    "Failures by first cause: " then "category count" pairs joined by ", " and a full stop
                          (or 'none.' if there are no failures); then
                          "Example <id>: page [doc p.N]; first failure: <category>."
    ## Limitations      two or more sentences: the size of the question set, that answers are extracted sentences,
                          that the corpus is three invented reports
    ## Next steps       two bullets
    The text must make check_memo pass."""
    n = rep["n"]
    fmt = lambda x: f"{100 * x:.1f}"
    sg = lambda x: f"{100 * x:+.1f}"
    fails = ", ".join(f"{c} {k}" for c, k in errors) + "." if errors else "none."
    qid, (doc, page), cat = example
    return "\n".join([
        "# Take-home memo: document QA over three annual reports",
        "",
        "## Result",
        f"The system was correct on {rep['correct']} of {n} hidden questions ({fmt(rep['accuracy'])}%), "
        f"95% Wilson interval {fmt(rep['wilson'][0])}% to {fmt(rep['wilson'][1])}%, "
        f"95% bootstrap interval {fmt(rep['boot'][0])}% to {fmt(rep['boot'][1])}%.",
        f"It answered {rep['answerable_correct']} of {rep['answerable_n']} answerable questions correctly and "
        f"abstained correctly on {rep['abstained_right']} of {rep['unanswerable_n']} unanswerable ones.",
        "",
        "## Baseline",
        f"The retrieval-only baseline was correct on {rep['baseline_correct']} of {n} ({fmt(rep['baseline_accuracy'])}%). "
        f"The paired difference is {sg(rep['diff'])} points (95% bootstrap interval {sg(rep['diff_lo'])} to {sg(rep['diff_hi'])}).",
        "",
        "## Error analysis",
        f"Failures by first cause: {fails}",
        f"Example {qid}: page [{doc} p.{page}]; first failure: {cat}.",
        "",
        "## Limitations",
        f"Only {n} questions were scored, so differences of a few points are not resolved by these data. "
        "The answers are extracted sentences, not written prose, so fluency is not tested. "
        "The corpus is three invented reports, and real filings contain tables and scans that this test does not.",
        "",
        "## Next steps",
        "- Read the failures in the largest category and fix the rule that let them through.",
        "- Add questions from a customer's own staff and score again on a sealed set.",
    ])


# --solution-only-begin
def _tokens_with_values(text):
    """(token, float) for every number in text, commas removed."""
    return [(n, float(n)) for n in numbers_in(text)]
# --solution-only-end


def report_values(rep):
    """GIVEN. Every number a report supports, as non-negative floats (signs are ignored): counts,
    and every fraction also as a percentage (x 100), plus 95 (the interval level)."""
    out = {95.0}

    def walk(v):
        if isinstance(v, bool):
            return
        if isinstance(v, (int, float)):
            out.add(abs(float(v)))
            if isinstance(v, float) and -1.0 <= v <= 1.0:
                out.add(abs(100.0 * v))
        elif isinstance(v, (tuple, list)):
            for x in v:
                walk(x)
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
    walk(rep)
    return out


def check_memo(memo, rep, errors, corpus):
    """Problems found in a memo (an empty list means it passes).

    Use sections() with MEMO_SECTIONS, in that order:
      'missing section: <Name>'                for each required section that is absent (spelled as in MEMO_SECTIONS)
      For Result and Baseline, for each line: every number in it (numbers_in, skipping any that lie inside a
        [doc p.N] citation) must be within 0.051 of a value in report_values(rep); else
        'untied number: <n>'  (<n> as numbers_in gave it).
      For Error analysis: for each (category, count) in `errors`, the text of the section must contain
        '<category> <count>' or else 'missing error row: <category> <count>'; if sum of counts != n - correct:
        'error counts sum to <s>, report has <f> failures'.
        Every line there that contains a citation [doc p.N] must have each of its other numbers on the cited
        page of `corpus` (the load_corpus list), else 'number not on cited page: <n> [<doc> p.<N>]';
        a citation to a page that does not exist is 'unknown page: <doc> p.<N>'. Lines with no citation
        have every number checked against the counts in `errors`, n, and n - correct, else 'untied number: <n>'.
      'limitations too thin' if the Limitations section has fewer than 25 words.
    Report problems in that order: missing sections, then per section in the order above."""
    sec = sections(memo)
    problems = []
    for name in MEMO_SECTIONS:
        if name.casefold() not in sec:
            problems.append(f"missing section: {name}")
    allowed = report_values(rep)

    def strip_cites(line):
        return CITE_RE.sub(" ", line)

    for name in ("Result", "Baseline"):
        for line in sec.get(name.casefold(), []):
            for tok, val in _tokens_with_values(strip_cites(line)):
                if not any(abs(val - a) <= 0.051 for a in allowed):
                    problems.append(f"untied number: {tok}")
    if "error analysis" in sec:
        lines = sec["error analysis"]
        body = "\n".join(lines)
        for cat, count in errors:
            if f"{cat} {count}" not in body:
                problems.append(f"missing error row: {cat} {count}")
        total, failures = sum(c for _, c in errors), rep["n"] - rep["correct"]
        if total != failures:
            problems.append(f"error counts sum to {total}, report has {failures} failures")
        counts = {float(c) for _, c in errors} | {float(rep["n"]), float(failures)}
        pages = {(d["doc"], p["page"]): p["text"] for d in corpus for p in d["pages"]}
        for line in lines:
            cites = [(d, int(p)) for d, p in CITE_RE.findall(line)]
            nums = _tokens_with_values(strip_cites(line))
            if cites:
                for doc, page in cites:
                    if (doc, page) not in pages:
                        problems.append(f"unknown page: {doc} p.{page}")
                        continue
                    on_page = set(numbers_in(pages[(doc, page)]))
                    for tok, _ in nums:
                        if tok not in on_page:
                            problems.append(f"number not on cited page: {tok} [{doc} p.{page}]")
            else:
                for tok, val in nums:
                    if val not in counts:
                        problems.append(f"untied number: {tok}")
    if "limitations" in sec and len(" ".join(sec["limitations"]).split()) < 25:
        problems.append("limitations too thin")
    return problems
