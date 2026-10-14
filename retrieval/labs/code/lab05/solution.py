"""Lab 5: RAG with verified citations.

Chunk a small policy collection, retrieve with BM25, ask a quote-first model, and refuse to show any
answer whose quotes are not in the source. The model is a SCRIPT (fixtures.py) that makes the
mistakes real models make; the verifier is yours. Notation is chapters 13, 14 and 16's:

    chunk     {"id": "parking#2", "doc": "parking", "start": 311, "end": 502, "text": ...}
              text == the document text[start:end], byte for byte (offsets into the ORIGINAL)
    labels    {"S1": chunk, "S2": chunk, ...}      what the model may cite
    quotes    {"q1": {"src": "S2", "text": ...}}   what the model says it copied
    claim     one sentence of the answer, with the quote ids that support it
    verdict   "OK" | "UNCITED" | "BAD_POINTER" | "TOO_SHORT" | "FABRICATED_QUOTE" | "UNSUPPORTED"

What is GIVEN: the data, BM25, the prompt, split_claims, the Pipeline's offline half, the printing.
What YOU write is marked TODO:

    1  sentence_spans, chunk_document
    2  assemble
    3  norm_with_map, locate, verify_quote
    4  supports, verify_claim
    5  parse_response, Pipeline.answer
    6  score_answer, evaluate, risk_coverage

`python3 check.py` runs the milestones; the lab page explains each one.
"""
import re
import unicodedata
from collections import Counter

from bm25 import Bm25Index
from data import DOCS, QUESTIONS
from fixtures import make_model
from llm import count_tokens, text_of


# =============================================================================
# GIVEN: constants, the prompt, and claim splitting
# =============================================================================
SYSTEM = ("Answer only from the sources. First copy the quotes that support your answer, character for "
          "character, each as <quote id=\"q1\" src=\"S1\">...</quote> inside <quotes>. Then write the answer "
          "inside <answer>, putting the quote id in square brackets after each sentence. If the sources do "
          "not contain the answer, write <quotes>NONE</quotes>.")
ABSTAIN = "I could not find this in the documents."
REJECT = "I could not verify an answer from the documents."
MIN_QUOTE_CHARS = 15            # a shorter quote proves nothing: "the" is in every document
TYPOGRAPHIC = {                 # formatting variants that are not differences of content
    "‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "−": "-", "­": "",
}
STOP = set("a an the is are was were of to in on and or by for with be can may at as it its their this that "
           "from has have had will would should must each every up".split())
NEG = {"not", "no", "never", "cannot", "without", "nothing", "none"}


def build_prompt(question, context):
    """GIVEN: the user message. The sources come first; the question goes last."""
    return f"Sources:\n{context}\n\nQuestion: {question}"


def split_claims(answer_text):
    """GIVEN: split an <answer> body into claims: [(sentence, [quote ids]), ...].

    A claim is a sentence ending in . ! or ?, followed by zero or more [qN] markers. Text after
    the last full stop with no marker is a claim too.
    """
    claims, pos = [], 0
    for m in re.finditer(r"\s*(.+?[.!?])((?:\s*\[q\d+\])*)(?=\s|$)", answer_text, re.S):
        claims.append((m.group(1).strip(), re.findall(r"\[(q\d+)\]", m.group(2))))
        pos = m.end()
    rest = answer_text[pos:].strip()
    if rest:
        claims.append((re.sub(r"\s*\[q\d+\]", "", rest).strip(), re.findall(r"\[(q\d+)\]", rest)))
    return claims


# =============================================================================
# Milestone 1: chunks that remember where they came from
# =============================================================================
_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(‘“])|\n\s*\n")


def sentence_spans(text):
    """The sentences of `text` as (start, end) offsets into `text`, in order.

    A sentence ends after . ! or ? when whitespace and then a capital letter, a digit or an opening
    quote follow ("9.50" has no whitespace after its dot, so it never splits), and also at a blank
    line (so a title on its own line is its own sentence). Spans exclude the whitespace between
    sentences: text[start:end] is the sentence exactly as written, newlines inside it included.
    Empty or all-whitespace text gives [].

        sentence_spans("One. Two.") -> [(0, 4), (5, 9)]
    """
    spans, start = [], 0
    for m in _BOUNDARY.finditer(text):
        if text[start:m.start()].strip():
            spans.append((start, m.start()))
        start = m.end()
    if text[start:].strip():
        spans.append((start, len(text.rstrip())))
    # a span must not begin or end in whitespace
    out = []
    for s, e in spans:
        while s < e and text[s].isspace():
            s += 1
        while e > s and text[e - 1].isspace():
            e -= 1
        out.append((s, e))
    return out


def chunk_document(doc_id, text, max_chars=260, overlap=1):
    """Cut a document into chunks made of WHOLE sentences, keeping offsets.

    Greedily add sentences while the chunk, measured from the start of its first sentence to the end of
    its last (so inner newlines and spaces count), stays within max_chars. A sentence longer than
    max_chars is a chunk by itself and is never cut. Each chunk after the first starts `overlap`
    sentences before the end of the previous one, but always advances by at least one sentence.

    Chunk = {"id": f"{doc_id}#{n}" (n from 0), "doc": doc_id, "start", "end", "text"} with
    text == the original text[start:end]. No sentences gives [].
    """
    sents = sentence_spans(text)
    chunks, i = [], 0
    while i < len(sents):
        j = i + 1                                           # the chunk holds sentences i .. j - 1
        while j < len(sents) and sents[j][1] - sents[i][0] <= max_chars:
            j += 1
        s, e = sents[i][0], sents[j - 1][1]
        chunks.append({"id": f"{doc_id}#{len(chunks)}", "doc": doc_id, "start": s, "end": e, "text": text[s:e]})
        if j >= len(sents):
            break
        i = max(i + 1, j - overlap)                         # step back `overlap` sentences, but advance
    return chunks


# =============================================================================
# Milestone 2: the context the model sees
# =============================================================================
def fold(text):
    """GIVEN: compare-key for text: NFKC, typographic quotes straightened, case-folded, one space."""
    text = unicodedata.normalize("NFKC", text)
    text = "".join(TYPOGRAPHIC.get(c, c) for c in text)
    return " ".join(text.casefold().split())


def assemble(chunks, budget):
    """Turn ranked chunks (best first) into a labelled context within a token budget.

    1. Drop a chunk whose fold(text) equals an earlier chunk's (overlap and copies waste budget).
    2. Label the survivors S1, S2, ... in rank order. A line is  f"[S{n}] ({doc}) {text}"  with the
       chunk's whitespace collapsed to single spaces, so each source is one line.
    3. Add lines while the running total of count_tokens(line) stays within `budget`; stop at the
       first line that does not fit (cut by rank, never skip ahead to a smaller one). Labels are
       numbered over the lines kept.

    Returns (context, labels, dropped): the lines joined by "\\n", {"S1": chunk, ...} for the kept
    chunks, and how many of the input chunks did not make it (duplicates and over-budget together).
    """
    seen, kept, used = set(), [], 0
    for ch in chunks:
        key = fold(ch["text"])
        if key in seen:
            continue
        seen.add(key)
        line = f"[S{len(kept) + 1}] ({ch['doc']}) {' '.join(ch['text'].split())}"
        cost = count_tokens(line)
        if used + cost > budget:
            break
        used += cost
        kept.append((line, ch))
    context = "\n".join(line for line, _ in kept)
    labels = {f"S{n}": ch for n, (_, ch) in enumerate(kept, 1)}
    return context, labels, len(chunks) - len(kept)


# =============================================================================
# Milestone 3: gates 1 and 2, the pointer and the quote
# =============================================================================
def norm_with_map(text):
    """Normalise `text` for comparison AND remember where each character came from.

    Returns (norm, origin). `norm` is `text` with NFKC applied, TYPOGRAPHIC replacements made,
    case folded, every run of whitespace reduced to one space, and no space at either end.
    origin[i] is the index in `text` of the character that produced norm[i]. A character that
    expands (the ligature 'ﬁ' becomes 'fi') gives all its output characters the same origin. A
    dropped character (a soft hyphen) produces nothing.

        norm_with_map("A\\u00a0 B")  ->  ("a b", [0, 1, 3])      # NBSP and the space collapse to one
    """
    out, origin = [], []
    for i, ch in enumerate(text):
        piece = unicodedata.normalize("NFKC", ch)
        piece = "".join(TYPOGRAPHIC.get(c, c) for c in piece).casefold()
        for c in piece:
            if c.isspace():
                if out and out[-1] != " ":
                    out.append(" ")
                    origin.append(i)
            else:
                out.append(c)
                origin.append(i)
    while out and out[-1] == " ":
        out.pop()
        origin.pop()
    return "".join(out), origin


def locate(text, quote):
    """Where does `quote` occur in `text`? (start, end) offsets into the ORIGINAL `text`, or None.

    Tolerant about formatting (case, whitespace, ligatures, curly quotes), never about content: a
    changed digit or word is not found. text[start:end] is the source's own wording, newlines
    included. An empty quote is never found.
    """
    nt, origin = norm_with_map(text)
    nq, _ = norm_with_map(quote)
    if not nq:
        return None
    at = nt.find(nq)
    if at < 0:
        return None
    return origin[at], origin[at + len(nq) - 1] + 1


def verify_quote(label, quote, labels):
    """Gates 1 and 2 for one quote. Returns {"verdict", "doc", "span"}.

      * label not in `labels`                     -> "BAD_POINTER"      (gate 1)
      * len(quote.strip()) < MIN_QUOTE_CHARS      -> "TOO_SHORT"
      * quote not located in that chunk's text    -> "FABRICATED_QUOTE" (gate 2)
      * otherwise                                 -> "OK"

    On "OK", `doc` is the document id and `span` the (start, end) offsets of the quote in the
    DOCUMENT (the chunk's own offset plus the offset inside the chunk). Otherwise both are None.
    The order matters: a pointer is checked first, then the length, then the text.
    """
    bad = {"verdict": None, "doc": None, "span": None}
    chunk = labels.get(label)
    if chunk is None:
        return dict(bad, verdict="BAD_POINTER")
    if len(quote.strip()) < MIN_QUOTE_CHARS:
        return dict(bad, verdict="TOO_SHORT")
    hit = locate(chunk["text"], quote)
    if hit is None:
        return dict(bad, verdict="FABRICATED_QUOTE")
    return {"verdict": "OK", "doc": chunk["doc"], "span": (chunk["start"] + hit[0], chunk["start"] + hit[1])}


# =============================================================================
# Milestone 4: gate 3, does the span support the claim?
# =============================================================================
_WORD = re.compile(r"\d+(?:[.,]\d+)*|[a-z]+(?:'[a-z]+)?")


def _tokens(text):
    return _WORD.findall(fold(text))


def content_words(text):
    """GIVEN: the claim's content words: tokens that are not stop words, a trailing 's' dropped
    from words longer than three letters ('pounds' -> 'pound'). Numbers stay as written."""
    out = set()
    for t in _tokens(text):
        if t in STOP or t in NEG:
            continue
        if t[0].isalpha() and len(t) > 3 and t.endswith("s"):
            t = t[:-1]
        out.add(t)
    return out


def supports(claim, quote, threshold=0.75):
    """A crude stand-in for an entailment model (chapter 16): does `quote` support `claim`?

    Returns (ok, score). The claim is supported only if ALL of these hold:
      * every number in the claim (tokens starting with a digit) appears among the quote's numbers;
      * the claim and the quote agree on negation: both contain a word of NEG, or neither does
        (n't forms such as "isn't" count as negation);
      * score = (content words of the claim also in the quote) / (content words of the claim) is at
        least `threshold`.
    score is that coverage in [0, 1], reported even when a rule fails; a claim with no content
    words has score 0.0 and is not supported. Rules are checked on the score first only for
    reporting: a number or negation failure makes ok False whatever the score.
    """
    cw, qw = content_words(claim), content_words(quote)
    if not cw:
        return False, 0.0
    score = len(cw & qw) / len(cw)
    nums_ok = {w for w in cw if w[0].isdigit()} <= {w for w in qw if w[0].isdigit()}

    def negated(text):
        return any(t in NEG or t.endswith("n't") for t in _tokens(text))
    return (nums_ok and negated(claim) == negated(quote) and score >= threshold), score


def verify_claim(claim, cites, quotes, labels):
    """Run the gates on one claim. `cites` are its quote ids; `quotes` maps id -> {"src", "text"}.

    Returns {"claim", "verdict", "score", "spans"}. Verdict is the FIRST failure in this order:
      * no cites at all                                  -> "UNCITED"
      * a cited id missing from `quotes`                 -> "BAD_POINTER"
      * any cited quote failing verify_quote             -> that verdict ("BAD_POINTER", "TOO_SHORT",
        "FABRICATED_QUOTE"), taking the first failing quote in `cites` order
      * supports(claim, all cited quotes joined by " ") not ok -> "UNSUPPORTED"
      * otherwise                                        -> "OK"
    `score` is the support score (0.0 when gate 3 never ran); `spans` lists (doc, start, end) for
    each verified quote (empty unless the verdict is "OK").
    """
    out = {"claim": claim, "verdict": None, "score": 0.0, "spans": []}
    if not cites:
        return dict(out, verdict="UNCITED")
    if any(c not in quotes for c in cites):
        return dict(out, verdict="BAD_POINTER")
    spans = []
    for c in cites:
        v = verify_quote(quotes[c]["src"], quotes[c]["text"], labels)
        if v["verdict"] != "OK":
            return dict(out, verdict=v["verdict"])
        spans.append((v["doc"],) + v["span"])
    ok, score = supports(claim, " ".join(quotes[c]["text"] for c in cites))
    if not ok:
        return dict(out, verdict="UNSUPPORTED", score=score)
    return dict(out, verdict="OK", score=score, spans=spans)


# =============================================================================
# Milestone 5: read the model's reply, and the pipeline with three outcomes
# =============================================================================
def parse_response(text):
    """Read a quote-first reply.

    Returns {"none": bool, "quotes": {id: {"src", "text"}}, "claims": [{"text", "cites"}]}.
      * <quotes>NONE</quotes> (any case, any whitespace) -> none True, no quotes, no claims.
      * Otherwise each <quote id="q1" src="S2">...</quote> in the <quotes> block becomes
        quotes["q1"] = {"src": "S2", "text": the quote with surrounding whitespace stripped}.
      * The body of <answer>...</answer> goes through split_claims; each claim keeps its text and
        the ids it cites, in order. A reply with no <answer> has no claims.
    A reply that has no <quotes> tag at all is NOT an abstention: none is False and quotes is {},
    so any claim in it is uncited.
    """
    block = re.search(r"<quotes>(.*?)</quotes>", text, re.S | re.I)
    if block and block.group(1).strip().upper() == "NONE":
        return {"none": True, "quotes": {}, "claims": []}
    quotes = {}
    if block:
        for m in re.finditer(r'<quote\s+id="(q\d+)"\s+src="(S\d+)"\s*>(.*?)</quote>', block.group(1), re.S):
            quotes[m.group(1)] = {"src": m.group(2), "text": m.group(3).strip()}
    ans = re.search(r"<answer>(.*?)</answer>", text, re.S | re.I)
    claims = [{"text": t, "cites": c} for t, c in split_claims(ans.group(1))] if ans else []
    return {"none": False, "quotes": quotes, "claims": claims}


class Pipeline:
    """Chunk, index, retrieve, ask, verify. The offline half is GIVEN; `answer` is yours."""

    def __init__(self, docs, model, k=4, budget=300, max_chars=260, overlap=1):
        self.model, self.k, self.budget = model, k, budget
        self.chunks = [c for d, t in docs.items() for c in chunk_document(d, t, max_chars, overlap)]
        self.by_id = {c["id"]: c for c in self.chunks}
        self.index = Bm25Index({c["id"]: fold(c["text"]) for c in self.chunks})      # GIVEN

    def retrieve(self, question):
        """GIVEN: the top k chunks for the question, best first."""
        return [self.by_id[i] for i, _ in self.index.search(fold(question), self.k)]

    def answer(self, question, mode="reject", min_support=0.0):
        """Answer `question` from the documents, or refuse. Returns a dict with

          "status"   "answered" | "rejected" | "abstained"
          "text"     what the user would see ("" never: refusals carry ABSTAIN or REJECT)
          "claims"   the verify_claim dicts for every claim the model made (empty if none)
          "support"  the smallest support score among the claims shown (0.0 if none shown)
          "context"  the labelled context string, "labels" the label map

        Steps: retrieve; assemble(chunks, self.budget); if the context is empty -> abstained with
        ABSTAIN. Ask the model: model.complete([{"role": "user", "content": build_prompt(question,
        context)}], system=SYSTEM); parse_response(text_of(reply)). If it says NONE or makes no claims
        -> abstained. Verify every claim with verify_claim.
          mode "reject": if ANY claim is not OK -> rejected with REJECT, nothing else shown.
          mode "drop":   keep the OK claims; if none are OK -> rejected, else answered.
        An answer is the kept claims' texts joined by spaces, each followed by its sources as
        f" [{doc}:{start}-{end}]" for each span. Finally, if support < min_support the answer is
        replaced by an abstention (status "abstained", text ABSTAIN).
        """
        context, labels, _ = assemble(self.retrieve(question), self.budget)
        base = {"claims": [], "support": 0.0, "context": context, "labels": labels}
        if not labels:
            return dict(base, status="abstained", text=ABSTAIN)
        reply = self.model.complete([{"role": "user", "content": build_prompt(question, context)}], system=SYSTEM)
        parsed = parse_response(text_of(reply))
        if parsed["none"] or not parsed["claims"]:
            return dict(base, status="abstained", text=ABSTAIN)
        verdicts = [verify_claim(c["text"], c["cites"], parsed["quotes"], labels) for c in parsed["claims"]]
        good = [v for v in verdicts if v["verdict"] == "OK"]
        base["claims"] = verdicts
        if (mode == "reject" and len(good) < len(verdicts)) or not good:
            return dict(base, status="rejected", text=REJECT)
        support = min(v["score"] for v in good)
        if support < min_support:
            return dict(base, status="abstained", text=ABSTAIN)
        shown = " ".join(v["claim"] + "".join(f" [{d}:{s}-{e}]" for d, s, e in v["spans"]) for v in good)
        return dict(base, status="answered", text=shown, support=support)


# =============================================================================
# Milestone 6: measure it
# =============================================================================
def score_answer(question, result):
    """Classify one result against its question row (qid, text, answerable, phrase, doc):

      answerable, status "answered": "correct" if `phrase` occurs in the shown text (compare after
          fold()), else "wrong"
      answerable, any other status:  "missed"
      unanswerable, status "answered": "wrong"
      unanswerable, any other status:  "safe"
    """
    _, _, answerable, phrase, _ = question
    if result["status"] == "answered":
        if not answerable:
            return "wrong"
        return "correct" if fold(phrase) in fold(result["text"]) else "wrong"
    return "missed" if answerable else "safe"


def evaluate(pipeline, questions, mode="reject", min_support=0.0):
    """Run every question and summarise.

    Returns {"outcomes": {qid: outcome}, "counts": Counter of outcomes, "answered": n, "coverage":
    answered / total, "risk": wrong / answered (0.0 if nothing was answered), "verdicts": Counter of
    claim verdicts over all questions (what the model did before any policy), "rows": [(support,
    is_correct)] for each answered question}.
    """
    outcomes, verdicts, rows = {}, Counter(), []
    answered = 0
    for q in questions:
        res = pipeline.answer(q[1], mode=mode, min_support=min_support)
        outcomes[q[0]] = score_answer(q, res)
        verdicts.update(v["verdict"] for v in res["claims"])
        if res["status"] == "answered":
            answered += 1
            rows.append((res["support"], outcomes[q[0]] == "correct"))
    counts = Counter(outcomes.values())
    return {"outcomes": outcomes, "counts": counts, "answered": answered,
            "coverage": answered / len(questions), "risk": counts["wrong"] / answered if answered else 0.0,
            "verdicts": verdicts, "rows": rows}


def risk_coverage(rows, thresholds):
    """The risk-coverage table of chapter 16. `rows` are (support, is_correct) for answered
    questions. For each threshold t, keep the rows with support >= t and return
    (t, coverage, risk): coverage = kept / len(rows), risk = wrong among kept / kept (0.0 if none
    kept). An empty `rows` gives coverage 0.0 and risk 0.0 for every threshold.
    """
    table = []
    for t in thresholds:
        kept = [ok for s, ok in rows if s >= t]
        wrong = sum(1 for ok in kept if not ok)
        table.append((t, len(kept) / len(rows) if rows else 0.0, wrong / len(kept) if kept else 0.0))
    return table


# =============================================================================
# GIVEN: print what the lab is about
# =============================================================================
def build(**kw):
    return Pipeline(DOCS, make_model(QUESTIONS), **kw)


if __name__ == "__main__":
    pipe = build()
    print(f"{len(pipe.chunks)} chunks from {len(DOCS)} documents\n")
    for q in QUESTIONS:
        r = pipe.answer(q[1])
        verdicts = " ".join(v["verdict"] for v in r["claims"]) or "-"
        print(f"{q[0]}  {r['status']:<9} {verdicts:<34} {q[1]}")
    print()
    for mode in ("reject", "drop"):
        ev = evaluate(pipe, QUESTIONS, mode=mode)
        c = ev["counts"]
        print(f"mode={mode:<7} answered {ev['answered']:>2} of {len(QUESTIONS)}  correct {c['correct']}  wrong {c['wrong']}  "
              f"missed {c['missed']}  safe {c['safe']}   risk {ev['risk']:.0%}")
    print("\nrisk-coverage (mode=drop), answered questions only:")
    for t, cov, risk in risk_coverage(evaluate(pipe, QUESTIONS, mode="drop")["rows"], [0.0, 0.8, 0.9, 1.0]):
        print(f"  support >= {t:.1f}: coverage {cov:.0%}, risk {risk:.0%}")
