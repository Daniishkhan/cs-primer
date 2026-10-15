# Drill: A4 Lab 6, milestone 5 of 6: cross-check
# Everything else in this file is already written. Fill in:
#     origin, cross_check
# Check it with: python3 check.py 5

"""Lab 6 solution: A Mini Deep-Research Agent. A complete reference answer.

The data classes, the prompts and `normalise` are given in the starter, and so are the pieces of the world in fixtures.py (the
30-document Northvale corpus, a BM25 `Index`, and three stand-in models: planner, reader and writer).
Check this file with

    python3 check.py solution   # checks this file
    python3 check.py solution 4 # only milestone 4
    python3 check.py solution 4 7 # milestone 4, replaying ONLY the random case of seed 7

  1. parse_json_list, plan                         from a question to sub-questions, whatever the model sends back
  2. search_all, merge, triage                     parallel search, then decide what is worth reading
  3. read_docs                                     one document per context, claims with quotes, bad output filtered
  4. verify_claims, audit_draft                    the citation checker: claims against documents, sentences against claims
  5. origin, cross_check                           independent origins, conflicts, outdated sources
  6. assemble, research                            drop what cannot be supported, render the report, run the whole pipeline

THE CLAIM.  A reading model returns claims, small checkable statements, as dicts:

    {"doc": "d1", "metric": "road repair spend", "year": 2024, "value": 4.2,
     "quote": "expenditure in 2024 was 4.2 million pounds"}

read_docs gives every accepted claim an "id": "c1", "c2", ... in order. A DOCUMENT is a dict with
"id", "title", "kind", "date", "derived_from" (the id of the document it copies, or None),
"supersedes" (ids of documents it replaces) and "text".

Standard library only. llm.py is the shared stand-in model module; do not edit it.
"""
from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from fixtures import PRIOR, Index, Models, load_docs, make_models, reader_prompt, writer_prompt
from llm import text_of

Doc = Dict[str, Any]
Claim = Dict[str, Any]

MIN_QUOTE_WORDS = 3          # a quote shorter than this proves nothing: "of the" is in every document


# =============================================================================
# Given: records, prompts and small helpers
# =============================================================================
@dataclass
class ReadResult:
    claims: List[Claim]                       # accepted claims, with ids c1, c2, ...
    malformed: List[Tuple[str, str]]          # (doc_id, reason) for each claim that was dropped
    unreadable: List[str]                     # doc ids whose reply was not a JSON list at all


@dataclass
class Audit:
    sentence: str
    problems: List[str]

    @property
    def ok(self) -> bool:
        return not self.problems


@dataclass
class Finding:
    metric: str
    year: int
    status: str                               # "corroborated", "single_source" or "conflict"
    values: Dict[float, List[str]]            # value -> the independent ORIGINS that report it, in natural order
    best: float                               # the value with most origins (ties: the lower value)
    note: str = ""                            # for a conflict: what might explain it, or ""


@dataclass
class Report:
    text: str                                 # the rendered report
    kept: List[str]                           # the rendered sentences that survived the audit
    dropped: List[Tuple[str, List[str]]]      # (draft sentence, problems) for each sentence removed
    sources: List[str]                        # doc ids, in citation order


@dataclass
class Trace:
    """Everything the pipeline did, so a test (or you) can see each stage."""
    queries: List[str]
    to_read: List[str]
    skipped: List[str]
    read: ReadResult
    verified: List[Claim]
    rejected: List[Dict[str, Any]]
    findings: List[Finding]
    outdated: List[Claim]
    draft: List[str]
    report: Report


def plan_prompt(question: str) -> str:
    return f"PLAN: split the question into short search queries. Reply with a JSON list of strings.\nQUESTION: {question}"


def normalise(s: str) -> str:
    """Lower-case and collapse every run of whitespace to one space: how quotes and pages are compared."""
    return re.sub(r"\s+", " ", s.lower()).strip()


def numbers(s: str) -> List[float]:
    """Every number written in s: '1,350' is 1350, '2.50' is 2.5."""
    return [float(t.replace(",", "")) for t in re.findall(r"\d+(?:,\d{3})*(?:\.\d+)?", s)]


def natural_key(doc_id: str) -> int:
    """'d10' sorts after 'd9': documents are listed in the order of their numbers."""
    return int(doc_id[1:])


# =============================================================================
# Milestone 1: plan
# =============================================================================
def parse_json_list(reply: str) -> Optional[list]:
    """The JSON list in a model's reply, or None.

    Models wrap JSON in a markdown code fence (```json ... ```) or add a sentence before it. Accept a
    reply that is a bare JSON list, or a list inside a fence. Anything else (prose, an object, a
    truncated list) gives None. Never raise.
    """
    text = reply.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fenced:
        text = fenced.group(1).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, list) else None


def plan(planner, question: str, max_queries: int = 4) -> List[str]:
    """Ask the planner for search queries and clean them up.

    Send ONE user message, plan_prompt(question), and read text_of(reply) with parse_json_list. Keep
    only entries that are non-empty strings (after strip()), strip them, drop duplicates that differ
    only in case or spacing (keep the first spelling), keep the order, and keep at most max_queries.
    If nothing usable comes back (prose, an empty list, only junk), fall back to [question.strip()].
    """
    reply = planner.complete([{"role": "user", "content": plan_prompt(question)}])
    queries, seen = [], set()
    for item in parse_json_list(text_of(reply)) or []:
        if not isinstance(item, str) or not item.strip():
            continue
        q = item.strip()
        key = " ".join(q.lower().split())              # the same query in other case or spacing
        if key not in seen:
            seen.add(key)
            queries.append(q)
    return queries[:max_queries] or [question.strip()]


# =============================================================================
# Milestone 2: search in parallel, then triage
# =============================================================================
def search_all(index, queries: List[str], k: int = 6, workers: int = 4) -> List[List[Tuple[str, float]]]:
    """Run index.search(query, k) for every query at the same time (a thread pool of `workers`).

    Return one result list per query, IN THE ORDER OF THE QUERIES, whichever finishes first.
    A query whose search raises an exception contributes [] and the others still count.
    """
    def one(query):
        try:
            return index.search(query, k)
        except Exception:                               # a failed search is an empty one; the others still count
            return []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(one, queries))             # map keeps the order of the queries


def merge(per_query: List[List[Tuple[str, float]]]) -> Dict[str, float]:
    """One relevance number per document, between 0 and 1.

    BM25 scores from different queries are not comparable, so divide each query's scores by that
    query's best score (its top hit becomes 1.0), then give each document the HIGHEST such value it
    got from any query. An empty result list contributes nothing.
    """
    relevance: Dict[str, float] = {}
    for results in per_query:
        if not results:
            continue
        best = max(score for _, score in results)
        if best <= 0:
            continue
        for doc_id, score in results:
            relevance[doc_id] = max(relevance.get(doc_id, 0.0), score / best)
    return relevance


def triage(relevance: Dict[str, float], docs: Dict[str, Doc], threshold: float = 0.4,
           max_docs: int = 8) -> Tuple[List[str], List[str]]:
    """Decide which documents are worth reading. Returns (to_read, skipped).

    value = relevance x (0.5 + PRIOR[kind] / 2): a primary source keeps its relevance, a forum post
    keeps a little over half of it. A document is a candidate when value >= threshold. Read the
    max_docs candidates with the highest value (ties: lower number first). Everything else in
    `relevance` is skipped. Both lists are returned in natural order ('d2' before 'd10').
    """
    value = {d: r * (0.5 + PRIOR[docs[d]["kind"]] / 2) for d, r in relevance.items()}
    candidates = sorted((d for d, v in value.items() if v >= threshold), key=lambda d: (-value[d], natural_key(d)))
    chosen = set(candidates[:max_docs])
    return (sorted(chosen, key=natural_key),
            sorted((d for d in relevance if d not in chosen), key=natural_key))


# =============================================================================
# Milestone 3: read
# =============================================================================
def read_docs(reader, question: str, doc_ids: List[str], docs: Dict[str, Doc]) -> ReadResult:
    """Have the reader extract claims from each document, in its own context.

    For each doc id, in the order given, send the reader exactly ONE user message:
    reader_prompt(question, docs[doc_id]) (so it sees that document and no other) and parse the reply
    with parse_json_list. A reply that is not a JSON list puts the doc id in `unreadable`. For each
    item of the list, drop it into `malformed` as (doc_id, reason) unless it is valid:

      "not an object"                         the item is not a dict
      "missing field <name>"                  one of doc, metric, year, value, quote is absent
      "wrong type for <name>"                 doc, metric, quote must be str; year an int; value an int or float
                                              (a bool is not an int here)
      "claim names another document"          its "doc" is not the document that was read

    Valid claims are copied (do not modify the reader's dicts) with "id": "c1", "c2", ... counting
    across all documents, in order. Do not check quotes here: that is Milestone 4.
    """
    claims: List[Claim] = []
    malformed: List[Tuple[str, str]] = []
    unreadable: List[str] = []
    types = {"doc": str, "metric": str, "quote": str}
    for doc_id in doc_ids:
        reply = reader.complete([{"role": "user", "content": reader_prompt(question, docs[doc_id])}])
        items = parse_json_list(text_of(reply))
        if items is None:
            unreadable.append(doc_id)
            continue
        for item in items:
            reason = None
            if not isinstance(item, dict):
                reason = "not an object"
            else:
                for name in ("doc", "metric", "year", "value", "quote"):
                    if name not in item:
                        reason = f"missing field {name}"
                        break
                else:
                    if any(not isinstance(item[n], t) for n, t in types.items()):
                        reason = "wrong type for " + next(n for n, t in types.items() if not isinstance(item[n], t))
                    elif not isinstance(item["year"], int) or isinstance(item["year"], bool):
                        reason = "wrong type for year"
                    elif not isinstance(item["value"], (int, float)) or isinstance(item["value"], bool):
                        reason = "wrong type for value"
                    elif item["doc"] != doc_id:
                        reason = "claim names another document"
            if reason:
                malformed.append((doc_id, reason))
            else:
                claims.append({**item, "id": f"c{len(claims) + 1}"})
    return ReadResult(claims, malformed, unreadable)


# =============================================================================
# Milestone 4: the citation checker
# =============================================================================
def verify_claims(claims: List[Claim], docs: Dict[str, Doc]) -> Tuple[List[Claim], List[Dict[str, Any]]]:
    """Check every claim against the document it cites. Returns (verified, rejected).

    rejected items are {"claim": claim, "reason": reason}. Test in this order and stop at the first failure:

      "unknown document"        claim["doc"] is not in docs
      "empty quote"             the quote is blank
      "quote too short"         fewer than MIN_QUOTE_WORDS words
      "quote not in source"     normalise(quote) is not inside normalise(document text)
      "value not in quote"      no number written in the quote equals claim["value"]
                                (read "1,350" as 1350 and "2.50" as 2.5)

    Keep both lists in the input order.
    """
    verified, rejected = [], []
    for c in claims:
        reason = None
        if c["doc"] not in docs:
            reason = "unknown document"
        elif not c["quote"].strip():
            reason = "empty quote"
        elif len(c["quote"].split()) < MIN_QUOTE_WORDS:
            reason = "quote too short"
        elif normalise(c["quote"]) not in normalise(docs[c["doc"]]["text"]):
            reason = "quote not in source"
        elif not any(abs(n - c["value"]) < 1e-9 for n in numbers(c["quote"])):
            reason = "value not in quote"
        if reason:
            rejected.append({"claim": c, "reason": reason})
        else:
            verified.append(c)
    return verified, rejected


def audit_draft(draft: List[str], claims: List[Claim]) -> List[Audit]:
    """Audit every sentence of a draft against the claims it cites. One Audit per sentence, in order.

    A sentence cites claims with markers like [c3]. `claims` are the claims the writer was allowed
    to use. The problems, in this order, each at most once:

      "no citation"                    the sentence has no [cN] marker
      "unknown claim c99"              a marker names an id that is not in `claims` (one per such id, in order)
      "24 is not in the cited claims"  a number written in the sentence (markers removed) that equals
                                       neither the value nor the year of any CITED claim. Numbers are
                                       listed smallest first, written with format(x, "g"). Read
                                       "1,350" as 1350.
    """
    by_id = {c["id"]: c for c in claims}
    audits = []
    for sentence in draft:
        ids = re.findall(r"\[(c\d+)\]", sentence)
        problems = [] if ids else ["no citation"]
        problems += [f"unknown claim {i}" for i in dict.fromkeys(ids) if i not in by_id]
        allowed = set()
        for i in ids:
            if i in by_id:
                allowed |= {by_id[i]["value"], by_id[i]["year"]}
        stated = numbers(re.sub(r"\[c\d+\]", "", sentence))
        for n in sorted({n for n in stated if not any(abs(n - a) < 1e-9 for a in allowed)}):
            problems.append(f"{format(n, 'g')} is not in the cited claims")
        audits.append(Audit(sentence, problems))
    return audits


# =============================================================================
# Milestone 5: cross-check
# =============================================================================
def origin(doc_id: str, docs: Dict[str, Doc]) -> str:
    """The document at the end of the derived_from chain: the original source of what doc_id says.

    A newspaper that copies a press release that copies a report is one witness, the report. A
    chain that loops, or leaves the corpus, ends at the last document it can reach.
    """
    raise NotImplementedError("TODO milestone 5: origin")


def cross_check(claims: List[Claim], docs: Dict[str, Doc]) -> Tuple[List[Finding], List[Claim]]:
    """Compare the verified claims. Returns (findings, outdated).

    1. A document that appears in another document's "supersedes" list is outdated. Claims from outdated
       documents go to `outdated` (input order) and take no part in the comparison.
    2. The remaining claims are grouped by (metric, year); findings are ordered by (metric, year).
    3. In a group, values maps each distinct value to the sorted list of ORIGINS of the documents
       that report it. status: "conflict" if there are two or more distinct values; otherwise
       "corroborated" if the one value has two or more origins; otherwise "single_source".
    4. best is the value with the most origins (ties: the lower value).
    5. For a conflict, look for an explanation. For every other value v, gap = round(abs(v - best), 2).
       If a remaining claim of a DIFFERENT metric has value == gap, add the sentence
       "<v> is <gap> away from <best>; a verified claim of <gap> exists (<metric>, <docs>)." where the
       numbers are written with format(x, ",g") and <docs> is the sorted, comma-separated list of the
       documents of all such claims. note is these sentences joined by a space, values in ascending order.
    """
    raise NotImplementedError("TODO milestone 5: cross_check")


# =============================================================================
# Milestone 6: the report, and the whole pipeline
# =============================================================================
def assemble(question: str, draft: List[str], claims: List[Claim], findings: List[Finding],
             outdated: List[Claim], docs: Dict[str, Doc]) -> Report:
    """Audit the draft, drop what fails, and render the report. `claims` are the claims the writer may cite.

    Sentences that fail audit_draft are dropped (kept in Report.dropped with their problems). Each run
    of claim markers in a kept sentence, such as " [c1][c5]", is replaced by source numbers: " [1][2]".
    A source is a document; numbers are given in order of first use across the report, and the numbers in
    one run are written in ascending order, each document once.

    The text is these blocks, separated by one blank line; skip a block that would be empty:

        Question: <question>
        <blank>
        Findings
        - <kept sentence>              (one line each; "- (nothing could be supported)" if none)

        Where sources disagree         (one line per finding with status "conflict")
        - <Metric> in <year>: <value> (<origins>) versus <value> (<origins>). <note>
                                       values ordered by most origins first, then lower value, written
                                       with format(x, ",g"); the metric starts with a capital letter; no
                                       trailing space when the note is empty

        Set aside as outdated          (one line per outdated document, natural order, each once)
        - <doc id>: <title> (superseded by <the document that supersedes it>)

        Dropped <k> of <n> draft sentences that could not be traced to verified claims.   (only if k > 0)

        Sources
        [1] <doc id>: <title> (<kind>, <date>)

    Report.sources is the list of doc ids in that order.
    """
    by_id = {c["id"]: c for c in claims}
    audits = audit_draft(draft, claims)
    numbering: Dict[str, int] = {}

    def cite(match):
        docs_in_run = list(dict.fromkeys(by_id[i]["doc"] for i in re.findall(r"c\d+", match.group(0))))
        nums = [numbering.setdefault(d, len(numbering) + 1) for d in docs_in_run]
        return " " + "".join(f"[{n}]" for n in sorted(nums))

    kept = [re.sub(r"(?:\s*\[c\d+\])+", cite, a.sentence) for a in audits if a.ok]
    dropped = [(a.sentence, a.problems) for a in audits if not a.ok]
    blocks = [f"Question: {question}"]
    blocks.append("\n".join(["Findings"] + [f"- {s}" for s in kept] if kept else ["Findings", "- (nothing could be supported)"]))
    lines = []
    for f in findings:
        if f.status == "conflict":
            parts = [f"{format(v, ',g')} ({', '.join(f.values[v])})" for v in sorted(f.values, key=lambda v: (-len(f.values[v]), v))]
            lines.append(f"- {f.metric.capitalize()} in {f.year}: " + " versus ".join(parts) + "." + (" " + f.note if f.note else ""))
    if lines:
        blocks.append("\n".join(["Where sources disagree"] + lines))
    replaced_by = {old: doc["id"] for doc in docs.values() for old in doc.get("supersedes", [])}
    old_docs = sorted({c["doc"] for c in outdated}, key=natural_key)
    if old_docs:
        blocks.append("\n".join(["Set aside as outdated"] + [f"- {d}: {docs[d]['title']} (superseded by {replaced_by[d]})" for d in old_docs]))
    if dropped:
        blocks.append(f"Dropped {len(dropped)} of {len(audits)} draft sentences that could not be traced to verified claims.")
    ordered = sorted(numbering, key=numbering.get)
    if ordered:
        blocks.append("\n".join(["Sources"] + [f"[{numbering[d]}] {d}: {docs[d]['title']} ({docs[d]['kind']}, {docs[d]['date']})" for d in ordered]))
    return Report("\n\n".join(blocks), kept, dropped, ordered)


def research(question: str, models: Models, index: Index, docs: Dict[str, Doc],
             k: int = 6, threshold: float = 0.4, max_docs: int = 8) -> Trace:
    """The whole pipeline: plan, search in parallel, merge and triage, read, verify, cross-check,
    write, assemble.

    The writer gets only the claims that are verified AND not outdated. Ask it once:
    models.writer.complete([{"role": "user", "content": writer_prompt(question, usable)}]) and split its
    reply into sentences, one per non-blank line. Return a Trace holding every stage.
    """
    queries = plan(models.planner, question)
    hits = search_all(index, queries, k)
    to_read, skipped = triage(merge(hits), docs, threshold, max_docs)
    read = read_docs(models.reader, question, to_read, docs)
    verified, rejected = verify_claims(read.claims, docs)
    findings, outdated = cross_check(verified, docs)
    old = {c["id"] for c in outdated}
    usable = [c for c in verified if c["id"] not in old]            # the writer never sees an outdated claim
    reply = models.writer.complete([{"role": "user", "content": writer_prompt(question, usable)}])
    draft = [line.strip() for line in text_of(reply).splitlines() if line.strip()]
    report = assemble(question, draft, usable, findings, outdated, docs)
    return Trace(queries, to_read, skipped, read, verified, rejected, findings, outdated, draft, report)


if __name__ == "__main__":
    import sys
    from fixtures import QUESTIONS
    name = sys.argv[1] if len(sys.argv) > 1 else "roads"
    documents = load_docs()
    print(research(QUESTIONS[name], make_models(), Index(documents), documents).report.text)
