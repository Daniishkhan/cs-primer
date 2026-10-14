"""fixtures.py: the world Lab 6 runs in. GIVEN: do not edit.

    load_docs()    the 30-document corpus about the (fictional) Northvale council, as {id: document}
    PRIOR          how much a kind of publisher is trusted before you read it
    QUESTIONS      the three research questions the lab answers
    Index          a small BM25 search index over the corpus (the "search engine")
    make_models()  the three stand-in models: planner, reader and writer

The corpus has the problems real corpora have: primary sources and copies of them (derived_from), a
blog and a forum post that are wrong or vague, two honest sources that disagree because they count
different things, and one policy that has been replaced by a newer one (supersedes). The first
eight documents are the ones chapter 16 uses; documents d9 to d30 are new.

The three "models" are deterministic stand-ins. The planner and the writer are written as rules; the
reader replays a table of what a reading model returned for each document, including mistakes a real
one makes: an invented quote, a paraphrase, a quote with the wrong number beside it, a claim
credited to the wrong document, a claim with a field missing, and a reply that is not JSON at all.
"""
from __future__ import annotations

import json
import math
import os
import re
from typing import Any, Dict, List, Tuple

from llm import RuleModel, ScriptedModel

HERE = os.path.dirname(os.path.abspath(__file__))

# A priori trust in a kind of publisher. A heuristic, not truth: a forum post can be right.
PRIOR = {"primary": 1.0, "news": 0.6, "blog": 0.3, "forum": 0.1}

QUESTIONS = {
    "roads": "How much did Northvale spend on road repair in 2024, and how does that compare with 2023?",
    "potholes": "How many potholes did Northvale repair in 2024?",
    "fares": "What is the current single bus fare cap in Northvale?",
}


def load_docs() -> Dict[str, Dict[str, Any]]:
    """{doc_id: {"id", "title", "kind", "date", "derived_from", "supersedes", "text"}}"""
    with open(os.path.join(HERE, "corpus.json"), encoding="utf-8") as f:
        return {d["id"]: d for d in json.load(f)}


# =============================================================================
# The search engine: BM25 over title + text
# =============================================================================
STOP = set("the a an of in on to was were is for and by at as from up are it its be has have that this with which".split())


def tokenize(s: str) -> List[str]:
    """Lower-case words and numbers, stop words removed, a trailing 's' stripped ('potholes' -> 'pothole')."""
    return [w[:-1] if len(w) > 3 and w.endswith("s") else w for w in re.findall(r"[a-z0-9]+", s.lower()) if w not in STOP]


class Index:
    """BM25 (k1 = 1.5, b = 0.75) over each document's title and text. search(query, k) returns
    [(doc_id, score)], best first, ties broken by doc id, only documents with a positive score."""

    def __init__(self, docs: Dict[str, Dict[str, Any]], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.tf = {i: _count(tokenize(d["title"] + " " + d["text"])) for i, d in docs.items()}
        self.len = {i: sum(t.values()) for i, t in self.tf.items()}
        self.avg = sum(self.len.values()) / len(self.len)
        df: Dict[str, int] = {}
        for t in self.tf.values():
            for w in t:
                df[w] = df.get(w, 0) + 1
        n = len(self.tf)
        self.idf = {w: math.log(1 + (n - c + 0.5) / (c + 0.5)) for w, c in df.items()}

    def search(self, query: str, k: int = 6) -> List[Tuple[str, float]]:
        scores = {}
        for i, tf in self.tf.items():
            s = 0.0
            for w in set(tokenize(query)):
                f = tf.get(w, 0)
                if f:
                    s += self.idf[w] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * self.len[i] / self.avg))
            if s > 0:
                scores[i] = s
        return sorted(scores.items(), key=lambda p: (-p[1], p[0]))[:k]


def _count(words: List[str]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for w in words:
        out[w] = out.get(w, 0) + 1
    return out


# =============================================================================
# The planner: a rule-based stand-in
# =============================================================================
PLANS = {
    # clean JSON
    "road repair": ["road repair spending 2024", "Northvale spent on roads in 2024", "road repair spending 2023", "storm damage road repair increase"],
    # a code fence, duplicates that differ in case and spaces, a non-string, an empty string
    "potholes": "```json\n[\"pothole repairs 2024\", \"Pothole repairs 2024\", \"potholes repaired by the contractor\", \"  potholes repaired by council crews \", "
                "7, \"\", \"pothole response time\", \"pothole repairs 2024\"]\n```",
    # prose instead of JSON: the caller must fall back to the question itself
    "bus fare": "I would start with the council's fares policy and then check the operator.",
}


def make_planner() -> RuleModel:
    return RuleModel([(key, json.dumps(v) if isinstance(v, list) else v) for key, v in PLANS.items()], default="[]")


# =============================================================================
# The reader: replays what a reading model returned for each document
# =============================================================================
def C(doc, metric, year, value, quote):
    return {"doc": doc, "metric": metric, "year": year, "value": value, "quote": quote}


ROADS, POTHOLES, FARES = "road repair spend", "potholes repaired", "bus single fare cap"
FOCUS = {"road repair": {ROADS, "grant", "storm programme extra"},
         "pothole": {POTHOLES, "in-house pothole repairs"},
         "bus fare": {FARES}}

READER = {
    "d1": [C("d1", ROADS, 2024, 4.2, "expenditure in 2024 was 4.2 million pounds"),
           C("d1", ROADS, 2023, 3.4, "Expenditure in 2023 was 3.4 million pounds")],
    "d2": [C("d2", ROADS, 2024, 4.2, "2024 road repair spending of 4.2 million pounds"),
           C("d2", ROADS, 2023, 3.4, "2023 comparator of 3.4 million pounds")],
    "d3": [C("d3", ROADS, 2024, 4.2, "road repair spending reached 4.2 million pounds in 2024"),
           C("d3", ROADS, 2023, 3.4, "the council confirmed a 24 per cent rise")],          # invented: not in the page
    "d4": [C("d4", ROADS, 2024, 3.1, "spends about 3.1 million pounds a year on road repair")],
    "d5": [C("d5", ROADS, 2024, 6, "")],                                                      # no quote at all
    "d6": [C("d6", "storm programme extra", 2024, 0.8, "extra 0.8 million pounds for storm damage")],
    "d7": [C("d7", "grant", 2024, 0.3, "0.3 million pound government grant")],
    "d8": [C("d8", ROADS, 2024, 4.5, "spent 4.5 million pounds on roads in 2024"),
           C("d8", "grant", 2024, 0.3, "0.3 million pound government grant"),
           C("d8", "grant", 2024, 0.5, "0.3 million pound government grant")],               # the number is not in the quote
    "d9": [C("d9", ROADS, 2024, 4.5, "spent 4.5 million pounds on roads in 2024"),
           C("d8", "grant", 2024, 0.3, "0.3 million pound government grant")],               # credited to the wrong document
    "d10": [C("d10", POTHOLES, 2024, 1350, "repaired 1,350 potholes in 2024")],
    "d11": [C("d11", POTHOLES, 2024, 1200, "repaired 1,200 potholes in 2024")],
    "d12": [{"doc": "d12", "metric": "in-house pothole repairs", "year": 2024, "quote": "crew repaired 150 potholes in 2024"},   # no value
            C("d12", "in-house pothole repairs", 2024, 150, "crew repaired 150 potholes in 2024")],
    "d13": [C("d13", POTHOLES, 2024, 1350, "1,350 potholes repaired in 2024")],
    "d14": [C("d14", POTHOLES, 2023, 900, "council fixed just 900 potholes in 2023")],          # a paraphrase: "only" became "just"
    "d16": [C("d16", FARES, 2025, 2.0, "single bus fares in Northvale are capped at 2.00 pounds")],   # still on the web, no longer true
    "d17": [C("d17", FARES, 2025, 2.5, "the single bus fare cap is 2.50 pounds")],
    "d18": [C("d18", FARES, 2025, 2.5, "single fare cap will rise to 2.50 pounds")],
    "d19": [C("d19", FARES, 2025, 2.5, "capped at 2.50 pounds")],
    "d20": [C("d20", FARES, 2025, 2.5, "raising the single fare cap from 2.00 pounds to 2.50 pounds")],
}
RAW = {"d15": "I could not find any claims about that in this page."}                         # not JSON


def reader_prompt(question: str, doc: Dict[str, Any]) -> str:
    """The one message a reader sees: the question and ONE document. (The stand-in reads the first line.)"""
    return f"DOC {doc['id']}: extract claims with verbatim quotes as a JSON list of objects with doc, metric, year, value, quote.\nQUESTION: {question}\n---\n{doc['text']}"


def _reader(messages, tools, system):
    prompt = messages[-1]["content"]
    doc = re.match(r"DOC (d\d+):", prompt).group(1)
    q = re.search(r"QUESTION: (.*)", prompt).group(1).lower()
    focus = next((f for key, f in FOCUS.items() if key in q), set())
    if doc in RAW:
        return RAW[doc]
    claims = [c for c in READER.get(doc, []) if c["metric"] in focus]
    return json.dumps(claims)


def make_reader() -> ScriptedModel:
    return ScriptedModel(_reader)


# =============================================================================
# The writer: turns claims into a draft, and adds the kinds of sentence real writers add
# =============================================================================
PHRASE = {
    ROADS: "Road repair spending in {year} was {value} million pounds",
    "grant": "The government grant towards road repair in {year} was {value} million pounds",
    "storm programme extra": "The extra storm damage repair money in {year} was {value} million pounds",
    POTHOLES: "Potholes repaired in {year}: {value}",
    "in-house pothole repairs": "The council's own crew repaired {value} potholes in {year}",
    FARES: "The single bus fare cap in {year} is {value} pounds",
}


def writer_prompt(question: str, claims: List[Dict[str, Any]]) -> str:
    """The message the writer sees: the question and ONLY the claims it may use, each with its id."""
    rows = [{"id": c["id"], "metric": c["metric"], "year": c["year"], "value": c["value"], "doc": c["doc"]} for c in claims]
    return f"WRITE a short sourced answer using only these claims. Cite claim ids like [c3].\nQUESTION: {question}\nCLAIMS:\n" + json.dumps(rows)


def _writer(messages, tools, system):
    prompt = messages[-1]["content"]
    q = re.search(r"QUESTION: (.*)", prompt).group(1).lower()
    claims = json.loads(prompt.split("CLAIMS:\n", 1)[1])
    lines, groups = [], {}
    for c in claims:
        groups.setdefault((c["metric"], c["year"], c["value"]), []).append(c["id"])
    for (metric, year, value), ids in groups.items():
        lines.append(PHRASE[metric].format(year=year, value=format(value, ",g")) + " " + "".join(f"[{i}]" for i in ids) + ".")
    first = lambda metric, year: next((c["id"] for c in claims if c["metric"] == metric and c["year"] == year), "c0")
    if "road repair" in q and claims:
        lines += [f"The rise is 24 per cent [{first(ROADS, 2023)}].",            # a number no cited claim contains
                  "Spending was driven by storm damage.",                        # no citation
                  "Road surfaces improved everywhere [c99]."]                    # a claim id that does not exist
    elif "pothole" in q and claims:
        lines += [f"Reported potholes are fixed within 10 working days [{first(POTHOLES, 2024)}].",
                  "The council fixed more potholes than ever before."]
    elif "bus fare" in q and claims:
        lines += ["Northvale has the lowest bus fares in the region."]
    return "\n".join(lines)


def make_writer() -> ScriptedModel:
    return ScriptedModel(_writer)


class Models:
    def __init__(self, planner, reader, writer):
        self.planner, self.reader, self.writer = planner, reader, writer


def make_models() -> Models:
    return Models(make_planner(), make_reader(), make_writer())
